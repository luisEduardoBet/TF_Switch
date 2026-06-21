from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from util import * 
from db import *



start_db()
app =  FastAPI()
templates =  Jinja2Templates(directory="templates")



@app.get("/")
async def root(request:Request):
    host = request.client.host
    mac_addr= await getSnmpMac(host)
    admin = verify_admin(mac_addr[0]) if mac_addr else None            

    if admin: 
        return templates.TemplateResponse(request, "index.html")

    return "Usuário Não habilitado a acessar o sistema"
    




