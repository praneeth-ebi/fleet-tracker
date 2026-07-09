import re
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Organization, Role
from ..schemas import OrganizationCreate, OrganizationOut
from ..auth import require_role, hash_password

router = APIRouter(prefix="/organizations", tags=["organizations"])

SUBDOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


@router.get("/", response_model=List[OrganizationOut])
def list_organizations(db: Session = Depends(get_db), _sa: User = Depends(require_role(Role.superadmin))):
    return db.query(Organization).all()


@router.post("/", response_model=OrganizationOut)
def create_organization(payload: OrganizationCreate, db: Session = Depends(get_db),
                         _sa: User = Depends(require_role(Role.superadmin))):
    subdomain = payload.subdomain.strip().lower()
    if not SUBDOMAIN_RE.match(subdomain):
        raise HTTPException(status_code=400,
                             detail="Subdomain must be lowercase letters/numbers/hyphens only, e.g. 'idkexpress'")
    if db.query(Organization).filter(Organization.subdomain == subdomain).first():
        raise HTTPException(status_code=400, detail="That subdomain is already in use")

    org = Organization(name=payload.name, subdomain=subdomain)
    db.add(org)
    db.flush()  # get org.id without committing yet, so both rows succeed or fail together

    admin_user = User(
        username=payload.admin_username,
        organization_id=org.id,
        hashed_password=hash_password(payload.admin_password),
        role=Role.admin,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(org)
    return org


@router.delete("/{org_id}")
def deactivate_organization(org_id: str, db: Session = Depends(get_db),
                             _sa: User = Depends(require_role(Role.superadmin))):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.is_active = False
    db.commit()
    return {"status": "deactivated"}
