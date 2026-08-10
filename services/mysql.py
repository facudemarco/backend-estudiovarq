import os
import re
import threading
from datetime import datetime

from dotenv import load_dotenv
import pymysql

from services.stages import normalize_phone

load_dotenv(override=True)

LEAD_COLUMNS = (
    "lead_id", "phone", "name", "lastName", "email", "totalsM2", "address",
    "anotherPlace", "bathroom", "diningRoom", "kitchen", "livingRoom", "garage",
    "mainBedroom", "secondBedroom", "plants", "startDate", "zone", "comments",
    "source", "stage", "status", "question_index", "cualificado", "razon_no_cual",
    "etapa_seg", "prox_seg_ts", "ultimo_msg_ts", "last_message", "last_direction",
    "unread", "calendar_event_id", "notas",
    "q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9",
)
_DT_COLUMNS = {"prox_seg_ts", "ultimo_msg_ts", "created_at", "updated_at"}

_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    """Pool persistente: reutiliza conexiones (Hostinger limita a 500 conexiones/hora)."""
    global _pool
    with _pool_lock:
        if _pool is None:
            from dbutils.pooled_db import PooledDB
            _pool = PooledDB(
                creator=pymysql,
                maxconnections=6,
                mincached=1,
                maxcached=3,
                blocking=True,
                ping=7,
                host=os.getenv("HOST"),
                user=os.getenv("USER"),
                password=os.getenv("PASSWORD"),
                database=os.getenv("DATABASE"),
                connect_timeout=10,
                cursorclass=pymysql.cursors.DictCursor,
            )
        return _pool


def get_conn():
    return _get_pool().connection()


def _ts_to_iso(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%S")
    return str(value)


def _parse_ts(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    v = str(value).replace("T", " ")
    if "." in v:
        v = v.split(".")[0]
    try:
        return datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _lead_from_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if k in _DT_COLUMNS and v is not None:
            out[k] = _ts_to_iso(v)
        else:
            out[k] = "" if v is None else v
    return out


def _cols_of(table: str) -> set:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SHOW COLUMNS FROM {table}")
    cols = {r["Field"] for r in cur.fetchall()}
    conn.close()
    return cols


def get_lead(phone: str):
    phone_n = normalize_phone(phone)
    if not phone_n:
        return None
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM crm_leads WHERE phone=%s", (phone_n,))
    row = cur.fetchone()
    conn.close()
    return _lead_from_row(dict(row)) if row else None


def upsert_lead(fields: dict):
    phone_n = normalize_phone(fields.get("phone"))
    if not phone_n:
        raise ValueError("phone requerido")
    cols = _cols_of("crm_leads")
    data = {k: ("" if v is None else v) for k, v in fields.items() if k in cols}
    data["phone"] = phone_n
    if not data:
        return {"phone": phone_n}
    keys = list(data.keys())
    placeholders = ", ".join(["%s"] * len(keys))
    updates = ", ".join(f"{k}=VALUES({k})" for k in keys if k != "phone")
    if updates:
        sql = (f"INSERT INTO crm_leads ({', '.join(keys)}) VALUES ({placeholders}) "
               f"ON DUPLICATE KEY UPDATE {updates}")
    else:
        sql = f"INSERT IGNORE INTO crm_leads ({', '.join(keys)}) VALUES ({placeholders})"
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, [data[k] for k in keys])
    conn.commit()
    conn.close()
    return {"phone": phone_n}


def update_lead(phone: str, changes: dict) -> bool:
    phone_n = normalize_phone(phone)
    if not phone_n or not changes:
        return False
    cols = _cols_of("crm_leads")
    valid = {}
    for k, v in changes.items():
        if k not in cols or k == "phone":
            continue
        if k in _DT_COLUMNS:
            valid[k] = _parse_ts(v)
        else:
            valid[k] = None if v is None else str(v)
    if not valid:
        return True
    sets = ", ".join(f"{k}=%s" for k in valid)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE crm_leads SET {sets} WHERE phone=%s", [*valid.values(), phone_n])
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def insert_message(phone: str, direction: str, text: str, source: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO crm_messages (phone, direction, text, source, ts) VALUES (%s, %s, %s, %s, NOW())",
        (normalize_phone(phone), direction, (text or "")[:4000], source),
    )
    conn.commit()
    mid = cur.lastrowid
    conn.close()
    return mid


def list_messages(phone: str) -> list:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, phone, direction, text, source, ts FROM crm_messages WHERE phone=%s ORDER BY ts, id",
        (normalize_phone(phone),),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    for r in rows:
        r["ts"] = _ts_to_iso(r["ts"])
    return rows


def insert_event(phone: str, tipo: str, actor: str = "bot", detail=None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    import json
    cur.execute(
        "INSERT INTO crm_events (phone, tipo, detail, actor, ts) VALUES (%s, %s, %s, %s, NOW())",
        (normalize_phone(phone), (tipo or "")[:40], json.dumps(detail, ensure_ascii=False) if detail else None, actor),
    )
    conn.commit()
    eid = cur.lastrowid
    conn.close()
    return eid


def list_events(phone: str) -> list:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, phone, tipo, detail, actor, ts FROM crm_events WHERE phone=%s ORDER BY ts, id",
        (normalize_phone(phone),),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    import json
    for r in rows:
        r["ts"] = _ts_to_iso(r["ts"])
        r["detail"] = json.loads(r["detail"]) if r.get("detail") else None
    return rows


def list_leads(stage=None, q=None, source=None, sort="updated_at", limit=500) -> list:
    where, params = [], []
    if stage:
        where.append("status=%s")
        params.append(stage)
    if q:
        where.append("(name LIKE %s OR phone LIKE %s OR email LIKE %s)")
        like = f"%{q}%"
        params += [like, like, like]
    if source:
        where.append("source=%s")
        params.append(source)
    sql = "SELECT * FROM crm_leads"
    if where:
        sql += " WHERE " + " AND ".join(where)
    order = {"created_at": "created_at", "prox_seg_ts": "prox_seg_ts"}.get(sort, "COALESCE(ultimo_msg_ts, created_at)")
    sql += f" ORDER BY {order} DESC LIMIT {int(limit)}"
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return [_lead_from_row(r) for r in rows]


def leads_pending(lte_ts: datetime) -> list:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM crm_leads WHERE prox_seg_ts IS NOT NULL AND prox_seg_ts <= %s",
        (lte_ts.strftime("%Y-%m-%d %H:%M:%S"),),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return [_lead_from_row(r) for r in rows]


def search(q: str) -> dict:
    like = f"%{q}%"
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM crm_leads WHERE name LIKE %s OR phone LIKE %s OR email LIKE %s LIMIT 50", (like, like, like))
    leads = [_lead_from_row(dict(r)) for r in cur.fetchall()]
    cur.execute("SELECT * FROM crm_messages WHERE text LIKE %s ORDER BY ts DESC LIMIT 50", (like,))
    msgs = []
    for r in cur.fetchall():
        d = dict(r)
        d["ts"] = _ts_to_iso(d["ts"])
        msgs.append(d)
    conn.close()
    return {"leads": leads, "messages": msgs}


def mark_read(phone: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE crm_leads SET unread=0 WHERE phone=%s", (normalize_phone(phone),))
    conn.commit()
    conn.close()


def incr_unread(phone: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE crm_leads SET unread=unread+1 WHERE phone=%s", (normalize_phone(phone),))
    conn.commit()
    conn.close()
