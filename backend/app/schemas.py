from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from .models import Role


# ---- Auth ----
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


# ---- Users ----
class UserCreate(BaseModel):
    username: str
    password: str
    role: Role = Role.operator


class UserOut(BaseModel):
    id: str
    username: str
    role: Role
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Devices ----
class DeviceCreate(BaseModel):
    name: str


class DeviceOut(BaseModel):
    id: str
    name: str
    device_token: str
    last_seen: Optional[datetime]
    battery_level: Optional[float]
    signal_strength: Optional[int]
    last_lat: Optional[float]
    last_lng: Optional[float]
    is_active: bool

    class Config:
        from_attributes = True


class DevicePublicOut(BaseModel):
    """Same as DeviceOut but without exposing the secret device_token to the dashboard."""
    id: str
    name: str
    last_seen: Optional[datetime]
    battery_level: Optional[float]
    signal_strength: Optional[int]
    last_lat: Optional[float]
    last_lng: Optional[float]
    is_active: bool
    online: bool

    class Config:
        from_attributes = True


# ---- Location check-in (sent BY the iPad) ----
class CheckIn(BaseModel):
    device_token: str
    lat: float
    lng: float
    battery_level: Optional[float] = Field(None, ge=0, le=1)
    accuracy_m: Optional[float] = None
    signal_strength: Optional[int] = Field(None, ge=0, le=4)


class LocationPingOut(BaseModel):
    lat: float
    lng: float
    battery_level: Optional[float]
    recorded_at: datetime

    class Config:
        from_attributes = True
