# tests/test_n8n_calendario.py
import json
from pathlib import Path

def _gen_workflow():
    from scripts.n8n_calendario import build_calendario_workflow
    return build_calendario_workflow()

def test_workflow_has_webhook_gcal_chain():
    wf = _gen_workflow()
    nodes = {n["name"]: n for n in wf["nodes"]}
    assert set(nodes) == {"Webhook Calendario", "GCal Get All", "Responder Todo"}
    wh = nodes["Webhook Calendario"]
    assert wh["type"] == "n8n-nodes-base.webhook"
    assert wh["parameters"]["path"] == "estudiovarq-calendario"
    assert wh["parameters"]["httpMethod"] == "POST"
    assert wh["parameters"]["responseMode"] == "responseNode"
    assert wh["parameters"]["authentication"] == "headerAuth"
    assert wh["credentials"]["httpHeaderAuth"]["id"] == "lR6ya95Eh7j2TOEZ"
    gcal = nodes["GCal Get All"]
    assert gcal["type"] == "n8n-nodes-base.googleCalendar"
    assert gcal["parameters"]["operation"] == "getAll"
    assert gcal["credentials"]["googleCalendarOAuth2Api"]["id"] == "d4YauwT9uHxEtwxo"
    assert "timeMin" in json.dumps(gcal["parameters"]["options"])
    assert nodes["Responder Todo"]["type"] == "n8n-nodes-base.respondToWebhook"
    assert nodes["Responder Todo"]["parameters"]["respondWith"] == "allIncomingItems"
    assert wf["connections"]["Webhook Calendario"]["main"][0][0]["node"] == "GCal Get All"
    assert wf["connections"]["GCal Get All"]["main"][0][0]["node"] == "Responder Todo"
