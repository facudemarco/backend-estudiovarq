from fastapi import FastAPI
import os
import uvicorn
from models.houses import Houses
# from routers.login import router as routerLogin
from routers.house import router as routerHouses
from routers.contact import router as routerContact
from routers.wizardForm import router as routerWizardForm
from routers.whatsapp import router as routerWhatsapp
from routers.crm import router as routerCrm
from routers.auth import router as routerAuth, get_current_user
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://www.estudiovarq.com.ar",
    "https://estudiovarq-website.vercel.app",
    "https://estudiovarq.com.ar",
    "estudiovarq-website.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Secret"],
)

BOT_PATHS = {"/agent/state", "/agent/qr"}


CRM_X_SECRET = os.environ.get("CRM_SECRET", "MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_EstudioVARq")

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if path.startswith("/crm/"):
            x_secret = request.headers.get("X-Secret")
            if x_secret == CRM_X_SECRET:
                return await call_next(request)
            session = request.cookies.get("session")
            if not get_current_user(session):
                return JSONResponse(status_code=401, content={"detail": "no autenticado"})
        if path == "/auth/me":
            session = request.cookies.get("session")
            if not get_current_user(session):
                return JSONResponse(status_code=401, content={"detail": "no autenticado"})
        return await call_next(request)


app.add_middleware(AuthMiddleware)


@app.get('/')
def read_root():
    return {"message": "Estudio VArq API by iWeb Techonology. All rights reserved"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

# app.include_router(routerLogin)
app.include_router(routerHouses)
app.include_router(routerContact)
app.include_router(routerWizardForm)
app.include_router(routerWhatsapp)
app.include_router(routerCrm)
app.include_router(routerAuth)