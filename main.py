import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import db
import scheduler as sched
from util import getSnmpMac, setPortOff, setPortOn, get_client_ip, getSnmpAdminStatus

# Exige que o MAC da máquina cliente bata com o MAC cadastrado do usuário.
REQUIRE_MAC = os.getenv("REQUIRE_MAC", "1") == "1"
SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")

STATUS_LABEL = {1: "Liberada", 2: "Bloqueada", 3: "Teste", None: "Sem resposta"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.start_db()
    sched.start_scheduler()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
templates = Jinja2Templates(directory="templates")


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def current_user(request: Request):
    return request.session.get("user")


def redirect(url, status_code=303):
    return RedirectResponse(url, status_code=status_code)


async def resolve_client_mac(ip):
    """Procura o MAC do IP do cliente consultando os switches cadastrados
    (uma sala pode ter mais de um switch)."""
    tentados = set()
    for s in db.list_switches():
        if s["ip_addr"] in tentados:
            continue
        tentados.add(s["ip_addr"])
        info = await getSnmpMac(ip, s["ip_addr"])
        if info:
            return info[0]
    return None


# ----------------------------------------------------------------------------
# Autenticação
# ----------------------------------------------------------------------------
@app.get("/")
async def root(request: Request):
    if current_user(request):
        return redirect("/dashboard")
    return redirect("/login")


@app.get("/login")
async def login_page(request: Request, erro: str = None):
    return templates.TemplateResponse(request, "login.html", {"erro": erro})


@app.post("/login")
async def login(request: Request, login: str = Form(...), senha: str = Form(...)):
    user = db.verify_login(login, senha)
    if not user:
        return redirect("/login?erro=Usuário ou senha inválidos")

    # Camada extra: a máquina (MAC obtido via SNMP a partir do IP) deve ser uma
    # máquina REGISTRADA (MAC pertence a algum usuário). A senha identifica quem
    # é. Impede acesso a partir de máquinas desconhecidas.
    if REQUIRE_MAC:
        ip = get_client_ip(request)
        mac = await resolve_client_mac(ip) if ip else None
        if not mac or not db.get_user_by_mac(mac):
            return redirect("/login?erro=Máquina não autorizada")

    request.session["user"] = {
        "id": user["id"],
        "login": user["login"],
        "role": user["role"],
    }
    return redirect("/dashboard")


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return redirect("/login")


# ----------------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------------
async def _portas_com_estado_real(switches):
    """Monta as linhas de porta combinando o status do banco (intenção) com a
    leitura ao vivo do switch (realidade), por switch."""
    portas = db.get_portas()
    sw_map = {s["id"]: s for s in switches}

    live = {}
    for s in switches:
        live[s["id"]] = await getSnmpAdminStatus(s["ip_addr"], s["num_portas"])

    linhas = []
    for p in portas:
        switch_val = live.get(p["switch"], {}).get(p["porta"])
        db_val = 1 if p["status"] else 2
        linhas.append({
            "Id": p["Id"],
            "porta": p["porta"],
            "switch_id": p["switch"],
            "switch_nome": sw_map[p["switch"]]["nome"],
            "reservada": p["reservada"],
            "status": p["status"],
            "db_label": STATUS_LABEL[db_val],
            "switch_label": STATUS_LABEL.get(switch_val, "Desconhecido"),
            "ok": switch_val == db_val,
        })
    return linhas


@app.get("/dashboard")
async def dashboard(request: Request, erro: str = None):
    user = current_user(request)
    if not user:
        return redirect("/login")

    if user["role"] == "admin":
        switches = db.list_switches()
        ctx = {
            "user": user,
            "switches": switches,
            "linhas": await _portas_com_estado_real(switches),
            "agendamentos": db.list_agendamentos(),
            "professores": db.list_professores(),
            "erro": erro,
        }
        return templates.TemplateResponse(request, "admin.html", ctx)

    ctx = {
        "user": user,
        "switches": db.list_switches(),
        # Todas as portas: o professor vê o status; reservadas aparecem mas não
        # podem ser selecionadas (e o backend rejeita reservadas de qualquer forma).
        "portas": db.get_portas(),
        "agendamentos": db.list_agendamentos(criado_por=user["id"]),
        "erro": erro,
    }
    return templates.TemplateResponse(request, "professor.html", ctx)


# ----------------------------------------------------------------------------
# Ações do ADMIN
# ----------------------------------------------------------------------------
@app.post("/admin/porta/toggle")
async def admin_toggle(request: Request, porta_id: int = Form(...), action: str = Form(...)):
    user = current_user(request)
    if not user or user["role"] != "admin":
        return redirect("/login")

    porta = db.get_porta(porta_id)
    if not porta or porta["reservada"]:
        return redirect("/dashboard")

    # Ação manual do admin sobrepõe qualquer agendamento daquela porta.
    ag = db.get_agendamento_by_porta(porta_id)
    if ag:
        sched.cancel_agendamento_jobs(ag["id"])
        db.mark_agendamento_status(ag["id"], "cancelado")

    if action == "block":
        ok = await setPortOff(porta["porta"], porta["switch_ip"])
        novo_status = 0
    else:
        ok = await setPortOn(porta["porta"], porta["switch_ip"])
        novo_status = 1

    # Só atualiza o banco se o switch confirmou — o switch é a fonte da verdade.
    if ok:
        db.set_porta_status(porta_id, novo_status)
        return redirect("/dashboard")

    return redirect(
        f"/dashboard?erro=Falha ao falar com o switch {porta['switch_nome']} "
        f"(porta {porta['porta']}). Nada foi alterado."
    )


@app.post("/admin/professor/create")
async def admin_create_prof(
    request: Request,
    mac: str = Form(...),
    login: str = Form(...),
    senha: str = Form(...),
):
    user = current_user(request)
    if not user or user["role"] != "admin":
        return redirect("/login")
    ok, err = db.create_professor(mac.strip(), login.strip(), senha)
    if not ok:
        return redirect("/dashboard?erro=Não foi possível cadastrar (login ou MAC já existe).")
    return redirect("/dashboard")


@app.post("/admin/professor/delete")
async def admin_delete_prof(request: Request, user_id: int = Form(...)):
    user = current_user(request)
    if not user or user["role"] != "admin":
        return redirect("/login")
    db.delete_professor(user_id)
    return redirect("/dashboard")


# ----------------------------------------------------------------------------
# Ações do PROFESSOR
# ----------------------------------------------------------------------------
@app.post("/prof/agendamento/create")
async def prof_create_agendamento(
    request: Request,
    fim: str = Form(...),
    porta_ids: list[int] = Form(...),
    inicio: str = Form(None),
    inicio_now: str = Form(None),
):
    user = current_user(request)
    if not user:
        return redirect("/login")

    # "Iniciar agora": ignora o campo de data e usa o horário atual.
    if inicio_now:
        ini = datetime.now()
    elif inicio:
        ini = sched._parse(inicio)
    else:
        return redirect("/dashboard?erro=Informe o início ou marque 'Iniciar agora'.")

    f = sched._parse(fim)
    if f <= ini:
        return redirect("/dashboard?erro=O fim deve ser depois do início.")

    # Garante que nenhuma porta reservada seja bloqueada.
    validas = []
    for pid in porta_ids:
        p = db.get_porta(pid)
        if p and not p["reservada"]:
            validas.append(pid)
    if not validas:
        return redirect("/dashboard?erro=Nenhuma porta válida selecionada.")

    inicio_str = ini.strftime(sched.FMT)
    fim_str = f.strftime(sched.FMT)
    ag_id = db.create_agendamento(inicio_str, fim_str, user["id"], validas)
    sched.schedule_agendamento(ag_id, inicio_str, fim_str)
    return redirect("/dashboard")


# ----------------------------------------------------------------------------
# API JSON (usada pelo JS da página do professor para polling sem reload)
# ----------------------------------------------------------------------------
@app.get("/api/portas")
async def api_portas(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return JSONResponse(db.get_portas())


@app.get("/api/agendamentos")
async def api_agendamentos(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    criado_por = user["id"] if user["role"] != "admin" else None
    ags = db.list_agendamentos(criado_por=criado_por)
    return JSONResponse(ags)


# ----------------------------------------------------------------------------
# Cancelamento de agendamento (professor e admin)
# ----------------------------------------------------------------------------
@app.post("/agendamento/cancel")
async def cancel_agendamento(request: Request, agendamento_id: int = Form(...)):
    user = current_user(request)
    if not user:
        return redirect("/login")

    ag = db.get_agendamento(agendamento_id)
    if not ag:
        return redirect("/dashboard")

    # Professor só cancela o próprio; admin cancela qualquer um.
    if user["role"] != "admin" and ag["criado_por"] != user["id"]:
        return redirect("/dashboard")

    # Só cancela se ainda estiver ativo/pendente.
    if ag.get("status") not in ("pendente", "ativo"):
        return redirect("/dashboard")

    sched.cancel_agendamento_jobs(agendamento_id)
    db.mark_agendamento_status(agendamento_id, "cancelado")
    return redirect("/dashboard")
