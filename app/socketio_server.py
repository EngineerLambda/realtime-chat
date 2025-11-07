import socketio
from .utils import decode_token
from .services import ChatService
from .repositories import UserRepository  # Import the UserRepository

# create a Socket.IO server
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


@sio.event
async def connect(sid, environ):
    """Handle new client connections and authenticate them via token in cookie."""
    print(f"Socket connected: {sid}")
    token = environ.get("HTTP_COOKIE", "").split("access_token=")[-1].split(";")[0]
    if not token:
        print(f"Authentication failed for {sid}: no token")
        await sio.disconnect(sid)
        return
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        await sio.save_session(sid, {"user_id": user_id})
        print(f"User {user_id} authenticated for SID {sid}")
    except Exception as e:
        print(f"Authentication failed for {sid}: {e}")
        await sio.disconnect(sid)


@sio.event
async def join_room(sid, data):
    room = data.get("room")
    print(f"Received join_room event from SID {sid} for room: {room}")  # Debug log
    if room:
        await sio.enter_room(sid, room)
        print(f"SID {sid} successfully joined room {room}")

        # Fetch the username of the user who joined
        session = await sio.get_session(sid)
        user_id = session.get("user_id")
        user_repo = UserRepository()
        user = await user_repo.find_by_id(user_id)
        username = user.get("username", "Unknown User")

        # If it's a DM, fetch the other participant's username
        if room.startswith("dm:"):
            participant_ids = room.split(":")[1].split("-")
            other_user_id = [uid for uid in participant_ids if uid != user_id][0]
            other_user = await user_repo.find_by_id(other_user_id)
            other_username = other_user.get("username", "Unknown User")
            room_display = f"DM with {other_username}"
        else:
            room_display = room

        # Notify the room about the new participant with the username
        await sio.emit("system", {"message": f"{username} has joined the room {room_display}."}, room=room)


@sio.event
async def message(sid, data):
    print(f"Received message event from SID {sid} with data: {data}")  # Debug log
    session = await sio.get_session(sid)
    user_id = session.get("user_id")
    print(f"User ID from session: {user_id}")  # Debug log

    room_id = data.get("room")
    is_group = room_id.startswith("group:")

    chat_service = ChatService()
    msg = await chat_service.post_message(room_id, user_id, data["content"], is_group)
    print(f"Message processed and saved: {msg}")  # Debug log
    # Emit the message to the room
    await sio.emit("message", {"message": msg}, room=data["room"])
    print(f"Message emitted to room {data['room']}")