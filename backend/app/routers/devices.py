from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Device, DeviceAssignment, LocationPing, Role
from ..schemas import DeviceCreate, DeviceOut, DevicePublicOut, LocationPingOut
from ..auth import require_role, get_current_user

router = APIRouter(prefix="/devices", tags=["devices"])

ONLINE_THRESHOLD_MINUTES = 10  # a device is "offline" if no check-in within this window


def to_public(device: Device) -> DevicePublicOut:
    online = bool(device.last_seen and
                   device.last_seen > datetime.utcnow() - timedelta(minutes=ONLINE_THRESHOLD_MINUTES))
    return DevicePublicOut(
        id=device.id, name=device.name, last_seen=device.last_seen,
        battery_level=device.battery_level, signal_strength=device.signal_strength,
        last_lat=device.last_lat, last_lng=device.last_lng,
        is_active=device.is_active, online=online,
    )


@router.post("/", response_model=DeviceOut)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db),
                   _admin: User = Depends(require_role(Role.admin))):
    device = Device(name=payload.name)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device  # includes device_token -- give this to whoever sets up that iPad


@router.get("/", response_model=List[DevicePublicOut])
def list_devices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == Role.client:
        assigned_ids = [a.device_id for a in user.assigned_devices]
        devices = db.query(Device).filter(Device.id.in_(assigned_ids)).all()
    else:
        devices = db.query(Device).all()
    return [to_public(d) for d in devices]


@router.get("/{device_id}/history", response_model=List[LocationPingOut])
def device_history(device_id: str, hours: int = 24 * 30, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    if user.role == Role.client:
        allowed = {a.device_id for a in user.assigned_devices}
        if device_id not in allowed:
            raise HTTPException(status_code=403, detail="Not authorized for this device")

    since = datetime.utcnow() - timedelta(hours=hours)
    pings = (db.query(LocationPing)
             .filter(LocationPing.device_id == device_id, LocationPing.recorded_at >= since)
             .order_by(LocationPing.recorded_at.asc())
             .all())
    return pings


@router.post("/{device_id}/assign/{user_id}")
def assign_device(device_id: str, user_id: str, db: Session = Depends(get_db),
                   _admin: User = Depends(require_role(Role.admin))):
    if not db.query(Device).filter(Device.id == device_id).first():
        raise HTTPException(status_code=404, detail="Device not found")
    db.add(DeviceAssignment(device_id=device_id, user_id=user_id))
    db.commit()
    return {"status": "assigned"}
