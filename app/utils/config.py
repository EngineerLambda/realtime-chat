from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    """Simple settings object reading from environment. We avoid pydantic here to be
    tolerant of extra environment variables that some platforms provide (DATABASE_URL,
    JWT_SECRET_KEY, etc.)."""

    def __init__(self) -> None:
        self.app_name: str = os.getenv("APP_NAME", "realtime-chat")
        self.debug: bool = str(os.getenv("DEBUG", "True")).lower() in ("1", "true", "yes")
        # support several common env names
        self.mongo_uri: str = os.getenv("DATABASE_URL") or os.getenv("MONGO_URI") or "mongodb://localhost:27017"
        self.mongo_db: str = os.getenv("MONGO_DB") or "realtime_chat"
        self.jwt_secret: str = os.getenv("JWT_SECRET_KEY") or os.getenv("JWT_SECRET") or "changeme_in_prod"
        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM") or "HS256"

        # access token expiry: prefer explicit seconds, otherwise support days env var
        if os.getenv("ACCESS_TOKEN_EXPIRES_SECONDS"):
            self.access_token_expires_seconds = int(os.getenv("ACCESS_TOKEN_EXPIRES_SECONDS"))
        elif os.getenv("ACCESS_TOKEN_EXPIRE_DAYS"):
            self.access_token_expires_seconds = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS")) * 24 * 3600
        else:
            self.access_token_expires_seconds = 60 * 15

        self.refresh_token_expires_seconds = int(os.getenv("REFRESH_TOKEN_EXPIRES_SECONDS") or 60 * 60 * 24 * 7)


settings = Settings()
