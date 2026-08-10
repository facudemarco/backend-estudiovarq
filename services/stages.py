import re
from datetime import datetime, timedelta

AGENDAR_RE = re.compile(r"AGENDAR\s*:\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:?\d{2})?)")


def extract_agendar_mark(reply: str) -> tuple:
    """Extrae la marca AGENDAR:ISO del reply del agente. Devuelve (iso, reply_sin_marca)."""
    text = reply or ""
    m = AGENDAR_RE.search(text)
    if not m:
        return None, text
    cleaned = (text[:m.start()] + " " + text[m.end():]).strip()
    return m.group(1), cleaned


CHAIN = {
    "6h1": {"next": "6h2", "delay": {"hours": 6}},
    "6h2": {"next": "6h3", "delay": {"hours": 6}},
    "6h3": {"next": "24h1", "delay": {"days": 1}},
    "24h1": {"next": "24h2", "delay": {"days": 1}},
    "24h2": {"next": "24h3", "delay": {"days": 1}},
    "24h3": {"next": "72h1", "delay": {"days": 3}},
    "72h1": {"next": "72h2", "delay": {"days": 1}},
    "72h2": {"next": "72h3", "delay": {"days": 1}},
    "72h3": {"next": "7d1", "delay": {"days": 4}},
    "7d1": {"next": "7d2", "delay": {"days": 1}},
    "7d2": {"next": "7d3", "delay": {"days": 1}},
    "7d3": {"next": "10d", "delay": {"days": 3}},
    "10d": {"next": "m1", "delay": {"months": 1}},
    "m1": {"next": "m2", "delay": {"months": 1}},
    "m2": {"next": "m3", "delay": {"months": 1}},
    "m3": {"next": "m4", "delay": {"months": 1}},
    "m4": {"next": "m5", "delay": {"months": 1}},
    "m5": {"next": "m6", "delay": {"months": 1}},
    "m6": {"next": None, "delay": None},
}


def normalize_phone(raw) -> str:
    if raw is None:
        return ""
    digits = re.sub(r"[^\d]", "", str(raw))
    if not digits:
        return ""
    return "+" + digits


def derive_stage(status: str, etapa_seg: str, question_index=0, paused: bool = False) -> str:
    if paused:
        return "Pausado por humano"
    if status == "inactivo":
        return "Inactivo"
    if status == "nuevo":
        return "Nuevo"
    if status == "wizard":
        q = str(question_index or "")
        return f"Wizard Q{q}" if q.isdigit() and int(q) > 0 else "Wizard"
    if etapa_seg:
        if etapa_seg.startswith("m"):
            return f"Nurturing mensual {etapa_seg}"
        return f"Seguimiento {etapa_seg}"
    if status == "cualificado":
        return "Calentando"
    if status == "agendado":
        return "Agendado"
    if status == "no_cualificado":
        return "Nurturing"
    return "Nuevo"


def next_etapa(etapa_seg: str):
    entry = CHAIN.get(etapa_seg)
    if not entry:
        return None, None
    return entry["next"], entry["delay"]


def add_delay(base: datetime, delay: dict) -> datetime:
    if not delay:
        return base
    if "hours" in delay:
        return base + timedelta(hours=delay["hours"])
    if "days" in delay:
        return base + timedelta(days=delay["days"])
    if "months" in delay:
        month = base.month - 1 + delay["months"]
        year = base.year + month // 12
        month = month % 12 + 1
        day = min(base.day, 28)
        return base.replace(year=year, month=month, day=day)
    return base
