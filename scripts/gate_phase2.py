"""Gate e2e Plan 2: valida que el flujo n8n escriba en MySQL (no en Sheets)."""
import json
import os
import sys
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

N8N = "https://n8n.iwebtecnology.com"
KEY = os.getenv("N8N_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiNzE0NmExYy04YTJhLTQ3NGYtYmJiNC01NWZjMGQ4ZjQ5NzkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOGVkMWJkZjItY2JjNS00NmViLWI1NDUtZTdmNGFkMjM2ODg3IiwiaWF0IjoxNzg0OTM2MDI0fQ.2BeT3WAS5okQwJ5ACMYtDltqCTYywgQ4MXz6SF8wssU")
BACKEND = "http://localhost:8000"
CRM_SECRET = os.getenv("CRM_SECRET", "")
TEST_USER = "test_user_plan"
TEST_PASSWORD = "clave-segura-123"
TEST_PHONE = "+5491199900009"
TEST_PHONE_DIGITS = "5491199900009"
LEAD = {
    "phone": TEST_PHONE, "lead_id": "gate2-0001", "name": "Gate Plan2",
    "lastName": "Test", "email": "gate2@test.com", "totalsM2": 120,
    "address": "Calle 1", "anotherPlace": "", "bathroom": "1", "diningRoom": "1",
    "kitchen": "1", "livingRoom": "1", "garage": "", "mainBedroom": "2",
    "secondBedroom": "1", "plants": "", "startDate": "", "zone": "CABA",
    "comments": "", "source": "wizardForm", "status": "nuevo", "question_index": 0,
}
WIZARD_ANSWERS = ["Obra nueva", "Casa", "Sí", "CABA", "200", "Todo",
                  "Quiero ver mi casa antes de construirla", "Más de 100.000 USD", "en un mes"]
STEPS = []
REPORT = "/tmp/opencode/gate2_report.txt"


def check(name, cond, extra=""):
    STEPS.append((name, bool(cond), extra))
    line = f"{'PASS' if cond else 'FAIL'} - {name} {extra}"
    print(line, flush=True)
    with open(REPORT, "a") as f:
        f.write(line + "\n")
    return bool(cond)


def wait_for(predicate, timeout=90, interval=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def main():
    open(REPORT, "w").close()
    ok = True
    session = requests.Session()
    r = session.post(f"{BACKEND}/auth/login",
                     json={"username": TEST_USER, "password": TEST_PASSWORD}, timeout=10)
    ok &= check("login (cookie de sesión)", r.status_code == 200 and r.json().get("ok"), r.text[:100])

    r = session.get(f"{BACKEND}/crm/status", timeout=10)
    ok &= check("backend vivo", r.status_code == 200, r.text[:80])

    r = requests.post(f"{N8N}/webhook/estudiovarq-entrada-testing", json=LEAD, timeout=20)
    ok &= check("webhook entrada responde 200", r.status_code == 200, r.text[:80])

    def lead_status():
        r = requests.get(f"{BACKEND}/crm/lead", params={"phone": TEST_PHONE}, timeout=10,
                         headers={"X-Secret": CRM_SECRET})
        return r.json() if r.status_code == 200 else None

    ok &= wait_for(lambda: (lead_status() or {}).get("status") in ("wizard", "nuevo"))
    st = lead_status()
    ok &= check("lead creado en MySQL", st is not None)
    ok &= check("status inicial ok", st.get("status") in ("wizard", "nuevo"), f"status={st and st.get('status')}")

    status_inicial = st and st.get("status")
    if status_inicial == "nuevo":
        # Hora no laboral: la rama no laboral deja el lead en 'nuevo' (sin wizard).
        # Se siembra el estado que la rama laboral habría producido (status=wizard, question_index=1)
        # para poder ejercitar el resto del flujo (wizard -> cualificado -> warming).
        seed = {"status": "wizard", "question_index": 1}
        r = requests.post(f"{BACKEND}/crm/update-lead",
                          json={"phone": TEST_PHONE, "changes": seed},
                          headers={"X-Secret": CRM_SECRET}, timeout=10)
        st = lead_status()
        ok &= check("seed wizard (rama laboral simulada)",
                    r.status_code == 200 and st and st.get("status") == "wizard",
                    f"status={st and st.get('status')} qidx={st and st.get('question_index')}")

    for i, ans in enumerate(WIZARD_ANSWERS, start=1):
        r = requests.post(f"{N8N}/webhook/estudiovarq-reply-testing",
                          json={"phone": TEST_PHONE, "text": ans}, timeout=20)
        time.sleep(2)

    def wizard_done():
        st = lead_status() or {}
        return st.get("question_index") == 10 and st.get("status") == "cualificado"

    ok &= wait_for(wizard_done, timeout=120)
    st = lead_status() or {}
    ok &= check("wizard completo en MySQL (q9, cualificado)",
                st.get("question_index") == 10 and st.get("status") == "cualificado",
                f"qidx={st.get('question_index')} status={st.get('status')}")
    ok &= check("q1..q9 persistidas", all(st.get(f"q{i}") for i in range(1, 10)),
                str([st.get(f"q{i}") for i in range(1, 10)]))

    r = session.get(f"{BACKEND}/crm/metrics", timeout=10)
    ok &= check("metrics 200", r.status_code == 200)

    r = session.get(f"{BACKEND}/crm/calendar", timeout=30)
    ok &= check("calendar 200 (webhook GCal)", r.status_code == 200)

    # --- Warming con agendado (parte manual del gate automatizada) ---
    warming_msgs = [
        "Hola, si me interesa coordinar la llamada",
        "Coordinemos el lunes 10 de agosto a las 15 hs",
    ]
    for msg in warming_msgs:
        requests.post(f"{N8N}/webhook/estudiovarq-reply-testing",
                      json={"phone": TEST_PHONE, "text": msg}, timeout=20)
        time.sleep(8)

    def has_calendar_event():
        st = lead_status() or {}
        return bool(st.get("calendar_event_id"))

    got_event = wait_for(has_calendar_event, timeout=120, interval=5)
    if not got_event:
        # Reintento con mensaje más explícito (el LLM es variable)
        requests.post(f"{N8N}/webhook/estudiovarq-reply-testing",
                      json={"phone": TEST_PHONE,
                            "text": "Sí, agendemos para el lunes 10 de agosto a las 15 hs, dale"},
                      timeout=20)
        got_event = wait_for(has_calendar_event, timeout=120, interval=5)
    st = lead_status() or {}
    ok &= check("calendar_event_id persistido", got_event and bool(st.get("calendar_event_id")),
                f"calendar_event_id={st.get('calendar_event_id') or ''}")

    # Verificación del evento en GCal via webhook calendario
    cal_ev = None
    if st.get("calendar_event_id"):
        r = requests.post(f"{N8N}/webhook/estudiovarq-calendario",
                          json={"timeMin": "2026-08-01T00:00:00", "timeMax": "2026-08-31T23:59:59"},
                          headers={"X-Secret": CRM_SECRET}, timeout=30)
        events = r.json()
        if isinstance(events, dict):
            events = [events]
        cal_ev = [e for e in events if e.get("id") == st.get("calendar_event_id")]
        ok &= check("evento GCal presente en calendario", r.status_code == 200 and cal_ev,
                    json.dumps(cal_ev[0] if cal_ev else events)[:200])

    # --- Seguimientos (el /run de la API no existe: 405; se fuerza vía cron + prox_seg_ts pasado) ---
    seg_ok = False
    st = lead_status() or {}
    prox_actual = st.get("prox_seg_ts") or ""
    r = requests.post(f"{BACKEND}/crm/update-lead",
                      json={"phone": TEST_PHONE,
                            "changes": {"prox_seg_ts": "2020-01-01T00:00:00"}},
                      headers={"X-Secret": CRM_SECRET}, timeout=10)
    etapa_antes = (lead_status() or {}).get("etapa_seg")
    now = datetime.now()
    laboral = (now.weekday() < 5) and (8 <= now.hour < 18)
    if not laboral:
        # El workflow de Seguimientos solo avanza etapas en ventana laboral (Lun-Vie 08-18 ARG);
        # el check no puede pasar fuera de esa ventana (por diseño, no por bug).
        check("seguimiento: etapa_seg avanzó", False,
              f"etapa_antes={etapa_antes} etapa_despues={etapa_antes} "
              f"(ventana no laboral: {now.strftime('%a %H:%M')} ARG; el cron solo avanza Lun-Vie 08-18 ARG)")
    else:
        print(f"  -> esperando tick del cron de Seguimientos (cron */15; prox_seg_ts forzado al pasado, etapa={etapa_antes})...")
        seg_ok = wait_for(lambda: (lead_status() or {}).get("etapa_seg") != etapa_antes,
                          timeout=1000, interval=10)
        st = lead_status() or {}
        ok &= check("seguimiento: etapa_seg avanzó", seg_ok,
                    f"etapa_antes={etapa_antes} etapa_despues={st.get('etapa_seg')} ultimo_msg_ts={st.get('ultimo_msg_ts')}")

    with open("/tmp/opencode/gate2_report.txt", "w") as f:
        f.write("\n".join(f"{p} - {n}{(' - ' + e) if e else ''}" for p, n, e in STEPS))
    print("\nRESULTADO:", "TODO OK" if all(s[1] for s in STEPS) else "HUBO FALLOS")
    return 0 if all(s[1] for s in STEPS) else 1


if __name__ == "__main__":
    sys.exit(main())
