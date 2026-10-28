"""로그인/세션: 서명된 쿠키(itsdangerous) + PBKDF2 비밀번호 해시(표준 라이브러리)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from pathlib import Path

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .db import DATA_DIR

COOKIE_NAME = "mdocs_session"
SESSION_MAX_AGE = 60 * 60 * 12  # 12시간


def _secret_key() -> str:
    env = os.environ.get("MEETING_DOCS_SECRET")
    if env:
        return env
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    p: Path = DATA_DIR / "secret_key.txt"
    if not p.exists():
        p.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return p.read_text(encoding="utf-8").strip()


_serializer = URLSafeTimedSerializer(_secret_key(), salt="session")


def hash_password(plain: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, 200_000)
    return "pbkdf2$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(plain: str, stored: str) -> bool:
    try:
        _, salt_b64, digest_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except (ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, 200_000)
    return hmac.compare_digest(digest, expected)


def make_session(payload: dict) -> str:
    return _serializer.dumps(payload)


def read_session(request: Request) -> dict | None:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return None
    try:
        return _serializer.loads(raw, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None


class RedirectToLogin(HTTPException):
    def __init__(self, target: str):
        super().__init__(status_code=303, headers={"Location": target})


def require_admin(request: Request) -> dict:
    s = read_session(request)
    if not s or s.get("role") != "admin":
        raise RedirectToLogin("/login?next=" + request.url.path)
    return s


def require_group(request: Request) -> dict:
    """연구회 세션 또는 관리자 세션. 관리자는 모든 연구회 페이지를 열 수 있다."""
    s = read_session(request)
    if not s or s.get("role") not in ("group", "admin"):
        raise RedirectToLogin("/g/login?next=" + request.url.path)
    return s
