from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from datetime import timedelta
import logging
from ..utils.utils import normalize_doc

logger = logging.getLogger(__name__)
from pydantic import BaseModel
from ..services.auth_service import AuthService
from ..utils.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
auth = AuthService()


class SignupPayload(BaseModel):
    username: str
    email: str
    password: str


class LoginPayload(BaseModel):
    email: str
    password: str


@router.post("/signup")
async def signup(payload: SignupPayload):
    try:
        user = await auth.signup(payload.username, payload.email, payload.password)
        return {"user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login(payload: LoginPayload):
    try:
        r = await auth.login(payload.email, payload.password)
        # debug: ensure we are returning JSON-serializable data
        try:
            logger.debug("login response types: %s", {k: type(v).__name__ for k, v in r.items()})
        except Exception:
            pass
        # set tokens as secure, https-only cookies (access token short-lived, refresh longer)
        resp = JSONResponse(content=normalize_doc(r, exclude={"password_hash"}))
        access_max_age = int(getattr(settings, "access_token_expires_seconds", 15 * 60))
        refresh_max_age = int(getattr(settings, "refresh_token_expires_seconds", 7 * 24 * 3600))
        # Set HttpOnly cookies for tokens with SameSite=None for cross-origin requests
        resp.set_cookie("access_token", r.get("access_token"), max_age=access_max_age, secure=not settings.debug, httponly=True, samesite="lax")
        resp.set_cookie("refresh_token", r.get("refresh_token"), max_age=refresh_max_age, secure=not settings.debug, httponly=True, samesite="lax")
        # user id available to JS (not HttpOnly) so UI can show current user; keep it minimal
        user = r.get("user") or {}
        if user and user.get("_id"):
            resp.set_cookie("user_id", user.get("_id"), max_age=access_max_age, secure=not settings.debug, httponly=False, samesite="lax")
        return resp
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


class RefreshPayload(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh(payload: RefreshPayload):
    try:
        return await auth.refresh(payload.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


class LogoutPayload(BaseModel):
    refresh_token: str


@router.post("/logout")
async def logout(payload: LogoutPayload = None, request: Request = None):
    # accept refresh token either from payload or from cookie
    token = None
    if payload and getattr(payload, 'refresh_token', None):
        token = payload.refresh_token
    if not token and request:
        token = request.cookies.get('refresh_token')
    if token:
        await auth.logout(token)
    # clear cookies on logout
    resp = JSONResponse(content={"ok": True})
    resp.delete_cookie('access_token', secure=not settings.debug, httponly=True, samesite="lax")
    resp.delete_cookie('refresh_token', secure=not settings.debug, httponly=True, samesite="lax")
    resp.delete_cookie('user_id', secure=not settings.debug, httponly=False, samesite="lax")
    return resp
