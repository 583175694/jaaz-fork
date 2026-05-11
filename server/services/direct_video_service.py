import asyncio
import json
from typing import Any, Dict, List, Optional

from nanoid import generate

from models.config_model import ModelInfo
from services.ad_video_prompt_runtime import compile_ad_video_prompt
from services.db_service import db_service
from services.prompt_confirmation_service import request_prompt_bundle_confirmation
from services.production_workflow_service import (
    build_video_brief_asset,
    collect_primary_storyboard_variants,
    get_current_continuity_asset,
    load_canvas_data,
    upsert_video_brief,
)
from services.stream_service import add_stream_task, get_stream_task, remove_stream_task
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


def _normalize_text_model(data: Dict[str, Any]) -> Optional[ModelInfo]:
    text_model = data.get("text_model", {})
    if not isinstance(text_model, dict):
        return None

    provider = str(text_model.get("provider", "") or "").strip()
    model = str(text_model.get("model", "") or "").strip()
    url = str(text_model.get("url", "") or "").strip()
    if not provider or not model:
        return None

    return {
        "provider": provider,
        "model": model,
        "url": url,
        "type": "text",
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


def _normalize_selection_mode(data: Dict[str, Any]) -> str:
    value = str(data.get("selection_mode", "") or "").strip()
    return value or "reference_images"


def _normalize_frame_file_id(data: Dict[str, Any], key: str) -> str:
    return str(data.get(key, "") or "").strip()


def _normalize_skip_prompt_confirmation(data: Dict[str, Any]) -> bool:
    return bool(data.get("skip_prompt_confirmation", False))


def _resolve_ordered_reference_file_ids(
    file_ids: List[str],
    selection_mode: str,
    start_frame_file_id: str,
    end_frame_file_id: str,
) -> List[str]:
    normalized_file_ids = [str(file_id or "").strip() for file_id in file_ids if str(file_id or "").strip()]
    if selection_mode != "start_end_frames":
        return normalized_file_ids[:APIPOD_VIDEO_REFERENCE_IMAGES_MAX]

    ordered_candidates = [
        str(start_frame_file_id or "").strip(),
        str(end_frame_file_id or "").strip(),
    ]
    ordered: List[str] = []
    for candidate in ordered_candidates:
        if candidate and candidate not in ordered:
            ordered.append(candidate)

    if not ordered and normalized_file_ids:
        ordered.append(normalized_file_ids[0])
    if len(ordered) < 2 and len(normalized_file_ids) > 1:
        tail_candidate = normalized_file_ids[-1]
        if tail_candidate and tail_candidate not in ordered:
            ordered.append(tail_candidate)

    return ordered[:APIPOD_VIDEO_REFERENCE_IMAGES_MAX]


async def _compile_direct_video_prompt(
    *,
    session_id: str,
    canvas_id: str,
    prompt: str,
    messages: List[Dict[str, Any]],
    file_ids: List[str],
    selection_mode: str,
    start_frame_file_id: str,
    end_frame_file_id: str,
    duration: int,
    aspect_ratio: str,
    resolution: str,
    text_model: Optional[ModelInfo],
) -> Dict[str, Any]:
    selection = await _resolve_storyboard_video_selection(
        canvas_id=canvas_id,
        file_ids=file_ids,
        start_frame_file_id=start_frame_file_id,
        end_frame_file_id=end_frame_file_id,
    )
    file_ids = selection["file_ids"]
    start_frame_file_id = selection["start_frame_file_id"]
    end_frame_file_id = selection["end_frame_file_id"]
    reference_file_ids = _resolve_ordered_reference_file_ids(
        file_ids=file_ids,
        selection_mode=selection_mode,
        start_frame_file_id=start_frame_file_id,
        end_frame_file_id=end_frame_file_id,
    )
    storyboard_id = str(selection.get("storyboard_id", "") or "")
    continuity_ids = selection.get("continuity_ids", set())
    continuity_versions = selection.get("continuity_versions", set())

    if len(continuity_ids) > 1 or len(continuity_versions) > 1:
        raise RuntimeError(
            "当前选中的分镜主版本存在多个 continuity 版本，暂不能直接生成视频。请先统一分镜版本。"
        )

    model_name = get_apipod_video_model_name()
    if len(file_ids) > 1 and not apipod_video_supports_multi_reference_images(model_name):
        raise RuntimeError(
            format_apipod_multi_reference_images_not_supported_error(model_name)
        )

    compiled = await compile_ad_video_prompt(
        session_id=session_id,
        prompt=prompt,
        messages=messages,
        duration=duration,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        selected_image_count=len(reference_file_ids),
        platform_hint="canvas selected storyboard to video",
        canvas_id=canvas_id,
        selection_mode=selection_mode,
        start_frame_file_id=start_frame_file_id,
        end_frame_file_id=end_frame_file_id,
        text_model=text_model,
    )
    compiled_video_prompt = str(compiled["video_prompt"] or prompt).strip()
    return {
        "selection": selection,
        "reference_file_ids": reference_file_ids,
        "storyboard_id": storyboard_id,
        "compiled": compiled,
        "compiled_video_prompt": compiled_video_prompt,
        "start_frame_file_id": start_frame_file_id,
        "end_frame_file_id": end_frame_file_id,
    }


async def _resolve_storyboard_video_selection(
    canvas_id: str,
    file_ids: List[str],
    start_frame_file_id: str,
    end_frame_file_id: str,
) -> Dict[str, Any]:
    canvas_data = await load_canvas_data(canvas_id)
    files = canvas_data.get("files", {}) if isinstance(canvas_data, dict) else {}
    if not isinstance(files, dict):
        files = {}

    selected_file_ids = [str(file_id or "").strip() for file_id in file_ids if str(file_id or "").strip()]
    selected_storyboard_id = ""
    continuity_ids = set()
    continuity_versions = set()

    for file_id in selected_file_ids:
        file_info = files.get(file_id)
        if not isinstance(file_info, dict):
            continue
        meta = file_info.get("storyboardMeta")
        if not isinstance(meta, dict):
            continue
        storyboard_id = str(meta.get("storyboard_id", "") or "")
        continuity_id = str(meta.get("continuity_id", "") or "")
        continuity_version = int(meta.get("continuity_version", 1) or 1)
        if storyboard_id and not selected_storyboard_id:
            selected_storyboard_id = storyboard_id
        if continuity_id:
            continuity_ids.add(continuity_id)
        continuity_versions.add(continuity_version)

    if selected_storyboard_id:
        primary_variants = collect_primary_storyboard_variants(canvas_data, selected_storyboard_id)
        if primary_variants:
            selected_file_ids = [str(item.get("file_id", "") or "") for item in primary_variants]
            if not start_frame_file_id:
                start_frame_file_id = selected_file_ids[0] if selected_file_ids else ""
            if not end_frame_file_id:
                end_frame_file_id = selected_file_ids[-1] if selected_file_ids else ""

    return {
        "canvas_data": canvas_data,
        "file_ids": selected_file_ids,
        "start_frame_file_id": start_frame_file_id,
        "end_frame_file_id": end_frame_file_id,
        "storyboard_id": selected_storyboard_id,
        "continuity_ids": continuity_ids,
        "continuity_versions": continuity_versions,
    }


def _build_video_prompt_confirmation_payload(
    compiled: Dict[str, Any],
    selected_image_count: int,
    duration: int,
    aspect_ratio: str,
    resolution: str,
    video_brief: Dict[str, Any] | None = None,
    selected_storyboard_variants: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    brief = compiled.get("brief", {}) if isinstance(compiled, dict) else {}
    storyboard_meta = (
        compiled.get("selected_frame_storyboard_meta", {})
        if isinstance(compiled, dict)
        else {}
    )
    start_frame_meta = storyboard_meta.get("start_frame", {}) if isinstance(storyboard_meta, dict) else {}
    end_frame_meta = storyboard_meta.get("end_frame", {}) if isinstance(storyboard_meta, dict) else {}
    prompt = (
        "请基于当前已选分镜生成视频，保持人物、产品、场景和灯光的连续性，"
        "并按照分镜关系完成开场、推进和收束。\n\n"
        f"目标：{str(brief.get('objective', '') or '输出一条连续的短视频')}\n"
        f"调性：{str(brief.get('tone', '') or 'premium commercial')}\n"
        f"参考分镜数量：{selected_image_count}\n"
        f"时长：{duration} 秒\n"
        f"比例：{aspect_ratio}\n"
        f"分辨率：{resolution}"
    )
    execution_prompt = prompt + "\n" + str(compiled.get("video_prompt", "") or "")
    return {
        "prompt": execution_prompt,
        "brief_id": str((video_brief or {}).get("brief_id", "") or ""),
        "video_brief": video_brief or {},
        "continuity_summary": {
            "start_frame": start_frame_meta,
            "end_frame": end_frame_meta,
        },
        "display_summary": {
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "selected_image_count": selected_image_count,
            "selected_storyboard_variants": selected_storyboard_variants or [],
            "start_frame": {
                "shot_id": str(start_frame_meta.get("shot_id", "") or ""),
                "narrative_role": str(start_frame_meta.get("narrative_role", "") or ""),
                "shot_family_id": str(start_frame_meta.get("shot_family_id", "") or ""),
            },
            "end_frame": {
                "shot_id": str(end_frame_meta.get("shot_id", "") or ""),
                "narrative_role": str(end_frame_meta.get("narrative_role", "") or ""),
                "shot_family_id": str(end_frame_meta.get("shot_family_id", "") or ""),
            },
        },
    }


async def handle_direct_video(data: Dict[str, Any]) -> None:
    messages: List[Dict[str, Any]] = data.get("messages", [])
    session_id: str = data.get("session_id", "")
    canvas_id: str = data.get("canvas_id", "")
    text_model = _normalize_text_model(data)
    prompt: str = str(data.get("prompt", "") or "")
    file_ids = _normalize_file_ids(data)
    selection_mode = _normalize_selection_mode(data)
    start_frame_file_id = _normalize_frame_file_id(data, "start_frame_file_id")
    end_frame_file_id = _normalize_frame_file_id(data, "end_frame_file_id")
    duration: int = int(data.get("duration", 6) or 6)
    aspect_ratio: str = str(data.get("aspect_ratio", "16:9") or "16:9")
    resolution: str = str(data.get("resolution", "1080p") or "1080p")
    skip_prompt_confirmation = _normalize_skip_prompt_confirmation(data)
    model_name = get_apipod_video_model_name()
    print(
        "🎬 direct_video request",
        {
            "session_id": session_id,
            "canvas_id": canvas_id,
            "text_model": (
                f"{text_model.get('provider')}:{text_model.get('model')}"
                if text_model
                else ""
            ),
            "model_name": model_name,
            "file_ids": file_ids,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "selection_mode": selection_mode,
            "start_frame_file_id": start_frame_file_id,
            "end_frame_file_id": end_frame_file_id,
            "prompt_preview": prompt[:120],
        },
    )
    if (
        not str(prompt or "").strip()
        or "这是一条画布里的“选中分镜生成视频”操作请求" in prompt
        or "基于这些参考图生成一个" in prompt
    ):
        print(
            "🎬 direct_video received canvas prompt shell",
            {
                "session_id": session_id,
                "canvas_id": canvas_id,
                "will_compile_from_history": True,
            },
        )

    existing_task = get_stream_task(session_id)
    if existing_task and not existing_task.done():
        print(
            "🎬 direct_video duplicate request ignored",
            {
                "session_id": session_id,
                "canvas_id": canvas_id,
            },
        )
        await send_to_websocket(
            session_id,
            {
                "type": "info",
                "info": "视频生成正在进行中，请等待当前任务完成。",
            },
        )
        return

    existing_sessions = await db_service.list_sessions(canvas_id)
    if not any(session.get("id") == session_id for session in existing_sessions):
        await db_service.create_chat_session(
            session_id,
            text_model.get("model") if text_model else model_name,
            text_model.get("provider") if text_model else "apipodvideo",
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
            selection_mode=selection_mode,
            start_frame_file_id=start_frame_file_id,
            end_frame_file_id=end_frame_file_id,
            duration=duration,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            text_model=text_model,
            skip_prompt_confirmation=skip_prompt_confirmation,
        )
    )
    print(
        "🎬 direct_video task created",
        {
            "session_id": session_id,
            "canvas_id": canvas_id,
            "file_count": len(file_ids),
        },
    )
    add_stream_task(session_id, task)
    try:
        await task
        print(
            "🎬 direct_video task completed",
            {
                "session_id": session_id,
                "canvas_id": canvas_id,
            },
        )
    except asyncio.exceptions.CancelledError:
        print(f"🛑Direct video generation session {session_id} cancelled")
    finally:
        remove_stream_task(session_id)
        await send_to_websocket(session_id, {"type": "done"})


async def preview_direct_video_prompt(data: Dict[str, Any]) -> Dict[str, Any]:
    session_id: str = str(data.get("session_id", "") or "")
    canvas_id: str = str(data.get("canvas_id", "") or "")
    if not canvas_id:
        raise RuntimeError("canvas_id is required")

    text_model = _normalize_text_model(data)
    prompt: str = str(data.get("prompt", "") or "")
    file_ids = _normalize_file_ids(data)
    selection_mode = _normalize_selection_mode(data)
    start_frame_file_id = _normalize_frame_file_id(data, "start_frame_file_id")
    end_frame_file_id = _normalize_frame_file_id(data, "end_frame_file_id")
    duration: int = int(data.get("duration", 6) or 6)
    aspect_ratio: str = str(data.get("aspect_ratio", "16:9") or "16:9")
    resolution: str = str(data.get("resolution", "1080p") or "1080p")

    if not file_ids:
        raise RuntimeError("请至少选择一张分镜图")

    result = await _compile_direct_video_prompt(
        session_id=session_id,
        canvas_id=canvas_id,
        prompt=prompt,
        messages=[],
        file_ids=file_ids,
        selection_mode=selection_mode,
        start_frame_file_id=start_frame_file_id,
        end_frame_file_id=end_frame_file_id,
        duration=duration,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        text_model=text_model,
    )

    compiled = result["compiled"]
    return {
        "prompt": result["compiled_video_prompt"],
        "brief": compiled.get("brief", {}),
        "qa_issues": compiled.get("qa_issues", []),
        "reference_file_ids": result["reference_file_ids"],
        "start_frame_file_id": result["start_frame_file_id"],
        "end_frame_file_id": result["end_frame_file_id"],
        "selection_context": compiled.get("selection_context", {}),
        "selected_frame_storyboard_meta": compiled.get(
            "selected_frame_storyboard_meta", {}
        ),
    }


async def _process_direct_video_generation(
    messages: List[Dict[str, Any]],
    session_id: str,
    canvas_id: str,
    prompt: str,
    file_ids: List[str],
    selection_mode: str,
    start_frame_file_id: str,
    end_frame_file_id: str,
    duration: int,
    aspect_ratio: str,
    resolution: str,
    text_model: Optional[ModelInfo],
    skip_prompt_confirmation: bool,
) -> None:
    ai_response = await create_direct_video_response(
        session_id=session_id,
        canvas_id=canvas_id,
        prompt=prompt,
        messages=messages,
        file_ids=file_ids,
        selection_mode=selection_mode,
        start_frame_file_id=start_frame_file_id,
        end_frame_file_id=end_frame_file_id,
        duration=duration,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        text_model=text_model,
        skip_prompt_confirmation=skip_prompt_confirmation,
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
    messages: List[Dict[str, Any]],
    file_ids: List[str],
    selection_mode: str,
    start_frame_file_id: str,
    end_frame_file_id: str,
    duration: int,
    aspect_ratio: str,
    resolution: str,
    text_model: Optional[ModelInfo],
    skip_prompt_confirmation: bool,
) -> Dict[str, Any]:
    try:
        compile_result = await _compile_direct_video_prompt(
            session_id=session_id,
            canvas_id=canvas_id,
            prompt=prompt,
            messages=messages,
            file_ids=file_ids,
            selection_mode=selection_mode,
            start_frame_file_id=start_frame_file_id,
            end_frame_file_id=end_frame_file_id,
            duration=duration,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            text_model=text_model,
        )
        selection = compile_result["selection"]
        reference_file_ids = compile_result["reference_file_ids"]
        storyboard_id = compile_result["storyboard_id"]
        compiled = compile_result["compiled"]
        compiled_video_prompt = compile_result["compiled_video_prompt"]
        start_frame_file_id = compile_result["start_frame_file_id"]
        end_frame_file_id = compile_result["end_frame_file_id"]
        model_name = get_apipod_video_model_name()
        brief = compiled["brief"]
        print(
            "🎬 direct_video compiled brief",
            {
                "session_id": session_id,
                "objective": brief.get("objective"),
                "tone": brief.get("tone"),
                "platform": brief.get("platform"),
                "product_priority": brief.get("product_priority"),
            },
        )
        print(
            "🎬 direct_video compiled prompt",
            {
                "session_id": session_id,
                "selected_image_count": len(reference_file_ids),
                "selection_mode": selection_mode,
                "start_frame_file_id": start_frame_file_id,
                "end_frame_file_id": end_frame_file_id,
                "reference_file_ids": reference_file_ids,
                "selected_frame_metadata_roles": list(
                    (compiled.get("selected_frame_generation_meta") or {}).keys()
                ),
                "selected_frame_storyboard_roles": list(
                    (compiled.get("selected_frame_storyboard_meta") or {}).keys()
                ),
                "prompt_preview": compiled_video_prompt[:300],
            },
        )
        continuity_asset = await get_current_continuity_asset(canvas_id)
        selected_storyboard_variants: List[Dict[str, Any]] = []
        if storyboard_id:
            for item in collect_primary_storyboard_variants(selection.get("canvas_data", {}), storyboard_id):
                meta = item.get("storyboard_meta", {})
                if not isinstance(meta, dict):
                    continue
                selected_storyboard_variants.append(
                    {
                        "shot_id": str(meta.get("shot_id", "") or ""),
                        "narrative_role": str(meta.get("narrative_role", "") or ""),
                        "shot_family_id": str(meta.get("shot_family_id", "") or ""),
                        "variant_id": str(meta.get("variant_id", "") or ""),
                    }
                )
        video_brief = build_video_brief_asset(
            continuity_asset=continuity_asset,
            compiled=compiled,
            storyboard_id=storyboard_id,
            duration=duration,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
        )
        await upsert_video_brief(canvas_id, video_brief)

        confirmation_payload = _build_video_prompt_confirmation_payload(
            compiled=compiled,
            selected_image_count=len(reference_file_ids),
            duration=duration,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            video_brief=video_brief,
            selected_storyboard_variants=selected_storyboard_variants,
        )

        if not skip_prompt_confirmation:
            confirmation_status = await request_prompt_bundle_confirmation(
                session_id=session_id,
                tool_name="generate_video_from_storyboard",
                payload=confirmation_payload,
            )
            if confirmation_status == "revise":
                return {
                    "role": "assistant",
                    "content": "已返回修改，请调整分镜选择或视频参数后重新提交。",
                }
            if confirmation_status != "confirmed":
                return {
                    "role": "assistant",
                    "content": "已取消视频生成。",
                }

        video_brief["status"] = "confirmed"
        await upsert_video_brief(canvas_id, video_brief)

        input_images = []
        for file_id in reference_file_ids:
            processed_image = await process_input_image(file_id, canvas_id=canvas_id)
            if processed_image:
                input_images.append(processed_image)
        print(
            "🎬 direct_video processed inputs",
            {
                "requested_file_count": len(reference_file_ids),
                "accepted_file_count": len(input_images),
                "max_reference_images": APIPOD_VIDEO_REFERENCE_IMAGES_MAX,
                "reference_file_ids": reference_file_ids,
            },
        )

        normalized_input_images = input_images or None

        result = await generate_video_with_provider(
            prompt=str(confirmation_payload.get("prompt", "") or compiled_video_prompt),
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
            source_file_ids=reference_file_ids,
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
