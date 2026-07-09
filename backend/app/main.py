from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os
from .database import Base, engine, SessionLocal
from .models import User, Role
from .auth import hash_password
from .routers import auth, users, devices, locations, organizations

# Creates tables if they don't exist yet. Fine for this project's scale;
# for bigger changes later we'd move to Alembic migrations.
Base.metadata.create_all(bind=engine)


def bootstrap_superadmin():
    """
    Creates the platform-level superadmin (you) -- the account that creates
    and manages client Organizations. Not tied to any organization. Safe to
    leave in place -- it's a no-op once the user exists.
    """
    username = os.getenv("SUPERADMIN_USERNAME")
    password = os.getenv("SUPERADMIN_PASSWORD")
    if not username or not password:
        print("[bootstrap] SUPERADMIN_USERNAME/SUPERADMIN_PASSWORD not set in environment -- skipping superadmin creation")
        return
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username, User.organization_id.is_(None)).first()
        if not existing:
            db.add(User(username=username, hashed_password=hash_password(password),
                         role=Role.superadmin, organization_id=None))
            db.commit()
            print(f"[bootstrap] Created superadmin user '{username}'")
        else:
            print(f"[bootstrap] Superadmin user '{username}' already exists, skipping")
    finally:
        db.close()


bootstrap_superadmin()

app = FastAPI(title="Fleet Tracker API")

# Allow the dashboard's subdomains (any origin for now -- tighten once you
# have a fixed domain pattern, e.g. via a regex for "https://*.yourapp.com")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(organizations.router)
app.include_router(users.router)
app.include_router(devices.router)
app.include_router(locations.router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "fleet-tracker-api"}
