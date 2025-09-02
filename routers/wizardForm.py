from fastapi import HTTPException, APIRouter
from pydantic import BaseModel
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
import requests
import uuid

load_dotenv()

router = APIRouter()

class FormData(BaseModel):
    address: str
    anotherPlace: str
    bathroom: str
    comments: str
    diningRoom: str
    email: str
    garage: str
    kitchen: str
    lastName: str
    livingRoom: str
    mainBedroom: str
    name: str
    phone: str
    totalsM2: float
    plants: str
    secondBedroom: str
    startDate: str
    zone: str

def wizardForm(form_data: FormData):
    sender_email = "iweb.contacto@gmail.com"
    sender_password = os.environ.get("SENDER_PASSWORD")
    if not sender_password:
        raise HTTPException(status_code=500, detail="La contraseña del remitente no está configurada")

    receiver_email = "consultaform@estudiovarq.com.ar"
    subject = f"{form_data.name} {form_data.lastName} - M2 - Inicio"
    body = (
        f"Datos del cliente:\n \nNombre: {form_data.name}\nApellido: {form_data.lastName}\n"
        f"Teléfono: {form_data.phone}\nEmail: {form_data.email}\nDirección: {form_data.address}\n"
        f"Zona de terreno existente: {form_data.zone}\n \nDatos del proyecto:\n \nFecha de inicio: {form_data.startDate}\n"
        f"Baño: {form_data.bathroom}\nComedor: {form_data.diningRoom}\nCocina: {form_data.kitchen}\n"
        f"Living: {form_data.livingRoom}\nOtro tipo de ambiente: {form_data.anotherPlace}\n"
        f"Dormitorio principal: {form_data.mainBedroom}\nDormitorio secundario: {form_data.secondBedroom}\n"
        f"Plantas: {form_data.plants}\nCochera: {form_data.garage}\nTotal de metros cuadrados: {form_data.totalsM2} \n"
        f"Comentarios: {form_data.comments}"
    )
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("Correo enviado exitosamente")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")
        raise HTTPException(status_code=500, detail="Error al enviar el correo")
    try:
        lead_id = str(uuid.uuid4())
        webhook_url = os.environ.get(
            "N8N_ENTRADA_URL",  # prod
            "https://n8n.iwebtecnology.com/webhook/estudiovarq-chat"
        )
        payload = {
            "lead_id": lead_id,
            "name": form_data.name,
            "lastName": form_data.lastName,
            "email": form_data.email,
            "phone": str(form_data.phone),
            "calendly_link": os.environ.get(
                "CALENDLY_LINK_DEFAULT",
                "https://calendly.com/lasshaky-fju6/llamada-con-un-arquitecto"
            ),
            "address": form_data.address,
            "anotherPlace": form_data.anotherPlace,
            "bathroom": form_data.bathroom,
            "comments": form_data.comments,
            "diningRoom": form_data.diningRoom,
            "garage": form_data.garage,
            "kitchen": form_data.kitchen,
            "livingRoom": form_data.livingRoom,
            "mainBedroom": form_data.mainBedroom,
            "totalsM2": form_data.totalsM2,
            "plants": form_data.plants,
            "secondBedroom": form_data.secondBedroom,
            "startDate": form_data.startDate,
            "zone": form_data.zone,
            "source": "wizardForm"
        }
        requests.post(webhook_url, json=payload, timeout=20)
    except Exception as e:
        print(f"Error al enviar datos a n8n: {e}")

@router.post("/wizardForm")
async def send_email(form_data: FormData):
    wizardForm(form_data)
    return {"message": "Formulario enviado exitosamente"}

def wizardFormHouses(form_data: FormData):
    try:
        lead_id = str(uuid.uuid4())
        webhook_url = os.environ.get(
            "N8N_ENTRADA_URL",
            "https://n8n.iwebtecnology.com/webhook/estudiovarq-chat"
        )
        payload = {
            "lead_id": lead_id,
            "name": form_data.name,
            "lastName": form_data.lastName,
            "email": form_data.email,
            "phone": str(form_data.phone),
            "calendly_link": os.environ.get(
                "CALENDLY_LINK_DEFAULT",
                "https://calendly.com/lasshaky-fju6/llamada-con-un-arquitecto"
            ),
            "address": form_data.address,
            "anotherPlace": form_data.anotherPlace,
            "bathroom": form_data.bathroom,
            "comments": form_data.comments,
            "diningRoom": form_data.diningRoom,
            "garage": form_data.garage,
            "kitchen": form_data.kitchen,
            "livingRoom": form_data.livingRoom,
            "mainBedroom": form_data.mainBedroom,
            "totalsM2": form_data.totalsM2,
            "plants": form_data.plants,
            "secondBedroom": form_data.secondBedroom,
            "startDate": form_data.startDate,
            "zone": form_data.zone,
            "source": "wizardFormHouses"
        }
        requests.post(webhook_url, json=payload, timeout=20)
    except Exception as e:
        print(f"Error al enviar datos a n8n: {e}")

@router.post("/wizardFormHouses")
async def send_email2(form_data: FormData):
    wizardFormHouses(form_data)
    return {"message": "Formulario enviado exitosamente"}