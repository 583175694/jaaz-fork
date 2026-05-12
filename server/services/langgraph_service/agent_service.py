from models.tool_model import ToolInfoJson
from services.db_service import db_service
from .StreamProcessor import StreamProcessor
from .agent_manager import AgentManager
import traceback
from utils.http_client import HttpClient
from langgraph_swarm import create_swarm  # type: ignore
from langchain_openai import ChatOpenAI
import langchain_openai.chat_models.base as langchain_openai_base
from langchain_ollama import ChatOllama
from services.websocket_service import send_to_websocket  # type: ignore
from services.config_service import config_service
from typing import Optional, List, Dict, Any, cast, Set, TypedDict
from models.config_model import ModelInfo
import json


class ContextInfo(TypedDict):
    """Context information passed to tools"""
    canvas_id: str
    session_id: str
    model_info: Dict[str, List[ModelInfo]]


def _sanitize_openai_message_content(
    content: Any,
    *,
    role: str,
    has_tool_calls: bool,
) -> Any:
    """Normalize message content before sending it to OpenAI-compatible APIs.

    APIPod rejects list-style text blocks whose `text` field is an empty string.
    LangGraph/LangChain can produce those blocks for assistant tool-call turns.
    """
    if content is None:
        if has_tool_calls:
            return "Calling tools."
        if role == "tool":
            return "Tool executed successfully."
        return content

    if isinstance(content, str):
        if content.strip():
            return content
        if has_tool_calls:
            return "Calling tools."
        if role == "tool":
            return "Tool executed successfully."
        return content

    if not isinstance(content, list):
        return content

    sanitized_blocks: List[Any] = []
    for block in content:
        if isinstance(block, str):
            if block.strip():
                sanitized_blocks.append(block)
            continue

        if not isinstance(block, dict):
            sanitized_blocks.append(block)
            continue

        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                sanitized_blocks.append({**block, "text": text})
            continue

        sanitized_blocks.append(block)

    if sanitized_blocks:
        return sanitized_blocks

    if has_tool_calls:
        return "Calling tools."
    if role == "tool":
        return "Tool executed successfully."
    return sanitized_blocks


def _sanitize_openai_payload_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove empty text blocks and normalize tool-call turns."""
    sanitized_messages: List[Dict[str, Any]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            sanitized_messages.append(message)
            continue

        normalized_message = dict(message)
        role = str(normalized_message.get("role", "") or "")
        has_tool_calls = bool(
            normalized_message.get("tool_calls")
            or normalized_message.get("function_call")
        )
        original_content = normalized_message.get("content")
        normalized_content = _sanitize_openai_message_content(
            original_content,
            role=role,
            has_tool_calls=has_tool_calls,
        )
        if normalized_content != original_content:
            print(
                "🧹 sanitized outbound model message",
                {
                    "index": index,
                    "role": role,
                    "has_tool_calls": has_tool_calls,
                    "original_content_type": type(original_content).__name__,
                    "normalized_content_type": type(normalized_content).__name__ if normalized_content is not None else "NoneType",
                },
            )
        normalized_message["content"] = normalized_content
        sanitized_messages.append(normalized_message)

    return sanitized_messages


def _find_empty_text_blocks(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block_index, block in enumerate(content):
            if not isinstance(block, dict):
                continue
            if block.get("type") != "text":
                continue
            text = block.get("text")
            if isinstance(text, str) and not text.strip():
                findings.append(
                    {
                        "message_index": index,
                        "block_index": block_index,
                        "role": message.get("role"),
                        "has_tool_calls": bool(message.get("tool_calls")),
                        "tool_call_id": message.get("tool_call_id"),
                        "message_keys": sorted(message.keys()),
                    }
                )
    return findings


_ORIGINAL_CONVERT_MESSAGE_TO_DICT = langchain_openai_base._convert_message_to_dict
_CONVERT_PATCH_INSTALLED = False


def _patched_convert_message_to_dict(message: Any) -> Dict[str, Any]:
    message_dict = _ORIGINAL_CONVERT_MESSAGE_TO_DICT(message)
    role = str(message_dict.get("role", "") or "")
    has_tool_calls = bool(
        message_dict.get("tool_calls")
        or message_dict.get("function_call")
    )
    original_content = message_dict.get("content")
    normalized_content = _sanitize_openai_message_content(
        original_content,
        role=role,
        has_tool_calls=has_tool_calls,
    )
    if normalized_content != original_content:
        print(
            "🧹 patched message conversion sanitized content",
            {
                "role": role,
                "has_tool_calls": has_tool_calls,
                "original_content_type": type(original_content).__name__,
                "normalized_content_type": type(normalized_content).__name__ if normalized_content is not None else "NoneType",
            },
        )
    message_dict["content"] = normalized_content
    return message_dict


def _install_langchain_openai_payload_patch() -> None:
    global _CONVERT_PATCH_INSTALLED
    if _CONVERT_PATCH_INSTALLED:
        return
    langchain_openai_base._convert_message_to_dict = _patched_convert_message_to_dict
    _CONVERT_PATCH_INSTALLED = True
    print("🩹 installed langchain_openai message conversion patch")


class APIPodCompatibleChatOpenAI(ChatOpenAI):
    """ChatOpenAI wrapper that normalizes empty multimodal content blocks."""

    def _get_request_payload(
        self,
        input_: Any,
        *,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        messages = payload.get("messages")
        if isinstance(messages, list):
            sanitized_messages = _sanitize_openai_payload_messages(messages)
            try:
                with open("/tmp/jaaz-last-openai-payload.json", "w", encoding="utf-8") as payload_file:
                    json.dump(
                        {
                            **payload,
                            "messages": sanitized_messages,
                        },
                        payload_file,
                        ensure_ascii=False,
                        default=str,
                    )
            except Exception as write_error:
                print("🟠 failed to persist outbound payload", write_error)
            empty_text_findings = _find_empty_text_blocks(sanitized_messages)
            if empty_text_findings:
                print(
                    "🟠 outbound payload still has empty text blocks",
                    empty_text_findings,
                )
                print(
                    "🟠 outbound payload excerpt",
                    json.dumps(
                        sanitized_messages[:6],
                        ensure_ascii=False,
                        default=str,
                    )[:4000],
                )
            else:
                print(
                    "🧾 outbound model payload summary",
                    [
                        {
                            "index": index,
                            "role": message.get("role"),
                            "has_tool_calls": bool(message.get("tool_calls")),
                            "tool_call_id": message.get("tool_call_id"),
                            "content_type": type(message.get("content")).__name__,
                        }
                        for index, message in enumerate(sanitized_messages[:8])
                        if isinstance(message, dict)
                    ],
                )
            payload["messages"] = sanitized_messages
        return payload


def _fix_chat_history(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """修复聊天历史中不完整的工具调用

    根据LangGraph文档建议，移除没有对应ToolMessage的tool_calls
    参考: https://langchain-ai.github.io/langgraph/troubleshooting/errors/INVALID_CHAT_HISTORY/
    """
    if not messages:
        return messages

    fixed_messages: List[Dict[str, Any]] = []
    tool_call_ids: Set[str] = set()

    # 第一遍：收集所有ToolMessage的tool_call_id
    for msg in messages:
        if msg.get('role') == 'tool' and msg.get('tool_call_id'):
            tool_call_id = msg.get('tool_call_id')
            if tool_call_id:
                tool_call_ids.add(tool_call_id)

    # 第二遍：修复AIMessage中的tool_calls
    for msg in messages:
        if msg.get('role') == 'assistant' and msg.get('tool_calls'):
            # 过滤掉没有对应ToolMessage的tool_calls
            valid_tool_calls: List[Dict[str, Any]] = []
            removed_calls: List[str] = []

            for tool_call in msg.get('tool_calls', []):
                tool_call_id = tool_call.get('id')
                if tool_call_id in tool_call_ids:
                    valid_tool_calls.append(tool_call)
                elif tool_call_id:
                    removed_calls.append(tool_call_id)

            # 记录修复信息
            if removed_calls:
                print(
                    f"🔧 修复消息历史：移除了 {len(removed_calls)} 个不完整的工具调用: {removed_calls}")

            # 更新消息
            if valid_tool_calls:
                msg_copy = msg.copy()
                msg_copy['tool_calls'] = valid_tool_calls
                fixed_messages.append(msg_copy)
            elif msg.get('content'):  # 如果没有有效的tool_calls但有content，保留消息
                msg_copy = msg.copy()
                msg_copy.pop('tool_calls', None)  # 移除空的tool_calls
                fixed_messages.append(msg_copy)
            # 如果既没有有效tool_calls也没有content，跳过这条消息
        else:
            # 非assistant消息或没有tool_calls的消息直接保留
            fixed_messages.append(msg)

    return fixed_messages


def _compact_multimodal_history(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Trim heavy historical base64 images from prior turns.

    The current UI stores some canvas/magic interactions as full data URLs
    inside chat history. Re-sending all older base64 images on every turn can
    create multi-megabyte payloads and cause upstream provider failures. Keep
    the latest user turn untouched, but strip historical inline images while
    preserving surrounding text context.
    """
    if not messages:
        return messages

    last_user_index = -1
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].get("role") == "user":
            last_user_index = index
            break

    compacted: List[Dict[str, Any]] = []
    for index, message in enumerate(messages):
        if index == last_user_index:
            compacted.append(message)
            continue

        content = message.get("content")
        if not isinstance(content, list):
            compacted.append(message)
            continue

        new_content: List[Dict[str, Any]] = []
        removed_inline_images = 0
        for item in content:
            if item.get("type") != "image_url":
                new_content.append(item)
                continue

            image_url = item.get("image_url", {})
            url = image_url.get("url", "") if isinstance(image_url, dict) else ""
            if not isinstance(url, str):
                removed_inline_images += 1
                continue

            normalized_url = url.strip().lower()
            is_inline_data_url = normalized_url.startswith("data:")
            is_relative_url = normalized_url.startswith("/")
            is_local_url = (
                normalized_url.startswith("http://localhost")
                or normalized_url.startswith("https://localhost")
                or normalized_url.startswith("http://127.0.0.1")
                or normalized_url.startswith("https://127.0.0.1")
                or normalized_url.startswith("http://0.0.0.0")
                or normalized_url.startswith("https://0.0.0.0")
            )
            if is_inline_data_url or is_relative_url or is_local_url:
                removed_inline_images += 1
                continue

            new_content.append(item)

        if removed_inline_images == 0:
            compacted.append(message)
            continue

        if not new_content:
            new_content = [{
                "type": "text",
                "text": f"[{removed_inline_images} previous inline image(s) omitted from history]",
            }]
        elif any(item.get("type") == "text" for item in new_content):
            for item in new_content:
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    item["text"] += (
                        f"\n\n[{removed_inline_images} previous inline image(s) omitted from history]"
                    )
                    break

        compacted_message = message.copy()
        compacted_message["content"] = new_content
        compacted.append(compacted_message)

    return compacted


def _extract_latest_user_text(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue

        content = message.get("content")
        if isinstance(content, str):
            return content.strip()

        if not isinstance(content, list):
            return ""

        text_parts: List[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                text_parts.append(item["text"].strip())
        return "\n".join(part for part in text_parts if part).strip()

    return ""


def _choose_initial_agent(
    fixed_messages: List[Dict[str, Any]],
    last_agent: Optional[str],
    agent_names: List[str],
    tool_list: List[ToolInfoJson],
) -> str:
    if last_agent:
        return last_agent

    latest_user_text = _extract_latest_user_text(fixed_messages).lower()
    if not latest_user_text:
        return agent_names[0]

    has_media_tools = any(
        tool.get("type") in {"image", "video"} for tool in tool_list
    )
    if not has_media_tools:
        return agent_names[0]

    creator_agent = "image_video_creator"
    if creator_agent not in agent_names:
        return agent_names[0]

    media_intent_signals = [
        "image",
        "images",
        "picture",
        "pictures",
        "storyboard",
        "keyframe",
        "video",
        "videos",
        "shot",
        "shots",
        "commercial storyboard",
        "premium commercial storyboard",
        "<input_images",
        "分镜",
        "分镜图",
        "图片",
        "图像",
        "视频",
        "短片",
        "广告片",
        "画面",
    ]

    if any(signal in latest_user_text for signal in media_intent_signals):
        return creator_agent

    return agent_names[0]


async def langgraph_multi_agent(
    messages: List[Dict[str, Any]],
    canvas_id: str,
    session_id: str,
    text_model: ModelInfo,
    tool_list: List[ToolInfoJson],
    system_prompt: Optional[str] = None
) -> None:
    """多智能体处理函数

    Args:
        messages: 消息历史
        canvas_id: 画布ID
        session_id: 会话ID
        text_model: 文本模型配置
        tool_list: 工具模型配置列表（图像或视频模型）
        system_prompt: 系统提示词
    """
    try:
        # 0. 修复消息历史
        fixed_messages = _fix_chat_history(messages)
        fixed_messages = _compact_multimodal_history(fixed_messages)
        fixed_messages = _sanitize_openai_payload_messages(fixed_messages)
        print(
            "🤖 langgraph_multi_agent start",
            {
                "session_id": session_id,
                "canvas_id": canvas_id,
                "incoming_message_count": len(messages),
                "fixed_message_count": len(fixed_messages),
                "text_model": f"{text_model.get('provider')}:{text_model.get('model')}",
                "tool_ids": [tool.get("id") for tool in tool_list],
            },
        )

        # 2. 文本模型
        text_model_instance = _create_text_model(text_model)

        # 3. 创建智能体
        agents = AgentManager.create_agents(
            text_model_instance,
            tool_list,  # 传入所有注册的工具
            system_prompt or ""
        )
        agent_names = [agent.name for agent in agents]
        print('👇agent_names', agent_names)
        last_agent = AgentManager.get_last_active_agent(
            fixed_messages, agent_names)

        print('👇last_agent', last_agent)
        initial_agent = _choose_initial_agent(
            fixed_messages=fixed_messages,
            last_agent=last_agent,
            agent_names=agent_names,
            tool_list=tool_list,
        )
        print('👇initial_agent', initial_agent)

        # 4. 创建智能体群组
        swarm = create_swarm(
            agents=agents,  # type: ignore
            default_active_agent=initial_agent
        )

        # 5. 创建上下文
        context = {
            'canvas_id': canvas_id,
            'session_id': session_id,
            'tool_list': tool_list,
            'messages': fixed_messages,
        }
        print(
            "🤖 langgraph context ready",
            {
                "session_id": session_id,
                "initial_agent": initial_agent,
                "tool_count": len(tool_list),
            },
        )

        # 6. 流处理
        processor = StreamProcessor(
            session_id, db_service, send_to_websocket)  # type: ignore
        await processor.process_stream(swarm, fixed_messages, context)
        print(
            "🤖 langgraph_multi_agent done",
            {
                "session_id": session_id,
                "canvas_id": canvas_id,
            },
        )

    except Exception as e:
        await _handle_error(e, session_id)


def _create_text_model(text_model: ModelInfo) -> Any:
    """创建语言模型实例"""
    _install_langchain_openai_payload_patch()
    model = text_model.get('model')
    provider = text_model.get('provider')
    url = text_model.get('url')
    api_key = config_service.app_config.get(  # type: ignore
        provider, {}).get("api_key", "")

    # TODO: Verify if max token is working
    # max_tokens = text_model.get('max_tokens', 8148)

    if provider == 'ollama':
        return ChatOllama(
            model=model,
            base_url=url,
        )
    else:
        # Create httpx client with SSL configuration for ChatOpenAI
        http_client = HttpClient.create_sync_client()
        http_async_client = HttpClient.create_async_client()
        return APIPodCompatibleChatOpenAI(
            model=model,
            api_key=api_key,  # type: ignore
            timeout=300,
            base_url=url,
            temperature=0,
            disable_streaming="tool_calling",
            model_kwargs={"parallel_tool_calls": False},
            # max_tokens=max_tokens, # TODO: 暂时注释掉有问题的参数
            http_client=http_client,
            http_async_client=http_async_client
        )


async def _handle_error(error: Exception, session_id: str) -> None:
    """处理错误"""
    print('Error in langgraph_agent', error)
    tb_str = traceback.format_exc()
    print(f"Full traceback:\n{tb_str}")
    traceback.print_exc()

    error_message = str(error)
    normalized_error = error_message.lower()
    if "invalid_api_key" in normalized_error or "authenticationerror" in normalized_error:
        error_message = (
            "Text model authentication failed. "
            "Please update the API key for the selected text provider in Settings -> Providers. "
            "Current failing model: apipodcode:gpt-5.4."
        )

    await send_to_websocket(session_id, cast(Dict[str, Any], {
        'type': 'error',
        'error': error_message
    }))
