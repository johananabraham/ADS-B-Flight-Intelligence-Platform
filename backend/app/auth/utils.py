"""Authentication utilities for JWT and password handling."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from ..core.config import get_settings
from ..schemas.auth import TokenData
from ..models.user import UserRole

settings = get_settings()

# New hashes avoid bcrypt's 72-byte input limit; existing bcrypt hashes still verify.
pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")
DUMMY_PASSWORD_HASH = pwd_context.hash("invalid-credential-timing-placeholder")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to compare against

    Returns:
        True if the password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plain password.

    Args:
        password: The plain text password to hash

    Returns:
        The hashed password
    """
    return pwd_context.hash(password)


def create_access_token(
    user_id: int,
    username: str,
    role: UserRole,
    session_id: str | None = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token.

    Args:
        user_id: The user's ID
        username: The user's username
        role: The user's role
        expires_delta: Optional custom expiration time

    Returns:
        The encoded JWT token
    """
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode = {
        "sub": str(user_id),
        "username": username,
        "role": role.value,
        "jti": session_id or str(uuid4()),
        "exp": expire,
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token to decode

    Returns:
        TokenData if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: int = int(payload.get("sub"))
        username: str = payload.get("username")
        role: str = payload.get("role")
        session_id: str = payload.get("jti")

        if user_id is None or username is None or role is None or not session_id:
            return None

        return TokenData(
            user_id=user_id,
            username=username,
            role=UserRole(role),
            session_id=session_id,
        )
    except (JWTError, TypeError, ValueError):
        return None
