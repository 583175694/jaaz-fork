from __future__ import annotations

from typing import Any, Dict, List, cast

from models.config_model import ModelInfo
from models.tool_model import ToolInfoJson
from services.config_service import config_service

DEFAULT_TEXT_PROVIDER = "apipodcode"
DEFAULT_TEXT_MODEL = "gpt-5.4"
DEFAULT_IMAGE_TOOL_ID = "generate_image_by_gpt_image_2_edit_apipod"
DEFAULT_VIDEO_TOOL_ID = "generate_video_by_veo3_apipod"
ALLOWED_TOOL_IDS = {DEFAULT_IMAGE_TOOL_ID, DEFAULT_VIDEO_TOOL_ID}


def get_default_text_model() -> ModelInfo:
    config = config_service.get_config().get(DEFAULT_TEXT_PROVIDER, {})
    return cast(
        ModelInfo,
        {
            "provider": DEFAULT_TEXT_PROVIDER,
            "model": DEFAULT_TEXT_MODEL,
            "url": str(config.get("url", "")),
            "type": "text",
        },
    )


def sanitize_tool_list(tool_list: list[Dict[str, Any]] | list[ToolInfoJson] | None) -> list[ToolInfoJson]:
    normalized: list[ToolInfoJson] = []
    seen_ids: set[str] = set()
    for tool in tool_list or []:
        tool_id = str(tool.get("id", "") or "").strip() if isinstance(tool, dict) else ""
        if tool_id not in ALLOWED_TOOL_IDS or tool_id in seen_ids:
            continue
        seen_ids.add(tool_id)
        normalized.append(
            cast(
                ToolInfoJson,
                {
                    "id": tool_id,
                    "provider": str(tool.get("provider", "") or ""),
                    "display_name": str(tool.get("display_name", "") or ""),
                    "type": str(tool.get("type", "") or ""),
                },
            )
        )

    if normalized:
        return normalized

    return [
        cast(
            ToolInfoJson,
            {
                "id": DEFAULT_IMAGE_TOOL_ID,
                "provider": "apipodgptimage",
                "display_name": "APIPod Images",
                "type": "image",
            },
        ),
        cast(
            ToolInfoJson,
            {
                "id": DEFAULT_VIDEO_TOOL_ID,
                "provider": "apipodvideo",
                "display_name": "APIPod Video",
                "type": "video",
            },
        ),
    ]


def filter_allowed_tool_ids(tool_ids: List[str]) -> List[str]:
    return [tool_id for tool_id in tool_ids if tool_id in ALLOWED_TOOL_IDS]
