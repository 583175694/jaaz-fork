from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore
from pydantic import BaseModel, Field

from tools.video_generation.video_generation_core import generate_video_with_provider
from tools.utils.image_utils import process_input_image
from tools.video_providers.apipod_provider import (
    APIPOD_VIDEO_REFERENCE_IMAGES_MAX,
    apipod_video_supports_multi_reference_images,
    format_apipod_multi_reference_images_not_supported_error,
    get_apipod_video_model_name,
)


class GenerateVideoByVeo3ZenlayerInputSchema(BaseModel):
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
    "generate_video_by_veo3_zenlayer",
    description="Generate videos using Google Veo 3.1 Fast via APIPod. Supports text-to-video and up to two reference images.",
    args_schema=GenerateVideoByVeo3ZenlayerInputSchema,
)
async def generate_video_by_veo3_zenlayer(
    prompt: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    resolution: str = "1080p",
    duration: int = 6,
    aspect_ratio: str = "16:9",
    input_images: list[str] | None = None,
) -> str:
    processed_input_images = None
    canvas_id = str(config.get("configurable", {}).get("canvas_id", "") or "")
    model_name = get_apipod_video_model_name()
    if input_images and len(input_images) > 1 and not apipod_video_supports_multi_reference_images(model_name):
        raise RuntimeError(format_apipod_multi_reference_images_not_supported_error(model_name))

    if input_images and len(input_images) > 0:
        normalized_images = []
        for file_id in input_images[:APIPOD_VIDEO_REFERENCE_IMAGES_MAX]:
            processed_image = await process_input_image(file_id, canvas_id=canvas_id)
            if processed_image:
                normalized_images.append(processed_image)
        if normalized_images:
            processed_input_images = normalized_images

    return await generate_video_with_provider(
        prompt=prompt,
        resolution=resolution,
        duration=duration,
        aspect_ratio=aspect_ratio,
        model=model_name,
        tool_call_id=tool_call_id,
        config=config,
        input_images=processed_input_images,
        source_file_ids=input_images,
        camera_fixed=True,
        provider_hint="apipodvideo",
    )


__all__ = ["generate_video_by_veo3_zenlayer"]
