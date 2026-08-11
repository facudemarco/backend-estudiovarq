"""Reemplaza los nodos Google Sheets del workflow de entrada por HTTP Request al backend."""
import json
import os
import requests

N8N_BASE = "https://n8n.iwebtecnology.com/api/v1"
N8N_KEY = os.getenv("N8N_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiNzE0NmExYy04YTJhLTQ3NGYtYmJiNC01NWZjMGQ4ZjQ5NzkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOGVkMWJkZjItY2JjNS00NmViLWI1NDUtZTdmNGFkMjM2ODg3IiwiaWF0IjoxNzg0OTM2MDI0fQ.2BeT3WAS5okQwJ5ACMYtDltqCTYywgQ4MXz6SF8wssU")
WF_ID = "h1kQ7hg0aWjYXl4v"
BACKEND = os.getenv("BACKEND_URL", "https://api-estudiovarq.iwebtecnology.com")
AGENT_URL = os.getenv("AGENT_URL", "https://api-estudiovarq.iwebtecnology.com/send")
HEADERS = [
    {"name": "Content-Type", "value": "application/json"},
    {"name": "X-Secret", "value": "={{ $credentials.httpHeaderAuth ? $credentials.httpHeaderAuth.value : '' }}"},
]


def _http_node(name: str, url: str, json_body: str, on_error: str, position: list) -> dict:
    return {
        "parameters": {
            "method": "POST",
            "url": url,
            "sendBody": True,
            "contentType": "json",
            "specifyBody": "json",
            "jsonBody": json_body,
            "sendHeaders": True,
            "headerParameters": {"parameters": HEADERS},
            "options": {"retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000},
        },
        "id": f"in-{name[:8]}-0001-0001-0001-000000000001",
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.4,
        "position": position,
        "onError": on_error or "stopWorkflow",
        "credentials": {"httpHeaderAuth": {"id": "lR6ya95Eh7j2TOEZ", "name": "EstudioVARq Secret"}},
    }


SHEET_TO_HTTP = {
    "Upsert lead (laboral)": {
        "url": f"{BACKEND}/crm/upsert-lead",
        "body": "={{ JSON.stringify($json.lead) }}",
    },
    "Upsert lead (no laboral)": {
        "url": f"{BACKEND}/crm/upsert-lead",
        "body": "={{ JSON.stringify($json.lead) }}",
    },
    "Sheets status=wizard": {
        "url": f"{BACKEND}/crm/update-lead",
        "body": ("={{ JSON.stringify({ phone: $('Armar msg m1+m2').item.json.lead.phone, "
                 "changes: { status: 'wizard', question_index: 1, "
                 "prox_seg_ts: $now.plus({hours: 6}).toISO(), etapa_seg: '6h' } }) }}"),
    },
    "Sheets status=nuevo (no laboral)": {
        "url": f"{BACKEND}/crm/update-lead",
        "body": ("={{ JSON.stringify({ phone: $('Armar msg no laboral').item.json.lead.phone, "
                 "changes: { status: 'nuevo', etapa_seg: 'apertura', "
                 "prox_seg_ts: $now.minus({minutes: 1}).toISO() } }) }}"),
    },
}

AGENT_SEND_NODES = {"Enviar m1", "Enviar m2", "Enviar aviso no laboral"}


def build_replaced_workflow(raw: dict) -> dict:
    wf = json.loads(json.dumps(raw))
    for node in wf["nodes"]:
        if node.get("name") in SHEET_TO_HTTP:
            spec = SHEET_TO_HTTP[node["name"]]
            new_node = _http_node(
                name=node["name"], url=spec["url"], json_body=spec["body"],
                on_error=node.get("onError"), position=node.get("position", [0, 0]),
            )
            node.clear()
            node.update(new_node)
        elif node.get("name") in AGENT_SEND_NODES:
            node.setdefault("parameters", {})["url"] = AGENT_URL
    return wf


def publish() -> None:
    headers = {"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"}
    raw = requests.get(f"{N8N_BASE}/workflows/{WF_ID}", headers=headers, timeout=30).json()
    new = build_replaced_workflow(raw)
    r = requests.put(f"{N8N_BASE}/workflows/{WF_ID}",
                      json={"name": raw.get("name", ""), "settings": raw.get("settings", {}),
                            "nodes": new["nodes"], "connections": new["connections"]},
                      headers=headers, timeout=30)
    r.raise_for_status()
    sheets = [n["name"] for n in new["nodes"] if "googleSheets" in n.get("type", "")]
    print(f"PUT ok. Sheets restantes: {sheets or 'ninguno'}")


if __name__ == "__main__":
    publish()
