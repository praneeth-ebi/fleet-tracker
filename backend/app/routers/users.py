from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Role
from ..schemas import UserCreate, UserOut
from ..auth import require_role, hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_role(Role.admin))):
    return db.query(User).all()


@router.post("/", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                 _admin: User = Depends(require_role(Role.admin))):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    user = User(username=payload.username,
                hashed_password=hash_password(payload.password),
                role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def deactivate_user(user_id: str, db: Session = Depends(get_db),
                     _admin: User = Depends(require_role(Role.admin))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    return {"status": "deactivated"}
