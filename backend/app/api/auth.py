"""Authentication API endpoints."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..auth.audit import record_audit_event
from ..auth.dependencies import get_current_user, require_admin
from ..auth.utils import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    get_password_hash,
    verify_password,
)
from ..core.config import get_settings
from ..schemas.auth import (
    SessionResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from ..models.user import AuthSession, User

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),  # Only admins can create users
):
    """Register a new user (admin only).

    Args:
        user_data: User registration data
        db: Database session
        _: Current admin user (required)

    Returns:
        The created user

    Raises:
        HTTPException: If username or email already exists
    """
    # Check if username already exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email already exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        role=user_data.role,
    )

    db.add(db_user)
    db.flush()
    record_audit_event(
        db,
        event_type="user.created",
        success=True,
        actor_user_id=_.id,
        target_type="user",
        target_id=str(db_user.id),
        details={"role": db_user.role.value},
    )
    db.commit()
    db.refresh(db_user)

    return db_user


@router.post("/login", response_model=SessionResponse)
async def login(
    credentials: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    """Authenticate and create a revocable HttpOnly browser session.

    Args:
        credentials: User login credentials
        db: Database session

    Returns:
        User data; the signed token is returned only in the response cookie

    Raises:
        HTTPException: If credentials are invalid
    """
    # Get user by username
    user = db.query(User).filter(User.username == credentials.username).first()

    password_hash = user.hashed_password if user else DUMMY_PASSWORD_HASH
    password_valid = verify_password(credentials.password, password_hash)
    if not user or not password_valid:
        record_audit_event(
            db,
            event_type="auth.login",
            success=False,
            target_type="username",
            target_id=credentials.username,
            details={"reason": "invalid_credentials"},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        record_audit_event(
            db,
            event_type="auth.login",
            success=False,
            actor_user_id=user.id,
            target_type="user",
            target_id=str(user.id),
            details={"reason": "inactive"},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Update last login
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    session_id = str(uuid4())
    user.last_login = now.replace(tzinfo=None)
    db.add(
        AuthSession(
            id=session_id,
            user_id=user.id,
            created_at=now,
            expires_at=expires_at,
        )
    )
    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        session_id=session_id,
        expires_delta=expires_at - now,
    )
    record_audit_event(
        db,
        event_type="auth.login",
        success=True,
        actor_user_id=user.id,
        target_type="session",
        target_id=session_id,
    )
    db.commit()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/",
    )
    return SessionResponse(user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current user information.

    Args:
        current_user: The authenticated user

    Returns:
        The current user's information
    """
    return current_user


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke the current server session and clear its browser cookie.

    Args:
        current_user: The authenticated user

    Returns:
        Success message
    """
    settings = get_settings()
    session_id = request.state.auth_session_id
    session = db.query(AuthSession).filter(AuthSession.id == session_id).first()
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
    record_audit_event(
        db,
        event_type="auth.logout",
        success=True,
        actor_user_id=current_user.id,
        target_type="session",
        target_id=session_id,
    )
    db.commit()
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.is_production,
        httponly=True,
        samesite="strict",
    )
    return {"message": "Successfully logged out"}
