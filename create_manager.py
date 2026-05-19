#!/usr/bin/env python3
"""
Run once to create the first manager account.

Usage (from the shiftcraft/ directory with venv active):
    python create_manager.py
"""
import getpass
import sys

sys.path.insert(0, ".")

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User, UserRole


def main():
    print("=== ShiftCraft — Create Manager Account ===\n")
    name = input("Full name:  ").strip()
    email = input("Email:      ").strip()
    password = getpass.getpass("Password:   ")

    if not name or not email or not password:
        print("All fields are required.")
        sys.exit(1)
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        sys.exit(1)

    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            print(f"\nError: {email} is already registered.")
            sys.exit(1)
        user = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.manager,
        )
        db.add(user)
        db.commit()
        print(f"\nDone. Manager account created for {name} ({email}).")
        print("You can now log in at http://127.0.0.1:8000")
    finally:
        db.close()


if __name__ == "__main__":
    main()
