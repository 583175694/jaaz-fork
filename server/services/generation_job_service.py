import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from nanoid import generate

from services.db_service import db_service
from services.websocket_service import broadcast_session_update


JOB_TYPE_DIRECT_STORYBOARD = "direct_storyboard"
JOB_TYPE_DIRECT_MULTIVIEW = "direct_multiview"
JOB_TYPE_STORYBOARD_REFINE = "storyboard_refine"
JOB_TYPE_DIRECT_VIDEO = "direct_video"

JOB_PROVIDER_APIPOD_IMAGE = "apipodgptimage"
JOB_PROVIDER_APIPOD_VIDEO = "apipodvideo"

ACTIVE_JOB_STATUSES = {"queued", "running"}

_job_runners: dict[str, Callable[[str], Awaitable[None]]] = {}
_client_worker_tasks: dict[str, asyncio.Task[Any]] = {}


def register_job_runner(
    job_type: str,
    runner: Callable[[str], Awaitable[None]],
) -> None:
    _job_runners[job_type] = runner


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_job(job: Dict[str, Any]) -> Dict[str, Any]:
    serialized = dict(job)
    for key in ("request_payload", "result_payload"):
        value = serialized.get(key)
        if isinstance(value, str) and value.strip():
            try:
                serialized[key] = json.loads(value)
            except Exception:
                pass
    request_payload = serialized.get("request_payload")
    if isinstance(request_payload, dict):
        request_payload.pop("_normalized_payload_key", None)
    return serialized


def _stringify_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item or "").strip() for item in values if str(item or "").strip()]


def build_summary_text(job_type: str, payload: Dict[str, Any]) -> str:
    if job_type == JOB_TYPE_DIRECT_VIDEO:
        duration = int(payload.get("duration", 6) or 6)
        aspect_ratio = str(payload.get("aspect_ratio", "16:9") or "16:9")
        return f"视频 {duration}s / {aspect_ratio}"
    if job_type == JOB_TYPE_DIRECT_STORYBOARD:
        shot_count = int(payload.get("shot_count", 4) or 4)
        aspect_ratio = str(payload.get("aspect_ratio", "16:9") or "16:9")
        return f"分镜 {shot_count} 张 / {aspect_ratio}"
    if job_type == JOB_TYPE_DIRECT_MULTIVIEW:
        azimuth = int(payload.get("azimuth", 45) or 45)
        framing = str(payload.get("framing", "medium") or "medium")
        return f"多视角候选 {azimuth}° / {framing}"
    if job_type == JOB_TYPE_STORYBOARD_REFINE:
        mode = str(payload.get("mode", "append") or "append")
        return f"编辑当前镜头 / {mode}"
    return job_type


def normalize_payload_for_dedup(job_type: str, payload: Dict[str, Any]) -> str:
    normalized: Dict[str, Any]
    if job_type == JOB_TYPE_DIRECT_VIDEO:
        normalized = {
            "canvas_id": str(payload.get("canvas_id", "") or ""),
            "prompt": str(payload.get("prompt", "") or ""),
            "file_ids": _stringify_list(payload.get("file_ids", [])),
            "duration": int(payload.get("duration", 6) or 6),
            "aspect_ratio": str(payload.get("aspect_ratio", "16:9") or "16:9"),
            "resolution": str(payload.get("resolution", "1080p") or "1080p"),
            "video_model": str(payload.get("video_model", "") or ""),
            "selection_mode": str(payload.get("selection_mode", "") or ""),
            "start_frame_file_id": str(payload.get("start_frame_file_id", "") or ""),
            "end_frame_file_id": str(payload.get("end_frame_file_id", "") or ""),
        }
    elif job_type == JOB_TYPE_DIRECT_STORYBOARD:
        normalized = {
            "canvas_id": str(payload.get("canvas_id", "") or ""),
            "main_image_file_id": str(payload.get("main_image_file_id", "") or ""),
            "reference_image_file_id": str(payload.get("reference_image_file_id", "") or ""),
            "prompt": str(payload.get("prompt", "") or ""),
            "shot_count": int(payload.get("shot_count", 4) or 4),
            "aspect_ratio": str(payload.get("aspect_ratio", "16:9") or "16:9"),
            "image_tool_id": str(payload.get("image_tool_id", "") or ""),
            "image_model": str(payload.get("image_model", "") or ""),
        }
    elif job_type == JOB_TYPE_DIRECT_MULTIVIEW:
        normalized = {
            "canvas_id": str(payload.get("canvas_id", "") or ""),
            "source_file_id": str(payload.get("source_file_id", "") or ""),
            "reference_image_file_id": str(payload.get("reference_image_file_id", "") or ""),
            "prompt": str(payload.get("prompt", "") or ""),
            "preset_name": str(payload.get("preset_name", "") or ""),
            "azimuth": int(payload.get("azimuth", 45) or 45),
            "elevation": int(payload.get("elevation", 0) or 0),
            "framing": str(payload.get("framing", "medium") or "medium"),
            "aspect_ratio": str(payload.get("aspect_ratio", "16:9") or "16:9"),
            "preview_only": bool(payload.get("preview_only", False)),
            "replace_source": bool(payload.get("replace_source", False)),
            "image_tool_id": str(payload.get("image_tool_id", "") or ""),
            "image_model": str(payload.get("image_model", "") or ""),
        }
    elif job_type == JOB_TYPE_STORYBOARD_REFINE:
        normalized = {
            "canvas_id": str(payload.get("canvas_id", "") or ""),
            "source_file_id": str(payload.get("source_file_id", "") or ""),
            "reference_image_file_id": str(payload.get("reference_image_file_id", "") or ""),
            "prompt": str(payload.get("prompt", "") or ""),
            "aspect_ratio": str(payload.get("aspect_ratio", "16:9") or "16:9"),
            "mode": str(payload.get("mode", "append") or "append"),
            "image_tool_id": str(payload.get("image_tool_id", "") or ""),
            "image_model": str(payload.get("image_model", "") or ""),
        }
    else:
        normalized = payload
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


async def _emit_job_event(job: Dict[str, Any], event_type: str) -> None:
    await broadcast_session_update(
        str(job.get("session_id", "") or ""),
        str(job.get("canvas_id", "") or ""),
        {
            "type": event_type,
            "job_id": str(job.get("id", "") or ""),
            "job_type": str(job.get("type", "") or ""),
            "client_id": str(job.get("client_id", "") or ""),
            "status": str(job.get("status", "") or ""),
            "summary_text": str(job.get("summary_text", "") or ""),
            "progress": job.get("progress"),
            "error_message": job.get("error_message"),
        },
    )


async def create_media_job(
    *,
    job_type: str,
    client_id: str,
    session_id: str,
    canvas_id: str,
    provider: str,
    request_payload: Dict[str, Any],
) -> Dict[str, Any]:
    normalized_payload = normalize_payload_for_dedup(job_type, request_payload)
    persisted_payload = {
        **request_payload,
        "_normalized_payload_key": normalized_payload,
    }
    existing = await db_service.find_active_generation_job(
        session_id=session_id,
        canvas_id=canvas_id,
        client_id=client_id,
        type=job_type,
        request_payload=normalized_payload,
    )
    if existing:
        ensure_client_worker(client_id)
        serialized_existing = _serialize_job(existing)
        serialized_existing["deduplicated"] = True
        return serialized_existing

    job_id = f"job_{generate(size=12)}"
    summary_text = build_summary_text(job_type, request_payload)
    await db_service.create_generation_job(
        id=job_id,
        type=job_type,
        session_id=session_id,
        canvas_id=canvas_id,
        client_id=client_id,
        status="queued",
        provider=provider,
        request_payload=json.dumps(persisted_payload, ensure_ascii=False, sort_keys=True),
        summary_text=summary_text,
    )
    job = await db_service.get_generation_job(job_id)
    if not job:
        raise RuntimeError("failed to create generation job")
    await _emit_job_event(job, "job_queued")
    ensure_client_worker(client_id)
    serialized_job = _serialize_job(job)
    serialized_job["deduplicated"] = False
    return serialized_job


def ensure_client_worker(client_id: str) -> None:
    if not client_id:
        return
    existing = _client_worker_tasks.get(client_id)
    if existing and not existing.done():
        return

    task = asyncio.create_task(_run_client_worker(client_id))
    _client_worker_tasks[client_id] = task

    def _cleanup(_: asyncio.Task[Any]) -> None:
        current = _client_worker_tasks.get(client_id)
        if current is task:
            _client_worker_tasks.pop(client_id, None)

    task.add_done_callback(_cleanup)


async def _run_client_worker(client_id: str) -> None:
    while True:
        job = await db_service.get_next_generation_job_for_client(client_id)
        if not job:
            return
        job_id = str(job.get("id", "") or "")
        job_type = str(job.get("type", "") or "")
        runner = _job_runners.get(job_type)
        if runner is None:
            await db_service.update_generation_job(
                job_id,
                status="failed",
                error_message=f"No job runner registered for {job_type}.",
                finished_at=_utc_now(),
            )
            failed_job = await db_service.get_generation_job(job_id)
            if failed_job:
                await _emit_job_event(failed_job, "job_failed")
            continue

        await db_service.update_generation_job(
            job_id,
            status="running",
            started_at=job.get("started_at") or _utc_now(),
        )
        running_job = await db_service.get_generation_job(job_id)
        if running_job:
            await _emit_job_event(running_job, "job_running")

        try:
            await runner(job_id)
        except asyncio.CancelledError:
            await db_service.update_generation_job(
                job_id,
                status="cancelled",
                finished_at=_utc_now(),
            )
            cancelled_job = await db_service.get_generation_job(job_id)
            if cancelled_job:
                await _emit_job_event(cancelled_job, "job_failed")
            raise
        except Exception as exc:
            await db_service.update_generation_job(
                job_id,
                status="failed",
                error_message=str(exc),
                finished_at=_utc_now(),
            )
            failed_job = await db_service.get_generation_job(job_id)
            if failed_job:
                await _emit_job_event(failed_job, "job_failed")


async def update_job_progress(
    job_id: str,
    *,
    progress: Optional[int] = None,
    provider_task_id: Optional[str] = None,
    result_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    if progress is not None:
        fields["progress"] = progress
    if provider_task_id:
        fields["provider_task_id"] = provider_task_id
    if result_payload is not None:
        fields["result_payload"] = json.dumps(result_payload, ensure_ascii=False)
    await db_service.update_generation_job(job_id, **fields)
    job = await db_service.get_generation_job(job_id)
    if not job:
        raise RuntimeError("job not found after progress update")
    await _emit_job_event(job, "job_progress")
    return _serialize_job(job)


async def mark_job_succeeded(
    job_id: str,
    *,
    progress: Optional[int] = 100,
    result_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    await db_service.update_generation_job(
        job_id,
        status="succeeded",
        progress=progress,
        result_payload=json.dumps(result_payload, ensure_ascii=False)
        if result_payload is not None
        else None,
        finished_at=_utc_now(),
    )
    job = await db_service.get_generation_job(job_id)
    if not job:
        raise RuntimeError("job not found after success update")
    await _emit_job_event(job, "job_succeeded")
    return _serialize_job(job)


async def mark_job_failed(
    job_id: str,
    *,
    error_message: str,
    result_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    await db_service.update_generation_job(
        job_id,
        status="failed",
        error_message=error_message,
        result_payload=json.dumps(result_payload, ensure_ascii=False)
        if result_payload is not None
        else None,
        finished_at=_utc_now(),
    )
    job = await db_service.get_generation_job(job_id)
    if not job:
        raise RuntimeError("job not found after failure update")
    await _emit_job_event(job, "job_failed")
    return _serialize_job(job)


async def list_canvas_jobs(
    canvas_id: str,
    *,
    client_id: str,
    job_type: Optional[str] = None,
    statuses: Optional[list[str]] = None,
    limit: int = 20,
    ascending: bool = False,
) -> list[Dict[str, Any]]:
    jobs = await db_service.list_generation_jobs(
        canvas_id=canvas_id,
        client_id=client_id,
        type=job_type,
        statuses=statuses,
        limit=limit,
        ascending=ascending,
    )
    return [_serialize_job(job) for job in jobs]


async def list_client_jobs(
    client_id: str,
    *,
    canvas_id: Optional[str] = None,
    statuses: Optional[list[str]] = None,
    limit: int = 20,
) -> list[Dict[str, Any]]:
    jobs = await db_service.list_generation_jobs(
        canvas_id=canvas_id,
        client_id=client_id,
        statuses=statuses,
        limit=limit,
        ascending=True,
    )
    return [_serialize_job(job) for job in jobs]


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    job = await db_service.get_generation_job(job_id)
    if not job:
        return None
    return _serialize_job(job)


async def recover_generation_jobs() -> None:
    jobs = await db_service.list_recoverable_generation_jobs()
    client_ids: set[str] = set()
    for job in jobs:
        client_id = str(job.get("client_id", "") or "")
        if not client_id:
            continue
        status = str(job.get("status", "") or "")
        if status == "running":
            await db_service.update_generation_job(
                str(job.get("id", "") or ""),
                status="queued",
                started_at=None,
            )
        client_ids.add(client_id)

    for client_id in client_ids:
        ensure_client_worker(client_id)
