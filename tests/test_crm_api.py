import os
import sys
import requests
from dotenv import load_dotenv
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(override=True)

from services import mysql as db

TEST_PHONE = "+5491199900002"
AGENT_RESUME = "http://localhost:3008/resume"


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
    try:
        requests.post(AGENT_RESUME, json={"phone": TEST_PHONE}, timeout=2)
    except Exception:
        pass


def test_list_leads_shape(client):
    db.upsert_lead({"phone": TEST_PHONE, "name": "API Test", "status": "wizard", "question_index": 4})
    r = client.get("/crm/leads")
    assert r.status_code == 200
    lead = next(x for x in r.json() if x["phone"] == TEST_PHONE)
    assert lead["name"] == "API Test"
    assert lead["stage"] == "Wizard Q4"
    assert lead["raw_status"] == "wizard"
    assert "paused" in lead and "unread" in lead


def test_detail_shape(client):
    db.upsert_lead({"phone": TEST_PHONE, "name": "API Test", "q3": "Ampliación"})
    db.insert_message(TEST_PHONE, "in", "hola", "lead")
    db.insert_event(TEST_PHONE, "q3", "bot")
    r = client.get(f"/crm/leads/{TEST_PHONE}")
    assert r.status_code == 200
    data = r.json()
    assert data["q3"] == "Ampliación"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["source"] == "lead"
    assert len(data["events"]) == 1
    assert data["events"][0]["tipo"] == "q3"


def test_detail_404(client):
    r = client.get("/crm/leads/+5491199900002")
    assert r.status_code == 404


def test_inbox_and_unread(client):
    r = client.post(
        "/crm/inbox",
        json={"phone": TEST_PHONE, "text": "mensaje entrante"},
        headers={"X-Secret": os.getenv("CRM_SECRET", "")},
    )
    assert r.status_code == 200
    lead = db.get_lead(TEST_PHONE)
    assert lead["unread"] == 1
    assert lead["last_message"] == "mensaje entrante"
    r = client.post(f"/crm/leads/{TEST_PHONE}/read")
    assert r.status_code == 200
    assert db.get_lead(TEST_PHONE)["unread"] == 0


def test_pause_resume_flow(client):
    db.upsert_lead({"phone": TEST_PHONE, "etapa_seg": "6h1", "prox_seg_ts": "2026-08-06T10:00:00"})
    # pause: el agente puede no estar disponible; el endpoint debe devolver 502 en ese caso
    r = client.post(f"/crm/leads/{TEST_PHONE}/pause")
    assert r.status_code in (200, 502)
    # resume con agente caido tambien tolera 502; el evento no se crea si falla el agente
    r = client.post(f"/crm/leads/{TEST_PHONE}/resume")
    assert r.status_code in (200, 502)
    if r.status_code == 200:
        lead = db.get_lead(TEST_PHONE)
        assert lead["etapa_seg"] == "6h2"
        assert any(e["tipo"] == "resume" for e in db.list_events(TEST_PHONE))
