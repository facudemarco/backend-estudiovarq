"""Reemplaza los nodos Google Sheets del ReplyHandler por HTTP Request al backend."""
import json
import os
import requests

N8N_BASE = "https://n8n.iwebtecnology.com/api/v1"
N8N_KEY = os.getenv("N8N_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiNzE0NmExYy04YTJhLTQ3NGYtYmJiNC01NWZjMGQ4ZjQ5NzkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOGVkMWJkZjItY2JjNS00NmViLWI1NDUtZTdmNGFkMjM2ODg3IiwiaWF0IjoxNzg0OTM2MDI0fQ.2BeT3WAS5okQwJ5ACMYtDltqCTYywgQ4MXz6SF8wssU")
WF_ID = "Pb3sx6n97pbvLDFH"
BACKEND = os.getenv("BACKEND_URL", "https://northwest-united-scott-conducted.trycloudflare.com")
HEADERS = [
    {"name": "Content-Type", "value": "application/json"},
    {"name": "X-Secret", "value": "={{ $credentials.httpHeaderAuth ? $credentials.httpHeaderAuth.value : '' }}"},
]


def _http_node(name: str, method: str, url: str, json_body: str, on_error: str, position: list) -> dict:
    node = {
        "parameters": {
            "method": method,
            "url": url,
            "sendHeaders": True,
            "headerParameters": {"parameters": HEADERS},
            "options": {"retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000},
        },
        "id": f"rp-{name[:8]}-0001-0001-0001-000000000001",
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
    "Read Lead por Telefono": {
        "method": "GET",
        "url": f"{BACKEND}/crm/lead?phone={{{{ $json.phone }}}}",
        "body": "",
    },
    "Guardar Respuesta Wizard": {
        "method": "POST",
        "url": f"{BACKEND}/crm/update-lead",
        "body": "={{ JSON.stringify({ phone: $json.sheet_row.phone, changes: $json.sheet_update }) }}",
    },
    "Actualizar Calificación": {
        "method": "POST",
        "url": f"{BACKEND}/crm/update-lead",
        "body": ("={{ JSON.stringify({ phone: $('Procesar Respuesta Wizard').first().json.calificacion_sheet_row.phone, "
                 "changes: $('Procesar Respuesta Wizard').first().json.calificacion.sheet_update }) }}"),
    },
}


def build_replaced_workflow(raw: dict) -> dict:
    wf = json.loads(json.dumps(raw))
    for node in wf["nodes"]:
        if node.get("name") in SHEET_TO_HTTP:
            spec = SHEET_TO_HTTP[node["name"]]
            new_node = _http_node(
                name=node["name"], method=spec["method"], url=spec["url"],
                json_body=spec["body"], on_error=node.get("onError"),
                position=node.get("position", [0, 0]),
            )
            node.clear()
            node.update(new_node)
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
