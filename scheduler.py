"""Agendamento de bloqueios/desbloqueios usando APScheduler.

Cada agendamento gera dois jobs:
  - block_<id>   : executado em 'inicio'  -> desliga as portas
  - unblock_<id> : executado em 'fim'     -> religa as portas e remove o agendamento
"""
import os
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import db
from util import setPortOff, setPortOn

_TZ = os.getenv("TZ")
scheduler = AsyncIOScheduler(timezone=_TZ) if _TZ else AsyncIOScheduler()

FMT = "%Y-%m-%d %H:%M:%S"


def _parse(dt):
    if isinstance(dt, datetime):
        return dt
    # aceita "YYYY-MM-DD HH:MM:SS" e "YYYY-MM-DDTHH:MM"
    dt = str(dt).replace("T", " ")
    for fmt in (FMT, "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(dt, fmt)
        except ValueError:
            continue
    raise ValueError(f"Formato de data inválido: {dt}")


async def _block_ports(agendamento_id):
    portas = db.get_agendamento_portas(agendamento_id)
    for p in portas:
        ok = await setPortOff(p["porta"], p["switch_ip"])
        if ok:
            db.set_porta_status(p["id"], 0)
        else:
            print(f"[scheduler] FALHA ao bloquear porta {p['porta']} "
                  f"no switch {p['switch_nome']} ({p['switch_ip']}).")
    db.mark_agendamento_status(agendamento_id, "ativo")
    print(f"[scheduler] Agendamento {agendamento_id}: bloqueio processado.")


async def _unblock_ports(agendamento_id):
    portas = db.get_agendamento_portas(agendamento_id)
    for p in portas:
        ok = await setPortOn(p["porta"], p["switch_ip"])
        if ok:
            db.set_porta_status(p["id"], 1)
        else:
            print(f"[scheduler] FALHA ao liberar porta {p['porta']} "
                  f"no switch {p['switch_nome']} ({p['switch_ip']}).")
    db.mark_agendamento_status(agendamento_id, "concluido")
    print(f"[scheduler] Agendamento {agendamento_id}: liberação processada (concluido).")


def schedule_agendamento(agendamento_id, inicio, fim):
    """Registra os jobs de bloqueio/desbloqueio de um agendamento."""
    inicio = _parse(inicio)
    fim = _parse(fim)
    agora = datetime.now()

    # Se o início já passou (ex.: reagendamento após reinício), bloqueia agora.
    run_block = inicio if inicio > agora else agora
    # misfire_grace_time alto garante que o job rode mesmo se o horário passar
    # antes do scheduler processá-lo (ex.: início "agora" ou app reiniciado).
    scheduler.add_job(
        _block_ports, "date", run_date=run_block, args=[agendamento_id],
        id=f"block_{agendamento_id}", replace_existing=True,
        misfire_grace_time=3600, coalesce=True,
    )
    scheduler.add_job(
        _unblock_ports, "date", run_date=fim, args=[agendamento_id],
        id=f"unblock_{agendamento_id}", replace_existing=True,
        misfire_grace_time=3600, coalesce=True,
    )


def cancel_agendamento_jobs(agendamento_id):
    for prefix in ("block", "unblock"):
        job_id = f"{prefix}_{agendamento_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)


def reschedule_pending():
    """Reagenda no startup tudo que ainda não terminou (jobs ficam em memória)."""
    for ag in db.list_pending_agendamentos():
        schedule_agendamento(ag["id"], ag["inicio"], ag["fim"])


def start_scheduler():
    if not scheduler.running:
        scheduler.start()
    reschedule_pending()
