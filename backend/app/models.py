import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Float, Integer, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    superadmin = "superadmin"  # platform-level: manages Organizations themselves, not tied to one
    admin = "admin"
    operator = "operator"
    client = "client"


class Organization(Base):
    """A tenant -- one client company. Every User (except superadmin) and every Device belongs to exactly one."""
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    subdomain = Column(String, unique=True, index=True, nullable=False)  # e.g. "idkexpress" -> idkexpress.yourapp.com
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="organization")
    devices = relationship("Device", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    # Username is unique per-organization, not globally -- two different
    # clients can both have a user named "admin". Superadmin users have
    # organization_id = None and must have a globally unique username.
    username = Column(String, index=True, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(Role), default=Role.operator, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")
    # Only relevant for role == client: restrict which devices they can see
    assigned_devices = relationship("DeviceAssignment", back_populates="user")

    __table_args__ = (
        UniqueConstraint("organization_id", "username", name="uq_username_per_org"),
    )


class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, default=gen_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)
    device_token = Column(String, unique=True, default=gen_uuid)  # used by the iPad to auth check-ins
    last_seen = Column(DateTime, nullable=True)
    battery_level = Column(Float, nullable=True)
    signal_strength = Column(Integer, nullable=True)  # 0-4 bars, optional
    last_lat = Column(Float, nullable=True)
    last_lng = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="devices")
    pings = relationship("LocationPing", back_populates="device")
    assignments = relationship("DeviceAssignment", back_populates="device")

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_device_name_per_org"),
    )


class DeviceAssignment(Base):
    """Links client-role users to only the devices they're allowed to view."""
    __tablename__ = "device_assignments"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    device_id = Column(String, ForeignKey("devices.id"))

    user = relationship("User", back_populates="assigned_devices")
    device = relationship("Device", back_populates="assignments")


class LocationPing(Base):
    __tablename__ = "location_pings"

    id = Column(String, primary_key=True, default=gen_uuid)
    device_id = Column(String, ForeignKey("devices.id"), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    battery_level = Column(Float, nullable=True)
    accuracy_m = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    device = relationship("Device", back_populates="pings")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)  # e.g. "login", "login_failed", "logout"
    detail = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
