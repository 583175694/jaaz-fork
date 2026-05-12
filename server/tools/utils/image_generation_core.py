"""
Image generation core module
Contains the main orchestration logic for image generation across different providers
"""

import re
from typing import Optional, Dict, Any
from common import DEFAULT_PORT
from tools.utils.image_utils import process_input_image
from ..image_providers.image_base_provider import ImageProviderBase

# 导入所有提供商以确保自动注册 (不要删除这些导入)
from ..image_providers.jaaz_provider import JaazImageProvider
from ..image_providers.apipod_provider import APIPodImageProvider
from ..image_providers.openai_provider import OpenAIImageProvider
from ..image_providers.replicate_provider import ReplicateImageProvider
from ..image_providers.volces_provider import VolcesProvider
from ..image_providers.wavespeed_provider import WavespeedProvider
from ..image_providers.apipod_gpt_image_provider import APIPodGPTImageProvider

# from ..image_providers.comfyui_provider import ComfyUIProvider
from .image_canvas_utils import (
    save_image_to_canvas,
)
import time

IMAGE_PROVIDERS: dict[str, ImageProviderBase] = {
    "jaaz": JaazImageProvider(),
    "nanobanana": APIPodImageProvider(),
    "openai": OpenAIImageProvider(),
    "replicate": ReplicateImageProvider(),
    "volces": VolcesProvider(),
    "wavespeed": WavespeedProvider(),
    "apipodgptimage": APIPodGPTImageProvider(),
}


def _infer_storyboard_metadata(prompt: str, aspect_ratio: str) -> Dict[str, Any]:
    normalized_prompt = str(prompt or "").strip()
    lower_prompt = normalized_prompt.lower()

    narrative_role = "generic_storyboard_frame"
    if any(signal in lower_prompt for signal in ["opening", "hook", "开场", "首镜", "scene 1", "shot 1"]):
        narrative_role = "establishing"
    elif any(signal in lower_prompt for signal in ["hero packshot", "收尾", "结尾", "resolution", "hero resolution", "scene 4", "shot 4"]):
        narrative_role = "closure"
    elif any(signal in lower_prompt for signal in ["reveal", "product reveal", "卖点", "scene 2", "shot 2"]):
        narrative_role = "progression"
    elif any(signal in lower_prompt for signal in ["benefit", "demonstration", "scene 3", "shot 3"]):
        narrative_role = "reaction"

    shot_id_match = re.search(r"\b(?:scene|shot)\s*([0-9]+)\b", normalized_prompt, flags=re.I)
    shot_id = ""
    if shot_id_match:
        shot_id = f"S{shot_id_match.group(1)}"
    else:
        cn_match = re.search(r"分镜([一二三四五六七八九十0-9]+)", normalized_prompt)
        if cn_match:
            shot_id = f"S{cn_match.group(1)}"

    summary = normalized_prompt[:280]
    return {
        "shot_id": shot_id,
        "narrative_role": narrative_role,
        "summary": summary,
        "aspect_ratio": aspect_ratio,
    }


async def generate_image_with_provider(
    canvas_id: str,
    session_id: str,
    provider: str,
    model: str,
    # image generator args
    prompt: str,
    aspect_ratio: str = "1:1",
    input_images: Optional[list[str]] = None,
    metadata_overrides: Optional[Dict[str, Any]] = None,
    storyboard_metadata_overrides: Optional[Dict[str, Any]] = None,
    preferred_position: Optional[Dict[str, float]] = None,
) -> str:
    """
    通用图像生成函数，支持不同的模型和提供商

    Args:
        prompt: 图像生成提示词
        aspect_ratio: 图像长宽比
        model_name: 内部模型名称 (如 'gpt-image-1', 'imagen-4')
        model: 模型标识符 (如 'openai/gpt-image-1', 'google/imagen-4')
        tool_call_id: 工具调用ID
        config: 上下文运行配置，包含canvas_id，session_id，model_info，由langgraph注入
        input_images: 可选的输入参考图像列表

    Returns:
        str: 生成结果消息
    """

    provider_instance = IMAGE_PROVIDERS.get(provider)
    if not provider_instance:
        raise ValueError(f"Unknown provider: {provider}")

    print(
        "🖼️ generate_image_with_provider start",
        {
            "session_id": session_id,
            "canvas_id": canvas_id,
            "provider": provider,
            "model": model,
            "aspect_ratio": aspect_ratio,
            "has_input_images": bool(input_images),
            "prompt_preview": prompt[:160],
        },
    )

    # Process input images for the provider
    processed_input_images: list[str] | None = None
    if input_images:
        processed_input_images = []
        for image_path in input_images:
            processed_image = await process_input_image(
                image_path,
                canvas_id=canvas_id,
            )
            if processed_image:
                processed_input_images.append(processed_image)

        print(f"Using {len(processed_input_images)} input images for generation")

    # Prepare metadata with all generation parameters
    metadata: Dict[str, Any] = {
        "prompt": prompt,
        "model": model,
        "provider": provider,
        "aspect_ratio": aspect_ratio,
        "input_images": input_images or [],
    }
    if metadata_overrides:
        metadata.update(metadata_overrides)
    storyboard_metadata = _infer_storyboard_metadata(prompt, aspect_ratio)
    if storyboard_metadata_overrides:
        storyboard_metadata.update(storyboard_metadata_overrides)

    # Generate image using the selected provider
    mime_type, width, height, filename = await provider_instance.generate(
        prompt=prompt,
        model=model,
        aspect_ratio=aspect_ratio,
        input_images=processed_input_images,
        metadata=metadata,
    )
    print(
        "🖼️ provider image generated",
        {
            "session_id": session_id,
            "canvas_id": canvas_id,
            "provider": provider,
            "model": model,
            "filename": filename,
            "mime_type": mime_type,
            "width": width,
            "height": height,
        },
    )

    # Save image to canvas
    image_url = await save_image_to_canvas(
        session_id,
        canvas_id,
        filename,
        mime_type,
        width,
        height,
        generation_metadata=metadata,
        storyboard_metadata=storyboard_metadata,
        preferred_position=preferred_position,
    )
    print(
        "🖼️ image persisted to canvas",
        {
            "session_id": session_id,
            "canvas_id": canvas_id,
            "provider": provider,
            "model": model,
            "filename": filename,
            "image_url": image_url,
        },
    )

    return f"image generated successfully ![image_id: {filename}](http://localhost:{DEFAULT_PORT}{image_url})"
