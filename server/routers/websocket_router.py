# routers/websocket_router.py
from services.websocket_state import sio, add_connection, remove_connection
from services.auth_service import is_auth_required, validate_session_token, SESSION_COOKIE_NAME
from http.cookies import SimpleCookie

@sio.event
async def connect(sid, environ, auth):
    if is_auth_required():
        cookies = SimpleCookie()
        cookies.load(environ.get("HTTP_COOKIE", ""))
        session_cookie = cookies.get(SESSION_COOKIE_NAME)
        token = session_cookie.value if session_cookie else None
        if not validate_session_token(token):
            print(f"Client {sid} rejected: authentication required")
            return False

    print(f"Client {sid} connected")
    
    user_info = auth or {}
    add_connection(sid, user_info)
    
    await sio.emit('connected', {'status': 'connected'}, room=sid)

@sio.event
async def disconnect(sid):
    print(f"Client {sid} disconnected")
    remove_connection(sid)

@sio.event
async def ping(sid, data):
    await sio.emit('pong', data, room=sid)
