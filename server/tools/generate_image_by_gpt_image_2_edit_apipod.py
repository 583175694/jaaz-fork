import re
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore
from pydantic import BaseModel, Field

from tools.utils.image_generation_core import generate_image_with_provider
from tools.image_providers.apipod_gpt_image_provider import (
    get_apipod_image_model_name,
    normalize_apipod_image_model_name,
)


class GenerateImageByGptImage2EditApipodInputSchema(BaseModel):
    prompt: str = Field(
        description="Required. The prompt for image generation or reference-image guided generation."
    )
    aspect_ratio: str = Field(
        description="Required. Aspect ratio of the image. Use one of: 1:1, 16:9, 4:3, 3:4, 9:16."
    )
    input_images: list[str] | None = Field(
        default=None,
        description="Optional. One or more input images for reference or editing. Pass a list of image ids.",
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


def _resolve_requested_image_model(message_history: object) -> str:
    if not isinstance(message_history, list):
        return get_apipod_image_model_name()

    for message in reversed(message_history):
        role = ""
        content = None
        if isinstance(message, dict):
            role = str(message.get("role", "") or "")
            content = message.get("content")
        else:
            role = str(getattr(message, "type", "") or getattr(message, "role", "") or "")
            content = getattr(message, "content", None)

        if role not in {"user", "human"}:
            continue

        text_parts: list[str] = []
        if isinstance(content, str):
            text_parts = [content]
        elif isinstance(content, list):
            for item in content:
                if (
                    isinstance(item, dict)
                    and item.get("type") == "text"
                    and isinstance(item.get("text"), str)
                ):
                    text_parts.append(item["text"])
                elif hasattr(item, "get") and item.get("type") == "text" and isinstance(item.get("text"), str):
                    text_parts.append(item.get("text"))
        content_text = "\n".join(
            part.strip() for part in text_parts if part and part.strip()
        )
        if not content_text:
            continue
        image_model_match = re.search(
            r"<image_model\b[^>]*>(.*?)</image_model>",
            content_text,
            flags=re.S,
        )
        if image_model_match:
            return normalize_apipod_image_model_name(image_model_match.group(1))

    return get_apipod_image_model_name()


@tool(
    "generate_image_by_gpt_image_2_edit_apipod",
    description="Generate or edit an image using APIPod Nano Banana. Use this when reference images are provided or when image editing is needed.",
    args_schema=GenerateImageByGptImage2EditApipodInputSchema,
)
async def generate_image_by_gpt_image_2_edit_apipod(
    prompt: str,
    aspect_ratio: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    input_images: list[str] | None = None,
) -> str:
    ctx = config.get("configurable", {})
    canvas_id = ctx.get("canvas_id", "")
    session_id = ctx.get("session_id", "")
    model_name = _resolve_requested_image_model(ctx.get("messages"))
    return await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider="apipodgptimage",
        model=model_name,
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        input_images=input_images,
    )


__all__ = ["generate_image_by_gpt_image_2_edit_apipod"]
