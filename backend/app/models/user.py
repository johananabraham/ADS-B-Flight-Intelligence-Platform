from datetime import datetime, timezone
import enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
)

from ..core.database import Base


class UserRole(str, enum.Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # RBAC
    role = Column(
        SQLEnum(
            UserRole,
            values_callable=lambda enum_type: [item.value for item in enum_type],
            native_enum=False,
            length=16,
        ),
        default=UserRole.VIEWER,
        nullable=False,
    )
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


class AuthSession(Base):
    """Server-tracked browser session referenced by a signed JWT cookie."""

    __tablename__ = "auth_sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_auth_sessions_active", "user_id", "revoked_at"),)


class AuditEvent(Base):
    """Security-relevant action without credentials or request-body storage."""

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(64), nullable=False, index=True)
    success = Column(Boolean, nullable=False)
    actor_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_type = Column(String(64), nullable=True)
    target_id = Column(String(128), nullable=True)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
