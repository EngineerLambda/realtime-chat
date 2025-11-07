from ..utils.repositories import UserRepository, SessionRepository
from ..utils.utils import hash_password, verify_password, create_access_token
from datetime import datetime, timedelta
from ..utils.config import settings


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