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

TEST_USER = "test_user_plan"
TEST_PASSWORD = "clave-segura-123"


@pytest.fixture
def auth_client():
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO crm_users (username, password_hash, role) VALUES (%s, %s, 'admin') "
        "ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash)",
        (TEST_USER, hash_password(TEST_PASSWORD)),
    )
    conn.commit()
    conn.close()
    client = TestClient(app)
    r = client.post("/auth/login", json={"username": TEST_USER, "password": TEST_PASSWORD})
    assert r.status_code == 200, r.text
    yield client


@pytest.fixture
def client(auth_client):
    return auth_client
