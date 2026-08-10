# tests/test_calendar.py
from unittest.mock import Mock, patch

from requests.exceptions import HTTPError


def test_calendar_proxies_to_n8n_webhook(client):
    fake_events = [
        {"id": "evt-1", "summary": "Llamada venta - Facu",
         "start": {"dateTime": "2026-08-06T10:00:00-03:00"},
         "end": {"dateTime": "2026-08-06T10:30:00-03:00"}},
    ]
    with patch("routers.crm.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = fake_events
        resp = client.get("/crm/calendar", params={"time_min": "2026-08-01T00:00:00", "time_max": "2026-08-31T23:59:59"})
    assert resp.status_code == 200
    body = resp.json()
    assert body == [{"id": "evt-1", "summary": "Llamada venta - Facu",
                     "start": "2026-08-06T10:00:00-03:00", "end": "2026-08-06T10:30:00-03:00"}]
    args, kwargs = mock_post.call_args
    assert "estudiovarq-calendario" in args[0]
    assert kwargs["json"] == {"timeMin": "2026-08-01T00:00:00", "timeMax": "2026-08-31T23:59:59"}
    assert kwargs["headers"]["X-Secret"]


def test_calendar_empty_when_webhook_returns_empty(client):
    with patch("routers.crm.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = []
        resp = client.get("/crm/calendar")
    assert resp.status_code == 200
    assert resp.json() == []


def test_calendar_raises_502_when_webhook_fails(client):
    with patch("routers.crm.requests.post") as mock_post:
        mock_post.side_effect = HTTPError("boom")
        resp = client.get("/crm/calendar")
    assert resp.status_code == 502


def test_calendar_wraps_single_event_dict(client):
    single = {"id": "evt-solo", "summary": "Llamada venta - Facu",
              "start": {"dateTime": "2026-08-06T15:00:00-03:00"},
              "end": {"dateTime": "2026-08-06T15:30:00-03:00"}}
    with patch("routers.crm.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = single
        resp = client.get("/crm/calendar")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == "evt-solo"
