from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from services.config_service import config_service
# from tools.video_models_dynamic import register_video_models  # Disabled video models
from services.tool_service import tool_service

router = APIRouter(prefix="/api/config")


@router.get("/exists")
async def config_exists():
    return {"exists": config_service.exists_config()}


@router.get("")
async def get_config():
    return config_service.get_public_config()


@router.post("")
async def update_config(request: Request):
    _ = await request.json()
    return JSONResponse(
        status_code=403,
        content={
            "status": "error",
            "message": "Production runtime uses built-in model configuration and does not allow config updates.",
        },
    )
