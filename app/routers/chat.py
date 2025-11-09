from fastapi import APIRouter, Depends, Request
from ..services.chat_service import ChatService
from typing import Optional
from ..utils.models import CreateGroupPayload, JoinGroupPayload

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
