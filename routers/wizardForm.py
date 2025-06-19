from fastapi import HTTPException, APIRouter
from pydantic import BaseModel
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

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
    body = f"Datos del cliente:\n \nNombre: {form_data.name}\nApellido: {form_data.lastName}\nTeléfono: {form_data.phone}\nEmail: {form_data.email}\nDirección: {form_data.address}\nZona de terreno existente: {form_data.zone}\n \nDatos del proyecto:\n \nFecha de inicio: {form_data.startDate}\nBaño: {form_data.bathroom}\nComedor: {form_data.diningRoom}\nCocina: {form_data.kitchen}\nLiving: {form_data.livingRoom}\nOtro tipo de ambiente: {form_data.anotherPlace}\nDormitorio principal: {form_data.mainBedroom}\nDormitorio secundario: {form_data.secondBedroom}\nPlantas: {form_data.plants}\nCochera: {form_data.garage}\nTotal de metros cuadrados: {form_data.totalsM2} \nComentarios: {form_data.comments}"
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

@router.post("/wizardForm")
async def send_email(form_data: FormData):
    wizardForm(form_data)
    return {"message": "Formulario enviado exitosamente"}

# -----

def wizardFormHouses(form_data: FormData):
    sender_email = "iweb.contacto@gmail.com"
    sender_password = os.environ.get("SENDER_PASSWORD")
    
    if not sender_password:
        raise HTTPException(status_code=500, detail="La contraseña del remitente no está configurada")
        
    receiver_email = "consultaform@estudiovarq.com.ar"
    subject = f"{form_data.name} {form_data.lastName} - M2 - Casas"
    body = f"Datos del cliente:\n \nNombre: {form_data.name}\nApellido: {form_data.lastName}\nTeléfono: {form_data.phone}\nEmail: {form_data.email}\nDirección: {form_data.address}\nZona de terreno existente: {form_data.zone}\n \nDatos del proyecto:\n \nFecha de inicio: {form_data.startDate}\nBaño: {form_data.bathroom}\nComedor: {form_data.diningRoom}\nCocina: {form_data.kitchen}\nLiving: {form_data.livingRoom}\nOtro tipo de ambiente: {form_data.anotherPlace}\nDormitorio principal: {form_data.mainBedroom}\nDormitorio secundario: {form_data.secondBedroom}\nPlantas: {form_data.plants}\nCochera: {form_data.garage}\nTotal de metros cuadrados: {form_data.totalsM2} \nComentarios: {form_data.comments}"
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

@router.post("/wizardFormHouses")
async def send_email2(form_data: FormData):
    wizardFormHouses(form_data)
    return {"message": "Formulario enviado exitosamente"}