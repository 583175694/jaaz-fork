import re
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore
from pydantic import BaseModel, Field

from services.ad_video_prompt_runtime import compile_ad_video_prompt
from tools.video_generation.video_generation_core import generate_video_with_provider
from tools.utils.image_utils import process_input_image
from tools.video_providers.apipod_provider import (
    APIPOD_VIDEO_REFERENCE_IMAGES_MAX,
    apipod_video_supports_multi_reference_images,
    format_apipod_multi_reference_images_not_supported_error,
    get_apipod_video_model_name,
)


def _resolve_ordered_reference_inputs(
    input_images: list[str] | None,
    selection_mode: str,
    start_frame_file_id: str,
    end_frame_file_id: str,
) -> list[str]:
    normalized_inputs = [str(file_id or "").strip() for file_id in (input_images or []) if str(file_id or "").strip()]
    if selection_mode != "start_end_frames":
        return normalized_inputs[:APIPOD_VIDEO_REFERENCE_IMAGES_MAX]

    ordered_candidates = [
        str(start_frame_file_id or "").strip(),
        str(end_frame_file_id or "").strip(),
    ]
    ordered: list[str] = []
    for candidate in ordered_candidates:
        if candidate and candidate not in ordered:
            ordered.append(candidate)

    if not ordered and normalized_inputs:
        ordered.append(normalized_inputs[0])
    if len(ordered) < 2 and len(normalized_inputs) > 1:
        tail_candidate = normalized_inputs[-1]
        if tail_candidate and tail_candidate not in ordered:
            ordered.append(tail_candidate)

    return ordered[:APIPOD_VIDEO_REFERENCE_IMAGES_MAX]


class GenerateVideoByVeo3ApipodInputSchema(BaseModel):
    prompt: str = Field(
        description="Required. The prompt for video generation. Describe what you want to see in the video."
    )
    resolution: str = Field(
        default="1080p",
        description="Optional. Allowed values: 720p, 1080p, 4k."
    )
    duration: int = Field(
        default=6,
        description="Optional. Allowed values: 4, 6, 8."
    )
    aspect_ratio: str = Field(
        default="16:9",
        description="Optional. Allowed values: 16:9, 9:16."
    )
    input_images: list[str] | None = Field(
        default=None,
        description="Optional. Pass up to two image ids for reference-image video generation.",
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool(
    "generate_video_by_veo3_apipod",
    description="Generate videos using Google Veo 3.1 via APIPod. Supports text-to-video and up to two ordered reference images for start/end frame control.",
    args_schema=GenerateVideoByVeo3ApipodInputSchema,
)
async def generate_video_by_veo3_apipod(
    prompt: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    resolution: str = "1080p",
    duration: int = 6,
    aspect_ratio: str = "16:9",
    input_images: list[str] | None = None,
) -> str:
    processed_input_images = None
    configurable = config.get("configurable", {})
    canvas_id = str(configurable.get("canvas_id", "") or "")
    session_id = str(configurable.get("session_id", "") or "")
    message_history = configurable.get("messages")
    selection_mode = "reference_images"
    start_frame_file_id = ""
    end_frame_file_id = ""

    if isinstance(message_history, list):
        for message in reversed(message_history):
            if message.get("role") != "user":
                continue
            content = message.get("content")
            text_parts: list[str] = []
            if isinstance(content, str):
                text_parts = [content]
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                        text_parts.append(item["text"])
            content_text = "\n".join(part.strip() for part in text_parts if part and part.strip())
            if not content_text:
                continue

            selection_match = re.search(
                r"<selection_mode\b[^>]*>(.*?)</selection_mode>",
                content_text,
                flags=re.S,
            )
            start_match = re.search(
                r"<start_frame\b[^>]*\bfile_id=\"([^\"]+)\"[^>]*/?>",
                content_text,
            )
            end_match = re.search(
                r"<end_frame\b[^>]*\bfile_id=\"([^\"]+)\"[^>]*/?>",
                content_text,
            )
            if selection_match:
                selection_mode = str(selection_match.group(1) or "").strip() or selection_mode
            if start_match:
                start_frame_file_id = str(start_match.group(1) or "").strip()
            if end_match:
                end_frame_file_id = str(end_match.group(1) or "").strip()
            if selection_match or start_match or end_match:
                break

    model_name = get_apipod_video_model_name()
    ordered_reference_inputs = _resolve_ordered_reference_inputs(
        input_images=input_images,
        selection_mode=selection_mode,
        start_frame_file_id=start_frame_file_id,
        end_frame_file_id=end_frame_file_id,
    )
    if ordered_reference_inputs and len(ordered_reference_inputs) > 1 and not apipod_video_supports_multi_reference_images(model_name):
        raise RuntimeError(format_apipod_multi_reference_images_not_supported_error(model_name))

    compiled = await compile_ad_video_prompt(
        session_id=session_id,
        prompt=prompt,
        messages=message_history if isinstance(message_history, list) else None,
        duration=duration,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        selected_image_count=len(ordered_reference_inputs),
        platform_hint="chat storyboard to video",
        canvas_id=canvas_id,
        selection_mode=selection_mode,
        start_frame_file_id=start_frame_file_id,
        end_frame_file_id=end_frame_file_id,
    )
    compiled_prompt = str(compiled["video_prompt"] or prompt)
    print(
        "🎬 tool video compiled prompt",
        {
            "session_id": session_id,
            "selected_image_count": len(ordered_reference_inputs),
            "selection_mode": selection_mode,
            "start_frame_file_id": start_frame_file_id,
            "end_frame_file_id": end_frame_file_id,
            "ordered_reference_inputs": ordered_reference_inputs,
            "prompt_preview": compiled_prompt[:300],
        },
    )

    if ordered_reference_inputs:
        normalized_images = []
        for file_id in ordered_reference_inputs:
            processed_image = await process_input_image(file_id, canvas_id=canvas_id)
            if processed_image:
                normalized_images.append(processed_image)
        if normalized_images:
            processed_input_images = normalized_images

    return await generate_video_with_provider(
        prompt=compiled_prompt,
        resolution=resolution,
        duration=duration,
        aspect_ratio=aspect_ratio,
        model=model_name,
        tool_call_id=tool_call_id,
        config=config,
        input_images=processed_input_images,
        source_file_ids=ordered_reference_inputs,
        camera_fixed=True,
        provider_hint="apipodvideo",
    )


__all__ = ["generate_video_by_veo3_apipod"]
