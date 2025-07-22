from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

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
