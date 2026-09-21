import os
import time
import uuid

import bcrypt
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER

router = APIRouter()

templates = Jinja2Templates(directory="templates")


def _hash(plain: str) -> bytes:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt())


USERS = {
    "kshitija": {
        "password_hash": _hash("Recall@6491"),
        "name": "Kshitija Shinde",
        "role": "Recall Coordinator",
    },
    "inspector": {
        "password_hash": _hash("Inspect@6491"),
        "name": "Food Safety Inspector",
        "role": "Inspector",
    },
}


def verify_password(username: str, password: str) -> bool:
    account = USERS.get(username)
    if account is None:
        bcrypt.checkpw(b"dummy", _hash("dummy"))
        return False
    return bcrypt.checkpw(password.encode(), account["password_hash"])


ACTIVE_SESSIONS: dict[str, float] = {}

IDLE_TIMEOUT_SECONDS = int(os.getenv("SESSION_MAX_AGE", "900"))


def current_user(request: Request):
    sid = request.session.get("sid")
    if not sid:
        return None

    last_seen = ACTIVE_SESSIONS.get(sid)
    if last_seen is None:
        request.session.clear()
        return None

    if time.time() - last_seen > IDLE_TIMEOUT_SECONDS:
        ACTIVE_SESSIONS.pop(sid, None)
        request.session.clear()
        return None

    ACTIVE_SESSIONS[sid] = time.time()
    return request.session.get("user")


@router.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"user": current_user(request), "active": "home"}
    )


@router.get("/login")
def login_page(request: Request):
    if current_user(request):
        return RedirectResponse(url="/dashboard", status_code=HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request, "login.html", {"user": None, "active": "login", "error": None}
    )


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if not verify_password(username.strip(), password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "user": None,
                "active": "login",
                "error": "Incorrect username or password. Please try again.",
                "attempted_username": username,
            },
            status_code=401,
        )

    account = USERS[username.strip()]

    sid = uuid.uuid4().hex
    ACTIVE_SESSIONS[sid] = time.time()

    request.session.clear()
    request.session["sid"] = sid
    request.session["user"] = {
        "username": username.strip(),
        "name": account["name"],
        "role": account["role"],
    }

    return RedirectResponse(url="/dashboard", status_code=HTTP_303_SEE_OTHER)


@router.get("/dashboard")
def dashboard(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login?expired=1", status_code=HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"user": user, "active": "dashboard", "idle_timeout": IDLE_TIMEOUT_SECONDS},
    )


@router.get("/logout")
def logout(request: Request):
    sid = request.session.get("sid")
    if sid:
        ACTIVE_SESSIONS.pop(sid, None)

    request.session.clear()
    return RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)
