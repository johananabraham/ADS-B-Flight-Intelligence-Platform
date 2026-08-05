"""Authentication API endpoints."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.user import User, UserRole
from ..schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
)
from ..auth.utils import (
    verify_password,
    get_password_hash,
    create_access_token,
)
from ..auth.dependencies import get_current_user, require_admin

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
    db.commit()
    db.refresh(db_user)

    return db_user


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: Session = Depends(get_db),
):
    """Login and get access token.

    Args:
        credentials: User login credentials
        db: Database session

    Returns:
        JWT access token and user data

    Raises:
        HTTPException: If credentials are invalid
    """
    # Get user by username
    user = db.query(User).filter(User.username == credentials.username).first()

    # Verify password
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create access token
    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


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
    current_user: User = Depends(get_current_user),
):
    """Logout the current user.

    Note: JWT tokens are stateless, so this endpoint is primarily for
    client-side cleanup. In production, consider implementing token
    blacklisting for enhanced security.

    Args:
        current_user: The authenticated user

    Returns:
        Success message
    """
    return {"message": "Successfully logged out"}
