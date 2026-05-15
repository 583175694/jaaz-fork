import asyncio
import base64
import json
import mimetypes
import os
import time
import traceback
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp
import toml

from services.config_service import FILES_DIR, config_service
from services.storage_service import storage_service
from utils.http_client import HttpClient

from .image_base_provider import ImageProviderBase
from ..utils.image_utils import generate_image_id, get_image_info_and_save

APIPOD_IMAGE_DEFAULT_MODEL = "nano-banana-pro"
APIPOD_IMAGE_SUPPORTED_MODELS = {"gpt-image-2", "nano-banana-pro"}
APIPOD_IMAGE_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _decode_data_url(data_url: str) -> tuple[bytes, str]:
    if not data_url.startswith("data:image/"):
        raise ValueError("APIPod image input must be a data URL")
    header, encoded = data_url.split(",", 1)
    mime_type = header.split(";")[0].split(":", 1)[1]
    return base64.b64decode(encoded), mime_type


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
        print(f"Warning: failed to upload APIPod image reference to COS: {exc}")
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
        print(f"Warning: failed to upload APIPod image reference file to COS: {exc}")
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
            "APIPod image source upload failed "
            f"status={response.status} body={text[:500]}"
        )

    result = json.loads(text)
    if result.get("status") != "success":
        raise RuntimeError(f"APIPod image source upload failed body={text[:500]}")

    page_url = result.get("data", {}).get("url", "")
    if not page_url:
        raise RuntimeError(f"APIPod image source upload missing url body={text[:500]}")

    return page_url.replace("http://tmpfiles.org/", "https://tmpfiles.org/dl/")


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
    for index, image_ref in enumerate(input_images, start=1):
        image_value = str(image_ref or "").strip()
        if not image_value:
            continue

        if image_value.startswith("data:image/"):
            normalized.append(
                await _upload_data_url_to_public_url(
                    image_value,
                    f"apipod_image_ref_{index}.png",
                )
            )
            continue

        if image_value.startswith(("http://", "https://")):
            normalized.append(image_value)
            continue

        full_path = os.path.join(FILES_DIR, image_value)
        if os.path.exists(full_path):
            guessed_mime_type = (
                mimetypes.guess_type(full_path)[0] or "application/octet-stream"
            )
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

    async def _submit_payload_with_retries(
        self,
        session: aiohttp.ClientSession,
        api_url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        attempt_label: str,
    ) -> tuple[int, str]:
        retry_delays = [0.0, 2.0, 5.0]
        last_error: RuntimeError | None = None

        for retry_index, delay_seconds in enumerate(retry_delays, start=1):
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

            async with session.post(
                api_url,
                headers=headers,
                json=payload,
            ) as response:
                text = await response.text()

            if response.status not in APIPOD_IMAGE_RETRYABLE_STATUS_CODES:
                return response.status, text

            last_error = RuntimeError(
                "APIPod image request failed "
                f"status={response.status} quality={payload.get('quality', 'unset')} "
                f"attempt={attempt_label} retry={retry_index}/{len(retry_delays)} "
                f"body={text[:500]}"
            )
            print(
                "Retrying transient APIPod image request failure",
                {
                    "status": response.status,
                    "model": payload.get("model"),
                    "quality": payload.get("quality", "unset"),
                    "attempt": attempt_label,
                    "retry": retry_index,
                },
            )

        raise last_error or RuntimeError("APIPod image request failed without response body")

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
        normalized_model = str(model or "").strip().lower()
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
        }
        if normalized_model == "nano-banana-pro":
            payload["quality"] = "2K"
        elif normalized_model in {"gpt-image-2", "gpt-image-2-edit"}:
            payload["quality"] = "1K"
        if input_images:
            payload["image_urls"] = input_images
        return payload

    def _build_retry_payloads(
        self,
        payload: dict[str, Any],
        model: str,
    ) -> list[dict[str, Any]]:
        variants: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_variant(candidate: dict[str, Any]) -> None:
            marker = json.dumps(candidate, sort_keys=True, ensure_ascii=True)
            if marker in seen:
                return
            seen.add(marker)
            variants.append(candidate)

        add_variant(dict(payload))

        normalized_model = str(model or "").strip().lower()
        if normalized_model == "nano-banana-pro":
            for quality in ("2K", "1K", None):
                candidate = dict(payload)
                if quality is None:
                    candidate.pop("quality", None)
                else:
                    candidate["quality"] = quality
                add_variant(candidate)

        return variants

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

                if response.status in APIPOD_IMAGE_RETRYABLE_STATUS_CODES:
                    await asyncio.sleep(3)
                    continue

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
        prepared_input_images = await _prepare_public_reference_images(input_images)

        payload = self._build_payload(
            prompt=prompt,
            model=model_name,
            aspect_ratio=aspect_ratio,
            input_images=prepared_input_images,
        )

        try:
            result: dict[str, Any] | None = None
            last_error: RuntimeError | None = None
            payload_variants = self._build_retry_payloads(payload, model_name)
            headers = self._build_headers(api_key)

            async with HttpClient.create_aiohttp() as session:
                for attempt_index, candidate_payload in enumerate(payload_variants, start=1):
                    response_status, text = await self._submit_payload_with_retries(
                        session=session,
                        api_url=api_url,
                        headers=headers,
                        payload=candidate_payload,
                        attempt_label=f"{attempt_index}/{len(payload_variants)}",
                    )

                    if response_status >= 400:
                        last_error = RuntimeError(
                            "APIPod image request failed "
                            f"status={response_status} quality={candidate_payload.get('quality', 'unset')} "
                            f"attempt={attempt_index}/{len(payload_variants)} body={text[:500]}"
                        )
                        if response_status == 400 and attempt_index < len(payload_variants):
                            print(
                                "Retrying APIPod image request with compatibility payload",
                                {
                                    "model": model_name,
                                    "attempt": attempt_index,
                                    "quality": candidate_payload.get("quality", "unset"),
                                },
                            )
                            continue
                        raise last_error

                    result = json.loads(text)
                    break

            if result is None:
                raise last_error or RuntimeError("APIPod image request failed without response body")

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
