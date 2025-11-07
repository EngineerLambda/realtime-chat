from .repositories import UserRepository, SessionRepository, MessageRepository, GroupRepository, ConversationRepository
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

    async def join_or_create_group_by_name(self, group_name: str, user_id: str) -> dict:
        """Finds a group by name or creates it if it doesn't exist. Adds user to members."""
        group = await self.groups.find_by_name(group_name)
        if group:
            # Group exists, ensure user is a member
            await self.groups.add_member(group["_id"], user_id)
            print(f"User {user_id} joined existing group '{group_name}'")
        else:
            # Group doesn't exist, create it with the user as the first member
            doc = {"name": group_name, "members": [user_id], "messages": []}
            group = await self.groups.create(doc)
            print(f"Created new group '{group_name}' for user {user_id}")
        return group

    async def list_user_chats(self, user_id: str):
        print(f"Listing chats for user {user_id}")  # Debug log
        groups = await self.groups.find_by_member(user_id)
        convs = await self.convs.find_by_participant(user_id)
        print(f"Groups found: {groups}")  # Debug log
        print(f"Conversations found: {convs}")  # Debug log
        
        # Process conversations (DMs)
        processed_convs = []
        for c in convs:
            if c.get("type") == "dm":
                parts = c.get("participant_ids", [])
                if len(parts) == 2:
                    c["room_id"] = f"dm:{parts[0]}-{parts[1]}"
                    other_id = next((pid for pid in parts if pid != user_id), None)
                    other_user = await self.users.find_by_id(other_id) if other_id else None
                    c["participant_display_name"] = other_user.get("username") if other_user else "Unknown User"
                if c.get("messages"):
                    c["last_message"] = c["messages"][-1]
            processed_convs.append(c)

        # Process groups
        processed_groups = []
        for g in groups:
            g["room_id"] = f"group:{g['_id']}"
            if g.get("messages"):
                g["last_message"] = g["messages"][-1]
            processed_groups.append(g)

        # Sort both lists by last_message timestamp
        sorter = lambda x: datetime.fromisoformat(x.get("last_message", {}).get("created_at", datetime.min.isoformat()))
        processed_convs.sort(key=sorter, reverse=True)
        processed_groups.sort(key=sorter, reverse=True)

        return {"groups": processed_groups, "conversations": processed_convs}

    async def post_message(self, chat_id: str, sender_id: str, content: str, is_group: bool = False) -> dict:
        print(f"Posting message to chat {chat_id} by user {sender_id}")  # Debug log
        msg = {"sender_id": sender_id, "content": content, "created_at": datetime.utcnow()}
        user = await UserRepository().find_by_id(sender_id)
        if user:
            msg["sender_username"] = user.get("username")

        # Determine if it's a group, DM, or something else, and persist message.
        if chat_id.startswith("group:"):
            group_id = chat_id.split(":", 1)[1]
            if ObjectId.is_valid(group_id):
                await self.groups.add_message(group_id, msg)
        elif chat_id.startswith("dm:"):
            dm_ids_str = chat_id.split(":", 1)[1]
            dm_ids = dm_ids_str.split("-")
            if len(dm_ids) == 2:
                # find_dm_between expects sorted ids, but room_id is already sorted
                conv = await self.convs.find_dm_between(dm_ids[0], dm_ids[1])
                if conv:
                    await self.convs.add_message(conv["_id"], msg)
        # Note: Messages to rooms that are not valid groups or DMs will not be persisted.
        # This is the desired behavior to avoid saving messages to arbitrary/temporary rooms.
        
        msg["chat_id"] = chat_id
        print(f"Message saved: {msg}")  # Debug log
        return normalize_doc(msg)

    async def get_history(self, chat_id: str, limit: int = 100):
        # This method is no longer needed as messages are embedded.
        # Kept for reference, but should be removed.
        return []
