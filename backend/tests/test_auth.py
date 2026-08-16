"""Tests for cookie sessions, revocation, CSRF defense, and RBAC."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.bootstrap import create_admin
from app.auth.rate_limiter import rate_limiter
from app.auth.utils import (
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.core.config import Settings
from app.core.database import get_db
from app.main import app
from app.models.user import AuditEvent, AuthSession, User, UserRole

ORIGIN = "http://localhost:5173"
ORIGIN_HEADERS = {"Origin": ORIGIN}
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    for table in (User.__table__, AuthSession.__table__, AuditEvent.__table__):
        table.create(bind=engine, checkfirst=True)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        for table in (AuditEvent.__table__, AuthSession.__table__, User.__table__):
            table.drop(bind=engine, checkfirst=True)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with test database."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    rate_limiter.request_history.clear()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _session_token(db_session, user: User, **session_overrides) -> str:
    session_id = str(uuid4())
    expires_at = session_overrides.pop(
        "expires_at", datetime.now(timezone.utc) + timedelta(hours=1)
    )
    db_session.add(
        AuthSession(
            id=session_id,
            user_id=user.id,
            expires_at=expires_at,
            **session_overrides,
        )
    )
    db_session.commit()
    return create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        session_id=session_id,
        expires_delta=expires_at - datetime.now(timezone.utc),
    )


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing."""
    user = User(
        username="admin",
        email="admin@test.com",
        hashed_password=get_password_hash("adminpass123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def operator_user(db_session):
    """Create an operator user for testing."""
    user = User(
        username="operator",
        email="operator@test.com",
        hashed_password=get_password_hash("operatorpass123"),
        role=UserRole.OPERATOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def viewer_user(db_session):
    """Create a viewer user for testing."""
    user = User(
        username="viewer",
        email="viewer@test.com",
        hashed_password=get_password_hash("viewerpass123"),
        role=UserRole.VIEWER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user, db_session):
    """Create a valid admin token."""
    return _session_token(db_session, admin_user)


@pytest.fixture
def operator_token(operator_user, db_session):
    """Create a valid operator token."""
    return _session_token(db_session, operator_user)


@pytest.fixture
def viewer_token(viewer_user, db_session):
    """Create a valid viewer token."""
    return _session_token(db_session, viewer_user)


# ==================== Utility Tests ====================


def test_password_hashing():
    """Test password hashing and verification."""
    password = "testpassword123"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_password_hashing_accepts_more_than_bcrypts_72_byte_limit():
    password = "long-password-" * 8
    hashed = get_password_hash(password)
    assert hashed.startswith("$bcrypt-sha256$")
    assert verify_password(password, hashed) is True


def test_create_and_decode_token(admin_user):
    """Test JWT token creation and decoding."""
    token = create_access_token(
        user_id=admin_user.id,
        username=admin_user.username,
        role=admin_user.role,
    )

    assert isinstance(token, str)

    decoded = decode_token(token)
    assert decoded is not None
    assert decoded.user_id == admin_user.id
    assert decoded.username == admin_user.username
    assert decoded.role == UserRole.ADMIN
    assert decoded.session_id


def test_decode_invalid_token():
    """Test decoding an invalid token."""
    decoded = decode_token("invalid.token.here")
    assert decoded is None


def test_token_expiration():
    """Test that expired tokens are rejected."""
    expired_token = create_access_token(
        user_id=1,
        username="test",
        role=UserRole.VIEWER,
        expires_delta=timedelta(seconds=-1),  # Expired 1 second ago
    )

    decoded = decode_token(expired_token)
    assert decoded is None  # Expired tokens should not decode


def test_production_requires_explicit_strong_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(_env_file=None, environment="production")
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret_key="too-short",
            cors_allowed_origins="https://example.test",
        )


def test_production_rejects_wildcard_origin():
    with pytest.raises(ValidationError, match="CORS_ALLOWED_ORIGINS"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret_key="a" * 32,
            cors_allowed_origins="*",
        )


# ==================== Login Tests ====================


def test_login_success(client, admin_user):
    """Test successful login."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "adminpass123"},
        headers=ORIGIN_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" not in data
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"
    cookie = response.headers["set-cookie"]
    assert "adsb_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Max-Age=28800" in cookie


def test_login_wrong_password(client, admin_user):
    """Test login with wrong password."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrongpassword"},
        headers=ORIGIN_HEADERS,
    )

    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_login_nonexistent_user(client):
    """Test login with non-existent user."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "nonexistent", "password": "password"},
        headers=ORIGIN_HEADERS,
    )

    assert response.status_code == 401


def test_login_audit_does_not_store_password_or_token(client, db_session):
    secret = "never-store-this-password"
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "missing", "password": secret},
        headers=ORIGIN_HEADERS,
    )
    assert response.status_code == 401
    event = db_session.query(AuditEvent).one()
    serialized = f"{event.target_id}{event.details}"
    assert event.event_type == "auth.login"
    assert event.success is False
    assert secret not in serialized
    assert "token" not in serialized.lower()


def test_login_inactive_user(client, db_session):
    """Test login with inactive user."""
    inactive_user = User(
        username="inactive",
        email="inactive@test.com",
        hashed_password=get_password_hash("password123"),
        role=UserRole.VIEWER,
        is_active=False,
    )
    db_session.add(inactive_user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "inactive", "password": "password123"},
        headers=ORIGIN_HEADERS,
    )

    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


def test_login_rate_limit_returns_429_response(client):
    for _ in range(rate_limiter.login_requests_per_minute):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "missing", "password": "not-the-password"},
            headers=ORIGIN_HEADERS,
        )
        assert response.status_code == 401

    limited = client.post(
        "/api/v1/auth/login",
        json={"username": "missing", "password": "not-the-password"},
        headers=ORIGIN_HEADERS,
    )
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"
    assert limited.headers["x-ratelimit-remaining"] == "0"


def test_bootstrap_rejects_invalid_email_before_database_access():
    assert create_admin("valid-name", "admin@example.invalid", "long-enough-password") is False


# ==================== Registration Tests ====================


def test_register_requires_admin(client, operator_token):
    """Test that registration requires admin role."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@test.com",
            "password": "password123",
            "role": "viewer",
        },
        headers={**ORIGIN_HEADERS, "Authorization": f"Bearer {operator_token}"},
    )

    assert response.status_code == 403


def test_register_success(client, admin_token):
    """Test successful user registration by admin."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@test.com",
            "password": "password123",
            "role": "viewer",
        },
        headers={**ORIGIN_HEADERS, "Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@test.com"
    assert data["role"] == "viewer"


def test_register_duplicate_username(client, admin_token, admin_user):
    """Test registration with duplicate username."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "admin",  # Already exists
            "email": "different@test.com",
            "password": "password123",
            "role": "viewer",
        },
        headers={**ORIGIN_HEADERS, "Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]


def test_register_duplicate_email(client, admin_token, admin_user):
    """Test registration with duplicate email."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "different",
            "email": "admin@test.com",  # Already exists
            "password": "password123",
            "role": "viewer",
        },
        headers={**ORIGIN_HEADERS, "Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


# ==================== Current User Tests ====================


def test_get_current_user(client, admin_token, admin_user):
    """Test getting current user information."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"


def test_get_current_user_no_token(client):
    """Test getting current user without token."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401  # No credentials


def test_get_current_user_invalid_token(client):
    """Test getting current user with invalid token."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


def test_login_cookie_authenticates_me(client, admin_user):
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "adminpass123"},
        headers=ORIGIN_HEADERS,
    )
    assert login.status_code == 200
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["id"] == admin_user.id


def test_revoked_session_is_rejected(client, admin_user, db_session):
    token = _session_token(
        db_session,
        admin_user,
        revoked_at=datetime.now(timezone.utc),
    )
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_expired_session_is_rejected(client, admin_user, db_session):
    token = _session_token(
        db_session,
        admin_user,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


# ==================== Protected Endpoint Tests ====================


def test_replay_command_requires_auth(client):
    """Test that replay commands require authentication."""
    response = client.post(
        "/api/v1/replay/commands",
        json={"action": "pause"},
        headers=ORIGIN_HEADERS,
    )
    assert response.status_code == 401  # No credentials


def test_state_change_rejects_missing_or_unapproved_origin(client):
    missing = client.post("/api/v1/replay/commands", json={"action": "pause"})
    unapproved = client.post(
        "/api/v1/replay/commands",
        json={"action": "pause"},
        headers={"Origin": "https://attacker.example"},
    )
    assert missing.status_code == 403
    assert unapproved.status_code == 403


def test_replay_command_requires_operator_role(client, viewer_token):
    """Test that replay commands require operator or admin role."""
    response = client.post(
        "/api/v1/replay/commands",
        json={"action": "pause"},
        headers={**ORIGIN_HEADERS, "Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403


# ==================== Role-Based Access Control Tests ====================


def test_admin_can_register_users(client, admin_token):
    """Test that admin can register new users."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@test.com",
            "password": "password123",
            "role": "viewer",
        },
        headers={**ORIGIN_HEADERS, "Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201


def test_operator_cannot_register_users(client, operator_token):
    """Test that operator cannot register new users."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@test.com",
            "password": "password123",
            "role": "viewer",
        },
        headers={**ORIGIN_HEADERS, "Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 403


def test_viewer_cannot_register_users(client, viewer_token):
    """Test that viewer cannot register new users."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@test.com",
            "password": "password123",
            "role": "viewer",
        },
        headers={**ORIGIN_HEADERS, "Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403


# ==================== Logout Tests ====================


def test_logout_revokes_session_and_clears_cookie(client, admin_token, db_session):
    """Test logout endpoint."""
    response = client.post(
        "/api/v1/auth/logout",
        headers={**ORIGIN_HEADERS, "Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert "Successfully logged out" in response.json()["message"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    decoded = decode_token(admin_token)
    assert decoded is not None
    session = db_session.get(AuthSession, decoded.session_id)
    assert session is not None and session.revoked_at is not None
    assert db_session.query(AuditEvent).filter_by(event_type="auth.logout").count() == 1
    denied = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert denied.status_code == 401
