import json
from typing import Any, Dict

from nanoid import generate

from services.tool_confirmation_manager import tool_confirmation_manager
from services.websocket_service import send_to_websocket


async def request_prompt_bundle_confirmation(
    session_id: str,
    tool_name: str,
    payload: Dict[str, Any],
) -> str:
    tool_call_id = f"pc_{generate(size=10)}"
    await send_to_websocket(
        session_id,
        {
            "type": "tool_call_pending_confirmation",
            "id": tool_call_id,
            "name": tool_name,
            "arguments": json.dumps(payload, ensure_ascii=False),
        },
    )
    kind = "tool"
    target_id = ""
    if tool_name == "generate_storyboard_from_main_image":
        if isinstance(payload.get("continuity_asset"), dict):
            kind = "continuity"
            target_id = str(payload["continuity_asset"].get("continuity_id", "") or "")
        elif isinstance(payload.get("storyboard_plan"), dict):
            kind = "storyboard_plan"
            target_id = str(payload["storyboard_plan"].get("storyboard_id", "") or "")
    elif tool_name == "generate_multiview_variant":
        kind = str(payload.get("task_type", "") or "multiview")
        target_id = str(payload.get("target_id", "") or payload.get("shot_family_id", "") or "")
    elif tool_name == "generate_video_from_storyboard":
        kind = "video_brief"
        target_id = str(payload.get("brief_id", "") or "")
    return await tool_confirmation_manager.request_confirmation(
        tool_call_id,
        session_id,
        tool_name,
        payload,
        kind=kind,
        target_id=target_id,
    )
