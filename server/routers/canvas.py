from fastapi import APIRouter, Request
#from routers.agent import chat
from services.chat_service import handle_chat
from services.db_service import db_service
import asyncio
import json
from typing import Any, Dict

router = APIRouter(prefix="/api/canvas")


def _merge_persisted_video_data(
    incoming_data: Dict[str, Any], existing_data: Dict[str, Any]
) -> Dict[str, Any]:
    incoming_elements = list(incoming_data.get("elements", []) or [])
    incoming_files = dict(incoming_data.get("files", {}) or {})

    existing_elements = list(existing_data.get("elements", []) or [])
    existing_files = dict(existing_data.get("files", {}) or {})

    incoming_element_ids = {
        str(element.get("id", "") or "")
        for element in incoming_elements
        if isinstance(element, dict)
    }
    incoming_file_ids = set(incoming_files.keys())

    merged_elements = list(incoming_elements)
    merged_files = dict(incoming_files)

    preserved_video_count = 0
    for element in existing_elements:
        if not isinstance(element, dict):
            continue
        if element.get("type") != "video":
            continue

        element_id = str(element.get("id", "") or "")
        file_id = str(element.get("fileId", "") or "")
        if element_id and element_id not in incoming_element_ids:
            merged_elements.append(element)
            preserved_video_count += 1

        if file_id and file_id not in incoming_file_ids and file_id in existing_files:
            merged_files[file_id] = existing_files[file_id]

    if preserved_video_count:
        print(
            "🎥 Preserved persisted video elements during canvas save",
            {"count": preserved_video_count},
        )

    return {
        **incoming_data,
        "elements": merged_elements,
        "files": merged_files,
    }

@router.get("/list")
async def list_canvases():
    return await db_service.list_canvases()

@router.post("/create")
async def create_canvas(request: Request):
    data = await request.json()
    id = data.get('canvas_id')
    name = data.get('name')

    asyncio.create_task(handle_chat(data))
    await db_service.create_canvas(id, name)
    return {"id": id }

@router.get("/{id}")
async def get_canvas(id: str):
    return await db_service.get_canvas_data(id)

@router.post("/{id}/save")
async def save_canvas(id: str, request: Request):
    payload = await request.json()
    incoming_data = payload["data"]
    existing_canvas = await db_service.get_canvas_data(id)
    existing_data = existing_canvas.get("data", {}) if existing_canvas else {}
    merged_data = _merge_persisted_video_data(incoming_data, existing_data)
    data_str = json.dumps(merged_data)
    await db_service.save_canvas_data(id, data_str, payload['thumbnail'])
    return {"id": id }

@router.post("/{id}/rename")
async def rename_canvas(id: str, request: Request):
    data = await request.json()
    name = data.get('name')
    await db_service.rename_canvas(id, name)
    return {"id": id }

@router.delete("/{id}/delete")
async def delete_canvas(id: str):
    await db_service.delete_canvas(id)
    return {"id": id }
