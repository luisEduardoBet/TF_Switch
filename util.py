from pysnmp.hlapi.asyncio import *
import asyncio

SWITCH_IP = '127.0.0.1'
COMMUNITY = 'switch'
PORTA_SNMP = 1161

#função feita para django (ver se funciona no fastApi)
def get_client_ip(request): 
    return request.META.get("REMOTE_ADDR")


#passa o ip e retorna o MAC e porta do IP solicitante.
async def getSnmpMac(ip_procurado):
    """
    Varre a tabela ARP do switch e retorna o MAC correspondente ao IP solicitado,
    corrigido para a nova API de geradores do pySNMP.
    """
    oid_inicial = "1.3.6.1.2.1.4.22.1.2"
    oid_atual = oid_inicial
    
    snmp_engine = SnmpEngine()
    alvo_transporte = await UdpTransportTarget.create((SWITCH_IP, PORTA_SNMP))
    
    # print(f"Varrendo a tabela ARP para encontrar o MAC do IP: {ip_procurado}...")
    
    while True:

        res = next_cmd(
            snmp_engine,
            CommunityData(COMMUNITY, mpModel=1),
            alvo_transporte,
            ContextData(),
            ObjectType(ObjectIdentity(oid_atual)),
            lexicographicMode=False
        )
        
        if isinstance(res, tuple):
            coroutine_alvo = res[0]
        else:
            coroutine_alvo = res

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
            
            #retorna MAC e porta da interface referente ao ip solicitado
            return (valor_retornado, porta_detectada) 
            
        if oid_atual == oid_retornado: 
            break

        oid_atual = oid_retornado

    #MAC não encontrado 
    return None

#Pega o status de todas as interfaces do switch (Up ou Down)
async def getSnmpPort():
    oid_base = "1.3.6.1.2.1.2.2.1.8"
    
    status_map = {
        1: "Up",
        2: "Down",
        3: "Teste"
    }
    
    resultados = {}
    print(f"Buscando o status das portas no agente {SWITCH_IP}...")

    snmp_engine = SnmpEngine()
    
    alvo_transporte = await UdpTransportTarget.create((SWITCH_IP, PORTA_SNMP))

    for porta_id in range(1, 25):
        oid_completo = f"{oid_base}.{porta_id}"
        
        errorIndication, errorStatus, inderError, varBinds = await get_cmd(
            snmp_engine,
            CommunityData(COMMUNITY, mpModel=1),
            alvo_transporte,
            ContextData(),
            ObjectType(ObjectIdentity(oid_completo))
        )
        
        if errorIndication:
            print(f"Erro na porta {porta_id}: {errorIndication}")
            resultados[porta_id] = "Erro de Comunicação"
        elif errorStatus:
            print(f"Erro na porta {porta_id}: {errorStatus.prettyPrint()}")
            resultados[porta_id] = "Erro SNMP"
        else:
            for varBind in varBinds:
                val = int(varBind[1])
                status_texto = status_map.get(val, f"Desconhecido ({val})")
                resultados[porta_id] = status_texto

    return resultados


#Função para fazer o set nas portas (passar a porta e o status desejado[1- para Up, 2 - para Down])
async def setSnmp(porta_id, novo_status):

    oid_base = "1.3.6.1.2.1.2.2.1.7"
    oid_completo = f"{oid_base}.{porta_id}"
    
    if novo_status not in [1, 2]:
        print("Status inválido! Use 1 para UP ou 2 para DOWN.")
        return False

    print(f"Enviando SET para o switch {SWITCH_IP} (Porta {porta_id} -> Status {novo_status})...")

    snmp_engine = SnmpEngine()
    alvo_transporte = await UdpTransportTarget.create((SWITCH_IP, PORTA_SNMP))

    errorIndication, errorStatus, indexError, varBinds = await set_cmd(
        snmp_engine,
        CommunityData(COMMUNITY, mpModel=1), 
        alvo_transporte,
        ContextData(),
        ObjectType(ObjectIdentity(oid_completo), Integer32(novo_status))
    )

    if errorIndication:
        print(f"Erro de comunicação: {errorIndication}")
        return False
    elif errorStatus:
        print(f"Erro SNMP ao tentar alterar: {errorStatus.prettyPrint()}")
        return False
    else:
        print(f"Sucesso! Porta {porta_id} alterada com êxito.")
        for varBind in varBinds:
            print(f"Confirmado pelo switch: {varBind[0].prettyPrint()} = {varBind[1].prettyPrint()}")
        return True
    
async def setPortOn(port):
    await setSnmp(port, 1)

async def setPortOff(port):
    await setSnmp(port, 2)


async def main():

    ip_alvo = "192.168.1.200" 
    
    mac_descoberto = await getSnmpMac(ip_alvo)
    if mac_descoberto:
        print(f"Endereço MAC do host: {mac_descoberto}")

if __name__ == "__main__":
    asyncio.run(main())

