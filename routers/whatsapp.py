from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
import subprocess
import json
import requests

router = APIRouter()

class WhatsAppMsg(BaseModel):
    from_: str
    text: str

@router.post("/api/whatsapp-webhook")
async def whatsapp_webhook(msg: WhatsAppMsg, background_tasks: BackgroundTasks):
    background_tasks.add_task(handle_whatsapp, msg.from_, msg.text)
    return {"received": True}

def handle_whatsapp(phone: str, text: str):
    # Aquí llama a tu flujo n8n, o procesa
    print(f"Webhook received: {phone} -> {text}")

class MessageRequest(BaseModel):
    phone: str
    message: str

@router.post("/send")
def send_message(req: MessageRequest):
    try:
        response = requests.post("https://api-estudiovarq.iwebtecnology.com/send", json={
            "phone": req.phone,
            "message": req.message
        })
        response.raise_for_status()
        return {"status": "ok", "log": response.json()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))