import os
import threading
import time
from datetime import datetime

from dotenv import load_dotenv
from google.auth.exceptions import DefaultCredentialsError
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv(override=True)

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
SHEET_LEADS = os.getenv("GOOGLE_SHEET_LEADS", "Leads")
SHEET_MESSAGES = os.getenv("GOOGLE_SHEET_MESSAGES", "Mensajes")
SHEET_EVENTS = os.getenv("GOOGLE_SHEET_EVENTS", "Eventos")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_client = None
_leads_cache = None
_leads_cache_ts = 0.0
_LEADS_TTL = 30.0
_sheets_lock = threading.RLock()

MESSAGES_HEADERS = ["id", "phone", "direction", "text", "ts", "actor"]
EVENTS_HEADERS = ["id", "phone", "step", "ts", "actor"]

from services.stages import (  # noqa: F401  (re-export para compat)
    CHAIN,
    add_delay,
    derive_stage,
    next_etapa,
    normalize_phone,
)


def get_client():
    global _client
    with _sheets_lock:
        if _client is not None:
            return _client
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not creds_path or not os.path.exists(creds_path):
            raise DefaultCredentialsError(
                "GOOGLE_APPLICATION_CREDENTIALS no apunta a un JSON de service account"
            )
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        _client = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return _client


def _values_to_rows(values, headers):
    rows = []
    for line in values or []:
        row = {}
        for i, h in enumerate(headers):
            row[h] = line[i] if i < len(line) else ""
        rows.append(row)
    return rows


def ensure_sheets():
    client = get_client()
    meta = client.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
    for title, headers in ((SHEET_MESSAGES, MESSAGES_HEADERS), (SHEET_EVENTS, EVENTS_HEADERS)):
        if title in existing:
            continue
        body = {
            "requests": [
                {
                    "addSheet": {
                        "properties": {"title": title},
                    }
                },
                {
                    "appendCells": {
                        "sheetId": None,
                        "rows": [{"values": [{"userEnteredValue": {"stringValue": h}} for h in headers]}],
                        "fields": "userEnteredValue",
                    }
                },
            ]
        }
        add_resp = client.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": [body["requests"][0]]},
        ).execute()
        new_sheet_id = add_resp["replies"][0]["addSheet"]["properties"]["sheetId"]
        client.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={
                "requests": [
                    {
                        "appendCells": {
                            "sheetId": new_sheet_id,
                            "rows": [
                                {"values": [{"userEnteredValue": {"stringValue": h}} for h in headers]}
                            ],
                            "fields": "userEnteredValue",
                        }
                    }
                ]
            },
        ).execute()


def read_leads() -> dict:
    global _leads_cache, _leads_cache_ts
    with _sheets_lock:
        if _leads_cache is not None and (time.time() - _leads_cache_ts) < _LEADS_TTL:
            return _leads_cache
        client = get_client()
        resp = client.spreadsheets().values().get(
            spreadsheetId=SHEET_ID, range=f"{SHEET_LEADS}!A1:AP", majorDimension="ROWS"
        ).execute()
        values = resp.get("values", [])
        if not values:
            _leads_cache = {}
            _leads_cache_ts = time.time()
            return {}
        headers = values[0]
        leads = {}
        for line in values[1:]:
            row = {}
            for i, h in enumerate(headers):
                row[h] = line[i] if i < len(line) else ""
            if not row.get("phone"):
                continue
            phone = normalize_phone(row["phone"])
            if phone:
                row["phone"] = phone
                leads[phone] = row
        _leads_cache = leads
        _leads_cache_ts = time.time()
        return leads


def invalidate_leads_cache():
    global _leads_cache_ts
    _leads_cache_ts = 0.0


def _read_sheet_all(title: str, headers: list) -> list:
    with _sheets_lock:
        client = get_client()
        resp = client.spreadsheets().values().get(
            spreadsheetId=SHEET_ID, range=f"{title}!A1:F", majorDimension="ROWS"
        ).execute()
        return _values_to_rows(resp.get("values", []), headers)


def read_messages(phone: str) -> list:
    rows = _read_sheet_all(SHEET_MESSAGES, MESSAGES_HEADERS)
    phone_n = normalize_phone(phone)
    return [r for r in rows if normalize_phone(r.get("phone", "")) == phone_n]


def read_events(phone: str) -> list:
    rows = _read_sheet_all(SHEET_EVENTS, EVENTS_HEADERS)
    phone_n = normalize_phone(phone)
    return [r for r in rows if normalize_phone(r.get("phone", "")) == phone_n]


def _append_row(title: str, values: list):
    with _sheets_lock:
        client = get_client()
        client.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range=f"{title}!A:F",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [values]},
        ).execute()


def _next_id(rows: list) -> int:
    ids = [int(r.get("id") or 0) for r in rows if str(r.get("id", "")).isdigit()]
    return (max(ids) + 1) if ids else 1


def append_message(phone: str, direction: str, text: str, actor: str):
    rows = _read_sheet_all(SHEET_MESSAGES, MESSAGES_HEADERS)
    _append_row(
        SHEET_MESSAGES,
        [
            _next_id(rows),
            normalize_phone(phone),
            direction,
            str(text)[:4000],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            actor,
        ],
    )


def append_event(phone: str, step: str, actor: str):
    rows = _read_sheet_all(SHEET_EVENTS, EVENTS_HEADERS)
    _append_row(
        SHEET_EVENTS,
        [
            _next_id(rows),
            normalize_phone(phone),
            step,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            actor,
        ],
    )


def update_lead(phone: str, changes: dict):
    if not changes:
        return
    phone_n = normalize_phone(phone)
    with _sheets_lock:
        leads = read_leads()
        if phone_n not in leads:
            return
        client = get_client()
        resp = client.spreadsheets().values().get(
            spreadsheetId=SHEET_ID, range=f"{SHEET_LEADS}!A1:AP", majorDimension="ROWS"
        ).execute()
        values = resp.get("values", [])
        if not values:
            return
        headers = values[0]
        phone_col = None
        for j, h in enumerate(headers):
            if h == "phone":
                phone_col = j
                break
        if phone_col is None:
            return
        row_index = None
        for i, line in enumerate(values[1:], start=2):
            if not line:
                continue
            cell = line[phone_col] if phone_col < len(line) else ""
            if normalize_phone(cell) == phone_n:
                row_index = i
                break
        if row_index is None:
            return
        col_updates = []
        for key, value in changes.items():
            if key in headers:
                col = headers.index(key)
                col_updates.append({"range": f"{SHEET_LEADS}!{_col_letter(col)}{row_index}", "values": [[value]]})
        if col_updates:
            client.spreadsheets().values().batchUpdate(
                spreadsheetId=SHEET_ID,
                body={"valueInputOption": "USER_ENTERED", "data": col_updates},
            ).execute()
        invalidate_leads_cache()


def _col_letter(idx: int) -> str:
    letter = ""
    while idx >= 0:
        letter = chr(65 + (idx % 26)) + letter
        idx = idx // 26 - 1
    return letter
