from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Role
from ..schemas import UserCreate, UserOut
from ..auth import require_role, hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_role(Role.admin))):
    return db.query(User).filter(User.organization_id == admin.organization_id).all()


@router.post("/", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                 admin: User = Depends(require_role(Role.admin))):
    existing = db.query(User).filter(
        User.organization_id == admin.organization_id,
        User.username == payload.username,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken in this organization")
    if payload.role == Role.superadmin:
        raise HTTPException(status_code=400, detail="Cannot create a superadmin through this endpoint")

    user = User(username=payload.username,
                organization_id=admin.organization_id,
                hashed_password=hash_password(payload.password),
                role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def deactivate_user(user_id: str, db: Session = Depends(get_db),
                     admin: User = Depends(require_role(Role.admin))):
    user = db.query(User).filter(User.id == user_id, User.organization_id == admin.organization_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    return {"status": "deactivated"}
