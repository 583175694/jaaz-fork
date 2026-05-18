from fastapi import APIRouter, HTTPException

from services.db_service import db_service

from services.production_workflow_service import (
    get_current_continuity_asset,
    get_current_main_image_file_id,
    get_current_video_brief,
    get_current_storyboard_plan,
    get_storyboard_plan,
    set_current_main_image_file_id,
)
from services.tool_confirmation_manager import tool_confirmation_manager

router = APIRouter(prefix="/api")


@router.get("/continuity/{canvas_id}/current")
async def get_current_continuity(canvas_id: str, client_id: str = ""):
    if not client_id:
        return {"item": None}
    item = await get_current_continuity_asset(canvas_id, client_id=client_id)
    return {"item": item}


@router.get("/main_image/{canvas_id}/current")
async def get_current_main_image(canvas_id: str, client_id: str = ""):
    if not client_id:
        return {"file_id": ""}
    file_id = await get_current_main_image_file_id(canvas_id, client_id=client_id)
    return {"file_id": file_id}


@router.post("/main_image/{canvas_id}/current")
async def set_current_main_image(canvas_id: str, payload: dict):
    client_id = str(payload.get("client_id", "") or "")
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")
    canvas = await db_service.get_canvas_data(canvas_id, client_id=client_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    file_id = str(payload.get("file_id", "") or "").strip()
    await set_current_main_image_file_id(canvas_id, file_id, client_id=client_id)
    return {"status": "done", "file_id": file_id}


@router.get("/storyboard/{canvas_id}/current")
async def get_current_storyboard(canvas_id: str, client_id: str = ""):
    if not client_id:
        return {"item": None}
    item = await get_current_storyboard_plan(canvas_id, client_id=client_id)
    return {"item": item}


@router.get("/storyboard/{canvas_id}/{storyboard_id}")
async def get_storyboard(canvas_id: str, storyboard_id: str, client_id: str = ""):
    if not client_id:
        return {"item": None}
    item = await get_storyboard_plan(canvas_id, storyboard_id, client_id=client_id)
    return {"item": item}


@router.get("/video/brief/{canvas_id}/current")
async def get_current_video_brief_endpoint(canvas_id: str, client_id: str = ""):
    if not client_id:
        return {"item": None}
    item = await get_current_video_brief(canvas_id, client_id=client_id)
    return {"item": item}


@router.get("/workflow/{session_id}/pending")
async def get_pending_workflow(session_id: str, client_id: str = ""):
    if not client_id:
        return {"items": []}
    session = await db_service.get_chat_session(session_id)
    if not session or str(session.get("client_id", "") or "") != client_id:
        return {"items": []}
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
