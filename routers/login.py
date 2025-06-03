# from fastapi import APIRouter, Depends, HTTPException, Form, Request
# from Database.dbGetConnection import getConnectionForLogin
# from fastapi.responses import JSONResponse, RedirectResponse
# from typing import Annotated
# from fastapi.security import OAuth2PasswordBearer

# router = APIRouter()

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# def authenticate_user(username: str, password: str):
#     connection = getConnectionForLogin()
#     if not connection:
#         return None
    
#     cursor = connection.cursor(dictionary=True)
#     cursor.execute("SELECT * FROM credentials WHERE username = %s AND password = %s", (username, password))
#     user = cursor.fetchone()
#     cursor.close()
#     connection.close()
#     return user

# @router.get("/items/")
# async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
#     return {"token": token}

# @router.get('/admin', response_class=JSONResponse, summary="Página de Inicio de Sesión", description="Endpoint que indica que la página de inicio de sesión está disponible.")
# def login_admin(request: Request):
#     return JSONResponse(content={"message": "Inicio de sesión disponible"}, status_code=200)

# @router.post('/login', response_class=JSONResponse, summary="Inicio de Sesión de Usuario", description="Endpoint para el inicio de sesión del usuario. La respuesta indica la página a renderizar en caso de éxito o fracaso.")
# def login(username: Annotated[str, Form(description="Nombre de usuario")], password: Annotated[str, Form(description="Contraseña")]):
#     user = authenticate_user(username, password)
#     if user:
#         return JSONResponse(content={"message": "Inicio de sesión exitoso", "redirect_url": "/dashboard"}, status_code=200)
#     else:
#         return JSONResponse(content={"message": "Inicio de sesión fallido", "redirect_url": "/failed-login"}, status_code=401)

# @router.get('/dashboard', response_class=JSONResponse, summary="Dashboard", description="Endpoint que indica la página del dashboard.")
# def dashboard(request: Request):
#     return JSONResponse(content={"message": "Bienvenido al dashboard", "data": {"key": "value"}}, status_code=200)

# @router.get('/failed-login', response_class=JSONResponse, summary="Inicio de Sesión Fallido", description="Endpoint que indica la página de inicio de sesión fallido.")
# def failed_login(request: Request):
#     return JSONResponse(content={"message": "Inicio de sesión fallido"}, status_code=401)