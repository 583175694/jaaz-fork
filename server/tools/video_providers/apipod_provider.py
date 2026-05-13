import base64
import asyncio
import json
import mimetypes
import os
import time
import traceback
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import aiohttp
import toml

from services.config_service import FILES_DIR, config_service
from services.storage_service import storage_service
from utils.http_client import HttpClient

from .video_base_provider import VideoProviderBase


APIPOD_VIDEO_DEFAULT_MODEL_NAME = "veo3-1-quality"
APIPOD_VIDEO_REFERENCE_IMAGES_MAX = 2


def get_apipod_video_model_name() -> str:
    config = config_service.app_config.get("apipodvideo", {})
    return str(
        config.get("model_name", APIPOD_VIDEO_DEFAULT_MODEL_NAME)
    ).strip() or APIPOD_VIDEO_DEFAULT_MODEL_NAME


def apipod_video_supports_multi_reference_images(model_name: str) -> bool:
    normalized = str(model_name or "").strip().lower()
    return normalized in {"veo3-1-fast", "veo3-1-quality"}


def format_apipod_multi_reference_images_not_supported_error(model_name: str) -> str:
    normalized = str(model_name or "").strip() or APIPOD_VIDEO_DEFAULT_MODEL_NAME
    return (
        f"当前配置的视频模型 `{normalized}` 不支持多张参考图。"
        "请切换到 `veo3-1-quality` 或 `veo3-1-fast`，以使用最多 2 张参考图生成 1 个视频。"
    )


def _decode_data_url(data_url: str) -> tuple[bytes, str]:
    if not data_url.startswith("data:image/"):
        raise ValueError("APIPod video input image must be a data URL")
    header, encoded = data_url.split(",", 1)
    mime_type = header.split(";")[0].split(":", 1)[1]
    return base64.b64decode(encoded), mime_type


async def _upload_data_url_to_public_url(data_url: str, filename: str) -> str:
    image_bytes, mime_type = _decode_data_url(data_url)
    cos_url = _upload_reference_bytes_to_cos(image_bytes, filename, mime_type)
    if cos_url:
        return cos_url

    return await _upload_reference_bytes_to_temporary_public_url(
        image_bytes,
        filename,
        mime_type,
    )


def _upload_reference_bytes_to_cos(
    image_bytes: bytes,
    filename: str,
    mime_type: str,
) -> str | None:
    try:
        return storage_service.upload_bytes(
            image_bytes,
            filename,
            content_type=mime_type,
        )
    except Exception as exc:
        print(f"Warning: failed to upload APIPod reference image to COS: {exc}")
        return None


def _upload_reference_file_to_cos(
    local_path: str,
    filename: str,
    mime_type: str,
) -> str | None:
    try:
        return storage_service.upload_local_file(
            local_path,
            filename,
            content_type=mime_type,
        )
    except Exception as exc:
        print(f"Warning: failed to upload APIPod reference file to COS: {exc}")
        return None


async def _upload_reference_bytes_to_temporary_public_url(
    image_bytes: bytes,
    filename: str,
    mime_type: str,
) -> str:
    async with HttpClient.create_aiohttp() as session:
        catbox_form = aiohttp.FormData()
        catbox_form.add_field("reqtype", "fileupload")
        catbox_form.add_field(
            "fileToUpload",
            image_bytes,
            filename=filename,
            content_type=mime_type,
        )
        async with session.post(
            "https://catbox.moe/user/api.php",
            data=catbox_form,
        ) as response:
            text = await response.text()

        if response.status < 400:
            normalized = str(text or "").strip()
            if normalized.startswith("https://files.catbox.moe/"):
                return normalized

        tmpfiles_form = aiohttp.FormData()
        tmpfiles_form.add_field(
            "file",
            image_bytes,
            filename=filename,
            content_type=mime_type,
        )
        async with session.post(
            "https://tmpfiles.org/api/v1/upload",
            data=tmpfiles_form,
        ) as response:
            text = await response.text()

    if response.status >= 400:
        raise RuntimeError(
            "APIPod video source upload failed "
            f"status={response.status} body={text[:500]}"
        )

    result = json.loads(text)
    if result.get("status") != "success":
        raise RuntimeError(f"APIPod video source upload failed body={text[:500]}")

    page_url = result.get("data", {}).get("url", "")
    if not page_url:
        raise RuntimeError(f"APIPod video source upload missing url body={text[:500]}")

    return page_url.replace("http://tmpfiles.org/", "https://tmpfiles.org/dl/")


async def _upload_reference_file_to_temporary_public_url(
    local_path: str,
    filename: str,
    mime_type: str,
) -> str:
    with open(local_path, "rb") as file_obj:
        file_bytes = file_obj.read()

    return await _upload_reference_bytes_to_temporary_public_url(
        file_bytes,
        filename,
        mime_type,
    )


async def _prepare_public_reference_images(
    input_images: Optional[list[str]],
) -> list[str]:
    if not input_images:
        return []

    normalized: list[str] = []
    for index, image_ref in enumerate(input_images[:APIPOD_VIDEO_REFERENCE_IMAGES_MAX], start=1):
        image_value = str(image_ref or "").strip()
        if not image_value:
            continue

        if image_value.startswith("data:image/"):
            normalized.append(
                await _upload_data_url_to_public_url(
                    image_value,
                    f"apipod_video_ref_{index}.png",
                )
            )
            continue

        if image_value.startswith(("http://", "https://")):
            normalized.append(image_value)
            continue

        full_path = os.path.join(FILES_DIR, image_value)
        if os.path.exists(full_path):
            guessed_mime_type = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
            filename = os.path.basename(full_path)
            cos_url = _upload_reference_file_to_cos(
                full_path,
                filename,
                guessed_mime_type,
            )
            if cos_url:
                normalized.append(cos_url)
                continue

            normalized.append(
                await _upload_reference_file_to_temporary_public_url(
                    full_path,
                    filename,
                    guessed_mime_type,
                )
            )
            continue

        normalized.append(image_value)

    return normalized


def _extract_task_id(result: dict[str, Any]) -> str:
    data = result.get("data")
    candidates = [
        result.get("task_id"),
        result.get("id"),
        data.get("task_id") if isinstance(data, dict) else None,
        data.get("id") if isinstance(data, dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _extract_video_url(result: dict[str, Any]) -> str:
    data = result.get("data")
    if isinstance(data, dict):
        result_value = data.get("result")
        if isinstance(result_value, list):
            for item in result_value:
                if isinstance(item, str) and item.strip():
                    return item.strip()
                if isinstance(item, dict):
                    for key in ("url", "video_url", "download_url"):
                        value = item.get(key)
                        if isinstance(value, str) and value.strip():
                            return value.strip()
        if isinstance(result_value, str) and result_value.strip():
            return result_value.strip()

    for key in ("url", "video_url", "download_url", "result"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


class APIPodVideoProvider(VideoProviderBase, provider_name="apipodvideo"):
    """APIPod Google Veo 3.1 provider."""

    def __init__(self):
        config = config_service.app_config.get("apipodvideo", {})
        if not config:
            config_file = getattr(config_service, "config_file", "")
            if config_file and os.path.exists(config_file):
                loaded = toml.load(config_file)
                config = loaded.get("apipodvideo", {})

        self.api_key = str(config.get("api_key", "")).strip()
        self.base_url = str(config.get("url", "")).strip()
        self.model_name = get_apipod_video_model_name()
        self.max_wait = float(config.get("max_wait_seconds", 900))

        if not self.api_key:
            raise ValueError("APIPod Video API key is not configured")
        if not self.base_url:
            raise ValueError("APIPod Video API URL is not configured")

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _build_payload(
        self,
        model_name: str,
        prompt: str,
        aspect_ratio: str,
        input_images: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
        }

        if input_images:
            if len(input_images) > 1 and not apipod_video_supports_multi_reference_images(
                model_name
            ):
                raise RuntimeError(
                    format_apipod_multi_reference_images_not_supported_error(model_name)
                )

            payload["image_urls"] = await _prepare_public_reference_images(input_images)
            print(
                "🎥 APIPod prepared reference images",
                {
                    "model_name": model_name,
                    "reference_count": len(payload["image_urls"]),
                },
            )

        return payload

    async def _poll_task(self, task_id: str) -> dict[str, Any]:
        parsed = urlparse(self.base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        status_url = f"{origin}/v1/videos/status/{task_id}"
        deadline = time.monotonic() + self.max_wait
        last_status = ""
        last_progress: int | None = None

        async with HttpClient.create_aiohttp() as session:
            while time.monotonic() < deadline:
                async with session.get(status_url, headers=self._build_headers()) as response:
                    text = await response.text()

                if response.status >= 400:
                    raise RuntimeError(
                        "APIPod video status query failed "
                        f"url={status_url} status={response.status} body={text[:500]}"
                    )

                try:
                    result = json.loads(text)
                except Exception as exc:
                    raise RuntimeError(
                        f"APIPod video status returned invalid JSON body={text[:500]}"
                    ) from exc

                task_data = result.get("data") or {}
                status = str(task_data.get("status", "")).lower()
                progress = task_data.get("progress")
                if status != last_status or progress != last_progress:
                    print(
                        "🎥 APIPod video poll",
                        {
                            "task_id": task_id,
                            "status": status,
                            "progress": progress,
                        },
                    )
                    last_status = status
                    last_progress = progress
                if status in {"completed", "succeeded", "success"}:
                    return result
                if status in {"failed", "error", "cancelled"}:
                    error_message = (
                        task_data.get("error")
                        or task_data.get("error_message")
                        or task_data.get("message")
                        or "Unknown error"
                    )
                    raise RuntimeError(f"APIPod video task failed: {error_message}")

                await asyncio.sleep(5)

        raise RuntimeError(
            f"APIPod video task timed out ({self.max_wait}s), task_id={task_id}"
        )

    async def generate(
        self,
        prompt: str,
        model: str,
        resolution: str = "1080p",
        duration: int = 6,
        aspect_ratio: str = "16:9",
        input_images: Optional[list[str]] = None,
        camera_fixed: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            model_name = str(model or self.model_name).strip() or self.model_name
            payload = await self._build_payload(
                model_name=model_name,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                input_images=input_images,
            )
            print(
                "🎥 APIPod video create request",
                {
                    "model_name": model_name,
                    "aspect_ratio": aspect_ratio,
                    "resolution": resolution,
                    "duration": duration,
                    "reference_count": len(payload.get("image_urls", [])),
                    "prompt_preview": prompt[:160],
                },
            )

            async with HttpClient.create_aiohttp() as session:
                async with session.post(
                    self.base_url,
                    headers=self._build_headers(),
                    json=payload,
                ) as response:
                    text = await response.text()

                if response.status >= 400:
                    raise RuntimeError(
                        "APIPod video request failed "
                        f"status={response.status} body={text[:500]}"
                    )

                try:
                    result = json.loads(text)
                except Exception as exc:
                    raise RuntimeError(
                        f"APIPod video returned invalid JSON body={text[:500]}"
                    ) from exc

            video_url = _extract_video_url(result)
            if not video_url:
                task_id = _extract_task_id(result)
                if not task_id:
                    raise RuntimeError(
                        "APIPod video response missing video URL and task id"
                    )
                print(
                    "🎥 APIPod video task created",
                    {"task_id": task_id, "initial_status": result.get("data", {}).get("status")},
                )
                result = await self._poll_task(task_id)
                video_url = _extract_video_url(result)

            if not video_url:
                raise RuntimeError("APIPod video completed without video URL")
            print("🎥 APIPod video completed", {"video_url": video_url})

            return {"video_url": video_url}
        except Exception as exc:
            print(f"Error generating video with APIPod: {exc}")
            traceback.print_exc()
            raise exc
