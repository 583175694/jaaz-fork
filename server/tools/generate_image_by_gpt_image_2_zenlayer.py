from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore
from pydantic import BaseModel, Field

from tools.utils.image_generation_core import generate_image_with_provider


class GenerateImageByGptImage2ZenlayerInputSchema(BaseModel):
    prompt: str = Field(
        description="Required. The prompt for image generation."
    )
    aspect_ratio: str = Field(
        description="Required. Aspect ratio of the image. Use one of: 1:1, 16:9, 4:3, 3:4, 9:16."
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool(
    "generate_image_by_gpt_image_2_zenlayer",
    description="Generate an image using Zenlayer OpenAI-compatible gpt-image-2. Use this for standard text-to-image generation only; do not use it for image editing or reference-image workflows.",
    args_schema=GenerateImageByGptImage2ZenlayerInputSchema,
)
async def generate_image_by_gpt_image_2_zenlayer(
    prompt: str,
    aspect_ratio: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> str:
    ctx = config.get("configurable", {})
    canvas_id = ctx.get("canvas_id", "")
    session_id = ctx.get("session_id", "")
    return await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider="zenlayer",
        model="gpt-image-2",
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        input_images=None,
    )


__all__ = ["generate_image_by_gpt_image_2_zenlayer"]
