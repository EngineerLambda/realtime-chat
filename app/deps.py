from fastapi import Depends, HTTPException, status, Header
from typing import Optional
from .utils import decode_token
from .repositories import UserRepository


async def get_current_user(authorization: Optional[str] = Header(None), cookie: Optional[str] = Header(None)):
    """Extract access token from Authorization header or cookie and return user dict or raise 401.
    This supports both Bearer Authorization headers and cookie-based access_token.
    """
    token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    # fallback: try cookie header which contains e.g. "access_token=...; other=..."
    if not token and cookie:
        # parse cookie header for access_token
        for part in cookie.split(";"):
            kv = part.strip().split("=", 1)
            if len(kv) == 2 and kv[0] == "access_token":
                token = kv[1]
                break

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = await UserRepository().find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
