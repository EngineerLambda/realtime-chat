from fastapi import APIRouter, Depends, Request
from ..services import ChatService
from typing import Optional
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["chat"])
service = ChatService()


class CreateGroupPayload(BaseModel):
    name: str
    members: list[str]


@router.post("/groups")
async def create_group(payload: CreateGroupPayload, request: Request):
    """Create a new group, automatically adding the current user as a member."""
    user_id = request.state.user.get("_id")
    # Ensure the creator is always in the member list
    members = list(set(payload.members + [user_id]))
    group = await service.groups.create({"name": payload.name, "members": members})
    return group


@router.get("/groups/{group_id}")
async def get_group(group_id: str):
    return await service.groups.find_by_id(group_id)


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


@router.get("/users/search")
async def search_users(q: str, request: Request):
    """Search for users by username."""
    current_user_id = request.state.user.get("_id")
    return await service.users.search_by_username(q, exclude_id=current_user_id)


@router.get("/users")
async def list_all_users(request: Request):
    """List all users on the platform, excluding the current user."""
    return await service.users.list_all()
