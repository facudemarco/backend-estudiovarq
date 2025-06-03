from fastapi import FastAPI
import uvicorn
from models.product import Product
# from routers.login import router as routerLogin
from routers.contact import router as routerContact
from routers.wizardForm import router as routerWizardForm
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://estudiovarq.com.ar",
    "https://www.estudiovarq.com.ar",
    "https://estudio-varq.vercel.app",
    "https://www.estudio-varq.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
def read_root():
    return {"message": "Estudio VArq API by iWeb Techonology. All rights reserved"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

# app.include_router(routerLogin)

app.include_router(routerContact)
app.include_router(routerWizardForm)