from fastapi import APIRouter
from models.tool_model import ToolInfoJson
from services.tool_service import tool_service
from services.config_service import config_service
from services.db_service import db_service
from models.config_model import ModelInfo

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok"}


# List all LLM models
@router.get("/list_models")
async def get_models() -> list[ModelInfo]:
    provider_config = config_service.get_config().get("apipodcode", {})
    return [{
        "provider": "apipodcode",
        "model": "gpt-5.4",
        "url": str(provider_config.get("url", "")),
        "type": "text",
    }]


@router.get("/list_tools")
async def list_tools() -> list[ToolInfoJson]:
    res: list[ToolInfoJson] = []
    for tool_id, tool_info in tool_service.tools.items():
        if tool_info.get('provider') == 'system':
            continue
        res.append({
            'id': tool_id,
            'provider': tool_info.get('provider', ''),
            'type': tool_info.get('type', ''),
            'display_name': tool_info.get('display_name', ''),
        })
    return res


@router.get("/list_chat_sessions")
async def list_chat_sessions(client_id: str = ""):
    if not client_id:
        return []
    return await db_service.list_sessions(client_id=client_id or None)


@router.get("/chat_session/{session_id}")
async def get_chat_session(session_id: str, client_id: str = ""):
    if not client_id:
        return []
    session = await db_service.get_chat_session(session_id)
    if not session:
        return []
    if str(session.get("client_id", "") or "") != client_id:
        return []
    return await db_service.get_chat_history(session_id)
