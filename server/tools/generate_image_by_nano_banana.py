from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore
from pydantic import BaseModel, Field

from tools.utils.image_generation_core import generate_image_with_provider


class GenerateImageByNanoBananaInputSchema(BaseModel):
    prompt: str = Field(
        description="Required. The prompt for image generation. If you want to edit an image, describe the desired edit in the prompt."
    )
    aspect_ratio: str = Field(
        description="Required. Aspect ratio of the image, only these values are allowed: 1:1, 16:9, 4:3, 3:4, 9:16."
    )
    input_images: list[str] | None = Field(
        default=None,
        description="Optional. One or more input images for reference or editing. Pass a list of image ids.",
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool(
    "generate_image_by_nano_banana",
    description="Generate or edit an image using Nano Banana Pro. Supports text-to-image and image-to-image generation.",
    args_schema=GenerateImageByNanoBananaInputSchema,
)
async def generate_image_by_nano_banana(
    prompt: str,
    aspect_ratio: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    input_images: list[str] | None = None,
) -> str:
    ctx = config.get("configurable", {})
    canvas_id = ctx.get("canvas_id", "")
    session_id = ctx.get("session_id", "")
    return await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider="nanobanana",
        model="nano-banana-pro",
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        input_images=input_images,
    )


__all__ = ["generate_image_by_nano_banana"]
