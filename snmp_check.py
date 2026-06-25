"""Diagnóstico: lê o ifAdminStatus de uma porta DIRETO do switch/simulador
via SNMP GET, sem passar pela aplicação web nem pelo banco.

Uso:
    python snmp_check.py <numero_da_porta>

Mostra o valor cru retornado pelo equipamento:
    1 = up (liberada) | 2 = down (bloqueada) | 3 = testing
"""
import asyncio
import sys

from util import SWITCH_IP, COMMUNITY, PORTA_SNMP, _make_target

try:
    from pysnmp.hlapi.v3arch.asyncio import (
        SnmpEngine, CommunityData, ContextData, ObjectType, ObjectIdentity, get_cmd,
    )
except ImportError:
    from pysnmp.hlapi.asyncio import (
        SnmpEngine, CommunityData, ContextData, ObjectType, ObjectIdentity, get_cmd,
    )

STATUS = {1: "up (liberada)", 2: "down (bloqueada)", 3: "testing"}


async def check(port):
    oid = f"1.3.6.1.2.1.2.2.1.7.{port}"
    engine = SnmpEngine()
    target = await _make_target(SWITCH_IP)

    errorIndication, errorStatus, _, varBinds = await get_cmd(
        engine, CommunityData(COMMUNITY, mpModel=1), target, ContextData(),
        ObjectType(ObjectIdentity(oid)),
    )

    print(f"Switch:  {SWITCH_IP}:{PORTA_SNMP}  (community '{COMMUNITY}')")
    print(f"OID:     {oid}  (ifAdminStatus da porta {port})")

    if errorIndication:
        print(f"ERRO de comunicação: {errorIndication}")
        return
    if errorStatus:
        print(f"ERRO SNMP: {errorStatus.prettyPrint()}")
        return

    raw = varBinds[0][1]
    try:
        val = int(raw)
        print(f"Valor lido do switch: {val} -> {STATUS.get(val, 'desconhecido')}")
    except (ValueError, TypeError):
        print(f"Valor lido do switch: vazio/sem instância (raw={raw.prettyPrint()!r})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python snmp_check.py <numero_da_porta>")
        sys.exit(1)
    asyncio.run(check(int(sys.argv[1])))
