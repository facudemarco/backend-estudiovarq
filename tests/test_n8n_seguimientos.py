# tests/test_n8n_seguimientos.py
import json
from pathlib import Path

def _wf():
    from scripts.n8n_seguimientos import build_replaced_workflow
    raw = json.loads((Path(__file__).parent.parent / "scripts" / "fixtures" / "wf-seg.json").read_text())
    return build_replaced_workflow(raw)

def test_sheets_replaced():
    wf = _wf()
    assert [n for n in wf["nodes"] if "googleSheets" in n.get("type", "")] == []

def test_leer_leads_uses_leads_pending_split():
    wf = _wf()
    n = [x for x in wf["nodes"] if x["name"] == "Leer Leads"][0]
    assert n["parameters"]["method"] == "GET"
    assert "crm/leads-pending" in n["parameters"]["url"]
    assert n["parameters"]["options"].get("splitIntoItems") is True

def test_actualizar_etapa_uses_phone():
    wf = _wf()
    n = [x for x in wf["nodes"] if x["name"] == "Actualizar Etapa"][0]
    assert "crm/update-lead" in n["parameters"]["url"]
    assert "phone: $json.phone" in n["parameters"]["jsonBody"]
    assert "sheet_update" in n["parameters"]["jsonBody"]
