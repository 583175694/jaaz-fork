from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from models.config_model import ModelInfo
from services.ad_prompt_compiler_service import (
    build_fallback_brief,
    compile_creative_brief,
    compile_video_prompt,
    _fallback_video_compilation,
    evaluate_video_prompt,
    rewrite_video_prompt,
)
from services.config_service import config_service
from services.db_service import db_service


def _get_default_text_model() -> ModelInfo:
    for provider_name, provider_config in config_service.app_config.items():
        models = provider_config.get("models", {})
        for model_name, model_config in models.items():
            if model_config.get("type") == "text":
                return {
                    "provider": provider_name,
                    "model": model_name,
                    "url": provider_config.get("url", ""),
                    "type": "text",
                }
    return {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "url": config_service.app_config.get("openai", {}).get("url", ""),
        "type": "text",
    }


async def resolve_session_text_model(session_id: str) -> ModelInfo:
    session = await db_service.get_chat_session(session_id)
    if session:
        provider = str(session.get("provider", "") or "")
        model = str(session.get("model", "") or "")
        provider_config = config_service.app_config.get(provider, {})
        provider_models = provider_config.get("models", {})
        model_config = provider_models.get(model, {})
        if provider and model and model_config.get("type") == "text":
            return {
                "provider": provider,
                "model": model,
                "url": provider_config.get("url", ""),
                "type": "text",
            }

    print(
        "⚠️ Falling back to default text model for ad video compiler",
        {"session_id": session_id},
    )
    return _get_default_text_model()


def _extract_text_from_content(content: Any) -> str:
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


def _strip_structured_video_markup(text: str) -> str:
    normalized = str(text or "")
    normalized = re.sub(r"<duration>.*?</duration>", "", normalized, flags=re.S)
    normalized = re.sub(r"<aspect_ratio>.*?</aspect_ratio>", "", normalized, flags=re.S)
    normalized = re.sub(r"<input_images\b[^>]*>.*?</input_images>", "", normalized, flags=re.S)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _is_canvas_video_shell_prompt(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return True

    shell_signals = [
        "请基于当前会话中已经形成的广告创意、分镜说明和所选参考图生成视频",
        "这是一条画布里的“选中分镜生成视频”操作请求",
        "this is a canvas storyboard-to-video request",
        "selected storyboard to video request",
        "基于这些参考图生成一个",
    ]
    return any(signal in normalized for signal in shell_signals)


def _build_message_text_record(message: Dict[str, Any]) -> Optional[Dict[str, str]]:
    role = str(message.get("role", "") or "").strip()
    if role not in {"user", "assistant"}:
        return None

    extracted = _strip_structured_video_markup(
        _extract_text_from_content(message.get("content"))
    )
    if not extracted:
        return None

    return {
        "role": role,
        "text": extracted,
    }


def _extract_tag_value(text: str, tag_name: str) -> str:
    pattern = rf"<{tag_name}\b[^>]*>(.*?)</{tag_name}>"
    match = re.search(pattern, str(text or ""), flags=re.S)
    if not match:
        return ""
    return str(match.group(1) or "").strip()


def _extract_tag_attribute(text: str, tag_name: str, attr_name: str) -> str:
    pattern = rf"<{tag_name}\b[^>]*\b{attr_name}=\"([^\"]+)\"[^>]*/?>"
    match = re.search(pattern, str(text or ""), flags=re.S)
    if not match:
        return ""
    return str(match.group(1) or "").strip()


def resolve_video_selection_context(
    explicit_prompt: str,
    messages: Optional[List[Dict[str, Any]]],
    selection_mode: str,
    start_frame_file_id: str,
    end_frame_file_id: str,
) -> Dict[str, str]:
    selected_mode = str(selection_mode or "").strip() or "reference_images"
    start_file = str(start_frame_file_id or "").strip()
    end_file = str(end_frame_file_id or "").strip()

    search_messages = list(messages or [])
    if explicit_prompt:
        search_messages.append({"role": "user", "content": explicit_prompt})

    for message in reversed(search_messages):
        content_text = _extract_text_from_content(message.get("content"))
        if not content_text:
            continue
        if not start_file:
            start_file = _extract_tag_attribute(content_text, "start_frame", "file_id")
        if not end_file:
            end_file = _extract_tag_attribute(content_text, "end_frame", "file_id")
        tag_mode = _extract_tag_value(content_text, "selection_mode")
        if tag_mode and selected_mode == "reference_images":
            selected_mode = tag_mode
        if start_file and end_file and selected_mode:
            break

    if not end_file and start_file:
        end_file = start_file

    return {
        "selection_mode": selected_mode,
        "start_frame_file_id": start_file,
        "end_frame_file_id": end_file,
    }


async def resolve_selected_frame_generation_metadata(
    canvas_id: str,
    start_frame_file_id: str,
    end_frame_file_id: str,
) -> Dict[str, Dict[str, Any]]:
    if not canvas_id:
        return {}

    canvas = await db_service.get_canvas_data(canvas_id)
    canvas_data = (canvas or {}).get("data", {}) if isinstance(canvas, dict) else {}
    files = canvas_data.get("files", {}) if isinstance(canvas_data, dict) else {}
    if not isinstance(files, dict):
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    for role, file_id in (
        ("start_frame", start_frame_file_id),
        ("end_frame", end_frame_file_id),
    ):
        file_info = files.get(file_id)
        if not isinstance(file_info, dict):
            continue
        generation_meta = file_info.get("generationMeta")
        if isinstance(generation_meta, dict):
            result[role] = generation_meta
    return result


async def resolve_selected_frame_storyboard_metadata(
    canvas_id: str,
    start_frame_file_id: str,
    end_frame_file_id: str,
) -> Dict[str, Dict[str, Any]]:
    if not canvas_id:
        return {}

    canvas = await db_service.get_canvas_data(canvas_id)
    canvas_data = (canvas or {}).get("data", {}) if isinstance(canvas, dict) else {}
    files = canvas_data.get("files", {}) if isinstance(canvas_data, dict) else {}
    if not isinstance(files, dict):
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    for role, file_id in (
        ("start_frame", start_frame_file_id),
        ("end_frame", end_frame_file_id),
    ):
        file_info = files.get(file_id)
        if not isinstance(file_info, dict):
            continue
        storyboard_meta = file_info.get("storyboardMeta")
        if isinstance(storyboard_meta, dict):
            result[role] = storyboard_meta
    return result


def build_video_compilation_context(
    messages: Optional[List[Dict[str, Any]]],
    explicit_prompt: str,
    selection_mode: str = "reference_images",
    start_frame_file_id: str = "",
    end_frame_file_id: str = "",
) -> str:
    sanitized_explicit_prompt = _strip_structured_video_markup(explicit_prompt)
    selection_context = resolve_video_selection_context(
        explicit_prompt=explicit_prompt,
        messages=messages,
        selection_mode=selection_mode,
        start_frame_file_id=start_frame_file_id,
        end_frame_file_id=end_frame_file_id,
    )
    message_records: List[Dict[str, str]] = []
    for message in messages or []:
        record = _build_message_text_record(message)
        if record:
            message_records.append(record)

    latest_user_instruction = ""
    if sanitized_explicit_prompt and not _is_canvas_video_shell_prompt(sanitized_explicit_prompt):
        latest_user_instruction = sanitized_explicit_prompt
    else:
        for record in reversed(message_records):
            if record["role"] == "user":
                if _is_canvas_video_shell_prompt(record["text"]):
                    continue
                latest_user_instruction = record["text"]
                break

    original_creative_request = ""
    for record in message_records:
        if record["role"] != "user":
            continue
        if _is_canvas_video_shell_prompt(record["text"]):
            continue
        if latest_user_instruction and record["text"] == latest_user_instruction:
            continue
        original_creative_request = record["text"]
        break

    recent_assistant_contexts: List[str] = []
    for record in reversed(message_records):
        if record["role"] != "assistant":
            continue
        if not record["text"]:
            continue
        recent_assistant_contexts.append(record["text"])
        if len(recent_assistant_contexts) >= 2:
            break
    recent_assistant_contexts.reverse()

    context_parts: List[str] = []
    if original_creative_request:
        context_parts.append(
            "Original creative request:\n"
            f"{original_creative_request}"
        )
    if recent_assistant_contexts:
        context_parts.append(
            "Storyboard and scene context from prior assistant outputs:\n"
            + "\n\n".join(recent_assistant_contexts)
        )
    if selection_context.get("selection_mode") == "start_end_frames":
        context_parts.append(
            "Selected storyboard bridge:\n"
            f"- selection_mode: {selection_context.get('selection_mode')}\n"
            f"- start_frame_file_id: {selection_context.get('start_frame_file_id') or 'unknown'}\n"
            f"- end_frame_file_id: {selection_context.get('end_frame_file_id') or 'unknown'}\n"
            "- Treat the first selected frame as the opening frame target.\n"
            "- Treat the second selected frame as the ending frame target.\n"
            "- Build a continuous advertising shot that transitions naturally from start frame to end frame.\n"
            "- Preserve character identity, product appearance, environment continuity, lighting logic, and campaign mood."
        )
    if latest_user_instruction:
        context_parts.append(
            "Current video generation instruction:\n"
            f"{latest_user_instruction}"
        )

    if context_parts:
        return "\n\n".join(context_parts)

    return sanitized_explicit_prompt or explicit_prompt


async def compile_ad_video_prompt(
    *,
    session_id: str,
    prompt: str,
    messages: Optional[List[Dict[str, Any]]],
    duration: int,
    aspect_ratio: str,
    resolution: str,
    selected_image_count: int,
    platform_hint: str,
    canvas_id: str = "",
    selection_mode: str = "reference_images",
    start_frame_file_id: str = "",
    end_frame_file_id: str = "",
) -> Dict[str, Any]:
    text_model = await resolve_session_text_model(session_id)
    selection_context = resolve_video_selection_context(
        explicit_prompt=prompt,
        messages=messages,
        selection_mode=selection_mode,
        start_frame_file_id=start_frame_file_id,
        end_frame_file_id=end_frame_file_id,
    )
    compilation_context = build_video_compilation_context(
        messages,
        prompt,
        selection_mode=selection_context["selection_mode"],
        start_frame_file_id=selection_context["start_frame_file_id"],
        end_frame_file_id=selection_context["end_frame_file_id"],
    )
    selected_frame_generation_meta = await resolve_selected_frame_generation_metadata(
        canvas_id=canvas_id,
        start_frame_file_id=selection_context["start_frame_file_id"],
        end_frame_file_id=selection_context["end_frame_file_id"],
    )
    selected_frame_storyboard_meta = await resolve_selected_frame_storyboard_metadata(
        canvas_id=canvas_id,
        start_frame_file_id=selection_context["start_frame_file_id"],
        end_frame_file_id=selection_context["end_frame_file_id"],
    )
    if selected_frame_storyboard_meta:
        storyboard_parts: List[str] = []
        for role in ("start_frame", "end_frame"):
            meta = selected_frame_storyboard_meta.get(role)
            if not meta:
                continue
            storyboard_parts.append(
                f"{role} storyboard metadata:\n"
                f"- shot_id: {str(meta.get('shot_id', '') or 'unknown')}\n"
                f"- narrative_role: {str(meta.get('narrative_role', '') or 'unknown')}\n"
                f"- summary: {str(meta.get('summary', '') or 'unknown')}\n"
                f"- aspect_ratio: {str(meta.get('aspect_ratio', '') or 'unknown')}"
            )
        if storyboard_parts:
            compilation_context = (
                f"{compilation_context}\n\n"
                "Selected frame storyboard metadata:\n"
                + "\n\n".join(storyboard_parts)
            )
    if selected_frame_generation_meta:
        metadata_parts: List[str] = []
        for role in ("start_frame", "end_frame"):
            meta = selected_frame_generation_meta.get(role)
            if not meta:
                continue
            prompt_text = str(meta.get("prompt", "") or "").strip()
            provider = str(meta.get("provider", "") or "").strip()
            model = str(meta.get("model", "") or "").strip()
            input_images = meta.get("input_images", [])
            metadata_parts.append(
                f"{role} generation metadata:\n"
                f"- provider: {provider or 'unknown'}\n"
                f"- model: {model or 'unknown'}\n"
                f"- prompt: {prompt_text or 'unknown'}\n"
                f"- input_images: {input_images if isinstance(input_images, list) else []}"
            )
        if metadata_parts:
            compilation_context = (
                f"{compilation_context}\n\n"
                "Selected frame source metadata:\n"
                + "\n\n".join(metadata_parts)
            )
    print(
        "🎬 compile_ad_video_prompt using deterministic compilation",
        {
            "session_id": session_id,
            "provider": text_model.get("provider"),
            "model": text_model.get("model"),
            "selected_image_count": selected_image_count,
            "platform_hint": platform_hint,
            "selection_mode": selection_context["selection_mode"],
            "start_frame_file_id": selection_context["start_frame_file_id"],
            "end_frame_file_id": selection_context["end_frame_file_id"],
            "selected_frame_metadata_roles": list(selected_frame_generation_meta.keys()),
            "selected_frame_storyboard_roles": list(selected_frame_storyboard_meta.keys()),
        },
    )
    effective_platform_hint = platform_hint
    if selection_context["selection_mode"] == "start_end_frames":
        effective_platform_hint = f"{platform_hint} with same-scene storyboard bridge"
    brief = await compile_creative_brief(
        text_model=text_model,
        user_prompt=compilation_context,
        duration=duration,
        aspect_ratio=aspect_ratio,
        platform_hint=effective_platform_hint,
    )
    compiled_video_prompt = await compile_video_prompt(
        text_model=text_model,
        brief=brief,
        original_prompt=compilation_context,
        duration=duration,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        selected_image_count=selected_image_count,
        selection_mode=selection_context["selection_mode"],
    )
    video_prompt = str(compiled_video_prompt.get("final_prompt") or prompt)
    qa_issues = evaluate_video_prompt(compiled_video_prompt)
    if qa_issues:
        print(
            "🎬 ad video compiler QA issues detected, rewriting once",
            {
                "session_id": session_id,
                "issues": qa_issues,
            },
        )
        compiled_video_prompt = rewrite_video_prompt(compiled_video_prompt, qa_issues)
        video_prompt = str(compiled_video_prompt.get("final_prompt") or video_prompt)
    if not video_prompt.strip():
        brief = build_fallback_brief(
            user_prompt=compilation_context,
            duration=duration,
            aspect_ratio=aspect_ratio,
            platform_hint=effective_platform_hint,
        )
        compiled_video_prompt = _fallback_video_compilation(
            brief=brief,
            original_prompt=compilation_context,
            duration=duration,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            selected_image_count=selected_image_count,
            selection_mode=selection_context["selection_mode"],
        )
        video_prompt = str(compiled_video_prompt.get("final_prompt") or prompt)

    return {
        "text_model": text_model,
        "context_prompt": compilation_context,
        "brief": brief,
        "compiled_video_prompt": compiled_video_prompt,
        "video_prompt": video_prompt,
        "qa_issues": qa_issues,
        "selection_context": selection_context,
        "selected_frame_generation_meta": selected_frame_generation_meta,
        "selected_frame_storyboard_meta": selected_frame_storyboard_meta,
    }
