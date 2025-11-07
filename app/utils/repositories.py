from .db import connect
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Optional, List, Any
from .utils import normalize_doc


class UserRepository:
    def __init__(self):
        self._db = connect()
        self.col = self._db["users"]

    async def create(self, user: dict) -> dict:
        user["created_at"] = datetime.utcnow()
        r = await self.col.insert_one(user)
        doc = await self.col.find_one({"_id": r.inserted_id})
        return normalize_doc(doc)

    async def find_by_email(self, email: str) -> Optional[dict]:
        doc = await self.col.find_one({"email": email})
        return normalize_doc(doc)

    async def find_by_id(self, _id: str) -> Optional[dict]:
        doc = await self.col.find_one({"_id": ObjectId(_id)})
        return normalize_doc(doc)

    async def list_all(self) -> List[dict]:
        cursor = self.col.find({})
        return [normalize_doc(user) async for user in cursor]


class SessionRepository:
    def __init__(self):
        self._db = connect()
        self.col = self._db["sessions"]

    async def create(self, session: dict) -> dict:
        session["created_at"] = datetime.utcnow()
        r = await self.col.insert_one(session)
        doc = await self.col.find_one({"_id": r.inserted_id})
        return normalize_doc(doc)

    async def find_by_refresh(self, token: str) -> Optional[dict]:
        doc = await self.col.find_one({"refresh_token": token})
        return normalize_doc(doc)

    async def delete(self, token: str):
        await self.col.delete_one({"refresh_token": token})


class MessageRepository:
    def __init__(self):
        self._db = connect()
        self.col = self._db["messages"]

    async def create(self, message: dict) -> dict:
        message["created_at"] = datetime.utcnow()
        r = await self.col.insert_one(message)
        doc = await self.col.find_one({"_id": r.inserted_id})
        return normalize_doc(doc)

    async def list_for_chat(self, chat_id: str, limit: int = 100) -> List[dict]:
        cursor = self.col.find({"chat_id": chat_id}).sort("created_at", -1).limit(limit)
        return [normalize_doc(m) async for m in cursor]


class GroupRepository:
    def __init__(self):
        self._db = connect()
        self.col = self._db["groups"]

    async def create(self, group: dict) -> dict:
        group["created_at"] = datetime.utcnow()
        r = await self.col.insert_one(group)
        doc = await self.col.find_one({"_id": r.inserted_id})
        return normalize_doc(doc)

    async def find_by_id(self, _id: str) -> Optional[dict]:
        doc = await self.col.find_one({"_id": ObjectId(_id)})
        return normalize_doc(doc)

    async def find_by_member(self, user_id: str) -> List[Any]:
        # returns groups where `members` array contains the user_id
        cursor = self.col.find({"members": user_id}).sort("created_at", -1)
        return [normalize_doc(g) async for g in cursor]

    async def find_by_name(self, name: str) -> Optional[dict]:
        doc = await self.col.find_one({"name": name})
        return normalize_doc(doc)

    async def add_member(self, group_id: str, user_id: str):
        """Add a user to the group's members list if they are not already a member."""
        await self.col.update_one({"_id": ObjectId(group_id)}, {"$addToSet": {"members": user_id}})

    async def add_message(self, group_id: str, message: dict):
        """Add a message to the group's messages array."""
        message["created_at"] = datetime.utcnow()
        await self.col.update_one({"_id": ObjectId(group_id)}, {"$push": {"messages": message}})

    async def delete(self, group_id: str):
        """Delete a group by its ID."""
        await self.col.delete_one({"_id": ObjectId(group_id)})


class ConversationRepository:
    """Simple conversation store for DMs or other conversation metadata.
    Conversations documents schema (example):
      {"participant_ids": ["id1","id2"], "created_at": ..., "type": "dm"}
    """
    def __init__(self):
        self._db = connect()
        self.col = self._db["conversations"]

    async def create(self, conv: dict) -> dict:
        conv["created_at"] = datetime.utcnow()
        r = await self.col.insert_one(conv)
        doc = await self.col.find_one({"_id": r.inserted_id})
        return normalize_doc(doc)

    async def find_dm_between(self, a: str, b: str) -> Optional[dict]:
        # participant_ids stored as unordered array of strings
        # find conversation with exactly these two participants
        ids = sorted([a, b])
        doc = await self.col.find_one({"type": "dm", "participant_ids": ids})
        return normalize_doc(doc)

    async def find_by_participant(self, user_id: str) -> List[Any]:
        cursor = self.col.find({"participant_ids": user_id}).sort("created_at", -1)
        return [normalize_doc(c) async for c in cursor]

    async def find_by_id(self, _id: str) -> Optional[dict]:
        doc = await self.col.find_one({"_id": ObjectId(_id)})
        return normalize_doc(doc)
    
    async def search_by_username(self, query: str, limit: int = 20, exclude_id: str = None) -> List[Any]:
        """Search for users by username, case-insensitive."""
        # This method seems to be misplaced in ConversationRepository. It should be in UserRepository.
        # For now, I'll just fix the import path for it to work.
        user_col = self._db["users"]
        find_filter = {"username": {"$regex": query, "$options": "i"}}
        if exclude_id:
            find_filter["_id"] = {"$ne": ObjectId(exclude_id)}
        cursor = user_col.find(find_filter).limit(limit)
        return [normalize_doc(u, exclude={"password_hash"}) async for u in cursor] # type: ignore

    async def add_message(self, conv_id: str, message: dict):
        """Add a message to the conversation.
        This assumes the conversation document has a `messages` array.
        """
        message["created_at"] = datetime.utcnow()
        result = await self.col.update_one(
            {"_id": ObjectId(conv_id)},
            {"$push": {"messages": message}}
        )
        return result.modified_count > 0

    async def delete(self, conv_id: str):
        """Delete a conversation by its ID."""
        await self.col.delete_one({"_id": ObjectId(conv_id)})
