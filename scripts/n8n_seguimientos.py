"""Reemplaza los nodos Google Sheets del workflow de Seguimientos por HTTP Request al backend."""
import json
import os
import requests

N8N_BASE = "https://n8n.iwebtecnology.com/api/v1"
N8N_KEY = os.getenv("N8N_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiNzE0NmExYy04YTJhLTQ3NGYtYmJiNC01NWZjMGQ4ZjQ5NzkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOGVkMWJkZjItY2JjNS00NmViLWI1NDUtZTdmNGFkMjM2ODg3IiwiaWF0IjoxNzg0OTM2MDI0fQ.2BeT3WAS5okQwJ5ACMYtDltqCTYywgQ4MXz6SF8wssU")
WF_ID = "sBkQNCRqYLwGZ70M"
BACKEND = os.getenv("BACKEND_URL", "https://api-estudiovarq.iwebtecnology.com")
AGENT_URL = os.getenv("AGENT_URL", "https://api-estudiovarq.iwebtecnology.com/send")
HEADERS = [
    {"name": "Content-Type", "value": "application/json"},
    {"name": "X-Secret", "value": "={{ $credentials.httpHeaderAuth ? $credentials.httpHeaderAuth.value : '' }}"},
]


def _http_node(name: str, method: str, url: str, json_body: str, on_error: str, position: list,
               extra_options: dict | None = None) -> dict:
    options = {"retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000}
    if extra_options:
        options.update(extra_options)
    node = {
        "parameters": {
            "method": method,
            "url": url,
            "sendHeaders": True,
            "headerParameters": {"parameters": HEADERS},
            "options": options,
        },
        "id": f"sg-{name[:8]}-0001-0001-0001-000000000001",
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.4,
        "position": position,
        "onError": on_error or "stopWorkflow",
        "credentials": {"httpHeaderAuth": {"id": "lR6ya95Eh7j2TOEZ", "name": "EstudioVARq Secret"}},
    }
    if method == "POST":
        node["parameters"]["sendBody"] = True
        node["parameters"]["contentType"] = "json"
        node["parameters"]["specifyBody"] = "json"
        node["parameters"]["jsonBody"] = json_body
    return node


SHEET_TO_HTTP = {
    "Leer Leads": {
        "method": "GET",
        "url": f"{BACKEND}/crm/leads-pending",
        "body": "",
        "extra_options": {"splitIntoItems": True},
    },
    "Actualizar Etapa": {
        "method": "POST",
        "url": f"{BACKEND}/crm/update-lead",
        "body": "={{ JSON.stringify({ phone: $('Evaluar Seguimientos').item.json.phone, changes: $('Evaluar Seguimientos').item.json.sheet_update }) }}",
        "extra_options": None,
    },
}

SEND_URL_NODES = {"Enviar Seguimiento"}


# Bug real de producción (2026-08-07): el Code node del evaluador iteraba
# `for (const lead of $input.all())` y leía `lead.etapa_seg`, pero n8n (Code node v2)
# entrega los items envueltos como `{ json, pairedItem }` -> `lead.etapa_seg` era
# siempre undefined y el evaluador emitía [] SIEMPRE. Este fix idempotente lo propaga
# a la regeneración del workflow (por si el túnel o un re-import reintroducen el patrón).
OLD_LOOP_LINE = "for (const lead of $input.all()) {"
NEW_LOOP_LINE = (
    "for (const it of $input.all()) { "
    "const RL = (it && it.json) ? it.json : it; const lead = RL;"
)
FIXED_JS = f"{NEW_LOOP_LINE}\n"

# Retomar fuera de horario (2026-08-11): el lead que entra de noche/no laboral queda
# con etapa_seg='apertura' y prox_seg_ts vencido; el evaluador lo retoma en el primer
# tick laboral (el guard `laboral` ya lo espera) y le manda m1+m2 como si hubiera
# entrado en horario, pasándolo a wizard (idéntico al flujo laboral del workflow de entrada).
APERTURA_ANCHOR = "  const etapa = String(lead.etapa_seg || '');\n  const stage = CHAIN[etapa];"
APERTURA_BLOCK = """  const etapa = String(lead.etapa_seg || '');
  if (etapa === 'apertura') {
    // lead retomado fuera de horario: solo en horario laboral, manda m1+m2 y pasa a wizard
    if (!laboral) continue;
    const apname = String(lead.name || '').trim() || 'cliente';
    const aptotal = String(lead.totalsM2 || '').trim();
    const apm1 = 'Hola ' + apname + '! 👋👋\\n\\nComo estás? Soy Sofía, del equipo de Estudio VArq - Arquitectura.\\n\\nMe alegra que estés con el proyecto de tu casa! Felicitaciones! ❤️\\n\\nEn base a las respuestas que diste en nuestro formulario, hice los cálculos y *los metros cuadrados totales de tu casa ideal son ' + aptotal + ' m2*.';
    const apm2 = 'El próximo paso es: Ver tu casa terminada antes de construirla y saber cuánto saldría hacerla 🏡\\n\\nTe interesa?';
    const apupdate = { status: 'wizard', question_index: 1, prox_seg_ts: $now.plus({ hours: 6 }).toISO(), etapa_seg: '6h', ultimo_msg_ts: now.toISO() };
    const apphone = String(lead.phone || '');
    out.push({ json: { phone: apphone, name: apname, message: apm1, etapa_actual: 'apertura', sheet_update: apupdate } });
    out.push({ json: { phone: apphone, name: apname, message: apm2, etapa_actual: 'apertura', sheet_update: {} } });
    continue;
  }
  const stage = CHAIN[etapa];"""


def build_replaced_workflow(raw: dict) -> dict:
    wf = json.loads(json.dumps(raw))
    for node in wf["nodes"]:
        if node.get("name") in SHEET_TO_HTTP:
            spec = SHEET_TO_HTTP[node["name"]]
            new_node = _http_node(
                name=node["name"], method=spec["method"], url=spec["url"],
                json_body=spec["body"], on_error=node.get("onError"),
                position=node.get("position", [0, 0]),
                extra_options=spec.get("extra_options"),
            )
            node.clear()
            node.update(new_node)
        if node.get("name") in SEND_URL_NODES:
            node.setdefault("parameters", {})["url"] = AGENT_URL
        if node.get("name") == "Evaluar Seguimientos":
            code = (node.get("parameters") or {}).get("jsCode", "")
            if OLD_LOOP_LINE in code and "const RL = " not in code:
                code = code.replace(OLD_LOOP_LINE, NEW_LOOP_LINE, 1)
                print("   [fix] shape de items aplicado a 'Evaluar Seguimientos' (Code node v2)")
            if "apertura" not in code and APERTURA_ANCHOR in code:
                code = code.replace(APERTURA_ANCHOR, APERTURA_BLOCK, 1)
                print("   [fix] etapa 'apertura' (retomar fuera de horario) inyectada en el evaluador")
            node["parameters"]["jsCode"] = code
    return wf


def publish() -> None:
    headers = {"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"}
    raw = requests.get(f"{N8N_BASE}/workflows/{WF_ID}", headers=headers, timeout=30).json()
    new = build_replaced_workflow(raw)
    r = requests.put(f"{N8N_BASE}/workflows/{WF_ID}",
                     json={"name": raw.get("name"), "settings": raw.get("settings") or {},
                           "nodes": new["nodes"], "connections": new["connections"]},
                     headers=headers, timeout=30)
    r.raise_for_status()
    print("PUT ok. Sheets restantes:",
          [n["name"] for n in new["nodes"] if "googleSheets" in n.get("type", "")] or "ninguno")


if __name__ == "__main__":
    publish()
