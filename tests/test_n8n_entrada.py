# tests/test_n8n_entrada.py
import json
from pathlib import Path

def _wf_from_fixture():
    from scripts.n8n_entrada import build_replaced_workflow, SHEET_TO_HTTP
    raw = json.loads((Path(__file__).parent.parent / "scripts" / "fixtures" / "wf-entrada.json").read_text())
    return build_replaced_workflow(raw)

def test_all_sheet_nodes_replaced():
    wf = _wf_from_fixture()
    sheets = [n for n in wf["nodes"] if "googleSheets" in n.get("type", "")]
    assert sheets == []
    names = {n["name"] for n in wf["nodes"]}
    assert names == {"Webhook entrada", "Normalizar lead", "IF horario laboral",
                     "Armar msg m1+m2", "Armar msg no laboral", "Enviar m1", "Enviar m2",
                     "Enviar aviso no laboral", "Wait 5s",
                     "Armar evento (bienvenida)", "Armar evento (no laboral)",
                     "Notificar CRM (bienvenida)", "Notificar CRM (no laboral)",
                     "Upsert lead (laboral)", "Upsert lead (no laboral)",
                     "Sheets status=wizard", "Sheets status=nuevo (no laboral)"}

def test_status_wizard_body_uses_correct_expressions():
    wf = _wf_from_fixture()
    n = [x for x in wf["nodes"] if x["name"] == "Sheets status=wizard"][0]
    assert n["type"] == "n8n-nodes-base.httpRequest"
    body = n["parameters"]["jsonBody"]
    assert "crm/update-lead" in n["parameters"]["url"]
    assert "'wizard'" in body
    assert "Armar msg m1+m2" in body
    assert n["credentials"]["httpHeaderAuth"]["id"] == "lR6ya95Eh7j2TOEZ"
    assert n["parameters"]["method"] == "POST"
