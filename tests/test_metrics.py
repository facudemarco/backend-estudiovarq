import os
import sys
from dotenv import load_dotenv
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(override=True)

from services import mysql as db

TEST_PHONE = "+5491199900004"


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


def test_metrics_shape(auth_client):
    db.upsert_lead({"phone": TEST_PHONE, "status": "cualificado", "source": "whatsapp"})
    db.insert_event(TEST_PHONE, "warming", "bot")
    r = auth_client.get("/crm/metrics")
    assert r.status_code == 200
    data = r.json()
    assert "by_stage" in data and "by_source" in data and "by_week" in data and "conversion" in data
    assert data["by_stage"].get("Calentando", 0) >= 1
    assert data["by_source"].get("whatsapp", 0) >= 1
    assert data["conversion"]["warming"] >= 1
    assert 0 <= data["conversion"]["rate"] <= 1
