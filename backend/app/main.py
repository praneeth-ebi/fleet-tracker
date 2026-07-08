from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os
from .database import Base, engine, SessionLocal
from .models import User, Role
from .auth import hash_password
from .routers import auth, users, devices, locations

# Creates tables if they don't exist yet. Fine for this project's scale;
# for bigger changes later we'd move to Alembic migrations.
Base.metadata.create_all(bind=engine)


def bootstrap_admin():
    """
    Render's free tier has no Shell access, so we can't run create_admin.py
    interactively. Instead: if ADMIN_USERNAME and ADMIN_PASSWORD are set as
    environment variables, and that user doesn't exist yet, create it here
    on startup. Safe to leave in place -- it's a no-op once the user exists.
    """
    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")
    if not username or not password:
        print("[bootstrap] ADMIN_USERNAME/ADMIN_PASSWORD not set in environment -- skipping admin creation")
        return
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == username).first():
            db.add(User(username=username, hashed_password=hash_password(password), role=Role.admin))
            db.commit()
            print(f"[bootstrap] Created admin user '{username}'")
        else:
            print(f"[bootstrap] Admin user '{username}' already exists, skipping")
    finally:
        db.close()


bootstrap_admin()

app = FastAPI(title="Fleet Tracker API")

# Allow the React dashboard (any origin for now -- tighten this once
# the dashboard has a fixed domain, e.g. ["https://fleet.yourcompany.com"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(devices.router)
app.include_router(locations.router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "fleet-tracker-api"}
