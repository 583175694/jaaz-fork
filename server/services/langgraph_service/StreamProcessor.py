# type: ignore[import]
import traceback
from typing import Optional, List, Dict, Any, Callable, Awaitable
from langchain_core.messages import AIMessageChunk, ToolCall, convert_to_openai_messages, ToolMessage
from langgraph.graph import StateGraph
import json


class StreamProcessor:
    """流式处理器 - 负责处理智能体的流式输出"""

    def __init__(self, session_id: str, db_service: Any, websocket_service: Callable[[str, Dict[str, Any]], Awaitable[None]]):
        self.session_id = session_id
        self.db_service = db_service
        self.websocket_service = websocket_service
        self.tool_calls: List[ToolCall] = []
        self.last_saved_message_index = 0
        self.last_streaming_tool_call_id: Optional[str] = None

    async def process_stream(self, swarm: StateGraph, messages: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        """处理整个流式响应

        Args:
            swarm: 智能体群组
            messages: 消息列表
            context: 上下文信息
        """
        self.last_saved_message_index = len(messages) - 1
        print(
            "🌊 StreamProcessor start",
            {
                "session_id": self.session_id,
                "initial_message_count": len(messages),
                "initial_last_saved_index": self.last_saved_message_index,
            },
        )

        compiled_swarm = swarm.compile()

        async for chunk in compiled_swarm.astream(
            {"messages": messages},
            config=context,
            stream_mode=["messages", "custom", 'values']
        ):
            await self._handle_chunk(chunk)

        # 发送完成事件
        print(
            "🌊 StreamProcessor completed",
            {
                "session_id": self.session_id,
                "final_last_saved_index": self.last_saved_message_index,
            },
        )
        await self.websocket_service(self.session_id, {
            'type': 'done'
        })

    async def _handle_chunk(self, chunk: Any) -> None:
        # print('👇chunk', chunk)
        """处理单个chunk"""
        chunk_type = chunk[0]

        if chunk_type == 'values':
            await self._handle_values_chunk(chunk[1])
        else:
            await self._handle_message_chunk(chunk[1][0])

    async def _handle_values_chunk(self, chunk_data: Dict[str, Any]) -> None:
        """处理 values 类型的 chunk"""
        all_messages = chunk_data.get('messages', [])
        oai_messages = convert_to_openai_messages(all_messages)
        # 确保 oai_messages 是列表类型
        if not isinstance(oai_messages, list):
            oai_messages = [oai_messages] if oai_messages else []

        assistant_names = [
            msg.get("name")
            for msg in oai_messages
            if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("name")
        ]
        if assistant_names:
            print(
                "🌊 values chunk assistants",
                {
                    "session_id": self.session_id,
                    "assistant_names_tail": assistant_names[-3:],
                    "message_count": len(oai_messages),
                },
            )

        # 发送所有消息到前端
        await self.websocket_service(self.session_id, {
            'type': 'all_messages',
            'messages': oai_messages
        })

        # 保存新消息到数据库
        for i in range(self.last_saved_message_index + 1, len(oai_messages)):
            new_message = oai_messages[i]
            if len(oai_messages) > 0:  # 确保有消息才保存
                print(
                    "💾 Persisting streamed message",
                    {
                        "session_id": self.session_id,
                        "index": i,
                        "role": new_message.get("role", "user"),
                        "name": new_message.get("name"),
                    },
                )
                await self.db_service.create_message(
                    self.session_id,
                    new_message.get('role', 'user'),
                    json.dumps(new_message)
                )
            self.last_saved_message_index = i

    async def _handle_message_chunk(self, ai_message_chunk: AIMessageChunk) -> None:
        """处理消息类型的 chunk"""
        # print('👇ai_message_chunk', ai_message_chunk)
        try:
            content = ai_message_chunk.content

            if isinstance(ai_message_chunk, ToolMessage):
                # 工具调用结果之后会在 values 类型中发送到前端，这里会更快出现一些
                oai_message = convert_to_openai_messages([ai_message_chunk])[0]
                await self.websocket_service(self.session_id, {
                    'type': 'tool_call_result',
                    'id': ai_message_chunk.tool_call_id,
                    'message': oai_message
                })
            elif content:
                # 发送文本内容
                await self.websocket_service(self.session_id, {
                    'type': 'delta',
                    'text': content
                })
            elif hasattr(ai_message_chunk, 'tool_calls') and ai_message_chunk.tool_calls and ai_message_chunk.tool_calls[0].get('name'):
                # 处理工具调用
                await self._handle_tool_calls(ai_message_chunk.tool_calls)

            # 处理工具调用参数流
            if hasattr(ai_message_chunk, 'tool_call_chunks'):
                await self._handle_tool_call_chunks(ai_message_chunk.tool_call_chunks)
        except Exception as e:
            print('🟠error', e)
            traceback.print_stack()

    async def _handle_tool_calls(self, tool_calls: List[ToolCall]) -> None:
        """处理工具调用"""
        self.tool_calls = [tc for tc in tool_calls if tc.get('name')]
        print(
            "🛠️ tool calls detected",
            {
                "session_id": self.session_id,
                "tool_names": [tc.get("name") for tc in self.tool_calls],
                "tool_ids": [tc.get("id") for tc in self.tool_calls],
                "tool_args": [tc.get("args") for tc in self.tool_calls],
            },
        )

        # 需要确认的工具列表
        TOOLS_REQUIRING_CONFIRMATION = {
            'generate_video_by_veo3_apipod',
        }

        for tool_call in self.tool_calls:
            tool_name = tool_call.get('name')
            tool_call_id = str(tool_call.get('id') or '').strip()

            if not tool_call_id:
                print(
                    '🟠 tool call missing id',
                    {
                        'session_id': self.session_id,
                        'tool_name': tool_name,
                        'tool_call': tool_call,
                    },
                )
                continue

            # 检查是否需要确认
            if tool_name in TOOLS_REQUIRING_CONFIRMATION:
                # 对于需要确认的工具，不在这里发送事件，让工具函数自己处理
                print(
                    f'🔄 Tool {tool_name} requires confirmation, skipping StreamProcessor event')
                continue
            else:
                await self.websocket_service(self.session_id, {
                    'type': 'tool_call',
                    'id': tool_call_id,
                    'name': tool_name,
                    'arguments': '{}'
                })

    async def _handle_tool_call_chunks(self, tool_call_chunks: List[Any]) -> None:
        """处理工具调用参数流"""
        for tool_call_chunk in tool_call_chunks:
            if tool_call_chunk.get('id'):
                # 标记新的流式工具调用参数开始
                self.last_streaming_tool_call_id = tool_call_chunk.get('id')
            else:
                if self.last_streaming_tool_call_id:
                    await self.websocket_service(self.session_id, {
                        'type': 'tool_call_arguments',
                        'id': self.last_streaming_tool_call_id,
                        'text': tool_call_chunk.get('args')
                    })
                else:
                    print('🟠no last_streaming_tool_call_id', tool_call_chunk)
