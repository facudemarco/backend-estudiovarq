"""Rediseña el WarmingAgent: agendado GCal determinista + persistencia de calendar_event_id."""
import json
import os
import requests
from pathlib import Path

N8N_BASE = "https://n8n.iwebtecnology.com/api/v1"
N8N_KEY = os.getenv("N8N_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiNzE0NmExYy04YTJhLTQ3NGYtYmJiNC01NWZjMGQ4ZjQ5NzkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOGVkMWJkZjItY2JjNS00NmViLWI1NDUtZTdmNGFkMjM2ODg3IiwiaWF0IjoxNzg0OTM2MDI0fQ.2BeT3WAS5okQwJ5ACMYtDltqCTYywgQ4MXz6SF8wssU")
WF_ID = "8y9D3gwEyjhEbWA7"
BACKEND = os.getenv("BACKEND_URL", "https://northwest-united-scott-conducted.trycloudflare.com")
GCAI_ID = "d4YauwT9uHxEtwxo"
GCAI_NAME = "Google Calendar account"
HEADERS = [
    {"name": "Content-Type", "value": "application/json"},
    {"name": "X-Secret", "value": "={{ $credentials.httpHeaderAuth ? $credentials.httpHeaderAuth.value : '' }}"},
]

def _parsear_agendar_code(backend: str, x_secret: str) -> str:
    return f"""const out = $json || {{}};
let start = null;
let end = null;
let clean = String(out.reply || '');
try {{
  const res = await this.helpers.httpRequest({{
    method: 'POST',
    url: '{backend}/crm/parse-agendar',
    headers: {{ 'Content-Type': 'application/json', 'X-Secret': '{x_secret}' }},
    body: JSON.stringify({{ reply: String(out.reply || '') }}),
  }});
  const data = (typeof res === 'string') ? JSON.parse(res) : res;
  start = data.start || null;
  clean = data.message || clean;
}} catch (e) {{
  start = null;
}}
if (start) {{
  const d = new Date(start);
  d.setMinutes(d.getMinutes() + 30);
  end = d.toISOString();
}}
return [{{ json: {{ phone: out.phone, chatInput: out.chatInput, lead_name: out.lead_name || '', reply: clean, clean_reply: clean, start, end }} }}];"""


def _crm_secret_from_env() -> str:
    """Lee CRM_SECRET del .env del backend (los Code nodes no usan credenciales)."""
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    secret = os.getenv("CRM_SECRET", "").strip()
    if not secret:
        raise RuntimeError("CRM_SECRET no está en backend-estudiovarq/.env")
    return secret


def _code_node(name: str, code: str, position: list, node_id: str) -> dict:
    return {
        "parameters": {"language": "javaScript", "mode": "runOnceForAllItems", "jsCode": code},
        "id": node_id, "name": name, "type": "n8n-nodes-base.code",
        "typeVersion": 2, "position": position,
    }


ENSAMBLAR_CODE = """const f = $('Formatear Salida').first().json;
return [{ json: { phone: f.phone, reply: f.reply } }];"""


def build_warming_workflow(raw: dict, x_secret: str | None = None) -> dict:
    secret = x_secret or _crm_secret_from_env()
    wf = json.loads(json.dumps(raw))
    wf["nodes"] = [n for n in wf["nodes"] if n.get("name") != "Agendar Llamada"]
    for node in wf["nodes"]:
        if node.get("name") == "AI Agent":
            node["parameters"]["options"]["systemMessage"] = node["parameters"]["options"].get("systemMessage", "") + "\n\nAGENDADO: cuando el cliente confirme día y hora exactos, agregá al final de tu mensaje la línea: AGENDAR:YYYY-MM-DDTHH:MM:SS-03:00 (ejemplo AGENDAR:2026-08-10T15:00:00-03:00). No crees eventos: solo reportás la fecha."
    parsear_code = _parsear_agendar_code(BACKEND, secret)
    new_names = {"Parsear Agendar", "IF tiene fecha", "Crear Evento GCal",
                 "Persistir calendar_event_id", "Ensamblar salida"}
    wf["nodes"] = [n for n in wf["nodes"] if n.get("name") not in new_names]
    wf["nodes"] += [
        _code_node("Parsear Agendar", parsear_code, [460, 0], "wm-parsear-0001-0001-0001-000000000001"),
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                    "conditions": [{
                        "id": "c1", "leftValue": "={{ $json.start }}", "rightValue": "",
                        "operator": {"type": "string", "operation": "notEmpty", "singleValue": True},
                    }],
                    "combinator": "and",
                },
                "options": {},
            },
            "id": "wm-if-0002-0002-0002-000000000002",
            "name": "IF tiene fecha",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [680, 0],
        },
        {
            "parameters": {
                "operation": "create",
                "calendar": {"__rl": True, "mode": "list", "value": "primary", "cachedResultName": "Primary calendar"},
                "start": "={{ $json.start }}",
                "end": "={{ $json.end }}",
                "summary": "Llamada venta - {{ $json.lead_name }}",
                "options": {},
            },
            "id": "wm-gcal-0003-0003-0003-000000000003",
            "name": "Crear Evento GCal",
            "type": "n8n-nodes-base.googleCalendar",
            "typeVersion": 3,
            "position": [900, -120],
            "credentials": {"googleCalendarOAuth2Api": {"id": GCAI_ID, "name": GCAI_NAME}},
        },
        {
            "parameters": {
                "method": "POST",
                "url": f"{BACKEND}/crm/update-lead",
                "sendBody": True,
                "contentType": "json",
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify({ phone: $('Formatear Salida').first().json.phone, changes: { calendar_event_id: $json.id } }) }}",
                "sendHeaders": True,
                "headerParameters": {"parameters": HEADERS},
                "options": {"retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000},
            },
            "id": "wm-persist-0004-0004-0004-000000000004",
            "name": "Persistir calendar_event_id",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.4,
            "position": [1120, -120],
            "onError": "continueErrorOutput",
            "credentials": {"httpHeaderAuth": {"id": "lR6ya95Eh7j2TOEZ", "name": "EstudioVARq Secret"}},
        },
        _code_node("Ensamblar salida", ENSAMBLAR_CODE, [900, 120], "wm-ensamblar-0005-0005-0005-000000000005"),
    ]
    wf["connections"] = {
        "Execute Workflow Trigger": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
        "OpenRouter Chat Model": {"ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]]},
        "Simple Memory": {"ai_memory": [[{"node": "AI Agent", "type": "ai_memory", "index": 0}]]},
        "Pinecone Vector Store": {"ai_tool": [[{"node": "AI Agent", "type": "ai_tool", "index": 0}]]},
        "Embeddings Qwen": {"ai_embedding": [[{"node": "Pinecone Vector Store", "type": "ai_embedding", "index": 0}]]},
        "AI Agent": {"main": [[{"node": "Formatear Salida", "type": "main", "index": 0}]]},
        "Formatear Salida": {"main": [[{"node": "Parsear Agendar", "type": "main", "index": 0}]]},
        "Parsear Agendar": {"main": [[{"node": "IF tiene fecha", "type": "main", "index": 0}]]},
        "IF tiene fecha": {"main": [
            [{"node": "Crear Evento GCal", "type": "main", "index": 0}],
            [{"node": "Ensamblar salida", "type": "main", "index": 0}],
        ]},
        "Crear Evento GCal": {"main": [[{"node": "Persistir calendar_event_id", "type": "main", "index": 0}]]},
        "Persistir calendar_event_id": {"main": [[{"node": "Ensamblar salida", "type": "main", "index": 0}]]},
        "Ensamblar salida": {"main": [[{"node": "Armar evento (warming)", "type": "main", "index": 0}]]},
        "Armar evento (warming)": {"main": [[{"node": "Notificar CRM (warming)", "type": "main", "index": 0}]]},
    }
    return wf


def publish() -> None:
    headers = {"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"}
    raw = requests.get(f"{N8N_BASE}/workflows/{WF_ID}", headers=headers, timeout=30).json()
    new = build_warming_workflow(raw)
    r = requests.put(f"{N8N_BASE}/workflows/{WF_ID}",
                     json={"name": raw.get("name"), "settings": raw.get("settings") or {},
                           "nodes": new["nodes"], "connections": new["connections"]},
                     headers=headers, timeout=30)
    r.raise_for_status()
    print("PUT ok. Nodos:", len(new["nodes"]))


if __name__ == "__main__":
    publish()
