from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, AuditLog
from ..schemas import LoginRequest, Token
from ..auth import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    client_ip = request.client.host if request.client else None

    if not user or not verify_password(payload.password, user.hashed_password):
        db.add(AuditLog(user_id=user.id if user else None,
                         action="login_failed",
                         detail=f"username={payload.username}",
                         ip_address=client_ip))
        db.commit()
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token({"sub": user.username, "role": user.role.value})

    db.add(AuditLog(user_id=user.id, action="login", ip_address=client_ip))
    db.commit()

    return Token(access_token=token)
