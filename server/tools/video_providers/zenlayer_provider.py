import asyncio
import json
import traceback
from typing import Any, Dict, Optional
from urllib.parse import quote, urlparse

from services.config_service import config_service
from utils.http_client import HttpClient

from .video_base_provider import VideoProviderBase


ZENLAYER_DEFAULT_MODEL_NAME = "veo-3.1-fast-generate-preview"
ZENLAYER_REFERENCE_IMAGES_MAX = 3
ZENLAYER_VEO31_MODEL_CANDIDATES = (
    "veo-3.1-fast-generate-preview",
    "veo-3.1-generate-preview",
)


def _build_zenlayer_gateway_origin(base_url: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid Zenlayer base URL: {base_url!r}")
    return f"{parsed.scheme}://{parsed.netloc}"


def _build_zenlayer_video_create_url(base_url: str, model: str) -> str:
    origin = _build_zenlayer_gateway_origin(base_url)
    return (
        f"{origin}/v1/v1beta/models/"
        f"{quote(model, safe='-._~')}:predictLongRunning"
    )


def _build_zenlayer_operation_urls(base_url: str, operation_name: str) -> list[str]:
    origin = _build_zenlayer_gateway_origin(base_url)
    normalized = str(operation_name or "").strip().lstrip("/")
    if normalized.startswith("v1/v1beta/"):
        normalized = normalized[len("v1/v1beta/") :]
    elif normalized.startswith("v1beta/"):
        normalized = normalized[len("v1beta/") :]
    return [
        f"{origin}/v1/v1beta/{normalized}",
        f"{origin}/v1beta/{normalized}",
    ]


def _extract_zenlayer_download_url(result: dict[str, Any]) -> Optional[str]:
    response = result.get("response")
    if not isinstance(response, dict):
        return None
    generate_video_response = response.get("generateVideoResponse")
    if not isinstance(generate_video_response, dict):
        return None
    samples = generate_video_response.get("generatedSamples")
    if not isinstance(samples, list):
        return None
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        video = sample.get("video")
        if isinstance(video, dict):
            uri = video.get("uri")
            if isinstance(uri, str) and uri.strip():
                return uri.strip()
    return None


def get_zenlayer_model_name() -> str:
    config = config_service.app_config.get("zenlayer", {})
    return str(config.get("model_name", ZENLAYER_DEFAULT_MODEL_NAME)).strip()


def _is_veo31_model(model_name: str) -> bool:
    return str(model_name or "").strip().startswith("veo-3.1")


def zenlayer_supports_multi_reference_images(model_name: str) -> bool:
    return _is_veo31_model(model_name)


def format_multi_reference_images_not_supported_error(model_name: str) -> str:
    normalized = str(model_name or "").strip() or ZENLAYER_DEFAULT_MODEL_NAME
    return (
        f"当前配置的视频模型 `{normalized}` 不支持多张参考图。"
        "Veo 3.0 仅支持 0 或 1 张参考图；要使用 2-3 张参考图生成 1 个视频，请切换到可用的 Veo 3.1 模型。"
    )


def _should_try_veo31_fallback(status: int, body: str, model_name: str) -> bool:
    if status != 404 or not _is_veo31_model(model_name):
        return False

    normalized = str(body or "").lower()
    return "publisher model" in normalized and (
        "not found" in normalized or "does not have access" in normalized
    )


def _get_veo31_fallback_models(model_name: str) -> list[str]:
    normalized = str(model_name or "").strip()
    return [
        candidate
        for candidate in ZENLAYER_VEO31_MODEL_CANDIDATES
        if candidate != normalized
    ]


def _build_zenlayer_image_payload(image_ref: str) -> Dict[str, str]:
    normalized = str(image_ref or "").strip()
    if not normalized:
        raise ValueError("Zenlayer image reference is empty")

    if normalized.startswith("data:"):
        header, _, encoded = normalized.partition(",")
        if not encoded:
            raise ValueError("Zenlayer image data URL missing base64 payload")

        mime_type = "image/png"
        if ";" in header:
            mime_type = header[len("data:") :].split(";", 1)[0] or mime_type

        return {
            "bytesBase64Encoded": encoded,
            "mimeType": mime_type,
        }

    if normalized.startswith("gs://"):
        return {"gcsUri": normalized}

    return {"uri": normalized}


def _normalize_reference_image_payloads(
    input_images: Optional[list[str]],
) -> list[Dict[str, str]]:
    if not input_images:
        return []

    normalized_images: list[Dict[str, str]] = []
    for image_ref in input_images[:ZENLAYER_REFERENCE_IMAGES_MAX]:
        normalized_images.append(_build_zenlayer_image_payload(image_ref))
    return normalized_images


def _normalize_reference_images(
    input_images: Optional[list[str]],
) -> list[Dict[str, Any]]:
    normalized_images: list[Dict[str, Any]] = []
    for image_payload in _normalize_reference_image_payloads(input_images):
        normalized_images.append(
            {
                "image": image_payload,
                "referenceType": "asset",
            }
        )
    return normalized_images


class ZenlayerVideoProvider(VideoProviderBase, provider_name="zenlayer"):
    """Zenlayer Google Veo provider."""

    def __init__(self):
        config = config_service.app_config.get("zenlayer", {})
        self.api_key = str(config.get("api_key", ""))
        self.base_url = str(config.get("url", "")).strip()
        self.model_name = get_zenlayer_model_name()
        self.max_wait = int(config.get("max_wait_seconds", 600))

        if not self.api_key:
            raise ValueError("Zenlayer API key is not configured")
        if not self.base_url:
            raise ValueError("Zenlayer base URL is not configured")

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

    def _build_payload(
        self,
        model_name: str,
        prompt: str,
        duration: int,
        aspect_ratio: str,
        resolution: str,
        input_images: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        instance: Dict[str, Any] = {"prompt": prompt}
        normalized_reference_images = _normalize_reference_images(input_images)
        normalized_image_payloads = _normalize_reference_image_payloads(input_images)
        payload_duration = duration

        if normalized_reference_images:
            if _is_veo31_model(model_name):
                instance["referenceImages"] = normalized_reference_images
            else:
                if len(normalized_reference_images) > 1:
                    raise RuntimeError(
                        "Current Zenlayer model does not support multiple reference images. "
                        "Please configure a Veo 3.1 model with access."
                    )
                instance["image"] = normalized_image_payloads[0]
        return {
            "instances": [instance],
            "parameters": {
                "durationSeconds": payload_duration,
                "aspectRatio": aspect_ratio,
                "resolution": resolution,
            },
        }

    async def _poll_operation(self, operation_name: str) -> dict[str, Any]:
        headers = self._build_headers()
        status_urls = _build_zenlayer_operation_urls(self.base_url, operation_name)

        async with HttpClient.create_aiohttp() as session:
            for _ in range(max(1, self.max_wait // 5)):
                for index, status_url in enumerate(status_urls):
                    async with session.get(status_url, headers=headers) as response:
                        text = await response.text()

                    if response.status == 404 and index + 1 < len(status_urls):
                        continue
                    if response.status >= 400:
                        raise RuntimeError(
                            "Zenlayer status query failed "
                            f"url={status_url} status={response.status} body={text[:500]}"
                        )

                    try:
                        result = json.loads(text)
                    except Exception as exc:
                        raise RuntimeError(
                            f"Zenlayer status returned invalid JSON url={status_url}"
                        ) from exc

                    if result.get("error"):
                        raise RuntimeError(
                            f"Zenlayer video task failed: {json.dumps(result['error'], ensure_ascii=False)}"
                        )

                    done = bool(result.get("done"))
                    download_url = _extract_zenlayer_download_url(result)
                    if done and download_url:
                        return {
                            "video_url": download_url,
                            "download_headers": {
                                "x-goog-api-key": self.api_key,
                            },
                        }
                    if done and not download_url:
                        raise RuntimeError("Zenlayer task completed without download URL")
                    break

                await asyncio.sleep(5)

        raise RuntimeError(
            f"Zenlayer video task timed out ({self.max_wait}s), operation={operation_name}"
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
            requested_model_name = model or self.model_name
            candidate_models = [requested_model_name]
            candidate_models.extend(_get_veo31_fallback_models(requested_model_name))
            attempted_errors: list[str] = []

            for attempt_index, model_name in enumerate(candidate_models):
                payload = self._build_payload(
                    model_name=model_name,
                    prompt=prompt,
                    duration=duration,
                    aspect_ratio=aspect_ratio,
                    resolution=resolution,
                    input_images=input_images,
                )
                request_url = _build_zenlayer_video_create_url(self.base_url, model_name)

                async with HttpClient.create_aiohttp() as session:
                    async with session.post(
                        request_url,
                        headers=self._build_headers(),
                        json=payload,
                    ) as response:
                        text = await response.text()

                    if response.status >= 400:
                        error_message = (
                            "Zenlayer task creation failed "
                            f"url={request_url} status={response.status} body={text[:500]}"
                        )
                        attempted_errors.append(error_message)
                        if _should_try_veo31_fallback(
                            response.status, text, model_name
                        ) and attempt_index + 1 < len(candidate_models):
                            print(
                                "Zenlayer create failed for "
                                f"{model_name}; trying fallback model "
                                f"{candidate_models[attempt_index + 1]}"
                            )
                            continue
                        raise RuntimeError(error_message)

                    try:
                        result = json.loads(text)
                    except Exception as exc:
                        raise RuntimeError(
                            f"Zenlayer create returned invalid JSON body={text[:500]}"
                        ) from exc

                operation_name = str(result.get("name") or "").strip()
                if not operation_name:
                    raise RuntimeError("Zenlayer create response missing operation name")

                return await self._poll_operation(operation_name)

            raise RuntimeError("; ".join(attempted_errors) or "Zenlayer create failed")
        except Exception as exc:
            print(f"Error generating video with Zenlayer: {exc}")
            traceback.print_exc()
            raise exc
