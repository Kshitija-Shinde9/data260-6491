import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models import Session as SessionRow, User

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "s6491_sid"
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "900"))


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True


def _verify_password(plain: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain.encode(), password_hash.encode())


def require_user(
    s6491_sid: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> User:
    if not s6491_sid:
        raise HTTPException(status_code=401, detail="Not logged in")

    session_row = db.get(SessionRow, s6491_sid)
    if not session_row:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    if session_row.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        db.delete(session_row)
        db.commit()
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    return session_row.user


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not _verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session_row = SessionRow(
        id=secrets.token_urlsafe(32),
        user_id=user.id,
        created_at=now,
        expires_at=now + timedelta(seconds=SESSION_MAX_AGE),
    )
    db.add(session_row)
    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_row.id,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )
    return user


@router.post("/logout")
def logout(
    response: Response,
    s6491_sid: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
):
    if s6491_sid:
        session_row = db.get(SessionRow, s6491_sid)
        if session_row:
            db.delete(session_row)
            db.commit()

    response.delete_cookie(SESSION_COOKIE)
    return {"message": "logged out"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(require_user)):
    return user
