from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Device, LocationPing
from ..schemas import CheckIn

router = APIRouter(prefix="/checkin", tags=["checkin"])


@router.post("/")
def check_in(payload: CheckIn, db: Session = Depends(get_db)):
    """
    Called directly by the iPad reporting page (no user login involved).
    Auth is via the device's own secret `device_token`, generated when the
    device was created in the dashboard.
    """
    device = db.query(Device).filter(Device.device_token == payload.device_token).first()
    if not device:
        raise HTTPException(status_code=404, detail="Unknown device token")

    now = datetime.utcnow()
    device.last_seen = now
    device.last_lat = payload.lat
    device.last_lng = payload.lng
    device.battery_level = payload.battery_level
    device.signal_strength = payload.signal_strength

    db.add(LocationPing(
        device_id=device.id,
        lat=payload.lat,
        lng=payload.lng,
        battery_level=payload.battery_level,
        accuracy_m=payload.accuracy_m,
        recorded_at=now,
    ))
    db.commit()
    return {"status": "ok"}
