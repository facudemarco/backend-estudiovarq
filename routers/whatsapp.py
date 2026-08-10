# routers/whatsapp.py
from fastapi import APIRouter, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel
import os
import requests

router = APIRouter()

# === Config ===
REPLIES_SECRET = os.getenv(
    "REPLIES_SECRET",
    "MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_EstudioVARq",
)

# OJO: este debe apuntar al AGENT, no a /send
WHATSAPP_AGENT_BASE_URL = os.getenv(
    "WHATSAPP_AGENT_URL",
    "http://localhost:3008",  # base
).rstrip("/")

WHATSAPP_AGENT_SEND_URL = f"{WHATSAPP_AGENT_BASE_URL}/send"
WHATSAPP_AGENT_UNSTOP_URL = f"{WHATSAPP_AGENT_BASE_URL}/unstopp"  # nueva ruta

# (Opcional) si alguna vez lo reactivás
N8N_REPLIES_URL = os.getenv(
    "N8N_REPLIES_URL",
    "https://n8n.iwebtecnology.com/webhook/estudiovarq-reply",
)

# === Models ===
class WhatsAppMsg(BaseModel):
    from_: str
    text: str

class MessageRequest(BaseModel):
    phone: str
    message: str

class UnstopRequest(BaseModel):
    phone: str

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
    if REPLIES_SECRET and x_secret != REPLIES_SECRET:
        print("backend: invalid secret on /api/whatsapp-webhook")
        raise HTTPException(status_code=401, detail="invalid secret")

    print(f"backend: received reply {msg.from_} -> {msg.text!r}")
    background_tasks.add_task(handle_whatsapp, msg.from_, msg.text)
    return {"ok": True}

def handle_whatsapp(phone: str, text: str):
    #   Si querés reactivar el forward a n8n, dejalo listo:
    try:
        payload = {"phone": phone, "text": text}
        r = requests.post(N8N_REPLIES_URL, json=payload, timeout=10)
        print(f"backend→n8n: {r.status_code} {r.text[:200]}")
        r.raise_for_status()
    except Exception as e:
        print(f"Error notificando reply a n8n: {e}")
    print(f"backend: mensaje recibido de {phone}: {text}")

@router.post("/send")
def send_message(req: MessageRequest):
    try:
        r = requests.post(
            WHATSAPP_AGENT_SEND_URL,
            json={"phone": req.phone, "message": req.message},
            timeout=10,
        )
        r.raise_for_status()
        try:
            return {"status": "ok", "log": r.json()}
        except Exception:
            return {"status": "ok", "log": r.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/unstopp")
def unstop_lead(
    req: UnstopRequest,
    x_secret: str | None = Header(default=None),
):
    """
    Desbloquea un phone en el agent (borra stopped.json para ese número).
    Recomendado proteger con el mismo X-Secret.
    """
    if REPLIES_SECRET and x_secret != REPLIES_SECRET:
        print("backend: invalid secret on /unstopp")
        raise HTTPException(status_code=401, detail="invalid secret")

    try:
        r = requests.post(
            WHATSAPP_AGENT_UNSTOP_URL,
            json={"phone": req.phone},
            timeout=10,
        )
        r.raise_for_status()
        try:
            return {"status": "ok", "log": r.json()}
        except Exception:
            return {"status": "ok", "log": r.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
