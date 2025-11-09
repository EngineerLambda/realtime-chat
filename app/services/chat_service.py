from ..utils.repositories import UserRepository, MessageRepository, GroupRepository, ConversationRepository
from ..utils.utils import normalize_doc
from datetime import datetime
from bson import ObjectId


class ChatService:
    def __init__(self):
        self.msgs = MessageRepository()
        self.groups = GroupRepository()
        self.users = UserRepository()
        self.convs = ConversationRepository()

    async def create_dm(self, user_a: str, user_b: str) -> dict:
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

    async def join_or_create_group_by_name(self, group_name: str, user_id: str) -> dict:
        """Finds a group by name or creates it if it doesn't exist. Adds user to members."""
        group = await self.groups.find_by_name(group_name)
        if group:
            # Group exists, ensure user is a member
            await self.groups.add_member(group["_id"], user_id)
        else:
            # Group doesn't exist, create it with the user as the first member
            doc = {"name": group_name, "members": [user_id], "messages": []}
            group = await self.groups.create(doc)
        return group

    async def list_user_chats(self, user_id: str):
        groups = await self.groups.find_by_member(user_id)
        convs = await self.convs.find_by_participant(user_id)
        
        # Process conversations (DMs)
        processed_convs = []
        for c in convs:
            if c.get("type") == "dm":
                parts = c.get("participant_ids", [])
                if len(parts) == 2:
                    c["room_id"] = f"dm:{parts[0]}-{parts[1]}"
                    other_id = next((pid for pid in parts if pid != user_id), None)
                    # If other_id is None, it's a DM with self.
                    if other_id is None and len(set(parts)) == 1:
                        other_id = user_id

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
        msg = {"sender_id": sender_id, "content": content, "created_at": datetime.utcnow()}
        user = await self.users.find_by_id(sender_id)
        if user:
            msg["sender_username"] = user.get("username")
        if chat_id.startswith("group:"):
            group_id = chat_id.split(":", 1)[1]
            if ObjectId.is_valid(group_id):
                await self.groups.add_message(group_id, msg)
        elif chat_id.startswith("dm:"):
            dm_ids_str = chat_id.split(":", 1)[1]
            dm_ids = dm_ids_str.split("-")
            if len(dm_ids) == 2:
                conv = await self.convs.find_dm_between(dm_ids[0], dm_ids[1])
                if conv:
                    await self.convs.add_message(conv["_id"], msg)
        msg["chat_id"] = chat_id
        return normalize_doc(msg)