"""Explicit one-shot administrator bootstrap for interactive and automated installs."""

from __future__ import annotations

import argparse
import getpass
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .audit import record_audit_event
from .utils import get_password_hash
from ..core.config import get_settings
from ..models.user import User, UserRole


def create_admin(username: str, email: str, password: str) -> bool:
    """Create the first administrator without publishing default credentials."""
    if not username.strip() or not email.strip() or len(password) < 12:
        print("Error: username, email, and a password of at least 12 characters are required.")
        return False

    engine = create_engine(get_settings().database_url)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    try:
        existing = (
            db.query(User)
            .filter((User.username == username) | (User.email == email))
            .first()
        )
        if existing:
            print("Error: the requested bootstrap username or email already exists.")
            return False

        admin = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        db.flush()
        record_audit_event(
            db,
            event_type="user.bootstrap_admin",
            success=True,
            actor_user_id=admin.id,
            target_type="user",
            target_id=str(admin.id),
            details={"role": UserRole.ADMIN.value},
        )
        db.commit()
        print(f"Administrator {admin.username!r} created successfully.")
        return True
    except Exception as exc:
        db.rollback()
        print(f"Error creating administrator: {type(exc).__name__}")
        return False
    finally:
        db.close()
        engine.dispose()


def _interactive_credentials() -> tuple[str, str, str] | None:
    username = input("Enter admin username: ").strip()
    email = input("Enter admin email: ").strip()
    if not username or not email:
        print("Error: username and email are required.")
        return None
    while True:
        password = getpass.getpass("Enter admin password: ")
        if len(password) < 12:
            print("Error: admin password must be at least 12 characters long.")
            continue
        if password != getpass.getpass("Confirm password: "):
            print("Error: passwords do not match.")
            continue
        return username, email, password


def _environment_credentials() -> tuple[str, str, str] | None:
    names = (
        "ADSB_BOOTSTRAP_USERNAME",
        "ADSB_BOOTSTRAP_EMAIL",
        "ADSB_BOOTSTRAP_PASSWORD",
    )
    username, email, password = (os.environ.get(name, "") for name in names)
    if not username or not email or not password:
        print(f"Error: --from-env requires {', '.join(names)}.")
        return None
    return username, email, password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-env",
        action="store_true",
        help="read explicit credentials from ADSB_BOOTSTRAP_* variables",
    )
    args = parser.parse_args(argv)
    credentials = (
        _environment_credentials() if args.from_env else _interactive_credentials()
    )
    if credentials is None:
        return 1
    return 0 if create_admin(*credentials) else 1


if __name__ == "__main__":
    raise SystemExit(main())
