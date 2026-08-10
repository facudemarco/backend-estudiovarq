import json
from pathlib import Path

def _wf():
    from scripts.n8n_warming import build_warming_workflow
    raw = json.loads((Path(__file__).parent.parent / "scripts" / "fixtures" / "wf-warming.json").read_text())
    return build_warming_workflow(raw, x_secret="test-secret")

def test_tool_removed_and_new_chain():
    wf = _wf()
    assert not any(n.get("name") == "Agendar Llamada" for n in wf["nodes"])
    names = {n["name"] for n in wf["nodes"]}
    assert {"Parsear Agendar", "IF tiene fecha", "Crear Evento GCal",
            "Persistir calendar_event_id", "Ensamblar salida"} <= names

def test_parsear_agendar_uses_this_helpers_http_request():
    wf = _wf()
    n = [x for x in wf["nodes"] if x["name"] == "Parsear Agendar"][0]
    assert "this.helpers.httpRequest" in n["parameters"]["jsCode"]
    assert "$helpers.httpRequest" not in n["parameters"]["jsCode"]

def test_build_is_idempotent():
    from scripts.n8n_warming import build_warming_workflow
    wf1 = _wf()
    wf2 = build_warming_workflow(wf1, x_secret="test-secret")
    names = [n["name"] for n in wf2["nodes"]]
    assert names.count("Parsear Agendar") == 1
    assert names.count("IF tiene fecha") == 1
    assert names.count("Crear Evento GCal") == 1
    assert names.count("Persistir calendar_event_id") == 1
    assert names.count("Ensamblar salida") == 1

def test_ensamblar_salida_preserves_reply_shape():
    wf = _wf()
    n = [x for x in wf["nodes"] if x["name"] == "Ensamblar salida"][0]
    assert "phone" in n["parameters"]["jsCode"] and "reply" in n["parameters"]["jsCode"]
    assert "Formatear Salida" in n["parameters"]["jsCode"]

def test_gcal_create_uses_calendar_creds():
    wf = _wf()
    n = [x for x in wf["nodes"] if x["name"] == "Crear Evento GCal"][0]
    assert n["type"] == "n8n-nodes-base.googleCalendar"
    assert n["parameters"]["operation"] == "create"
    assert n["credentials"]["googleCalendarOAuth2Api"]["id"] == "d4YauwT9uHxEtwxo"

def test_connections_chain():
    wf = _wf()
    conn = wf["connections"]
    assert conn["AI Agent"]["main"][0][0]["node"] == "Formatear Salida"
    assert conn["Formatear Salida"]["main"][0][0]["node"] == "Parsear Agendar"
    assert conn["Parsear Agendar"]["main"][0][0]["node"] == "IF tiene fecha"
    assert conn["IF tiene fecha"]["main"][0][0]["node"] == "Crear Evento GCal"
    assert conn["IF tiene fecha"]["main"][1][0]["node"] == "Ensamblar salida"
    assert conn["Crear Evento GCal"]["main"][0][0]["node"] == "Persistir calendar_event_id"
    assert conn["Persistir calendar_event_id"]["main"][0][0]["node"] == "Ensamblar salida"
    assert conn["Ensamblar salida"]["main"][0][0]["node"] == "Armar evento (warming)"
