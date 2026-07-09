from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, AuditLog, Organization, Role
from ..schemas import LoginRequest, Token
from ..auth import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else None

    def fail(detail_note: str):
        db.add(AuditLog(user_id=None, action="login_failed",
                         detail=f"username={payload.username} org_subdomain={payload.org_subdomain} ({detail_note})",
                         ip_address=client_ip))
        db.commit()
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    if payload.org_subdomain:
        # Normal client-org login: username is only unique within that org.
        org = db.query(Organization).filter(Organization.subdomain == payload.org_subdomain.lower()).first()
        if not org or not org.is_active:
            fail("org not found or inactive")
        user = db.query(User).filter(User.organization_id == org.id, User.username == payload.username).first()
    else:
        # Superadmin login: no org, username must be globally unique among superadmins.
        user = db.query(User).filter(User.organization_id.is_(None),
                                      User.username == payload.username,
                                      User.role == Role.superadmin).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        fail("bad credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token_data = {"sub": user.id, "role": user.role.value}
    if user.organization_id:
        token_data["org_id"] = user.organization_id
        token_data["org_subdomain"] = user.organization.subdomain
    token = create_access_token(token_data)

    db.add(AuditLog(user_id=user.id, action="login", ip_address=client_ip))
    db.commit()

    return Token(access_token=token)
