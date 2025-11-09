from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from ..services.chat_service import ChatService
from typing import Optional, AsyncGenerator
from ..utils.models import CreateGroupPayload, JoinGroupPayload, AiChatPayload
from ..services.ai_service import get_ai_response_stream
from ..utils.repositories import AiSessionRepository
import json

router = APIRouter(prefix="/chat", tags=["chat"])
service = ChatService()


@router.post("/groups")
async def create_group(payload: CreateGroupPayload, request: Request):
    """Create a new group, automatically adding the current user as a member."""
    user_id = request.state.user.get("_id")
    # Ensure the creator is always in the member list
    members = list(set(payload.members + [user_id]))
    group = await service.groups.create({"name": payload.name, "members": members})
    return group


@router.post("/groups/join-or-create")
async def join_or_create_group(payload: JoinGroupPayload, request: Request):
    """Join a group by name, or create it if it doesn't exist."""
    user_id = request.state.user.get("_id")
    group = await service.join_or_create_group_by_name(payload.name, user_id)
    return group


@router.get("/groups/{group_id}")
async def get_group(group_id: str):
    return await service.groups.find_by_id(group_id)


@router.delete("/groups/{group_id}")
async def delete_group(group_id: str, request: Request):
    """Deletes a group. For simplicity, any member can delete."""
    # In a real app, you might want to check for creator/admin privileges.
    await service.groups.delete(group_id)
    return {"ok": True, "message": "Group deleted"}


@router.get("/chats")
async def list_chats(request: Request):
    """List chats (groups and simple metadata) for the current user."""
    user_id = request.state.user.get("_id")
    if not user_id:
        return {"error": "User not authenticated"}
    chats = await service.list_user_chats(user_id)
    return chats


@router.post("/dm/{other_id}")
async def create_dm(other_id: str, request: Request):
    """Create or return a DM conversation between the current user and other_id."""
    user_id = request.state.user.get("_id")
    if not user_id:
        return {"error": "User not authenticated"}
    conv = await service.create_dm(user_id, other_id)
    return conv


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, request: Request):
    """Deletes a DM conversation document."""
    # Here too, you might want to check if the user is a participant.
    await service.convs.delete(conv_id)
    return {"ok": True, "message": "Conversation deleted"}


@router.get("/users/search")
async def search_users(q: str, request: Request):
    """Search for users by username."""
    current_user_id = request.state.user.get("_id")
    return await service.users.search_by_username(q, exclude_id=str(current_user_id))


@router.get("/users")
async def list_all_users(request: Request):
    """List all users on the platform, excluding the current user."""
    return await service.users.list_all()


@router.get("/ai/history")
async def get_ai_chat_history(request: Request):
    """Get the AI chat history for the current user."""
    user_id = request.state.user.get("_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    ai_sessions = AiSessionRepository()
    session = await ai_sessions.find_by_user_id(user_id)
    if not session:
        session = await ai_sessions.create(user_id)
    
    # Add a room_id for frontend consistency
    session["room_id"] = "ai_assistant"
    return session

@router.delete("/ai/history")
async def clear_ai_chat_history(request: Request):
    """Clears the AI chat history for the current user."""
    user_id = request.state.user.get("_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    ai_sessions = AiSessionRepository()
    session = await ai_sessions.find_by_user_id(user_id)
    if session:
        await ai_sessions.clear_messages(session["_id"])
    
    return {"ok": True, "message": "AI chat history cleared."}


@router.post("/ai")
async def chat_with_ai(payload: AiChatPayload, request: Request):
    """Streams a response from the AI assistant."""
    user_id = request.state.user.get("_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    ai_sessions = AiSessionRepository()
    session = await ai_sessions.find_by_user_id(user_id)
    if not session:
        session = await ai_sessions.create(user_id)

    await ai_sessions.add_message(session["_id"], {"role": "user", "content": payload.content})

    # Limit history to the last 20 messages to keep context relevant and manage token usage
    history = session.get("messages", [])[-20:]

    async def stream_wrapper() -> AsyncGenerator[str, None]:
        full_response = ""
        async for chunk in get_ai_response_stream(payload.content, history):
            full_response += chunk
            yield chunk
        await ai_sessions.add_message(session["_id"], {"role": "assistant", "content": full_response})

    return StreamingResponse(stream_wrapper(), media_type="text/event-stream")
