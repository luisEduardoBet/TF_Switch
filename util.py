try:
    # pysnmp 7.x
    from pysnmp.hlapi.v3arch.asyncio import *
except ImportError:
    # fallback para versões antigas (6.x)
    from pysnmp.hlapi.asyncio import *
import os

# IP/porta/community padrão do switch (usados quando nenhum IP é passado).
SWITCH_IP = os.getenv('SWITCH_IP', '10.90.90.90')
COMMUNITY = os.getenv('SWITCH_COMMUNITY', 'private')
PORTA_SNMP = int(os.getenv('SWITCH_PORT', '161'))


def get_client_ip(request):
    """Retorna o IP do cliente. Respeita X-Forwarded-For (útil atrás de
    proxy e em testes); senão usa o IP do socket."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


async def _make_target(ip):
    """Cria o alvo de transporte UDP de forma compatível com pysnmp 6.x e 7.x.
    Na 7.x a resolução de DNS é assíncrona via UdpTransportTarget.create();
    na 6.x usa-se o construtor direto."""
    endpoint = (ip, PORTA_SNMP)
    if hasattr(UdpTransportTarget, "create"):
        return await UdpTransportTarget.create(endpoint)
    return UdpTransportTarget(endpoint)


# Passa o IP procurado e retorna (MAC, porta) varrendo a tabela ARP do switch.
async def getSnmpMac(ip_procurado, switch_ip=None):
    switch_ip = switch_ip or SWITCH_IP
    oid_inicial = "1.3.6.1.2.1.4.22.1.2"
    oid_atual = oid_inicial

    snmp_engine = SnmpEngine()
    alvo_transporte = await _make_target(switch_ip)

    while True:
        res = next_cmd(
            snmp_engine,
            CommunityData(COMMUNITY, mpModel=1),
            alvo_transporte,
            ContextData(),
            ObjectType(ObjectIdentity(oid_atual)),
            lexicographicMode=False,
        )
        coroutine_alvo = res[0] if isinstance(res, tuple) else res
        errorIndication, errorStatus, errorIndex, varBinds = await coroutine_alvo

        if errorIndication or errorStatus or not varBinds:
            break

        varBind = varBinds[0]
        oid_retornado = str(varBind[0])
        valor_retornado = varBind[1].prettyPrint()

        if not oid_retornado.startswith(oid_inicial):
            break

        if oid_retornado.endswith(ip_procurado):
            partes_oid = oid_retornado.split('.')
            porta_detectada = partes_oid[-5]
            print("Valor REtornado:", valor_retornado)
            # retorna MAC e porta da interface referente ao ip solicitado
            return (valor_retornado, porta_detectada)

        if oid_atual == oid_retornado:
            break

        oid_atual = oid_retornado

    return None


# Lê o ifAdminStatus (1.3.6.1.2.1.2.2.1.7) de cada porta — o MESMO campo que o
# setSnmp escreve. Retorna {numero_porta: valor} com 1=up, 2=down, 3=testing,
# None quando o switch não respondeu.
async def getSnmpAdminStatus(switch_ip=None, num_portas=24):
    switch_ip = switch_ip or SWITCH_IP
    oid_base = "1.3.6.1.2.1.2.2.1.7"
    resultados = {}

    snmp_engine = SnmpEngine()
    alvo_transporte = await _make_target(switch_ip)

    for porta_id in range(1, num_portas + 1):
        oid_completo = f"{oid_base}.{porta_id}"
        errorIndication, errorStatus, _, varBinds = await get_cmd(
            snmp_engine,
            CommunityData(COMMUNITY, mpModel=1),
            alvo_transporte,
            ContextData(),
            ObjectType(ObjectIdentity(oid_completo)),
        )
        if errorIndication or errorStatus or not varBinds:
            resultados[porta_id] = None
        else:
            try:
                resultados[porta_id] = int(varBinds[0][1])
            except (ValueError, TypeError):
                resultados[porta_id] = None

    return resultados


# Faz o SET no ifAdminStatus de uma porta. status: 1=UP, 2=DOWN.
# Retorna True somente se o switch confirmou a alteração.
async def setSnmp(porta_id, novo_status, switch_ip=None):
    switch_ip = switch_ip or SWITCH_IP
    oid_base = "1.3.6.1.2.1.2.2.1.7"
    oid_completo = f"{oid_base}.{porta_id}"

    if novo_status not in [1, 2]:
        print("Status inválido! Use 1 para UP ou 2 para DOWN.")
        return False

    print(f"Enviando SET para {switch_ip} (Porta {porta_id} -> Status {novo_status})...")

    snmp_engine = SnmpEngine()
    alvo_transporte = await _make_target(switch_ip)

    errorIndication, errorStatus, indexError, varBinds = await set_cmd(
        snmp_engine,
        CommunityData(COMMUNITY, mpModel=1),
        alvo_transporte,
        ContextData(),
        ObjectType(ObjectIdentity(oid_completo), Integer32(novo_status)),
    )

    if errorIndication:
        print(f"Erro de comunicação: {errorIndication}")
        return False
    elif errorStatus:
        print(f"Erro SNMP ao tentar alterar: {errorStatus.prettyPrint()}")
        return False
    else:
        print(f"Sucesso! Porta {porta_id} alterada com êxito.")
        return True


async def setPortOn(port, switch_ip=None):
    return await setSnmp(port, 1, switch_ip)


async def setPortOff(port, switch_ip=None):
    return await setSnmp(port, 2, switch_ip)
