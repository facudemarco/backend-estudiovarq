from services.stages import extract_agendar_mark


def test_mark_extracted_and_stripped():
    start, cleaned = extract_agendar_mark(
        "Perfecto Facu! AGENDAR:2026-08-10T15:00:00-03:00 Te esperamos el lunes.")
    assert start == "2026-08-10T15:00:00-03:00"
    assert "AGENDAR" not in cleaned
    assert "Perfecto Facu!" in cleaned


def test_mark_with_seconds():
    start, cleaned = extract_agendar_mark("AGENDAR:2026-08-10T15:30:45-03:00 ok")
    assert start == "2026-08-10T15:30:45-03:00"


def test_no_mark_returns_none():
    start, cleaned = extract_agendar_mark("Hola, cualquier cosa avisame")
    assert start is None
    assert cleaned == "Hola, cualquier cosa avisame"


import os
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_parse_agendar_endpoint(client):
    resp = client.post("/crm/parse-agendar",
                       json={"reply": "OK AGENDAR:2026-08-10T15:00:00-03:00 listo"},
                       headers={"X-Secret": os.getenv("CRM_SECRET", "")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["start"] == "2026-08-10T15:00:00-03:00"
    assert "AGENDAR" not in body["message"]
