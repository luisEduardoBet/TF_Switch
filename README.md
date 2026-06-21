# TF_Switch

Plataforma web para controle de acesso à internet em laboratórios de informática. O professor bloqueia portas de um switch gerenciável via SNMP diretamente pelo navegador, sem precisar acessar o equipamento.

Desenvolvido como Trabalho Final da disciplina de **Gerência e Mobilidade de Redes** — UDESC.

---

## Funcionalidades

### Administrador
- Bloqueia ou libera qualquer porta imediatamente (sem agendamento)
- Ação manual cancela automaticamente qualquer agendamento ativo naquela porta
- Visualiza status de cada porta em duas colunas: **Banco** (intenção do sistema) vs **Switch ao vivo** (leitura SNMP real), com indicador de divergência
- Cancela agendamentos de qualquer professor
- Cadastra e remove professores

### Professor
- Seleciona portas e agenda um período de bloqueio (início + fim)
- Opção **"Iniciar agora"** (exibe o horário exato que será usado)
- Vê o status atual de todas as portas em tempo real (sem recarregar a página)
- Portas reservadas aparecem visualmente, mas não podem ser selecionadas
- Histórico de agendamentos com status: `pendente → ativo → concluído` (ou `cancelado`)

### Automação
- O bloqueio e a liberação das portas acontecem automaticamente nos horários agendados via **APScheduler**
- Agendamentos pendentes são reagendados automaticamente se o servidor reiniciar

---

## Arquitetura

```
browser ──► FastAPI (main.py)
                │
                ├── db.py        SQLite — usuários, switches, portas, agendamentos
                ├── scheduler.py APScheduler — jobs de bloquear/liberar
                └── util.py      SNMP via pysnmp 7.x
                        │
                        └──► switch (real ou simulador snmpsim)
```

| Componente | Tecnologia |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Frontend | Jinja2 + CSS puro (sem build step) |
| Banco de dados | SQLite |
| SNMP | pysnmp 7.x (`set_cmd`, `get_cmd`, `next_cmd`) |
| Agendamento | APScheduler 3.x (AsyncIOScheduler) |
| Deploy | Docker + Docker Compose |

### Por que dois Dockerfiles?

`snmpsim-lextudio` (simulador de switch) conflita com `pysnmp 7.x` (exige versão mais antiga). A solução é isolar cada um em sua própria imagem:

- `Dockerfile` — aplicação web (pysnmp 7.x)
- `Dockerfile.snmpsim` — simulador SNMP (snmpsim-lextudio)

---

## Estrutura de arquivos

```
TF_Switch/
├── main.py              Rotas FastAPI, lógica de autenticação e ações
├── db.py                Schema SQLite, seed de dados, funções de acesso
├── scheduler.py         Jobs APScheduler de bloqueio/liberação automática
├── util.py              Funções SNMP (get/set/walk)
├── snmp_check.py        Diagnóstico: lê uma porta direto do switch via CLI
├── requirements.txt     Dependências da aplicação web
├── Dockerfile           Imagem da aplicação web
├── Dockerfile.snmpsim   Imagem do simulador de switch
├── docker-compose.yml   Orquestração dos dois serviços
├── data/
│   └── switch.snmprec   Dados do simulador (ARP + ifAdminStatus)
└── templates/
    ├── login.html
    ├── admin.html
    └── professor.html
```

---

## Como executar

### Pré-requisitos
- [Docker](https://docs.docker.com/get-docker/) com Docker Compose

### Subir o ambiente completo

```bash
git clone <url-do-repositorio>
cd TF_Switch
docker compose up --build
```

A aplicação ficará disponível em `http://localhost:8000`.

### Usuários padrão (seed)

| Usuário | Senha | Papel |
|---|---|---|
| `admin` | `admin123` | Administrador |
| `professor` | `prof123` | Professor |

> **Autenticação por MAC:** com `REQUIRE_MAC=1` (padrão), o sistema verifica se o MAC da máquina do cliente está cadastrado no banco. Isso impede acesso a partir de computadores não autorizados.

---

## Configuração

Variáveis de ambiente (definidas no `docker-compose.yml`):

| Variável | Padrão | Descrição |
|---|---|---|
| `SWITCH_IP` | `127.0.0.1` | IP do switch (ou nome do serviço Docker) |
| `SWITCH_PORT` | `1161` | Porta UDP do agente SNMP |
| `SWITCH_COMMUNITY` | `switch` | Community string SNMP |
| `SECRET_KEY` | *(obrigatório trocar)* | Chave de assinatura das sessões |
| `REQUIRE_MAC` | `1` | `1` = exige MAC cadastrado; `0` = desativa verificação |
| `TZ` | — | Fuso horário (ex.: `America/Sao_Paulo`) |

### Usando com um switch real

Altere `SWITCH_IP` para o IP do equipamento físico e `SWITCH_PORT` para `161` (porta padrão SNMP):

```yaml
# docker-compose.yml
web:
  environment:
    - SWITCH_IP=192.168.1.1
    - SWITCH_PORT=161
    - SWITCH_COMMUNITY=public
```

---

## Banco de dados

Gerado automaticamente em `database.db` na primeira execução. O schema inclui:

- **`sala`** — laboratórios/salas
- **`switch`** — switches por sala (uma sala pode ter mais de um)
- **`porta`** — portas físicas, com flag `reservada` (não podem ser bloqueadas pelo professor)
- **`usuario`** — admin e professores, cada um com MAC cadastrado
- **`agendamento`** — períodos de bloqueio com status (`pendente`, `ativo`, `concluido`, `cancelado`)
- **`agendamento_porta`** — quais portas estão em cada agendamento

O banco é a **representação de intenção** do sistema. O switch é sempre a **fonte da verdade**: o status de uma porta só é atualizado no banco após o SNMP confirmar que o SET foi aplicado.

---

## Simulador SNMP

O arquivo `data/switch.snmprec` simula as tabelas relevantes do switch:

- **`1.3.6.1.2.1.2.2.1.7.<porta>`** — `ifAdminStatus` (1=up, 2=down)
  - Usando variação `writecache` para que SETs persistam em memória durante a sessão
- **`1.3.6.1.2.1.4.22.1.2.<ifIndex>.<IP>`** — tabela ARP (coluna 2 = MAC)
  - Usada para resolver o MAC do cliente a partir do IP, validando a máquina no login

> O arquivo `.snmprec` deve estar em **ordem crescente de OID**; entradas fora de ordem são ignoradas pelo GETNEXT/walk.

### Verificação manual de uma porta

```bash
docker compose exec web python snmp_check.py <numero_da_porta>
```

Exemplo de saída:
```
Switch:  snmpsim:1161  (community 'switch')
OID:     1.3.6.1.2.1.2.2.1.7.4  (ifAdminStatus da porta 4)
Valor lido do switch: 2 -> down (bloqueada)
```

---

## API interna (JSON)

Usada pelo JavaScript da página do professor para atualizar o status das portas a cada 5 segundos sem recarregar a página.

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/portas` | Lista todas as portas com status atual |
| `GET` | `/api/agendamentos` | Lista agendamentos do usuário logado |

Ambos requerem sessão autenticada; retornam `401` caso contrário.
