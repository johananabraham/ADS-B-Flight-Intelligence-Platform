"""Tests for authentication and authorization."""
import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole
from app.auth.utils import get_password_hash, create_access_token, decode_token, verify_password
from app.schemas.auth import TokenData

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_auth.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    # Only create the users table for auth tests to avoid GeoAlchemy2/SQLite issues
    User.__table__.create(bind=engine, checkfirst=True)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        User.__table__.drop(bind=engine, checkfirst=True)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with test database."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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
def admin_token(admin_user):
    """Create a valid admin token."""
    return create_access_token(
        user_id=admin_user.id,
        username=admin_user.username,
        role=admin_user.role,
    )


@pytest.fixture
def operator_token(operator_user):
    """Create a valid operator token."""
    return create_access_token(
        user_id=operator_user.id,
        username=operator_user.username,
        role=operator_user.role,
    )


@pytest.fixture
def viewer_token(viewer_user):
    """Create a valid viewer token."""
    return create_access_token(
        user_id=viewer_user.id,
        username=viewer_user.username,
        role=viewer_user.role,
    )


# ==================== Utility Tests ====================


def test_password_hashing():
    """Test password hashing and verification."""
    password = "testpassword123"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


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


# ==================== Login Tests ====================


def test_login_success(client, admin_user):
    """Test successful login."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "adminpass123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"


def test_login_wrong_password(client, admin_user):
    """Test login with wrong password."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrongpassword"},
    )

    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_login_nonexistent_user(client):
    """Test login with non-existent user."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "nonexistent", "password": "password"},
    )

    assert response.status_code == 401


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
    )

    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


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
        headers={"Authorization": f"Bearer {operator_token}"},
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
        headers={"Authorization": f"Bearer {admin_token}"},
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
        headers={"Authorization": f"Bearer {admin_token}"},
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
        headers={"Authorization": f"Bearer {admin_token}"},
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


# ==================== Protected Endpoint Tests ====================


def test_replay_command_requires_auth(client):
    """Test that replay commands require authentication."""
    response = client.post(
        "/api/v1/replay/commands",
        json={"action": "pause"},
    )
    assert response.status_code == 401  # No credentials


def test_replay_command_requires_operator_role(client, viewer_token):
    """Test that replay commands require operator or admin role."""
    response = client.post(
        "/api/v1/replay/commands",
        json={"action": "pause"},
        headers={"Authorization": f"Bearer {viewer_token}"},
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
        headers={"Authorization": f"Bearer {admin_token}"},
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
        headers={"Authorization": f"Bearer {operator_token}"},
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
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403


# ==================== Logout Tests ====================


def test_logout(client, admin_token):
    """Test logout endpoint."""
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert "Successfully logged out" in response.json()["message"]
