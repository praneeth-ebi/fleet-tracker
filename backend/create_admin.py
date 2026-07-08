"""
Run this ONCE after your first deploy to create the admin account.

Locally:
    python create_admin.py

On Render: open the "Shell" tab for your web service and run:
    python create_admin.py
"""
import getpass
from app.database import SessionLocal, Base, engine
from app.models import User, Role
from app.auth import hash_password

Base.metadata.create_all(bind=engine)


def main():
    db = SessionLocal()
    try:
        username = input("Admin username: ").strip()
        if db.query(User).filter(User.username == username).first():
            print("That username already exists.")
            return
        password = getpass.getpass("Admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords didn't match.")
            return

        user = User(username=username, hashed_password=hash_password(password), role=Role.admin)
        db.add(user)
        db.commit()
        print(f"Admin user '{username}' created.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
