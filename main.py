from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from util import * 


app =  FastAPI()
templates =  Jinja2Templates(directory="templates")

@app.get("/")
async def root(request:Request):
    host = request.client.host
    mac_addr = await getSnmpMac(host)

    return None  




