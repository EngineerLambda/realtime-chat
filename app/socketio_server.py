import socketio
from .services import ChatService
from .repositories import UserRepository
from .utils import decode_token
from http.cookies import SimpleCookie

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
# The ASGI app will be wrapped around the FastAPI app in main.py
chat_service = ChatService()
user_repo = UserRepository()


@sio.event
async def connect(sid, environ, auth):
    """Authenticate on connect. The client should send auth={"token": "<jwt>"} when connecting."""
    token = None
    if isinstance(auth, dict):
        token = auth.get("token")
    # fallback: try HTTP_AUTHORIZATION in environ
    if not token:
        http_auth = environ.get("HTTP_AUTHORIZATION") or environ.get("authorization")
        if http_auth:
            parts = http_auth.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
    # fallback: try cookies header (access_token cookie). environ may contain HTTP_COOKIE
    if not token:
        cookie_header = environ.get("HTTP_COOKIE") or environ.get("cookie")
        if cookie_header:
            c = SimpleCookie()
            try:
                c.load(cookie_header)
                if "access_token" in c:
                    token = c["access_token"].value
            except Exception:
                pass
    if not token:
        return False  # reject connection
    try:
        payload = decode_token(token)
    except Exception:
        return False
    user_id = payload.get("sub")
    if not user_id:
        return False
    user = await user_repo.find_by_id(user_id)
    if not user:
        return False
    # store user on session
    await sio.save_session(sid, {"user": user})
    # accepted
    return True


@sio.event
async def disconnect(sid):
    # session cleanup if needed
    try:
        await sio.save_session(sid, {})
    except Exception:
        pass


@sio.event
async def join_room(sid, data):
    # data: {"room": "room1"}
    room = data.get("room")
    if not room:
        return
    # enforce membership for protected rooms
    session = await sio.get_session(sid)
    user = session.get("user") if session else None
    user_id = user.get("_id") if user else None

    # group room convention: group:<group_id>
    if room.startswith("group:"):
        group_id = room.split("group:", 1)[1]
        group = await chat_service.groups.find_by_id(group_id)
        if not group:
            await sio.emit("error", {"message": "group_not_found"}, to=sid)
            return
        # members stored as list of user ids (strings)
        if user_id and user_id not in group.get("members", []):
            await sio.emit("error", {"message": "not_a_member"}, to=sid)
            return

    # dm room convention: dm:<userA>-<userB>
    if room.startswith("dm:"):
        # ensure the connecting user is one of the two participants
        parts = room.split("dm:", 1)[1].split("-")
        if user_id and user_id not in parts:
            await sio.emit("error", {"message": "not_a_participant"}, to=sid)
            return

    await sio.enter_room(sid, room)
    await sio.emit("system", {"message": f"{user.get('username')} joined"}, to=room)


@sio.event
async def leave_room(sid, data):
    room = data.get("room")
    if not room:
        return
    await sio.leave_room(sid, room)
    session = await sio.get_session(sid)
    user = session.get("user") if session else None
    await sio.emit("system", {"message": f"{user.get('username')} left"}, to=room)


@sio.event
async def message(sid, data):
    # data: {"room": "room1", "content": "hi", "is_group": false}
    room = data.get("room")
    content = data.get("content")
    is_group = data.get("is_group", False)
    if not room or not content:
        return
    session = await sio.get_session(sid)
    user = session.get("user") if session else None
    user_id = user.get("_id") if user else None
    # persist message
    try:
        msg = await chat_service.post_message(room, user_id, content, is_group)
    except Exception:
        msg = {"error": "failed_to_persist"}
    # broadcast to room
    # include sender_username on broadcast (post_message already enriches it)
    await sio.emit("message", {"message": msg}, to=room)
