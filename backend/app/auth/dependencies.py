"""FastAPI dependencies for authentication and authorization."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.config import get_settings
from ..models.user import AuthSession, User, UserRole
from ..schemas.auth import TokenData
from .utils import decode_token

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Resolve a live server session from cookie or API bearer compatibility.

    Args:
        credentials: Optional bearer credentials for non-browser API clients
        db: Database session

    Returns:
        The authenticated User object

    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token is None and credentials is not None:
        token = credentials.credentials
    if token is None:
        raise credentials_exception

    token_data: Optional[TokenData] = decode_token(token)
    if token_data is None:
        raise credentials_exception

    session = (
        db.query(AuthSession)
        .filter(AuthSession.id == token_data.session_id)
        .first()
    )
    now = datetime.now(timezone.utc)
    if (
        session is None
        or session.user_id != token_data.user_id
        or session.revoked_at is not None
        or _utc(session.expires_at) <= now
    ):
        raise credentials_exception

    # Get the user from database
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise credentials_exception

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    request.state.auth_session_id = session.id
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get the current active user.

    Args:
        current_user: The current authenticated user

    Returns:
        The current active user

    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return current_user


def require_role(*allowed_roles: UserRole):
    """Create a dependency that requires specific roles.

    Args:
        *allowed_roles: One or more UserRole values that are allowed

    Returns:
        A dependency function that checks user role

    Example:
        @router.get("/admin")
        async def admin_endpoint(user: User = Depends(require_role(UserRole.ADMIN))):
            ...
    """

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {', '.join([r.value for r in allowed_roles])}",
            )
        return current_user

    return role_checker


# Common role dependencies
require_admin = require_role(UserRole.ADMIN)
require_operator = require_role(UserRole.ADMIN, UserRole.OPERATOR)
require_viewer = require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)
