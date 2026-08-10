# tests/test_n8n_reply.py
import json
from pathlib import Path

def _wf():
    from scripts.n8n_reply import build_replaced_workflow
    raw = json.loads((Path(__file__).parent.parent / "scripts" / "fixtures" / "wf-reply.json").read_text())
    return build_replaced_workflow(raw)

def test_sheets_replaced():
    wf = _wf()
    assert [n for n in wf["nodes"] if "googleSheets" in n.get("type", "")] == []

def test_read_lead_is_get_with_phone():
    wf = _wf()
    n = [x for x in wf["nodes"] if x["name"] == "Read Lead por Telefono"][0]
    assert n["type"] == "n8n-nodes-base.httpRequest"
    assert n["parameters"]["method"] == "GET"
    assert "/crm/lead?phone=" in n["parameters"]["url"]

def test_update_nodes_use_sheet_update():
    wf = _wf()
    g = [x for x in wf["nodes"] if x["name"] == "Guardar Respuesta Wizard"][0]
    assert "changes: $json.sheet_update" in g["parameters"]["jsonBody"]
    c = [x for x in wf["nodes"] if x["name"] == "Actualizar Calificación"][0]
    assert "calificacion.sheet_update" in c["parameters"]["jsonBody"]
