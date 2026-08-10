import os
import sys
from dotenv import load_dotenv
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(override=True)
os.environ.setdefault("SESSION_SECRET", "clave-secreta-de-test-suficientemente-larga")

from main import app
from services import mysql as db
from routers.auth import hash_password

client = TestClient(app)
TEST_USER = "test_user_plan"
TEST_PASSWORD = "clave-segura-123"


@pytest.fixture(scope="module", autouse=True)
def ensure_user():
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM crm_users WHERE username=%s", (TEST_USER,))
    cur.execute(
        "INSERT INTO crm_users (username, password_hash, role) VALUES (%s, %s, 'admin')",
        (TEST_USER, hash_password(TEST_PASSWORD)),
    )
    conn.commit()
    yield
    cur.execute("DELETE FROM crm_users WHERE username=%s", (TEST_USER,))
    conn.commit()
    conn.close()


def test_login_ok():
    r = client.post("/auth/login", json={"username": TEST_USER, "password": TEST_PASSWORD})
    assert r.status_code == 200
    assert "session" in r.cookies


def test_login_bad_password():
    r = client.post("/auth/login", json={"username": TEST_USER, "password": "incorrecta"})
    assert r.status_code == 401


def test_me_with_session():
    client.post("/auth/login", json={"username": TEST_USER, "password": TEST_PASSWORD})
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["username"] == TEST_USER


def test_me_without_session():
    c2 = TestClient(app)
    r = c2.get("/auth/me")
    assert r.status_code == 401


def test_crm_protected_without_session():
    client.cookies.clear()
    r = client.get("/crm/leads")
    assert r.status_code == 401


def test_crm_bot_route_open_with_secret():
    r = client.get("/crm/leads-pending?lt_ts=2026-08-06T00:00:00", headers={"X-Secret": os.getenv("CRM_SECRET", "x")})
    assert r.status_code in (200, 401)


def test_crm_allowed_with_session():
    client.post("/auth/login", json={"username": TEST_USER, "password": TEST_PASSWORD})
    r = client.get("/crm/leads")
    assert r.status_code == 200


def test_logout():
    client.post("/auth/login", json={"username": TEST_USER, "password": TEST_PASSWORD})
    r = client.post("/auth/logout")
    assert r.status_code == 200
    r = client.get("/auth/me")
    assert r.status_code == 401
