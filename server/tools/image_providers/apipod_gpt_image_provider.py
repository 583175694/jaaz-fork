import asyncio
import json
import os
import time
import traceback
from typing import Any, Optional
from urllib.parse import urlparse

import toml

from services.config_service import FILES_DIR, config_service
from utils.http_client import HttpClient

from .image_base_provider import ImageProviderBase
from ..utils.image_utils import generate_image_id, get_image_info_and_save

APIPOD_IMAGE_DEFAULT_MODEL = "nano-banana-pro"
APIPOD_IMAGE_SUPPORTED_MODELS = {"gpt-image-2", "nano-banana-pro"}


def normalize_apipod_image_model_name(model_name: str) -> str:
    normalized = str(model_name or "").strip().lower()
    if normalized in APIPOD_IMAGE_SUPPORTED_MODELS:
        return normalized
    return APIPOD_IMAGE_DEFAULT_MODEL


def get_apipod_image_model_name() -> str:
    config = config_service.app_config.get("apipodgptimage", {})
    configured = str(config.get("model_name", APIPOD_IMAGE_DEFAULT_MODEL) or APIPOD_IMAGE_DEFAULT_MODEL)
    return normalize_apipod_image_model_name(configured)


class APIPodGPTImageProvider(ImageProviderBase):
    """APIPod image generation provider."""

    def _get_config(self) -> dict[str, Any]:
        config = config_service.app_config.get("apipodgptimage", {})
        if not config:
            config_file = getattr(config_service, "config_file", "")
            if config_file and os.path.exists(config_file):
                loaded = toml.load(config_file)
                config = loaded.get("apipodgptimage", {})

        api_key = str(config.get("api_key", "")).strip()
        api_url = str(config.get("url", "")).strip()
        if not api_key:
            raise ValueError("APIPod image API key is not configured")
        if not api_url:
            raise ValueError("APIPod image API URL is not configured")
        return config

    def _build_headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str,
        input_images: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
        }
        if str(model or "").strip().lower() in {"gpt-image-2", "gpt-image-2-edit"}:
            payload["quality"] = "1K"
        if input_images:
            payload["image_urls"] = input_images
        return payload

    def _extract_task_id(self, result: dict[str, Any]) -> str:
        data = result.get("data")
        candidates = [
            result.get("id"),
            result.get("task_id"),
            data.get("id") if isinstance(data, dict) else None,
            data.get("task_id") if isinstance(data, dict) else None,
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""

    def _extract_image_url(self, result: dict[str, Any]) -> str:
        data = result.get("data")
        if isinstance(data, dict):
            result_value = data.get("result")
            if isinstance(result_value, list):
                for item in result_value:
                    if isinstance(item, str) and item:
                        return item

        for key in ("url", "image_url", "result"):
            value = result.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item:
                        return item
        return ""

    async def _poll_task(
        self,
        task_id: str,
        api_key: str,
        api_url: str,
        max_wait: float = 600.0,
    ) -> dict[str, Any]:
        parsed = urlparse(api_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        status_url = f"{origin}/v1/images/status/{task_id}"
        deadline = time.monotonic() + max_wait
        headers = {"Authorization": f"Bearer {api_key}"}

        async with HttpClient.create_aiohttp() as session:
            while time.monotonic() < deadline:
                async with session.get(status_url, headers=headers) as response:
                    text = await response.text()

                if response.status >= 400:
                    raise RuntimeError(
                        "APIPod image status query failed "
                        f"url={status_url} status={response.status} body={text[:500]}"
                    )

                result = json.loads(text)
                task_data = result.get("data") or {}
                status = str(task_data.get("status", "")).lower()
                if status in {"completed", "succeeded", "success"}:
                    return result
                if status in {"failed", "error", "cancelled"}:
                    error_message = (
                        task_data.get("error")
                        or task_data.get("error_message")
                        or task_data.get("message")
                        or "Unknown error"
                    )
                    raise RuntimeError(f"APIPod image task failed: {error_message}")

                await asyncio.sleep(3)

        raise RuntimeError(f"APIPod image task timed out ({max_wait}s), task_id={task_id}")

    async def generate(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_images: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> tuple[str, int, int, str]:
        config = self._get_config()
        api_key = str(config.get("api_key", ""))
        api_url = str(config.get("url", "")).strip()
        requested_model = str(model or "").strip()
        model_name = (
            normalize_apipod_image_model_name(requested_model)
            if requested_model
            else get_apipod_image_model_name()
        )
        max_wait = float(config.get("max_wait_seconds", 600))

        payload = self._build_payload(
            prompt=prompt,
            model=model_name,
            aspect_ratio=aspect_ratio,
            input_images=input_images,
        )

        try:
            async with HttpClient.create_aiohttp() as session:
                async with session.post(
                    api_url,
                    headers=self._build_headers(api_key),
                    json=payload,
                ) as response:
                    text = await response.text()

                if response.status >= 400:
                    raise RuntimeError(
                        "APIPod image request failed "
                        f"status={response.status} body={text[:500]}"
                    )

                result = json.loads(text)

            image_url = self._extract_image_url(result)
            if not image_url:
                task_id = self._extract_task_id(result)
                if not task_id:
                    raise RuntimeError(
                        "APIPod image response missing image URL and task id"
                    )
                result = await self._poll_task(task_id, api_key, api_url, max_wait=max_wait)
                image_url = self._extract_image_url(result)

            if not image_url:
                raise RuntimeError("APIPod image completed without image URL")

            image_id = generate_image_id()
            mime_type, width, height, extension = await get_image_info_and_save(
                image_url,
                os.path.join(FILES_DIR, f"{image_id}"),
                is_b64=False,
                metadata=metadata,
            )

            filename = f"{image_id}.{extension}"
            return mime_type, width, height, filename
        except Exception as exc:
            print("Error generating image with APIPod image provider:", exc)
            traceback.print_exc()
            raise exc
