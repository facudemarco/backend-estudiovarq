# routers/crm.py
# CRM sobre MySQL (única fuente de verdad) + control del agent.
import os
from datetime import datetime
from uuid import uuid4
import requests
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional

from services import mysql as db
from services.stages import add_delay, derive_stage, extract_agendar_mark, next_etapa, normalize_phone

router = APIRouter()

AGENT_BASE = os.getenv("WHATSAPP_AGENT_URL", "http://localhost:3008").rstrip("/")
AGENT_SEND = f"{AGENT_BASE}/send"
AGENT_STATE = f"{AGENT_BASE}/state"
AGENT_PAUSE = f"{AGENT_BASE}/pause"
AGENT_RESUME = f"{AGENT_BASE}/resume"


def check_secret(x_secret: Optional[str]):
    s = os.getenv("CRM_SECRET", "").strip()
    if s and x_secret != s:
        raise HTTPException(status_code=401, detail="invalid secret")


def agent_paused_phones() -> set:
    try:
        r = requests.get(AGENT_STATE, timeout=5)
        data = r.json()
        stopped = data.get("stopped", {}) if isinstance(data.get("stopped"), dict) else {}
        return {normalize_phone(p) for p in stopped}
    except Exception:
        return set()


def agent_connected() -> bool:
    try:
        return bool(requests.get(AGENT_STATE, timeout=5).json().get("connected"))
    except Exception:
        return False


class InboxMsg(BaseModel):
    phone: str
    text: str


class OutMsg(BaseModel):
    text: str


class EventMsg(BaseModel):
    phone: str
    step: str


class UpdateLead(BaseModel):
    phone: str
    changes: dict


class ParseAgendarMsg(BaseModel):
    reply: str


@router.post("/crm/parse-agendar")
def crm_parse_agendar(msg: ParseAgendarMsg, x_secret: Optional[str] = Header(default=None)):
    check_secret(x_secret)
    start, cleaned = extract_agendar_mark(msg.reply)
    return {"start": start, "message": cleaned}


@router.post("/crm/inbox")
def crm_inbox(msg: InboxMsg, x_secret: Optional[str] = Header(default=None)):
    check_secret(x_secret)
    phone = normalize_phone(msg.phone)
    text = (msg.text or "")[:4000]
    if not phone:
        raise HTTPException(status_code=400, detail="phone inválido")
    db.upsert_lead({"phone": phone})
    db.insert_message(phone, "in", text, "lead")
    db.incr_unread(phone)
    db.update_lead(phone, {
        "ultimo_msg_ts": datetime.now().isoformat(),
        "last_message": text,
    })
    return {"ok": True}


@router.get("/crm/leads")
def crm_leads():
    leads = db.list_leads(sort="updated_at")
    paused = agent_paused_phones()
    result = []
    for row in leads:
        stage = derive_stage(
            row.get("status", ""),
            row.get("etapa_seg", ""),
            row.get("question_index", 0),
            paused=row["phone"] in paused,
        )
        result.append({
            "phone": row["phone"],
            "name": row.get("name") or row.get("lastName") or row["phone"],
            "stage": stage,
            "raw_status": row.get("status", ""),
            "etapa_seg": row.get("etapa_seg", ""),
            "prox_seg_ts": row.get("prox_seg_ts", ""),
            "last_message": row.get("last_message", ""),
            "ultimo_msg_ts": row.get("ultimo_msg_ts", ""),
            "updated_at": row.get("ultimo_msg_ts", "") or row.get("created_at", "") or row.get("prox_seg_ts", ""),
            "unread": row.get("unread", 0),
            "paused": row["phone"] in paused,
        })
    result.sort(key=lambda r: r["updated_at"], reverse=True)
    return result


@router.get("/crm/leads/{phone}")
def crm_lead_detail(phone: str):
    phone_n = normalize_phone(phone)
    row = db.get_lead(phone_n)
    if not row:
        raise HTTPException(status_code=404, detail="lead not found")
    paused = phone_n in agent_paused_phones()
    return {
        **row,
        "stage": derive_stage(row.get("status", ""), row.get("etapa_seg", ""), row.get("question_index", 0), paused=paused),
        "paused": paused,
        "messages": [
            {**m, "actor": "humano" if m["source"] == "human" else ("lead" if m["source"] == "lead" else "bot")}
            for m in db.list_messages(phone_n)
        ],
        "events": [{**e, "step": e["tipo"], "actor": e["actor"]} for e in db.list_events(phone_n)],
    }


@router.post("/crm/leads/{phone}/send")
def crm_send(phone: str, body: OutMsg):
    phone_n = normalize_phone(phone)
    text = (body.text or "")[:4000]
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    try:
        r = requests.post(AGENT_SEND, json={"phone": phone_n, "message": text, "force": True}, timeout=15)
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"agente no disponible: {e}")
    db.insert_message(phone_n, "out", text, "human")
    db.insert_event(phone_n, "humano", "humano")
    try:
        requests.post(AGENT_PAUSE, json={"phone": phone_n}, timeout=5)
    except Exception:
        pass
    db.update_lead(phone_n, {"last_message": text})
    return {"ok": True}


@router.post("/crm/events")
def crm_events(msg: EventMsg, x_secret: Optional[str] = Header(default=None)):
    check_secret(x_secret)
    phone_n = normalize_phone(msg.phone)
    step = (msg.step or "")[:40]
    if not phone_n or not step:
        raise HTTPException(status_code=400, detail="phone y step requeridos")
    db.insert_event(phone_n, step, "bot")
    return {"ok": True}


@router.post("/crm/leads/{phone}/pause")
def crm_pause(phone: str):
    phone_n = normalize_phone(phone)
    try:
        requests.post(AGENT_PAUSE, json={"phone": phone_n}, timeout=5).raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"agente no disponible: {e}")
    db.insert_event(phone_n, "pause", "humano")
    return {"ok": True}


@router.post("/crm/leads/{phone}/resume")
def crm_resume(phone: str):
    phone_n = normalize_phone(phone)
    try:
        requests.post(AGENT_RESUME, json={"phone": phone_n}, timeout=5).raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"agente no disponible: {e}")
    current = db.get_lead(phone_n) or {}
    etapa = current.get("etapa_seg", "")
    nxt, delay = next_etapa(etapa)
    if nxt:
        db.update_lead(phone_n, {"etapa_seg": nxt, "prox_seg_ts": add_delay(datetime.now(), delay).isoformat()})
    db.insert_event(phone_n, "resume", "humano")
    return {"ok": True}


@router.post("/crm/leads/{phone}/read")
def crm_read(phone: str):
    db.mark_read(normalize_phone(phone))
    return {"ok": True}


@router.post("/crm/upsert-lead")
def crm_upsert_lead(body: dict, x_secret: Optional[str] = Header(default=None)):
    check_secret(x_secret)
    phone = normalize_phone(body.get("phone"))
    if not phone:
        raise HTTPException(status_code=400, detail="phone requerido")
    db.upsert_lead({k: v for k, v in body.items() if k != "phone"} | {"phone": phone})
    return {"ok": True, "phone": phone}


@router.post("/crm/update-lead")
def crm_update_lead(body: UpdateLead, x_secret: Optional[str] = Header(default=None)):
    check_secret(x_secret)
    phone = normalize_phone(body.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="phone requerido")
    if not db.get_lead(phone):
        raise HTTPException(status_code=404, detail="lead not found")
    db.update_lead(phone, body.changes)
    return {"ok": True}


@router.get("/crm/lead")
def crm_lead_get(phone: str, x_secret: Optional[str] = Header(default=None)):
    check_secret(x_secret)
    row = db.get_lead(normalize_phone(phone))
    if not row:
        raise HTTPException(status_code=404, detail="lead not found")
    return row


@router.get("/crm/leads-pending")
def crm_leads_pending(lt_ts: Optional[str] = None, x_secret: Optional[str] = Header(default=None)):
    check_secret(x_secret)
    from services.mysql import _parse_ts
    cutoff = _parse_ts(lt_ts) if lt_ts else datetime.now()
    return db.leads_pending(cutoff)


@router.get("/crm/search")
def crm_search(q: str):
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="q debe tener 2+ caracteres")
    return db.search(q)


@router.get("/crm/metrics")
def crm_metrics():
    from collections import Counter
    conn = db.get_conn()
    cur = conn.cursor()

    cur.execute("SELECT status, etapa_seg, question_index, source FROM crm_leads")
    rows = cur.fetchall()
    by_stage = Counter()
    by_source = Counter()
    for row in rows:
        by_stage[derive_stage(row.get("status", "") or "", row.get("etapa_seg", "") or "", row.get("question_index", 0) or 0)] += 1
        by_source[row.get("source") or "whatsapp"] += 1

    cur.execute(
        "SELECT DATE_FORMAT(DATE_SUB(created_at, INTERVAL WEEKDAY(created_at) DAY), '%Y-%m-%d') AS week, COUNT(*) AS cnt "
        "FROM crm_leads WHERE created_at >= DATE_SUB(NOW(), INTERVAL 8 WEEK) GROUP BY week ORDER BY week"
    )
    by_week = [{"week": r["week"], "count": r["cnt"]} for r in cur.fetchall()]

    cur.execute("SELECT COUNT(*) AS cnt FROM crm_events WHERE tipo='warming'")
    warming = cur.fetchone()["cnt"] or 0
    cur.execute("SELECT COUNT(*) AS cnt FROM crm_leads WHERE status='agendado'")
    agendado = cur.fetchone()["cnt"] or 0
    conn.close()
    return {
        "by_stage": dict(by_stage),
        "by_source": dict(by_source),
        "by_week": by_week,
        "conversion": {"warming": warming, "agendado": agendado, "rate": round(agendado / warming, 3) if warming else 0},
    }


@router.get("/crm/status")
def crm_status():
    return {"connected": agent_connected()}


N8N_CALENDAR_WEBHOOK = os.getenv("N8N_CALENDAR_WEBHOOK", "https://n8n.iwebtecnology.com/webhook/estudiovarq-calendario")


def _normalize_event(ev: dict) -> dict:
    start = ev.get("start") or {}
    end = ev.get("end") or {}
    return {
        "id": ev.get("id") or "",
        "summary": ev.get("summary") or "",
        "start": start.get("dateTime") or start.get("date") or "",
        "end": end.get("dateTime") or end.get("date") or "",
    }


@router.get("/crm/calendar")
def crm_calendar(time_min: Optional[str] = None, time_max: Optional[str] = None):
    try:
        r = requests.post(N8N_CALENDAR_WEBHOOK,
                          json={"timeMin": time_min, "timeMax": time_max},
                          headers={"X-Secret": os.getenv("CRM_SECRET", "")}, timeout=30)
        r.raise_for_status()
        events = r.json() if r.text else []
    except Exception:
        raise HTTPException(status_code=502, detail="calendario no disponible")
    if isinstance(events, dict):
        events = events.get("items") or [events]
    return [_normalize_event(ev) for ev in (events or [])]


class TestFormData(BaseModel):
    name: str = "Lead de prueba"
    lastName: str = "DummY"
    phone: str = "5491100000000"
    email: str = "test@dummy.com"
    address: str = "Calle Falsa 123"
    zone: str = "CABA"
    totalsM2: float = 35.0
    bathroom: str = "1"
    kitchen: str = "1"
    livingRoom: str = "1"
    diningRoom: str = ""
    mainBedroom: str = "1"
    secondBedroom: str = ""
    plants: str = "1"
    garage: str = "0"
    anotherPlace: str = ""
    startDate: str = "2026-09-01"
    comments: str = "Lead generado por el form de prueba (no toca n8n ni envía mail)"


@router.post("/crm/test-form")
def crm_test_form(data: TestFormData):
    phone_n = normalize_phone(data.phone)
    if not phone_n:
        raise HTTPException(status_code=400, detail="phone inválido")
    lead = {
        "phone": phone_n,
        "name": data.name,
        "lastName": data.lastName,
        "email": data.email,
        "address": data.address,
        "zone": data.zone,
        "totalsM2": str(data.totalsM2),
        "bathroom": data.bathroom,
        "kitchen": data.kitchen,
        "livingRoom": data.livingRoom,
        "diningRoom": data.diningRoom,
        "mainBedroom": data.mainBedroom,
        "secondBedroom": data.secondBedroom,
        "plants": data.plants,
        "garage": data.garage,
        "anotherPlace": data.anotherPlace,
        "startDate": data.startDate,
        "comments": data.comments,
        "status": "nuevo",
        "source": "test-form",
    }
    try:
        db.upsert_lead(lead)
        db.insert_message(phone_n, "in", data.comments, source="test-form")
        db.insert_event(phone_n, "bienvenida", detail="lead creado por form de prueba", actor="system")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"no se pudo insertar el lead: {e}")

    # Dispara el mismo flujo que el form real: webhook n8n → upsert prod → m1/m2 → agente → WhatsApp
    try:
        webhook_url = os.getenv(
            "N8N_ENTRADA_URL",
            "https://n8n.iwebtecnology.com/webhook/estudiovarq-entrada",
        )
        payload = {
            "lead_id": str(uuid4()),
            "name": data.name,
            "lastName": data.lastName,
            "email": data.email,
            "phone": phone_n,
            "calendly_link": "https://calendly.com/lasshaky-fju6/llamada-con-un-arquitecto",
            "address": data.address,
            "anotherPlace": data.anotherPlace,
            "bathroom": data.bathroom,
            "comments": data.comments,
            "diningRoom": data.diningRoom,
            "garage": data.garage,
            "kitchen": data.kitchen,
            "livingRoom": data.livingRoom,
            "mainBedroom": data.mainBedroom,
            "totalsM2": data.totalsM2,
            "plants": data.plants,
            "secondBedroom": data.secondBedroom,
            "startDate": data.startDate,
            "zone": data.zone,
            "source": "test-form",
        }
        requests.post(webhook_url, json=payload, timeout=20)
    except Exception as e:
        print(f"test-form→n8n: {e}")
    return {"status": "ok", "phone": phone_n, "lead": db.get_lead(phone_n)}
