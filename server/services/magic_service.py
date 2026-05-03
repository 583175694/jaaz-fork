# services/magic_service.py

import asyncio
import base64
import json
import os
from io import BytesIO
from typing import Dict, Any, List

import aiohttp
from nanoid import generate
from PIL import Image

from common import DEFAULT_PORT
from services.config_service import FILES_DIR
from services.db_service import db_service
from services.stream_service import add_stream_task, remove_stream_task
from services.websocket_service import send_to_websocket
from tools.image_providers.apipod_gpt_image_provider import APIPodGPTImageProvider
from tools.utils.image_canvas_utils import save_image_to_canvas
from utils.http_client import HttpClient


def _extract_image_content(message: Dict[str, Any]) -> str:
    content = message.get("content", [])
    if not isinstance(content, list):
        return ""

    for item in content:
        if item.get("type") == "image_url":
            image_url = item.get("image_url", {})
            if isinstance(image_url, dict):
                url = image_url.get("url", "")
                if isinstance(url, str):
                    return url
    return ""


def _extract_text_content(message: Dict[str, Any]) -> str:
    content = message.get("content", [])
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""

    text_parts: list[str] = []
    for item in content:
        if item.get("type") == "text":
            text = item.get("text", "")
            if isinstance(text, str) and text.strip():
                text_parts.append(text.strip())
    return "\n".join(text_parts).strip()


def _decode_data_url(data_url: str) -> tuple[bytes, str]:
    if not data_url.startswith("data:image/"):
        raise ValueError("Magic input image must be a data URL")

    header, encoded = data_url.split(",", 1)
    mime_type = header.split(";")[0].split(":", 1)[1]
    return base64.b64decode(encoded), mime_type


def _save_magic_source_image(image_content: str, files_dir: str) -> str:
    image_bytes, mime_type = _decode_data_url(image_content)
    image = Image.open(BytesIO(image_bytes))

    ext_map = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
    }
    extension = ext_map.get(mime_type, "png")
    file_id = f"magic_src_{generate(size=8)}"
    filename = f"{file_id}.{extension}"
    path = os.path.join(files_dir, filename)

    image.save(path)
    return filename


async def _upload_magic_source_to_public_url(filename: str) -> str:
    file_path = os.path.join(FILES_DIR, filename)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Magic source file not found: {file_path}")

    async with HttpClient.create_aiohttp() as session:
        with open(file_path, "rb") as file_obj:
            form = aiohttp.FormData()
            form.add_field(
                "file",
                file_obj,
                filename=filename,
                content_type="image/png",
            )
            async with session.post(
                "https://tmpfiles.org/api/v1/upload",
                data=form,
            ) as response:
                text = await response.text()

        if response.status >= 400:
            raise RuntimeError(
                "Magic source upload failed "
                f"status={response.status} body={text[:500]}"
            )

        result = json.loads(text)
        if result.get("status") != "success":
            raise RuntimeError(f"Magic source upload failed body={text[:500]}")

        page_url = result.get("data", {}).get("url", "")
        if not page_url:
            raise RuntimeError(f"Magic source upload missing url body={text[:500]}")

        return page_url.replace("http://tmpfiles.org/", "https://tmpfiles.org/dl/")


async def _upload_data_url_to_public_url(data_url: str, filename: str) -> str:
    image_bytes, mime_type = _decode_data_url(data_url)
    async with HttpClient.create_aiohttp() as session:
        form = aiohttp.FormData()
        form.add_field(
            "file",
            image_bytes,
            filename=filename,
            content_type=mime_type,
        )
        async with session.post("https://tmpfiles.org/api/v1/upload", data=form) as response:
            text = await response.text()

    if response.status >= 400:
        raise RuntimeError(
            "Magic source upload failed "
            f"status={response.status} body={text[:500]}"
        )

    result = json.loads(text)
    if result.get("status") != "success":
        raise RuntimeError(f"Magic source upload failed body={text[:500]}")

    page_url = result.get("data", {}).get("url", "")
    if not page_url:
        raise RuntimeError(f"Magic source upload missing url body={text[:500]}")

    return page_url.replace("http://tmpfiles.org/", "https://tmpfiles.org/dl/")


def _pick_aspect_ratio(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "1:1"

    target_ratio = width / height
    supported = {
        "1:1": 1.0,
        "16:9": 16 / 9,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
        "9:16": 9 / 16,
    }
    return min(supported.items(), key=lambda item: abs(item[1] - target_ratio))[0]


def _build_magic_prompt(
    user_prompt: str,
    relation_hint: str,
    selected_image_count: int,
) -> str:
    if user_prompt:
        return user_prompt

    if relation_hint == "multi" or selected_image_count >= 2:
        return (
            "Create a fusion edit based on the selected canvas region. "
            "Treat this as a multi-image combination task, not a simple repaint. "
            "Preserve the overall scene layout, camera angle, and background structure. "
            "Keep the main subject clear and visually dominant, but merge distinctive visual traits, "
            "energy effects, costume details, or character design cues from the other selected image(s). "
            "Do not merely shift colors. Produce a believable hybrid design while keeping the composition stable."
        )

    return (
        "Redraw the selected canvas region as a polished illustration while preserving the original composition, "
        "subject placement, camera angle, and background layout. "
        "Keep the edit focused on the main subject and avoid unnecessary changes to the surrounding scene."
    )


def _build_multi_image_fusion_prompt(user_prompt: str) -> str:
    if user_prompt:
        return user_prompt

    return (
        "Treat the left reference image as the trait source and the right reference image as the main target composition. "
        "Edit the target image so the final result keeps the right image's background, camera angle, and overall pose as much as possible. "
        "Merge clear signature traits from the left image into the right image's main subject, including energy effects, costume details, character identity, "
        "or creature design language. Do not merely recolor the image. Create a convincing hybrid character while preserving the right-side scene."
    )


async def handle_magic(data: Dict[str, Any]) -> None:
    messages: List[Dict[str, Any]] = data.get("messages", [])
    session_id: str = data.get("session_id", "")
    canvas_id: str = data.get("canvas_id", "")
    width: int = int(data.get("width", 0) or 0)
    height: int = int(data.get("height", 0) or 0)
    relation_hint: str = str(data.get("relation_hint", "single") or "single")
    selected_image_count: int = int(data.get("selected_image_count", 0) or 0)
    selected_image_base64s: List[str] = data.get("selected_image_base64s", []) or []
    selected_image_positions: List[Dict[str, Any]] = data.get("selected_image_positions", []) or []

    if len(messages) == 1:
        prompt = messages[0].get("content", "")
        await db_service.create_chat_session(
            session_id,
            "gpt",
            "nanobanana",
            canvas_id,
            (prompt[:200] if isinstance(prompt, str) else "Magic Edit"),
        )

    if len(messages) > 0:
        await db_service.create_message(
            session_id, messages[-1].get("role", "user"), json.dumps(messages[-1])
        )

    task = asyncio.create_task(
        _process_magic_generation(
            messages,
            session_id,
            canvas_id,
            width=width,
            height=height,
            relation_hint=relation_hint,
            selected_image_count=selected_image_count,
            selected_image_base64s=selected_image_base64s,
            selected_image_positions=selected_image_positions,
        )
    )
    add_stream_task(session_id, task)
    try:
        await task
    except asyncio.exceptions.CancelledError:
        print(f"🛑Magic generation session {session_id} cancelled")
    finally:
        remove_stream_task(session_id)
        await send_to_websocket(session_id, {"type": "done"})

    print("✨ magic_service 处理完成")


async def _process_magic_generation(
    messages: List[Dict[str, Any]],
    session_id: str,
    canvas_id: str,
    width: int = 0,
    height: int = 0,
    relation_hint: str = "single",
    selected_image_count: int = 0,
    selected_image_base64s: List[str] | None = None,
    selected_image_positions: List[Dict[str, Any]] | None = None,
) -> None:
    ai_response = await create_magic_response(
        messages,
        session_id,
        canvas_id,
        width=width,
        height=height,
        relation_hint=relation_hint,
        selected_image_count=selected_image_count,
        selected_image_base64s=selected_image_base64s or [],
        selected_image_positions=selected_image_positions or [],
    )

    await db_service.create_message(session_id, "assistant", json.dumps(ai_response))
    all_messages = messages + [ai_response]
    await send_to_websocket(
        session_id, {"type": "all_messages", "messages": all_messages}
    )


async def create_magic_response(
    messages: List[Dict[str, Any]],
    session_id: str = "",
    canvas_id: str = "",
    width: int = 0,
    height: int = 0,
    relation_hint: str = "single",
    selected_image_count: int = 0,
    selected_image_base64s: List[str] | None = None,
    selected_image_positions: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    try:
        user_message = messages[-1] if messages else {}
        image_content = _extract_image_content(user_message)
        user_prompt = _extract_text_content(user_message)

        if not image_content:
            return {
                "role": "assistant",
                "content": [{"type": "text", "text": "✨ 未找到选区图片"}],
            }

        source_filename = _save_magic_source_image(image_content, FILES_DIR)
        source_filename = os.path.basename(source_filename)
        public_image_url = await _upload_magic_source_to_public_url(source_filename)
        aspect_ratio = _pick_aspect_ratio(width, height)

        prompt = _build_magic_prompt(user_prompt, relation_hint, selected_image_count)
        input_images = [public_image_url]

        if (relation_hint == "multi" or selected_image_count >= 2) and selected_image_base64s:
            ordered_base64s = selected_image_base64s
            if selected_image_positions and len(selected_image_positions) == len(selected_image_base64s):
                indexed = list(zip(selected_image_base64s, selected_image_positions))
                indexed.sort(key=lambda item: float(item[1].get("x", 0) or 0))
                ordered_base64s = [item[0] for item in indexed]

            reference_urls: list[str] = []
            for index, data_url in enumerate(ordered_base64s[:3]):
                reference_url = await _upload_data_url_to_public_url(
                    data_url, f"magic_ref_{index}.png"
                )
                reference_urls.append(reference_url)

            if reference_urls:
                prompt = _build_multi_image_fusion_prompt(user_prompt)
                input_images = reference_urls + [public_image_url]

        provider = APIPodGPTImageProvider()
        mime_type, width, height, filename = await provider.generate(
            prompt=prompt,
            model="gpt-image-2-edit",
            aspect_ratio=aspect_ratio,
            input_images=input_images,
            metadata={
                "prompt": prompt,
                "provider": "apipodgptimage",
                "source": "magic-edit",
                "source_file": source_filename,
                "source_url": public_image_url,
                "aspect_ratio": aspect_ratio,
                "relation_hint": relation_hint,
                "selected_image_count": selected_image_count,
                "input_image_count": len(input_images),
            },
        )

        image_url = ""
        if session_id and canvas_id:
            image_url = await save_image_to_canvas(
                session_id, canvas_id, filename, mime_type, width, height
            )

        return {
            "role": "assistant",
            "content": (
                "✨ GPT Image 2 Edit completed\n\n"
                f"![image_id: {filename}](http://localhost:{DEFAULT_PORT}{image_url})"
            ),
        }
    except (asyncio.TimeoutError, Exception) as e:
        error_msg = str(e)
        print(f"❌ GPT Image 2 Edit error: {error_msg}")
        return {
            "role": "assistant",
            "content": [{"type": "text", "text": f"✨ GPT Image 2 Edit Error: {error_msg}"}],
        }
