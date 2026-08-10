import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(override=True)

from services import sheets, mysql as db
from services.mysql import _parse_ts
from services.stages import normalize_phone


def migrate():
    leads = sheets.read_leads()
    n_leads = 0
    for phone, row in leads.items():
        for key in ("prox_seg_ts", "ultimo_msg_ts"):
            if key in row:
                parsed = _parse_ts(row[key])
                if parsed is None:
                    row.pop(key)
                else:
                    row[key] = parsed
        db.upsert_lead(row)
        n_leads += 1

    n_msgs = 0
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("SELECT MAX(id) FROM crm_messages")
    max_id = (cur.fetchone() or {}).get("MAX(id)") or 0
    conn.close()
    for row in sheets.read_messages(""):
        phone = normalize_phone(row.get("phone", ""))
        if not phone or int(row.get("id") or 0) <= max_id:
            continue
        actor = row.get("actor", "")
        source = {"humano": "human"}.get(actor, "lead" if row.get("direction") == "in" else "bot")
        db.insert_message(phone, row.get("direction", "in"), row.get("text", ""), source)
        n_msgs += 1

    n_evs = 0
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("SELECT MAX(id) FROM crm_events")
    max_ev = (cur.fetchone() or {}).get("MAX(id)") or 0
    conn.close()
    for row in sheets.read_events(""):
        phone = normalize_phone(row.get("phone", ""))
        if not phone or int(row.get("id") or 0) <= max_ev:
            continue
        db.insert_event(phone, row.get("step", "?"), row.get("actor", "bot") if row.get("actor") in ("humano", "bot") else "bot")
        n_evs += 1

    print(f"migración: {n_leads} leads, {n_msgs} mensajes, {n_evs} eventos")


if __name__ == "__main__":
    migrate()
