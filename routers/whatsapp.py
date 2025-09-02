# routers/whatsapp.py
from fastapi import APIRouter, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel
import os
import requests

router = APIRouter()

# === Config ===
N8N_REPLIES_URL = os.getenv(
    "N8N_REPLIES_URL",
    "https://n8n.iwebtecnology.com/webhook/estudiovarq-replies",
)
REPLIES_SECRET = os.getenv(
    "REPLIES_SECRET",
    "MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_EstudioVARq",
)
WHATSAPP_AGENT_URL = os.getenv(
    "WHATSAPP_AGENT_URL",
    "http://127.0.0.1:3008/send",
)

# === Models ===
class WhatsAppMsg(BaseModel):
    from_: str
    text: str

class MessageRequest(BaseModel):
    phone: str
    message: str

# === Endpoints ===
@router.get("/api/whatsapp-health")
def health():
    return {"ok": True}

@router.post("/api/whatsapp-webhook")
async def whatsapp_webhook(
    msg: WhatsAppMsg,
    background_tasks: BackgroundTasks,
    x_secret: str | None = Header(default=None),
):
    # Simple auth via header
    if REPLIES_SECRET and x_secret != REPLIES_SECRET:
        print("backend: invalid secret on /api/whatsapp-webhook")
        raise HTTPException(status_code=401, detail="invalid secret")

    print(f"backend: received reply {msg.from_} -> {msg.text!r}")
    background_tasks.add_task(handle_whatsapp, msg.from_, msg.text)
    return {"ok": True}

def handle_whatsapp(phone: str, text: str):
    try:
        payload = {"phone": phone, "text": text}
        r = requests.post(N8N_REPLIES_URL, json=payload, timeout=10)
        print(f"backend→n8n: {r.status_code} {r.text[:200]}")
        r.raise_for_status()
    except Exception as e:
        print(f"Error notificando reply a n8n: {e}")

@router.post("/send")
def send_message(req: MessageRequest):
    try:
        r = requests.post(
            WHATSAPP_AGENT_URL,
            json={"phone": req.phone, "message": req.message},
            timeout=10,
        )
        r.raise_for_status()
        # Puede que el agent devuelva texto plano
        try:
            return {"status": "ok", "log": r.json()}
        except Exception:
            return {"status": "ok", "log": r.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))