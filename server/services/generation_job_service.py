import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from nanoid import generate

from services.db_service import db_service
from services.websocket_service import broadcast_session_update


JOB_TYPE_DIRECT_VIDEO = "direct_video"
JOB_PROVIDER_APIPOD_VIDEO = "apipodvideo"
ACTIVE_JOB_STATUSES = {"queued", "running"}

_job_tasks: dict[str, asyncio.Task[Any]] = {}
_video_job_semaphore = asyncio.Semaphore(1)
_job_runner: Optional[Callable[[str], Awaitable[None]]] = None


def register_job_runner(
    job_type: str,
    runner: Callable[[str], Awaitable[None]],
) -> None:
    global _job_runner
    if job_type == JOB_TYPE_DIRECT_VIDEO:
        _job_runner = runner


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
    return serialized


async def _emit_job_event(job: Dict[str, Any], event_type: str) -> None:
    await broadcast_session_update(
        str(job.get("session_id", "") or ""),
        str(job.get("canvas_id", "") or ""),
        {
            "type": event_type,
            "job_id": str(job.get("id", "") or ""),
            "job_type": str(job.get("type", "") or ""),
            "status": str(job.get("status", "") or ""),
            "progress": job.get("progress"),
            "error_message": job.get("error_message"),
        },
    )


async def create_job(
    *,
    job_type: str,
    session_id: str,
    canvas_id: str,
    provider: str,
    request_payload: Dict[str, Any],
) -> Dict[str, Any]:
    payload_json = json.dumps(request_payload, ensure_ascii=False, sort_keys=True)
    existing = await db_service.find_active_generation_job(
        session_id=session_id,
        canvas_id=canvas_id,
        type=job_type,
        request_payload=payload_json,
    )
    if existing:
        start_generation_job(str(existing.get("id", "") or ""))
        serialized_existing = _serialize_job(existing)
        serialized_existing["deduplicated"] = True
        return serialized_existing

    job_id = f"job_{generate(size=12)}"
    await db_service.create_generation_job(
        id=job_id,
        type=job_type,
        session_id=session_id,
        canvas_id=canvas_id,
        status="queued",
        provider=provider,
        request_payload=payload_json,
    )
    job = await db_service.get_generation_job(job_id)
    if not job:
        raise RuntimeError("failed to create generation job")
    await _emit_job_event(job, "job_queued")
    start_generation_job(job_id)
    serialized_job = _serialize_job(job)
    serialized_job["deduplicated"] = False
    return serialized_job


def start_generation_job(job_id: str) -> None:
    existing = _job_tasks.get(job_id)
    if existing and not existing.done():
        return

    task = asyncio.create_task(_run_generation_job(job_id))
    _job_tasks[job_id] = task

    def _cleanup(_: asyncio.Task[Any]) -> None:
        current = _job_tasks.get(job_id)
        if current is task:
            _job_tasks.pop(job_id, None)

    task.add_done_callback(_cleanup)


async def _run_generation_job(job_id: str) -> None:
    job = await db_service.get_generation_job(job_id)
    if not job:
        return
    if str(job.get("type", "")) != JOB_TYPE_DIRECT_VIDEO:
        return
    if _job_runner is None:
        raise RuntimeError("direct video job runner is not registered")

    async with _video_job_semaphore:
        job = await db_service.get_generation_job(job_id)
        if not job or str(job.get("status", "")) not in ACTIVE_JOB_STATUSES:
            return

        await db_service.update_generation_job(
            job_id,
            status="running",
            started_at=job.get("started_at") or _utc_now(),
        )
        job = await db_service.get_generation_job(job_id)
        if not job:
            return
        await _emit_job_event(job, "job_running")

        try:
            await _job_runner(job_id)
        except asyncio.CancelledError:
            await db_service.update_generation_job(
                job_id,
                status="cancelled",
                finished_at=_utc_now(),
            )
            job = await db_service.get_generation_job(job_id)
            if job:
                await _emit_job_event(job, "job_failed")
            raise
        except Exception as exc:
            await db_service.update_generation_job(
                job_id,
                status="failed",
                error_message=str(exc),
                finished_at=_utc_now(),
            )
            job = await db_service.get_generation_job(job_id)
            if job:
                await _emit_job_event(job, "job_failed")


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
    job_type: Optional[str] = None,
    statuses: Optional[list[str]] = None,
    limit: int = 20,
) -> list[Dict[str, Any]]:
    jobs = await db_service.list_generation_jobs(
        canvas_id=canvas_id,
        type=job_type,
        statuses=statuses,
        limit=limit,
    )
    return [_serialize_job(job) for job in jobs]


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    job = await db_service.get_generation_job(job_id)
    if not job:
        return None
    return _serialize_job(job)


async def recover_generation_jobs() -> None:
    jobs = await db_service.list_recoverable_generation_jobs()
    for job in jobs:
        status = str(job.get("status", "") or "")
        provider_task_id = str(job.get("provider_task_id", "") or "")
        if status == "queued":
            start_generation_job(str(job.get("id", "") or ""))
            continue
        if status == "running" and provider_task_id:
            start_generation_job(str(job.get("id", "") or ""))
            continue
        if status == "running":
            await db_service.update_generation_job(
                str(job.get("id", "") or ""),
                status="failed",
                error_message="Job recovery failed because provider task id is missing.",
                finished_at=_utc_now(),
            )
