import os
import traceback
from typing import Optional, Any

from openai import OpenAI

from services.config_service import FILES_DIR, config_service

from .image_base_provider import ImageProviderBase
from ..utils.image_utils import get_image_info_and_save, generate_image_id


class ZenlayerOpenAIImageProvider(ImageProviderBase):
    """Zenlayer OpenAI-compatible image generation provider."""

    async def generate(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_images: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> tuple[str, int, int, str]:
        config = config_service.app_config.get("zenlayer", {})
        api_key = str(config.get("api_key", "")).strip()
        base_url = str(config.get("url", "")).strip()

        if not api_key:
            raise ValueError("Zenlayer API key is not configured")
        if not base_url:
            raise ValueError("Zenlayer API URL is not configured")
        if input_images:
            raise ValueError("Zenlayer gpt-image-2 currently supports text-to-image only")

        client = OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=300,
        )

        try:
            size_map = {
                "1:1": "1024x1024",
                "16:9": "1536x1024",
                "4:3": "1536x1024",
                "3:4": "1024x1536",
                "9:16": "1024x1536",
            }
            size = size_map.get(aspect_ratio, "1024x1024")

            result = client.images.generate(
                model=model,
                prompt=prompt,
                n=1,
                size=size,
                quality="high",
            )

            if not result.data or len(result.data) == 0:
                raise RuntimeError("No image data returned from Zenlayer gpt-image-2")

            image_data = result.data[0]
            if not getattr(image_data, "b64_json", None):
                raise RuntimeError("Zenlayer gpt-image-2 response missing b64_json")

            image_id = generate_image_id()
            mime_type, width, height, extension = await get_image_info_and_save(
                image_data.b64_json,
                os.path.join(FILES_DIR, image_id),
                is_b64=True,
            )

            filename = f"{image_id}.{extension}"
            return mime_type, width, height, filename
        except Exception as exc:
            print("Error generating image with Zenlayer gpt-image-2:", exc)
            traceback.print_exc()
            raise exc
