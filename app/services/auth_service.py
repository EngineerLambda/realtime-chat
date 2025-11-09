from ..utils.repositories import UserRepository, SessionRepository
from ..utils.utils import hash_password, verify_password, create_access_token
from datetime import datetime, timedelta
from .email_service import generate_otp, send_otp_email, send_confirmation_email, smtp_is_configured
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

    async def request_password_reset(self, email: str):
        if not smtp_is_configured():
            raise ConnectionError("email_service_not_configured")
        
        user = await self.users.find_by_email(email)
        if not user:
            # Don't reveal if user exists, just return success
            print(f"Password reset requested for non-existent user: {email}")
            return

        otp_code = generate_otp()
        otp_ttl_minutes = 10
        otp_expires = datetime.utcnow() + timedelta(minutes=otp_ttl_minutes)
        
        await self.users.update(user["_id"], {"otp_code": otp_code, "otp_expires": otp_expires})
        
        email_sent = send_otp_email(email, otp_code, otp_ttl_minutes)
        if not email_sent:
            raise ConnectionError("failed_to_send_email")

    async def reset_password(self, email: str, otp_code: str, new_password: str):
        user = await self.users.find_by_email(email)
        if not user:
            raise ValueError("invalid_user")

        stored_otp = user.get("otp_code")
        otp_expires = user.get("otp_expires")

        if not stored_otp or stored_otp != otp_code:
            raise ValueError("invalid_otp")

        if not otp_expires or datetime.utcnow() > datetime.fromisoformat(otp_expires):
            raise ValueError("expired_otp")

        await self.users.update(user["_id"], {"password_hash": hash_password(new_password), "otp_code": None, "otp_expires": None})
        send_confirmation_email(user_email=email, purpose="password")