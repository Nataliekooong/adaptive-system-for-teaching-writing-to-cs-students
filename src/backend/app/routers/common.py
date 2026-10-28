from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import modules
from ..auth import create_session, current_user, verify_password
from ..db import get_db
from ..models import AuthSession, FeedbackStyle, User
from ..services.events import log_event

router = APIRouter(prefix="/api", tags=["common"])


class LoginIn(BaseModel):
    username: str
    password: str


def _me(u: User) -> dict:
    return {"id": u.id, "username": u.username, "display_name": u.display_name, "role": u.role}


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.username == body.username.strip().lower()))
    if u is None or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Wrong username or password")
    token = create_session(db, u)
    log_event(db, u, "login")
    return {"token": token, "user": _me(u)}


@router.post("/auth/logout")
def logout(user: User = Depends(current_user), db: Session = Depends(get_db)):
    for s in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)):
        db.delete(s)
    db.commit()
    return {"ok": True}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return _me(user)


@router.get("/modules")
def module_registry(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Schema the frontend uses to render every on/off switch and setting."""
    styles = [{"key": s.key, "name": s.name, "enabled": s.enabled}
              for s in db.scalars(select(FeedbackStyle).order_by(FeedbackStyle.key))]
    return {"modules": modules.registry_schema(), "defaults": modules.default_config(), "styles": styles}


@router.get("/health")
def health():
    return {"ok": True}
