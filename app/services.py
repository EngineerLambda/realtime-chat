from .repositories import UserRepository, SessionRepository, MessageRepository, GroupRepository
from .utils import hash_password, verify_password, create_access_token
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
        from .repositories import ConversationRepository
        self.convs = ConversationRepository()

    async def create_dm(self, user_a: str, user_b: str) -> dict:
        """Create or return an existing DM conversation document between two user ids.
        Returns the conversation document (with _id and participant_ids).
        Also provides a canonical room id string under `room_id` key: dm:<a>-<b>
        """
        # check existing
        existing = await self.convs.find_dm_between(user_a, user_b)
        ids = sorted([user_a, user_b])
        room_id = f"dm:{ids[0]}-{ids[1]}"
        if existing:
            existing["room_id"] = room_id
            return existing
        doc = {"participant_ids": ids, "type": "dm"}
        created = await self.convs.create(doc)
        created["room_id"] = room_id
        return created

    async def list_user_chats(self, user_id: str):
        """Return groups and conversations for a user.
        Returns {groups: [...], conversations: [...]} where conversations include room_id.
        """
        groups = await self.groups.find_by_member(user_id)
        convs = await self.convs.find_by_participant(user_id)
        # add computed room_id for each conversation (for DMs)
        out_convs = []
        for c in convs:
            if c.get("type") == "dm":
                parts = c.get("participant_ids", [])
                if len(parts) == 2:
                    c["room_id"] = f"dm:{parts[0]}-{parts[1]}"
            out_convs.append(c)
        # attach last message summary for each conversation and group for sidebar preview
        from .repositories import UserRepository
        user_repo = UserRepository()
        # attach last message for convs
        for c in out_convs:
            room_id = c.get("room_id")
            if room_id:
                last = await self.msgs.list_for_chat(room_id, 1)
                if last:
                    m = last[0]
                    # try to attach sender username
                    sender_id = m.get("sender_id")
                    if sender_id:
                        u = await user_repo.find_by_id(sender_id)
                        m["sender_username"] = u.get("username") if u else None
                    c["last_message"] = m
        # attach last message for groups
        out_groups = []
        for g in groups:
            chat_id = f"group:{g.get('_id')}"
            last = await self.msgs.list_for_chat(chat_id, 1)
            if last:
                m = last[0]
                sender_id = m.get("sender_id")
                if sender_id:
                    u = await user_repo.find_by_id(sender_id)
                    m["sender_username"] = u.get("username") if u else None
                g["last_message"] = m
            out_groups.append(g)

        return {"groups": out_groups, "conversations": out_convs}

    async def post_message(self, chat_id: str, sender_id: str, content: str, is_group: bool = False) -> dict:
        msg = {"chat_id": chat_id, "sender_id": ObjectId(sender_id), "content": content, "is_group": is_group}
        created = await self.msgs.create(msg)
        # enrich with sender username for client convenience
        from .repositories import UserRepository
        user = await UserRepository().find_by_id(sender_id)
        if user:
            created["sender_username"] = user.get("username")
        else:
            created["sender_username"] = None
        return created

    async def get_history(self, chat_id: str, limit: int = 100):
        msgs = await self.msgs.list_for_chat(chat_id, limit)
        # attach sender usernames
        from .repositories import UserRepository
        user_repo = UserRepository()
        out = []
        for m in msgs:
            sender_id = m.get("sender_id")
            if sender_id:
                user = await user_repo.find_by_id(sender_id)
                m["sender_username"] = user.get("username") if user else None
            else:
                m["sender_username"] = None
            out.append(m)
        return out
