#!/usr/bin/env python3
"""
Create an admin user for the Aviation Intelligence Platform.
This script should be run once during initial setup.
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.models.user import User, UserRole
from app.auth.utils import get_password_hash

settings = get_settings()


def create_admin(username: str, email: str, password: str):
    """Create an admin user."""
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # Check if user already exists
        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing:
            print(f"❌ User with username '{username}' or email '{email}' already exists.")
            return False

        # Create admin user
        admin = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            role=UserRole.ADMIN,
            is_active=True,
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print(f"✅ Admin user created successfully!")
        print(f"   Username: {admin.username}")
        print(f"   Email: {admin.email}")
        print(f"   Role: {admin.role.value}")
        print(f"   ID: {admin.id}")
        return True

    except Exception as e:
        db.rollback()
        print(f"❌ Error creating admin user: {e}")
        return False
    finally:
        db.close()


def main():
    """Main function."""
    print("=" * 60)
    print("Aviation Intelligence Platform - Admin User Setup")
    print("=" * 60)
    print()

    # Get admin credentials
    username = input("Enter admin username [admin]: ").strip() or "admin"
    email = input("Enter admin email [admin@example.com]: ").strip() or "admin@example.com"

    # Get password with confirmation
    import getpass
    while True:
        password = getpass.getpass("Enter admin password: ")
        if len(password) < 8:
            print("❌ Password must be at least 8 characters long.")
            continue

        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("❌ Passwords do not match. Please try again.")
            continue

        break

    print()
    print("Creating admin user...")
    print(f"  Database: {settings.database_url}")
    print()

    success = create_admin(username, email, password)

    if success:
        print()
        print("=" * 60)
        print("✅ Setup complete! You can now login with these credentials.")
        print("=" * 60)
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
