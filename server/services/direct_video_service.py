import asyncio
import json
from typing import Any, Dict, List

from nanoid import generate

from models.config_model import ModelInfo
from services.db_service import db_service
from services.stream_service import add_stream_task, remove_stream_task
from services.websocket_service import send_to_websocket
from tools.utils.image_utils import process_input_image
from tools.video_generation.video_generation_core import generate_video_with_provider
from tools.video_providers.apipod_provider import (
    APIPOD_VIDEO_REFERENCE_IMAGES_MAX,
    apipod_video_supports_multi_reference_images,
    format_apipod_multi_reference_images_not_supported_error,
    get_apipod_video_model_name,
)


def _build_model_info() -> Dict[str, List[ModelInfo]]:
    model_name = get_apipod_video_model_name()
    return {
        model_name: [
            {
                "provider": "apipodvideo",
                "model": model_name,
                "url": "",
                "type": "video",
            }
        ]
    }


def _normalize_file_ids(data: Dict[str, Any]) -> List[str]:
    file_ids = data.get("file_ids", [])
    normalized: List[str] = []
    if isinstance(file_ids, list):
        for file_id in file_ids:
            value = str(file_id or "").strip()
            if value:
                normalized.append(value)

    if not normalized:
        legacy_file_id = str(data.get("file_id", "") or "").strip()
        if legacy_file_id:
            normalized.append(legacy_file_id)

    return normalized[:APIPOD_VIDEO_REFERENCE_IMAGES_MAX]


async def handle_direct_video(data: Dict[str, Any]) -> None:
    messages: List[Dict[str, Any]] = data.get("messages", [])
    session_id: str = data.get("session_id", "")
    canvas_id: str = data.get("canvas_id", "")
    prompt: str = str(data.get("prompt", "") or "")
    file_ids = _normalize_file_ids(data)
    duration: int = int(data.get("duration", 6) or 6)
    aspect_ratio: str = str(data.get("aspect_ratio", "16:9") or "16:9")
    resolution: str = str(data.get("resolution", "1080p") or "1080p")
    model_name = get_apipod_video_model_name()
    print(
        "🎬 direct_video request",
        {
            "session_id": session_id,
            "canvas_id": canvas_id,
            "model_name": model_name,
            "file_ids": file_ids,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "prompt_preview": prompt[:120],
        },
    )

    existing_sessions = await db_service.list_sessions(canvas_id)
    if not any(session.get("id") == session_id for session in existing_sessions):
        await db_service.create_chat_session(
            session_id,
            model_name,
            "apipodvideo",
            canvas_id,
            (prompt[:200] if prompt else "Generate Video"),
        )

    if len(messages) > 0:
        await db_service.create_message(
            session_id, messages[-1].get("role", "user"), json.dumps(messages[-1])
        )

    task = asyncio.create_task(
        _process_direct_video_generation(
            messages=messages,
            session_id=session_id,
            canvas_id=canvas_id,
            prompt=prompt,
            file_ids=file_ids,
            duration=duration,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
        )
    )
    add_stream_task(session_id, task)
    try:
        await task
    except asyncio.exceptions.CancelledError:
        print(f"🛑Direct video generation session {session_id} cancelled")
    finally:
        remove_stream_task(session_id)
        await send_to_websocket(session_id, {"type": "done"})


async def _process_direct_video_generation(
    messages: List[Dict[str, Any]],
    session_id: str,
    canvas_id: str,
    prompt: str,
    file_ids: List[str],
    duration: int,
    aspect_ratio: str,
    resolution: str,
) -> None:
    ai_response = await create_direct_video_response(
        session_id=session_id,
        canvas_id=canvas_id,
        prompt=prompt,
        file_ids=file_ids,
        duration=duration,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
    )

    await db_service.create_message(session_id, "assistant", json.dumps(ai_response))
    all_messages = messages + [ai_response]
    await send_to_websocket(
        session_id, {"type": "all_messages", "messages": all_messages}
    )


async def create_direct_video_response(
    session_id: str,
    canvas_id: str,
    prompt: str,
    file_ids: List[str],
    duration: int,
    aspect_ratio: str,
    resolution: str,
) -> Dict[str, Any]:
    try:
        model_name = get_apipod_video_model_name()
        if len(file_ids) > 1 and not apipod_video_supports_multi_reference_images(model_name):
            raise RuntimeError(format_apipod_multi_reference_images_not_supported_error(model_name))

        input_images = []
        for file_id in file_ids[:APIPOD_VIDEO_REFERENCE_IMAGES_MAX]:
            processed_image = await process_input_image(file_id, canvas_id=canvas_id)
            if processed_image:
                input_images.append(processed_image)
        print(
            "🎬 direct_video processed inputs",
            {
                "requested_file_count": len(file_ids),
                "accepted_file_count": len(input_images),
                "max_reference_images": APIPOD_VIDEO_REFERENCE_IMAGES_MAX,
            },
        )

        normalized_input_images = input_images or None

        result = await generate_video_with_provider(
            prompt=prompt,
            resolution=resolution,
            duration=duration,
            aspect_ratio=aspect_ratio,
            model=model_name,
            tool_call_id=f"call_direct_video_{generate(size=8)}",
            config={
                "configurable": {
                    "canvas_id": canvas_id,
                    "session_id": session_id,
                    "model_info": _build_model_info(),
                }
            },
            input_images=normalized_input_images,
            source_file_ids=file_ids,
            camera_fixed=True,
            provider_hint="apipodvideo",
        )

        return {
            "role": "assistant",
            "content": result,
        }
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Direct video generation error: {error_msg}")
        return {
            "role": "assistant",
            "content": [{"type": "text", "text": f"🎬 Video Error: {error_msg}"}],
        }
