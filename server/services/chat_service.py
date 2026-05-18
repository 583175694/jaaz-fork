# services/chat_service.py

# Import necessary modules
import asyncio
import json
from typing import Dict, Any, List, Optional

# Import service modules
from models.tool_model import ToolInfoJson
from services.db_service import db_service
from services.langgraph_service import langgraph_multi_agent
from services.websocket_service import send_to_websocket
from services.stream_service import add_stream_task, remove_stream_task
from services.ad_generation_runtime import maybe_compile_ad_image_messages
from models.config_model import ModelInfo
from services.runtime_defaults import get_default_text_model, sanitize_tool_list


async def handle_chat(data: Dict[str, Any]) -> None:
    """
    Handle an incoming chat request.

    Workflow:
    - Parse incoming chat data.
    - Optionally inject system prompt.
    - Save chat session and messages to the database.
    - Launch langgraph_agent task to process chat.
    - Manage stream task lifecycle (add, remove).
    - Notify frontend via WebSocket when stream is done.

    Args:
        data (dict): Chat request data containing:
            - messages: list of message dicts
            - session_id: unique session identifier
            - canvas_id: canvas identifier (contextual use)
            - text_model: text model configuration
            - tool_list: list of tool model configurations (images/videos)
    """
    # Extract fields from incoming data
    messages: List[Dict[str, Any]] = data.get('messages', [])
    session_id: str = data.get('session_id', '')
    canvas_id: str = data.get('canvas_id', '')
    client_id: str = str(data.get('client_id', '') or '')
    text_model: ModelInfo = get_default_text_model()
    tool_list: List[ToolInfoJson] = sanitize_tool_list(data.get('tool_list', []))

    print('👇 chat_service got tool_list', tool_list)
    print(
        "💬 handle_chat start",
        {
            "session_id": session_id,
            "canvas_id": canvas_id,
            "message_count": len(messages),
            "text_model": f"{text_model.get('provider')}:{text_model.get('model')}",
        },
    )

    # TODO: save and fetch system prompt from db or settings config
    system_prompt: Optional[str] = data.get('system_prompt')

    if not client_id:
        raise RuntimeError("client_id is required")

    if canvas_id and client_id:
        canvas = await db_service.get_canvas_data(canvas_id, client_id=client_id)
        if not canvas:
            raise RuntimeError("Canvas not found for current client.")

    try:
        messages = await maybe_compile_ad_image_messages(messages, text_model)
        print(
            "💬 handle_chat after prompt compile",
            {
                "session_id": session_id,
                "message_count": len(messages),
                "latest_role": messages[-1].get("role") if messages else None,
            },
        )
    except Exception as exc:
        print("⚠️ Failed to pre-compile advertising image prompt, continuing with original messages", {
            "error": str(exc),
            "session_id": session_id,
        })

    # If there is only one message, create a new chat session
    if len(messages) == 1:
        # create new session
        prompt = messages[0].get('content', '')
        # TODO: Better way to determin when to create new chat session.
        await db_service.create_chat_session(
            session_id,
            text_model.get('model'),
            text_model.get('provider'),
            canvas_id,
            (prompt[:200] if isinstance(prompt, str) else ''),
            client_id=client_id,
        )
        print(
            "💬 handle_chat session created",
            {
                "session_id": session_id,
                "canvas_id": canvas_id,
            },
        )

    await db_service.create_message(session_id, messages[-1].get('role', 'user'), json.dumps(messages[-1])) if len(messages) > 0 else None
    if len(messages) > 0:
        print(
            "💬 handle_chat latest message persisted",
            {
                "session_id": session_id,
                "role": messages[-1].get('role', 'user'),
            },
        )

    # Create and start langgraph_agent task for chat processing
    task = asyncio.create_task(langgraph_multi_agent(
        messages, canvas_id, session_id, text_model, tool_list, system_prompt))
    print(
        "💬 handle_chat langgraph task created",
        {
            "session_id": session_id,
            "canvas_id": canvas_id,
        },
    )

    # Register the task in stream_tasks (for possible cancellation)
    add_stream_task(session_id, task)
    try:
        # Await completion of the langgraph_agent task
        await task
        print(
            "💬 handle_chat langgraph task completed",
            {
                "session_id": session_id,
            },
        )
    except asyncio.exceptions.CancelledError:
        print(f"🛑Session {session_id} cancelled during stream")
    finally:
        # Always remove the task from stream_tasks after completion/cancellation
        remove_stream_task(session_id)
        # Notify frontend WebSocket that chat processing is done
        await send_to_websocket(session_id, {
            'type': 'done'
        })
