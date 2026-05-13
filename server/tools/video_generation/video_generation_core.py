"""
Video generation core module
Contains the main orchestration logic for video generation across different providers
"""

import traceback
from typing import List, cast, Optional, Any
from models.config_model import ModelInfo
from ..video_providers.video_base_provider import get_default_provider, VideoProviderBase
from ..video_providers.apipod_provider import APIPodVideoProvider  # type: ignore
from .video_canvas_utils import (
    send_video_start_notification,
    send_video_error_notification,
    process_video_result,
)


def _get_video_provider_candidates(
    ctx: dict[str, Any],
    model_name: str,
) -> List[ModelInfo]:
    """Return provider candidates for the current video model only.

    The chat context passes all selected tools together. If we fall back to that
    list without filtering, image tools can be mistaken as
    video providers and crash video generation with `Unknown provider`.
    """
    model_info = ctx.get("model_info", {})
    if isinstance(model_info, dict):
        candidates = model_info.get(model_name, [])
        if isinstance(candidates, list) and candidates:
            return cast(List[ModelInfo], candidates)

    tool_list = ctx.get("tool_list", [])
    if not isinstance(tool_list, list):
        return []

    matched_tools = [
        tool
        for tool in tool_list
        if tool.get("type") == "video"
        and (
            tool.get("id") == model_name
            or tool.get("id") == f"generate_video_by_{model_name}"
            or model_name in str(tool.get("id", ""))
        )
    ]
    if matched_tools:
        return cast(List[ModelInfo], matched_tools)

    # Fallback to any selected video tool, but never to image tools.
    video_tools = [tool for tool in tool_list if tool.get("type") == "video"]
    return cast(List[ModelInfo], video_tools)


async def generate_video_with_provider(
    prompt: str,
    resolution: str,
    duration: int,
    aspect_ratio: str,
    model: str,
    tool_call_id: str,
    config: Any,
    input_images: Optional[list[str]] = None,
    source_file_ids: Optional[list[str]] = None,
    camera_fixed: bool = True,
    provider_hint: Optional[str] = None,
    **kwargs: Any
) -> str:
    """
    Universal video generation function supporting different models and providers

    Args:
        prompt: Video generation prompt
        resolution: Video resolution (480p, 1080p)
        duration: Video duration in seconds (5, 10)
        aspect_ratio: Video aspect ratio (1:1, 16:9, 4:3, 21:9)
        model: Model identifier (e.g., 'doubao-seedance-1-0-pro')
        tool_call_id: Tool call ID
        config: Context runtime configuration containing canvas_id, session_id, model_info, injected by langgraph
        input_images: Optional input reference images list
        camera_fixed: Whether to keep camera fixed

    Returns:
        str: Generation result message
    """
    model_name = model.split(
        # Some model names contain "/", like "openai/gpt-image-1", need to handle
        '/')[-1]
    print(f'🛠️ Video Generation {model_name} tool_call_id', tool_call_id)
    ctx = config.get('configurable', {})
    canvas_id = ctx.get('canvas_id', '')
    session_id = ctx.get('session_id', '')
    print(f'🛠️ canvas_id {canvas_id} session_id {session_id}')

    # Inject the tool call id into the context
    ctx['tool_call_id'] = tool_call_id

    try:
        # Determine provider selection
        model_info_list = _get_video_provider_candidates(ctx, model_name)

        if provider_hint:
            provider_name = provider_hint
        else:
            # Default provider selection is already restricted to the built-in
            # production provider set.
            provider_name = get_default_provider(model_info_list)

        print(f"🎥 Using provider: {provider_name} for {model_name}")

        # Create provider instance
        provider_instance = VideoProviderBase.create_provider(provider_name)

        # Send start notification
        await send_video_start_notification(
            session_id,
            f"Starting video generation using {model_name} via {provider_name}..."
        )

        # Process input images for the provider
        processed_input_images = None
        if input_images:
            # For some providers, we might need to process input images differently
            # For now, just pass them as is
            processed_input_images = input_images

        # Generate video using the selected provider
        generation_result = await provider_instance.generate(
            prompt=prompt,
            model=model,
            resolution=resolution,
            duration=duration,
            aspect_ratio=aspect_ratio,
            input_images=processed_input_images,
            camera_fixed=camera_fixed,
            **kwargs
        )

        # Process video result (save, update canvas, notify)
        download_headers = None
        video_url = generation_result
        if isinstance(generation_result, dict):
            video_url = generation_result.get("video_url", "")
            download_headers = generation_result.get("download_headers")

        return await process_video_result(
            video_url=video_url,
            session_id=session_id,
            canvas_id=canvas_id,
            provider_name=f"{model_name} ({provider_name})",
            download_headers=download_headers,
            source_file_ids=source_file_ids,
        )

    except Exception as e:
        error_message = str(e)
        print(f"🎥 Error generating video with {model_name}: {error_message}")
        traceback.print_exc()

        # Send error notification
        await send_video_error_notification(session_id, error_message)

        # Re-raise the exception for proper error handling
        raise Exception(
            f"{model_name} video generation failed: {error_message}")
