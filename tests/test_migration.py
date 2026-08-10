import os
import sys
from dotenv import load_dotenv
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(override=True)

from services import mysql as db

TEST_PHONE = "+5491199900005"


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


def test_upsert_lead_maps_all_sheet_fields():
    row = {
        "lead_id": "abc-1", "phone": TEST_PHONE, "name": "Facu",
        "lastName": "Test", "email": "t@t.com", "totalsM2": "50",
        "address": "Av X", "zone": "CABA", "status": "cualificado",
        "question_index": "10", "etapa_seg": "6h", "q1": "Casa", "q9": "en un mes",
        "cualificado": "si", "calendar_event_id": "evt-1",
    }
    db.upsert_lead(row)
    got = db.get_lead(TEST_PHONE)
    assert got["lead_id"] == "abc-1"
    assert got["name"] == "Facu"
    assert got["status"] == "cualificado"
    assert got["q9"] == "en un mes"
    assert got["calendar_event_id"] == "evt-1"
    db.upsert_lead({**row, "q2": "Si"})
    got = db.get_lead(TEST_PHONE)
    assert got["q1"] == "Casa" and got["q2"] == "Si"
