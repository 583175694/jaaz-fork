from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from services.websocket_service import send_to_websocket
from services.tool_confirmation_manager import tool_confirmation_manager

router = APIRouter(prefix="/api")

class ToolConfirmationRequest(BaseModel):
    session_id: str
    tool_call_id: str
    confirmed: bool | None = None
    action: str | None = None


@router.get("/tool_confirmation/pending/{session_id}")
async def get_pending_tool_confirmations(session_id: str):
    """获取指定会话当前所有待确认请求"""
    pending_requests = tool_confirmation_manager.list_pending_requests(session_id)
    return {
        "items": [
            {
                "tool_call_id": request.tool_call_id,
                "session_id": request.session_id,
                "tool_name": request.tool_name,
                "kind": request.kind,
                "target_id": request.target_id,
                "arguments": request.arguments,
                "created_at": request.created_at.isoformat(),
            }
            for request in pending_requests
        ]
    }

@router.post("/tool_confirmation")
async def handle_tool_confirmation(request: ToolConfirmationRequest):
    """处理工具调用确认"""
    try:
        action = (request.action or "").strip().lower()
        if action not in {"confirm", "cancel", "revise"}:
            action = "confirm" if request.confirmed else "cancel"

        if action == "confirm":
            # 确认工具调用
            success = tool_confirmation_manager.confirm_tool(
                request.tool_call_id)
            if success:
                await send_to_websocket(request.session_id, {
                    'type': 'tool_call_confirmed',
                    'id': request.tool_call_id
                })
            else:
                raise HTTPException(
                    status_code=404, detail="Tool call not found or already processed")
        elif action == "revise":
            success = tool_confirmation_manager.revise_confirmation(
                request.tool_call_id)
            if success:
                await send_to_websocket(request.session_id, {
                    'type': 'tool_call_cancelled',
                    'id': request.tool_call_id,
                    'reason': 'revise',
                })
            else:
                raise HTTPException(
                    status_code=404, detail="Tool call not found or already processed")
        else:
            # 取消工具调用
            success = tool_confirmation_manager.cancel_confirmation(
                request.tool_call_id)
            if success:
                await send_to_websocket(request.session_id, {
                    'type': 'tool_call_cancelled',
                    'id': request.tool_call_id,
                    'reason': 'cancel',
                })
            else:
                raise HTTPException(
                    status_code=404, detail="Tool call not found or already processed")

        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
