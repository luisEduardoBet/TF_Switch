# Conectando a um Switch Real

Este guia explica passo a passo como substituir o simulador pelo switch físico do laboratório.

---

## O que você vai precisar

- O **IP do switch** na rede (ex.: `192.168.1.1`)
- A **community SNMP** configurada no switch (pergunte ao administrador de rede — geralmente é `public` para leitura)
- Se o switch tiver community separada para escrita (ex.: `private`), você vai precisar dela também
- Docker e Docker Compose instalados na máquina que vai rodar o sistema

---

## Passo 1 — Descobrir as informações do switch

Antes de qualquer coisa, confirme com o administrador de rede:

| Informação | O que é | Exemplo |
|---|---|---|
| IP do switch | Endereço do equipamento na rede | `192.168.1.1` |
| Community de leitura | Senha usada para consultar o switch | `public` |
| Community de escrita | Senha usada para alterar o switch | `private` |
| Número de portas | Quantas portas o switch tem | `24` ou `48` |

> Se o switch usar a mesma community para leitura e escrita, você só precisa de uma.

---

## Passo 2 — Editar o arquivo `docker-compose.yml`

Abra o arquivo `docker-compose.yml` na pasta do projeto. Ele tem esta aparência:

```yaml
services:
  snmpsim:
    ...

  web:
    ...
    environment:
      - SWITCH_IP=snmpsim
      - SWITCH_PORT=1161
      - SWITCH_COMMUNITY=switch
      - SWITCH_COMMUNITY_WRITE=switch
      ...
    depends_on:
      - snmpsim
```

Faça as seguintes alterações:

### 2.1 — Comentar o serviço do simulador

Adicione `#` no início das linhas do serviço `snmpsim` e da dependência:

```yaml
# snmpsim:           # linha comentada — simulador não é mais necessário
#   build:
#     ...

  web:
    ...
    # depends_on:    # linha comentada
    #   - snmpsim   # linha comentada
```

### 2.2 — Preencher os dados do switch real

Altere as variáveis de ambiente do serviço `web`:

```yaml
    environment:
      - SWITCH_IP=192.168.1.1      # coloque o IP do seu switch aqui
      - SWITCH_PORT=161            # porta padrão SNMP em switches reais
      - SWITCH_COMMUNITY=public    # community de leitura do seu switch
      - SWITCH_COMMUNITY_WRITE=private  # community de escrita (se for igual à de leitura, pode repetir o mesmo valor)
      - SECRET_KEY=uma-chave-secreta-longa-e-dificil  # troque por qualquer texto longo
      - REQUIRE_MAC=1
```

> **Dica:** Se o switch usar a mesma community para leitura e escrita, coloque o mesmo valor nas duas variáveis.

---

## Passo 3 — Verificar o número de portas

O sistema lê por padrão **24 portas**. Se o seu switch tiver um número diferente (ex.: 48), informe o administrador do sistema para que o valor seja ajustado no código antes de subir.

---

## Passo 4 — Subir o sistema

No terminal, dentro da pasta do projeto, execute:

```bash
docker compose up --build
```

Aguarde até aparecer uma mensagem parecida com:

```
web-1  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

Acesse `http://localhost:8000` no navegador.

---

## Passo 5 — Verificar se o switch está respondendo

Antes de testar pelo navegador, verifique a comunicação com o switch executando:

```bash
docker compose exec web python snmp_check.py 1
```

Substitua o `1` pelo número de qualquer porta do switch.

**Saída esperada (switch respondendo):**
```
Switch:  192.168.1.1:161  (community 'public')
OID:     1.3.6.1.2.1.2.2.1.7.1  (ifAdminStatus da porta 1)
Valor lido do switch: 1 -> up (liberada)
```

**Se aparecer erro de comunicação**, verifique:

- O IP está correto e o switch está ligado e acessível na rede
- A porta `161/udp` não está bloqueada por firewall
- A community está escrita exatamente igual à configurada no switch (maiúsculas e minúsculas importam)

---

## Resumo das alterações no `docker-compose.yml`

| O que muda | Valor no simulador | Valor no switch real |
|---|---|---|
| `SWITCH_IP` | `snmpsim` | IP do switch (ex.: `192.168.1.1`) |
| `SWITCH_PORT` | `1161` | `161` |
| `SWITCH_COMMUNITY` | `switch` | community de leitura (ex.: `public`) |
| `SWITCH_COMMUNITY_WRITE` | `switch` | community de escrita (ex.: `private`) |
| Serviço `snmpsim` | ativo | comentado (não é mais necessário) |
| `depends_on: snmpsim` | ativo | comentado |
