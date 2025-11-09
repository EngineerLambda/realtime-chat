from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
import logging
from ..utils.utils import normalize_doc
from ..utils.models import (
    SignupPayload,
    LoginPayload,
    ForgotPasswordPayload,
    ResendOTPPayload,
    ResetPasswordPayload,
    RefreshPayload,
    LogoutPayload,
)

logger = logging.getLogger(__name__)
from ..services.auth_service import AuthService
from ..utils.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
auth = AuthService()


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


@router.post("/refresh")
async def refresh(payload: RefreshPayload):
    try:
        return await auth.refresh(payload.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


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


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordPayload):
    try:
        await auth.request_password_reset(payload.email)
        # Always return a success message to prevent user enumeration
        return {"message": "If an account with that email exists, a password reset OTP has been sent."}
    except ConnectionError as e:
        if str(e) == "email_service_not_configured":
            raise HTTPException(status_code=503, detail="Email service is not configured.")
        else:
            raise HTTPException(status_code=500, detail="Failed to send email.")


@router.post("/resend-otp")
async def resend_otp(payload: ResendOTPPayload):
    """Resends the OTP for password reset."""
    try:
        # Re-using the same logic as forgot-password is correct here
        await auth.request_password_reset(payload.email)
        return {"message": "A new password reset OTP has been sent to your email."}
    except ConnectionError as e:
        if str(e) == "email_service_not_configured":
            raise HTTPException(status_code=503, detail="Email service is not configured.")
        else:
            raise HTTPException(status_code=500, detail="Failed to send email.")


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordPayload):
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    try:
        await auth.reset_password(payload.email, payload.otp_code, payload.new_password)
        return {"message": "Password has been reset successfully. You can now log in."}
    except ValueError as e:
        error_detail = "An error occurred."
        error_map = {
            "invalid_user": "Invalid user. Please check the email and try again.",
            "invalid_otp": "The OTP you entered is incorrect.",
            "expired_otp": "The OTP has expired. Please request a new one.",
        }
        error_detail = error_map.get(str(e), error_detail)
        raise HTTPException(status_code=400, detail=error_detail)
    except Exception:
        raise HTTPException(status_code=500, detail="An unexpected error occurred during password reset.")
