from fastapi import APIRouter, Depends
from ..services import ChatService
from typing import Optional
from ..deps import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["chat"])
service = ChatService()


@router.get("/history/{chat_id}")
async def history(chat_id: str, limit: Optional[int] = 100, user=Depends(get_current_user)):
    """Return message history for a chat (one-to-one or group). Requires auth."""
    return await service.get_history(chat_id, limit)


class CreateGroupPayload(BaseModel):
    name: str
    members: list[str]


@router.post("/groups")
async def create_group(payload: CreateGroupPayload, user=Depends(get_current_user)):
    # members should be list of user ids (strings)
    group = await service.groups.create({"name": payload.name, "members": payload.members})
    return group


@router.get("/groups/{group_id}")
async def get_group(group_id: str, user=Depends(get_current_user)):
    return await service.groups.find_by_id(group_id)


@router.get("/chats")
async def list_chats(user=Depends(get_current_user)):
    """List chats (groups and simple metadata) for the current user."""
    user_id = user.get("_id")
    return await service.list_user_chats(user_id)


@router.post("/dm/{other_id}")
async def create_dm(other_id: str, user=Depends(get_current_user)):
    """Create or return a DM conversation between the current user and other_id."""
    user_id = user.get("_id")
    conv = await service.create_dm(user_id, other_id)
    return conv
