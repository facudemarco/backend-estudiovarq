import os
import sys
from dotenv import load_dotenv
import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(override=True)


def _conn():
    return pymysql.connect(
        host=os.getenv("HOST"), user=os.getenv("USER"),
        password=os.getenv("PASSWORD"), database=os.getenv("DATABASE"),
        connect_timeout=10,
    )


def test_schema_columns_exist():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SHOW COLUMNS FROM crm_leads")
    cols = {r[0] for r in cur.fetchall()}
    for expected in ["status", "lead_id", "q1", "q9", "etapa_seg", "prox_seg_ts",
                     "calendar_event_id", "cualificado", "question_index"]:
        assert expected in cols, f"falta columna {expected}"
    cur.execute("SHOW COLUMNS FROM crm_messages")
    cols = {r[0] for r in cur.fetchall()}
    assert "source" in cols
    cur.execute("SHOW TABLES LIKE 'crm_events'")
    assert cur.fetchone() is not None, "crm_events no existe"
    cur.execute("SHOW TABLES LIKE 'crm_users'")
    assert cur.fetchone() is not None, "crm_users no existe"
    conn.close()
