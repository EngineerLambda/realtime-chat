from .db import connect
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Optional, List
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

    async def find_by_member(self, user_id: str) -> List[dict]:
        # returns groups where `members` array contains the user_id
        cursor = self.col.find({"members": user_id}).sort("created_at", -1)
        return [normalize_doc(g) async for g in cursor]


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

    async def find_by_participant(self, user_id: str) -> List[dict]:
        cursor = self.col.find({"participant_ids": user_id}).sort("created_at", -1)
        return [normalize_doc(c) async for c in cursor]

    async def find_by_id(self, _id: str) -> Optional[dict]:
        doc = await self.col.find_one({"_id": ObjectId(_id)})
        return normalize_doc(doc)
