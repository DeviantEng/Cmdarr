"""Auth API: login, logout, setup, status"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.auth import (
    generate_api_key,
    is_setup_required,
    require_auth,
    set_api_key_from_plain,
    verify_login,
)
from services.config_service import config_service

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class SetupRequest(BaseModel):
    username: str
    password: str


class AuthStatusResponse(BaseModel):
    setup_required: bool
    authenticated: bool
    username: str | None


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(request: Request):
    """Check if setup is needed, and if current request is authenticated."""
    setup_required = is_setup_required()
    if setup_required:
        return AuthStatusResponse(
            setup_required=True,
            authenticated=False,
            username=None,
        )

    session_id = request.cookies.get("cmdarr_session")
    sessions = getattr(request.app.state, "sessions", {})
    username = sessions.get(session_id) if session_id else None

    return AuthStatusResponse(
        setup_required=False,
        authenticated=username is not None,
        username=username,
    )


@router.post("/setup")
async def setup(request: Request, body: SetupRequest, response: Response):
    """First-run setup: create username and password."""
    if not is_setup_required():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setup already completed",
        )
    if not body.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")
    if not body.password:
        raise HTTPException(status_code=400, detail="Password is required")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    from app.auth import _hash_password

    config_service.set("CMDARR_AUTH_USERNAME", body.username.strip())
    config_service.set("CMDARR_AUTH_PASSWORD_HASH", _hash_password(body.password))

    # Create session
    session_id = secrets.token_urlsafe(32)
    if not hasattr(request.app.state, "sessions"):
        request.app.state.sessions = {}
    request.app.state.sessions[session_id] = body.username.strip()

    response.set_cookie(
        key="cmdarr_session",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,  # 7 days
    )
    return {"message": "Setup complete", "username": body.username.strip()}


@router.post("/login")
async def login(request: Request, body: LoginRequest, response: Response):
    """Login with username and password."""
    if is_setup_required():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setup required first",
        )
    if not verify_login(body.username, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    session_id = secrets.token_urlsafe(32)
    if not hasattr(request.app.state, "sessions"):
        request.app.state.sessions = {}
    request.app.state.sessions[session_id] = body.username

    response.set_cookie(
        key="cmdarr_session",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,  # 7 days
    )
    return {"message": "Logged in", "username": body.username}


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout and clear session."""
    session_id = request.cookies.get("cmdarr_session")
    if session_id and hasattr(request.app.state, "sessions"):
        request.app.state.sessions.pop(session_id, None)
    response.delete_cookie("cmdarr_session")
    return {"message": "Logged out"}


@router.post("/generate-api-key")
async def generate_api_key_endpoint(username: str = Depends(require_auth)):
    """Generate a new API key. Returns plain key once; store it securely."""
    plain_key = generate_api_key()
    set_api_key_from_plain(plain_key)
    return {
        "api_key": plain_key,
        "message": "API key generated. Store it securely; it will not be shown again.",
    }
