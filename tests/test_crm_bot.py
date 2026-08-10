import os
import sys
from dotenv import load_dotenv
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(override=True)

from services import mysql as db

TEST_PHONE = "+5491199900003"
SECRET = os.getenv("CRM_SECRET", "")


@pytest.fixture(autouse=True)
def clean():
    yield
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM crm_messages WHERE phone=%s", (TEST_PHONE,))
    cur.execute("DELETE FROM crm_events WHERE phone=%s", (TEST_PHONE,))
    cur.execute("DELETE FROM crm_leads WHERE phone=%s", (TEST_PHONE,))
    conn.commit()
    conn.close()


def _headers():
    return {"X-Secret": SECRET} if SECRET else {}


def test_upsert_lead_bot(client):
    r = client.post("/crm/upsert-lead", json={"phone": TEST_PHONE, "name": "Bot Lead", "q1": "Casa"}, headers=_headers())
    assert r.status_code == 200
    row = db.get_lead(TEST_PHONE)
    assert row["name"] == "Bot Lead"


def test_update_lead_bot(client):
    db.upsert_lead({"phone": TEST_PHONE})
    r = client.post("/crm/update-lead", json={"phone": TEST_PHONE, "changes": {"status": "wizard", "q2": "Si"}}, headers=_headers())
    assert r.status_code == 200
    row = db.get_lead(TEST_PHONE)
    assert row["status"] == "wizard" and row["q2"] == "Si"


def test_update_lead_bot_404(client):
    r = client.post("/crm/update-lead", json={"phone": TEST_PHONE, "changes": {"status": "x"}}, headers=_headers())
    assert r.status_code == 404


def test_get_lead_bot(client):
    db.upsert_lead({"phone": TEST_PHONE, "status": "cualificado"})
    r = client.get(f"/crm/lead?phone={TEST_PHONE}", headers=_headers())
    assert r.status_code == 200
    assert r.json()["status"] == "cualificado"


def test_get_lead_bot_404(client):
    r = client.get(f"/crm/lead?phone={TEST_PHONE}", headers=_headers())
    assert r.status_code == 404


def test_leads_pending_bot(client):
    db.upsert_lead({"phone": TEST_PHONE, "etapa_seg": "6h1", "prox_seg_ts": "2026-08-01T10:00:00"})
    r = client.get("/crm/leads-pending?lt_ts=2026-08-06T00:00:00", headers=_headers())
    assert r.status_code == 200
    assert any(x["phone"] == TEST_PHONE for x in r.json())


def test_search_endpoint(client):
    db.upsert_lead({"phone": TEST_PHONE, "name": "ParaBuscar"})
    db.insert_message(TEST_PHONE, "in", "fraseúnica", "lead")
    r = client.get("/crm/search?q=ParaBuscar", headers=_headers())
    assert r.status_code == 200
    assert any(x["phone"] == TEST_PHONE for x in r.json()["leads"])


def test_secret_required_when_set(client):
    r = client.post("/crm/upsert-lead", json={"phone": TEST_PHONE})
    assert r.status_code == 401
    r = client.post("/crm/upsert-lead", json={"phone": TEST_PHONE}, headers=_headers())
    assert r.status_code == 200
