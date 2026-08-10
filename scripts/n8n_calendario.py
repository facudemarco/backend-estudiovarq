"""Construye y publica el workflow n8n 'EstudioVARq — Calendario'."""
import json
import os
import sys
import requests

from pathlib import Path

N8N_BASE = "https://n8n.iwebtecnology.com/api/v1"
N8N_KEY = os.getenv("N8N_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiNzE0NmExYy04YTJhLTQ3NGYtYmJiNC01NWZjMGQ4ZjQ5NzkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOGVkMWJkZjItY2JjNS00NmViLWI1NDUtZTdmNGFkMjM2ODg3IiwiaWF0IjoxNzg0OTM2MDI0fQ.2BeT3WAS5okQwJ5ACMYtDltqCTYywgQ4MXz6SF8wssU")
GCAI_ID = "d4YauwT9uHxEtwxo"
GCAI_NAME = "Google Calendar account"
HTTP_AUTH_ID = "lR6ya95Eh7j2TOEZ"
HTTP_AUTH_NAME = "EstudioVARq Secret"


def build_calendario_workflow() -> dict:
    webhook = {
        "parameters": {
            "httpMethod": "POST",
            "path": "estudiovarq-calendario",
            "responseMode": "responseNode",
            "authentication": "headerAuth",
            "options": {},
        },
        "id": "cal-0000-0001-0000-000000000001",
        "name": "Webhook Calendario",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [-220, 300],
        "credentials": {"httpHeaderAuth": {"id": HTTP_AUTH_ID, "name": HTTP_AUTH_NAME}},
    }
    gcal = {
        "parameters": {
            "operation": "getAll",
            "calendar": {"__rl": True, "mode": "list", "value": "primary"},
            "options": {
                "timeMin": "={{ $json.body ? ($json.body.timeMin || '') : '' }}",
                "timeMax": "={{ $json.body ? ($json.body.timeMax || '') : '' }}",
            },
        },
        "id": "cal-0000-0001-0000-000000000002",
        "name": "GCal Get All",
        "type": "n8n-nodes-base.googleCalendar",
        "typeVersion": 3,
        "position": [40, 300],
        "credentials": {"googleCalendarOAuth2Api": {"id": GCAI_ID, "name": GCAI_NAME}},
    }
    respond = {
        "parameters": {"respondWith": "allIncomingItems"},
        "id": "cal-0000-0001-0000-000000000003",
        "name": "Responder Todo",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.2,
        "position": [300, 300],
    }
    return {
        "name": "EstudioVARq — Calendario",
        "nodes": [webhook, gcal, respond],
        "connections": {
            "Webhook Calendario": {"main": [[{"node": "GCal Get All", "type": "main", "index": 0}]]},
            "GCal Get All": {"main": [[{"node": "Responder Todo", "type": "main", "index": 0}]]},
        },
        "settings": {"executionOrder": "v1"},
    }


def publish_calendario() -> dict:
    headers = {"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"}
    payload = build_calendario_workflow()
    existing = requests.get(f"{N8N_BASE}/workflows", headers=headers, timeout=30,
                            params={"name": payload["name"]}).json()
    wfs = [w for w in existing.get("data", []) if w.get("name") == payload["name"]]
    if wfs:
        wf_id = wfs[0]["id"]
        body = {k: payload[k] for k in ("name", "nodes", "connections", "settings")}
        r = requests.put(f"{N8N_BASE}/workflows/{wf_id}", json=body, headers=headers, timeout=30)
        r.raise_for_status()
        print(f"workflow actualizado: {wf_id}")
        return r.json()
    r = requests.post(f"{N8N_BASE}/workflows", json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def main() -> None:
    wf = publish_calendario()
    print(f"workflow creado: {wf['id']} name={wf['name']} active={wf['active']}")


if __name__ == "__main__":
    main()
