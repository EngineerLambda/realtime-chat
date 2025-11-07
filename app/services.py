from .database import UserRepository, SessionRepository, MessageRepository, GroupRepository, ConversationRepository
from .utils import hash_password, verify_password, create_access_token, normalize_doc
from datetime import datetime, timedelta
from .config import settings
from typing import Optional
from bson import ObjectId


class AuthService:
    def __init__(self):
        self.users = UserRepository()
        self.sessions = SessionRepository()

    async def signup(self, username: str, email: str, password: str) -> dict:
        existing = await self.users.find_by_email(email)
        if existing:
            raise ValueError("email_taken")
        user = {"username": username, "email": email, "password_hash": hash_password(password)}
        return await self.users.create(user)

    async def login(self, email: str, password: str) -> dict:
        user = await self.users.find_by_email(email)
        # user now has ObjectId converted to strings by repository normalize_doc
        if not user or not verify_password(password, user.get("password_hash", "")):
            raise ValueError("invalid_credentials")

        access = create_access_token(str(user["_id"]))
        refresh = create_access_token(str(user["_id"]), expires_delta=settings.refresh_token_expires_seconds)
        session = {"user_id": user["_id"], "refresh_token": refresh, "expires_at": datetime.utcnow() + timedelta(seconds=settings.refresh_token_expires_seconds)}
        await self.sessions.create(session)

        # sanitize user before returning (remove password hash)
        user_sanitized = dict(user)
        user_sanitized.pop("password_hash", None)
        return {"access_token": access, "refresh_token": refresh, "user": user_sanitized}

    async def refresh(self, refresh_token: str) -> dict:
        session = await self.sessions.find_by_refresh(refresh_token)
        if not session:
            raise ValueError("invalid_refresh")
        user_id = session["user_id"]
        access = create_access_token(str(user_id))
        return {"access_token": access}

    async def logout(self, refresh_token: str):
        await self.sessions.delete(refresh_token)


class ChatService:
    def __init__(self):
        self.msgs = MessageRepository()
        self.groups = GroupRepository()
        self.users = UserRepository()
        self.convs = ConversationRepository()

    async def create_dm(self, user_a: str, user_b: str) -> dict:
        print(f"Creating or retrieving DM between {user_a} and {user_b}")  # Debug log
        existing = await self.convs.find_dm_between(user_a, user_b)
        ids = sorted([user_a, user_b])
        room_id = f"dm:{ids[0]}-{ids[1]}"
        if existing:
            print(f"Existing DM found: {existing}")  # Debug log
            existing["room_id"] = room_id
            return existing
        doc = {"participant_ids": ids, "type": "dm"}
        created = await self.convs.create(doc)
        created["room_id"] = room_id
        print(f"New DM created: {created}")  # Debug log
        return created

    async def list_user_chats(self, user_id: str):
        print(f"Listing chats for user {user_id}")  # Debug log
        groups = await self.groups.find_by_member(user_id)
        convs = await self.convs.find_by_participant(user_id)
        print(f"Groups found: {groups}")  # Debug log
        print(f"Conversations found: {convs}")  # Debug log
        
        # Process conversations to add room_id and display names
        processed_convs = []
        for c in convs:
            if c.get("type") == "dm":
                parts = c.get("participant_ids", [])
                if len(parts) == 2:
                    c["room_id"] = f"dm:{parts[0]}-{parts[1]}"
                    other_id = next((pid for pid in parts if pid != user_id), user_id)
                    if other_id:
                        other_user = await self.users.find_by_id(other_id)
                        if other_user:
                            c["participant_display_name"] = other_user.get("username")
            processed_convs.append(c)

        # Attach last_message for all processed chats
        for chat in processed_convs + groups:
            messages = chat.get("messages", [])
            if messages:
                chat["last_message"] = messages[-1]

        # Sort conversations and groups by last_message timestamp
        all_chats = processed_convs + groups
        all_chats.sort(key=lambda x: x.get("last_message", {}).get("created_at", datetime.min), reverse=True)

        print(f"Processed chats: {all_chats}")  # Debug log
        return {"groups": groups, "conversations": processed_convs}

    async def post_message(self, chat_id: str, sender_id: str, content: str, is_group: bool = False) -> dict:
        print(f"Posting message to chat {chat_id} by user {sender_id}")  # Debug log
        msg = {"sender_id": sender_id, "content": content, "created_at": datetime.utcnow()}
        user = await UserRepository().find_by_id(sender_id)
        if user:
            msg["sender_username"] = user.get("username")

        if is_group:
            group_id = chat_id.split(":")[-1]
            await self.groups.add_message(group_id, msg)
        else:
            conv = await self.convs.find_dm_between(*chat_id.split(":")[-1].split("-"))
            if conv:
                await self.convs.add_message(conv["_id"], msg)

        msg["chat_id"] = chat_id
        print(f"Message saved: {msg}")  # Debug log
        return normalize_doc(msg)

    async def get_history(self, chat_id: str, limit: int = 100):
        # This method is no longer needed as messages are embedded.
        # Kept for reference, but should be removed.
        return []
