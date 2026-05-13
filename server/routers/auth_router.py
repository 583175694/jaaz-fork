from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from services.auth_service import (
    clear_session_cookie,
    is_auth_required,
    request_is_authenticated,
    set_session_cookie,
    verify_password,
)


router = APIRouter(prefix="/api/auth")


class LoginRequest(BaseModel):
    password: str


@router.get("/status")
async def auth_status(request: Request):
    return {
        "authenticated": request_is_authenticated(request),
        "auth_required": is_auth_required(),
    }


@router.post("/login")
async def login(payload: LoginRequest, response: Response):
    if not verify_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    set_session_cookie(response)
    return {
        "authenticated": True,
        "auth_required": is_auth_required(),
    }


@router.post("/logout")
async def logout(response: Response):
    clear_session_cookie(response)
    return {
        "authenticated": False,
        "auth_required": is_auth_required(),
    }
