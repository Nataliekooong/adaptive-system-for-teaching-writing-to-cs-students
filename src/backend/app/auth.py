"""Dev authentication. McMaster SSO (OIDC/CAS) replaces `login` once the method is confirmed
(SRS §14); everything downstream only depends on `current_user`."""
import hashlib
import hmac
import os
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import AuthSession, User


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    candidate = hash_password(password, bytes.fromhex(salt_hex)).split("$")[1]
    return hmac.compare_digest(candidate, digest_hex)


def create_session(db: Session, user: User) -> str:
    token = secrets.token_hex(24)
    db.add(AuthSession(token=token, user_id=user.id))
    db.commit()
    return token


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not signed in")
    sess = db.get(AuthSession, authorization.removeprefix("Bearer "))
    if sess is None:
        raise HTTPException(401, "Session expired")
    return db.get(User, sess.user_id)


def require_instructor(user: User = Depends(current_user)) -> User:
    if user.role != "instructor":
        raise HTTPException(403, "Instructor access required")
    return user


def require_student(user: User = Depends(current_user)) -> User:
    if user.role != "student":
        raise HTTPException(403, "Student access required")
    return user
