#server/routers/chat_router.py
from fastapi import APIRouter, Request
from services.chat_service import handle_chat
from services.direct_storyboard_service import (
    handle_direct_multiview,
    handle_direct_storyboard,
    handle_direct_storyboard_refine,
    set_storyboard_primary_variant,
)
from services.direct_video_service import handle_direct_video, preview_direct_video_prompt
from services.stream_service import get_stream_task

router = APIRouter(prefix="/api")

@router.post("/chat")
async def chat(request: Request):
    """
    Endpoint to handle chat requests.

    Receives a JSON payload from the client, passes it to the chat handler,
    and returns a success status.

    Request body:
        JSON object containing chat data.

    Response:
        {"status": "done"}
    """
    data = await request.json()
    await handle_chat(data)
    return {"status": "done"}

@router.post("/cancel/{session_id}")
async def cancel_chat(session_id: str):
    """
    Endpoint to cancel an ongoing stream task for a given session_id.

    If the task exists and is not yet completed, it will be cancelled.

    Path parameter:
        session_id (str): The ID of the session whose task should be cancelled.

    Response:
        {"status": "cancelled"} if the task was cancelled.
        {"status": "not_found_or_done"} if no such task exists or it is already done.
    """
    task = get_stream_task(session_id)
    if task and not task.done():
        task.cancel()
        return {"status": "cancelled"}
    return {"status": "not_found_or_done"}

@router.post("/direct_video")
async def direct_video(request: Request):
    data = await request.json()
    await handle_direct_video(data)
    return {"status": "done"}


@router.post("/direct_video/prompt_preview")
async def direct_video_prompt_preview(request: Request):
    data = await request.json()
    result = await preview_direct_video_prompt(data)
    return {"status": "done", "result": result}


@router.post("/direct_storyboard")
async def direct_storyboard(request: Request):
    data = await request.json()
    await handle_direct_storyboard(data)
    return {"status": "done"}


@router.post("/direct_multiview")
async def direct_multiview(request: Request):
    data = await request.json()
    await handle_direct_multiview(data)
    return {"status": "done"}


@router.post("/storyboard/refine")
async def storyboard_refine(request: Request):
    data = await request.json()
    await handle_direct_storyboard_refine(data)
    return {"status": "done"}


@router.post("/storyboard/mark_primary")
async def storyboard_mark_primary(request: Request):
    data = await request.json()
    result = await set_storyboard_primary_variant(
        canvas_id=str(data.get("canvas_id", "") or ""),
        file_id=str(data.get("file_id", "") or ""),
    )
    return {"status": "done", "result": result}
