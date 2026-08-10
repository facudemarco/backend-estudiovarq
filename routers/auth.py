import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel

from services import mysql as db

load_dotenv(override=True)

router = APIRouter()

SECRET = os.getenv("SESSION_SECRET", "")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
COOKIE_NAME = "session"
TOKEN_TTL_HOURS = 12


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def read_token(token: str) -> Optional[dict]:
    if not SECRET:
        return None
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except Exception:
        return None


def get_current_user_data(session: str = Cookie(default=None)) -> Optional[dict]:
    return read_token(session or "")


def get_current_user(session: str = Cookie(default=None)) -> Optional[str]:
    data = get_current_user_data(session)
    return data.get("sub") if data else None


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: LoginBody, response: Response):
    if not SECRET:
        raise HTTPException(status_code=500, detail="SESSION_SECRET no configurado")
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, password_hash, role FROM crm_users WHERE username=%s", (body.username,))
    row = cur.fetchone()
    conn.close()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="credenciales inválidas")
    token = create_token(row["username"], row["role"])
    response.set_cookie(
        COOKIE_NAME, token,
        httponly=True, samesite="none", secure=COOKIE_SECURE,
        max_age=TOKEN_TTL_HOURS * 3600,
    )
    return {"ok": True}


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, samesite="none", secure=COOKIE_SECURE)
    return {"ok": True}


@router.get("/auth/me")
def me(session: str = Cookie(default=None)):
    data = get_current_user_data(session)
    if not data or not data.get("sub"):
        raise HTTPException(status_code=401, detail="no autenticado")
    return {"username": data["sub"], "role": data.get("role", "admin")}
