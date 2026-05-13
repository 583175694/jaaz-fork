import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_auth_modules(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "secret-pass")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")

    import services.auth_service as auth_service
    import routers.auth_router as auth_router

    importlib.reload(auth_service)
    importlib.reload(auth_router)
    return auth_service, auth_router


def _build_app(monkeypatch):
    auth_service, auth_router = _load_auth_modules(monkeypatch)

    app = FastAPI()
    app.add_middleware(auth_service.AuthMiddleware)
    app.include_router(auth_router.router)

    @app.get("/api/private")
    async def private_api():
        return {"ok": True}

    return app


def test_api_requires_login_when_password_is_configured(monkeypatch):
    app = _build_app(monkeypatch)
    client = TestClient(app)

    response = client.get("/api/private")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_login_sets_cookie_and_unlocks_api(monkeypatch):
    app = _build_app(monkeypatch)
    client = TestClient(app)

    login_response = client.post("/api/auth/login", json={"password": "secret-pass"})

    assert login_response.status_code == 200
    assert login_response.json() == {
        "authenticated": True,
        "auth_required": True,
    }
    assert "jaaz_session" in login_response.cookies

    response = client.get("/api/private")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_wrong_password_is_rejected(monkeypatch):
    app = _build_app(monkeypatch)
    client = TestClient(app)

    response = client.post("/api/auth/login", json={"password": "wrong"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid password"


def test_logout_clears_session(monkeypatch):
    app = _build_app(monkeypatch)
    client = TestClient(app)
    client.post("/api/auth/login", json={"password": "secret-pass"})

    logout_response = client.post("/api/auth/logout")
    protected_response = client.get("/api/private")

    assert logout_response.status_code == 200
    assert logout_response.json() == {
        "authenticated": False,
        "auth_required": True,
    }
    assert protected_response.status_code == 401
