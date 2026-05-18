#server/routers/chat_router.py
from fastapi import APIRouter, HTTPException, Request
from services.db_service import db_service
from services.chat_service import handle_chat
from services.direct_storyboard_service import (
    handle_direct_multiview,
    handle_direct_storyboard,
    handle_direct_storyboard_refine,
    preview_direct_storyboard_prompt,
    set_storyboard_primary_variant,
)
from services.direct_video_service import handle_direct_video, preview_direct_video_prompt
from services.generation_job_service import get_job, list_canvas_jobs, list_client_jobs
from services.stream_service import get_stream_task

router = APIRouter(prefix="/api")


def _wrap_media_job_response(payload):
    if not isinstance(payload, dict):
        return payload
    job_id = payload.get("id")
    status = str(payload.get("status", "") or "")
    if job_id and status in {"queued", "running"}:
        return {
            "status": "accepted",
            "job_id": job_id,
            "job": payload,
        }
    return payload

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
    job = await handle_direct_video(data)
    return _wrap_media_job_response(job)


@router.get("/jobs/{job_id}")
async def generation_job(job_id: str, client_id: str = ""):
    if not client_id:
        return {"job": None}
    job = await get_job(job_id)
    if job and str(job.get("client_id", "") or "") != client_id:
        job = None
    return {"job": job}


@router.get("/jobs")
async def client_generation_jobs(
    scope: str = "",
    client_id: str = "",
    canvas_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
):
    statuses = [item.strip() for item in str(status or "").split(",") if item.strip()]
    if scope != "client" or not client_id:
        return {"jobs": []}
    jobs = await list_client_jobs(
        client_id,
        canvas_id=canvas_id,
        statuses=statuses or None,
        limit=limit,
    )
    return {"jobs": jobs}


@router.get("/canvases/{canvas_id}/jobs")
async def canvas_generation_jobs(
    canvas_id: str,
    client_id: str = "",
    type: str | None = None,
    status: str | None = None,
    limit: int = 20,
):
    if not client_id:
        return {"jobs": []}
    statuses = [item.strip() for item in str(status or "").split(",") if item.strip()]
    jobs = await list_canvas_jobs(
        canvas_id,
        client_id=client_id,
        job_type=type,
        statuses=statuses or None,
        limit=limit,
        ascending=True,
    )
    return {"jobs": jobs}


@router.post("/direct_video/prompt_preview")
async def direct_video_prompt_preview(request: Request):
    data = await request.json()
    result = await preview_direct_video_prompt(data)
    return {"status": "done", "result": result}


@router.post("/direct_storyboard")
async def direct_storyboard(request: Request):
    data = await request.json()
    job = await handle_direct_storyboard(data)
    return _wrap_media_job_response(job)


@router.post("/direct_storyboard/prompt_preview")
async def direct_storyboard_prompt_preview(request: Request):
    data = await request.json()
    result = await preview_direct_storyboard_prompt(data)
    return {"status": "done", "result": result}


@router.post("/direct_multiview")
async def direct_multiview(request: Request):
    data = await request.json()
    job = await handle_direct_multiview(data)
    return _wrap_media_job_response(job)


@router.post("/storyboard/refine")
async def storyboard_refine(request: Request):
    data = await request.json()
    job = await handle_direct_storyboard_refine(data)
    return _wrap_media_job_response(job)


@router.post("/storyboard/mark_primary")
async def storyboard_mark_primary(request: Request):
    data = await request.json()
    client_id = str(data.get("client_id", "") or "")
    canvas_id = str(data.get("canvas_id", "") or "")
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")
    canvas = await db_service.get_canvas_data(canvas_id, client_id=client_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    result = await set_storyboard_primary_variant(
        canvas_id=canvas_id,
        file_id=str(data.get("file_id", "") or ""),
        client_id=client_id,
    )
    return {"status": "done", "result": result}
