from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt
from .config import settings
from typing import Any
from bson import ObjectId

def normalize_doc(obj: Any, exclude: set[str] | None = None) -> Any:
    """Recursively convert ObjectId to str in documents returned from Motor.
    Optionally exclude keys (e.g. password_hash) by name.
    """
    if exclude is None:
        exclude = set()

    if obj is None:
        return None
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in exclude:
                continue
            out[k] = normalize_doc(v, exclude)
        return out
    if isinstance(obj, list):
        return [normalize_doc(x, exclude) for x in obj]
    if isinstance(obj, ObjectId):
        return str(obj)
    # convert datetimes to ISO strings for JSON serialization
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


def create_access_token(subject: str, expires_delta: int | None = None) -> str:
    expire = datetime.utcnow() + timedelta(seconds=expires_delta or settings.access_token_expires_seconds)
    to_encode = {"sub": subject, "exp": expire.timestamp()}
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
