from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import auth, users, devices, locations

# Creates tables if they don't exist yet. Fine for this project's scale;
# for bigger changes later we'd move to Alembic migrations.
Base.metadata.create_all(bind=engine)

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
