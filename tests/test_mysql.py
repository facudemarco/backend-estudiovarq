import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(override=True)

from services import mysql as db

TEST_PHONE = "+5491199900001"


@pytest.fixture(autouse=True)
def clean_test_lead():
    yield
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM crm_messages WHERE phone=%s", (TEST_PHONE,))
    cur.execute("DELETE FROM crm_events WHERE phone=%s", (TEST_PHONE,))
    cur.execute("DELETE FROM crm_leads WHERE phone=%s", (TEST_PHONE,))
    conn.commit()
    conn.close()


def test_upsert_and_get_lead():
    db.upsert_lead({"phone": TEST_PHONE, "name": "Test", "q1": "Casa"})
    row = db.get_lead(TEST_PHONE)
    assert row["phone"] == TEST_PHONE
    assert row["name"] == "Test"
    assert row["q1"] == "Casa"
    db.upsert_lead({"phone": TEST_PHONE, "q2": "Si"})
    row = db.get_lead(TEST_PHONE)
    assert row["q1"] == "Casa"
    assert row["q2"] == "Si"


def test_update_lead_selective():
    db.upsert_lead({"phone": TEST_PHONE, "status": "nuevo"})
    ok = db.update_lead(TEST_PHONE, {"status": "wizard", "question_index": 3, "prox_seg_ts": "2026-08-06T15:00:00"})
    assert ok is True
    row = db.get_lead(TEST_PHONE)
    assert row["status"] == "wizard"
    assert row["question_index"] == 3
    assert row["prox_seg_ts"] == "2026-08-06T15:00:00"


def test_update_lead_unknown_column_ignored():
    db.upsert_lead({"phone": TEST_PHONE})
    ok = db.update_lead(TEST_PHONE, {"no_existe": "x"})
    assert ok is True
    row = db.get_lead(TEST_PHONE)
    assert "no_existe" not in row


def test_messages_roundtrip():
    db.upsert_lead({"phone": TEST_PHONE})
    db.insert_message(TEST_PHONE, "in", "hola", "lead")
    db.insert_message(TEST_PHONE, "out", "hola de nuevo", "bot")
    msgs = db.list_messages(TEST_PHONE)
    assert len(msgs) == 2
    assert msgs[0]["source"] == "lead"
    assert msgs[1]["source"] == "bot"


def test_events_roundtrip():
    db.upsert_lead({"phone": TEST_PHONE})
    db.insert_event(TEST_PHONE, "q3", "bot", {"nota": "x"})
    db.insert_event(TEST_PHONE, "pause", "humano")
    evs = db.list_events(TEST_PHONE)
    assert len(evs) == 2
    assert evs[0]["tipo"] == "q3"
    assert evs[1]["actor"] == "humano"


def test_list_leads_filters():
    db.upsert_lead({"phone": TEST_PHONE, "name": "FiltroTest", "status": "wizard"})
    found = db.list_leads(stage="wizard")
    assert any(l["phone"] == TEST_PHONE for l in found)
    found = db.list_leads(q="FiltroTest")
    assert any(l["phone"] == TEST_PHONE for l in found)
    found = db.list_leads(stage="cualificado")
    assert not any(l["phone"] == TEST_PHONE for l in found)


def test_leads_pending():
    db.upsert_lead({"phone": TEST_PHONE, "etapa_seg": "6h1", "prox_seg_ts": (datetime.now() - timedelta(minutes=5)).isoformat()})
    pend = db.leads_pending(datetime.now())
    assert any(l["phone"] == TEST_PHONE for l in pend)


def test_search():
    db.upsert_lead({"phone": TEST_PHONE, "name": "BuscadoTest"})
    db.insert_message(TEST_PHONE, "in", "palabrasecreta", "lead")
    res = db.search("BuscadoTest")
    assert any(l["phone"] == TEST_PHONE for l in res["leads"])
    res = db.search("palabrasecreta")
    assert any(m["phone"] == TEST_PHONE for m in res["messages"])


def test_unread():
    db.upsert_lead({"phone": TEST_PHONE})
    db.incr_unread(TEST_PHONE)
    db.incr_unread(TEST_PHONE)
    assert db.get_lead(TEST_PHONE)["unread"] == 2
    db.mark_read(TEST_PHONE)
    assert db.get_lead(TEST_PHONE)["unread"] == 0
