# TF_Switch

Plataforma web para controle de acesso à internet em laboratórios de informática. O professor bloqueia portas de um switch gerenciável via SNMP diretamente pelo navegador, sem precisar acessar o equipamento.

Desenvolvido como Trabalho Final da disciplina de **Gerência e Mobilidade de Redes** — UDESC.

---
## Manual de Utilização da Interface Gráfica (UI)
---

### Funcionalidades

#### Administrador
- Bloqueia ou libera qualquer porta imediatamente (sem agendamento)
- Ação manual cancela automaticamente qualquer agendamento ativo naquela porta
- Visualiza status de cada porta em duas colunas: **Banco** (intenção do sistema) vs **Switch ao vivo** (leitura SNMP real), com indicador de divergência
- Cancela agendamentos de qualquer professor
- Cadastra e remove professores

#### Professor
- Seleciona portas e agenda um período de bloqueio (início + fim)
- Opção **"Iniciar agora"** (exibe o horário exato que será usado)
- Vê o status atual de todas as portas em tempo real (sem recarregar a página)
- Portas reservadas aparecem visualmente, mas não podem ser selecionadas
- Histórico de agendamentos com status: `pendente → ativo → concluído` (ou `cancelado`)

#### Automação
- O bloqueio e a liberação das portas acontecem automaticamente nos horários agendados via **APScheduler**
- Agendamentos pendentes são reagendados automaticamente se o servidor reiniciar

---

### 1. Tela de Login
Interface de autenticação simples e direta para acesso aos painéis de controle.

* **Como acessar:** Insira suas credenciais de acesso nos campos **Usuário** e **Senha** e clique em **Entrar**.
* **Tratamento de Erros:** Caso as credenciais estejam incorretas, um alerta vermelho (`⚠`) será exibido no topo do cartão informando o problema.

---

### 2. Painel do Professor
Destinado aos docentes para visualização do estado atual das portas e criação de agendamentos temporários de bloqueio.

#### Elementos da Interface
* Exibe o nome do professor logado e um indicador em tempo real (`conectando...` ou `atualizado HH:MM:SS`) que realiza leituras automáticas na API do switch a cada **5 segundos**.
* Representação visual de cada porta dividida por switch:
  * <kbd>liberada</kbd> (Verde): Porta ativa e com tráfego liberado.
  * <kbd>bloqueada</kbd> (Vermelho): Porta com acesso cortado.
  * <kbd>reservada</kbd> (Pontilhado/Opaco): Porta protegida pelo sistema (não permite interação).

#### Como Agendar um Bloqueio de Acesso
1. **Selecione as Portas:** Clique sobre os cards das portas desejadas no Grid. Elas ficarão com uma borda azul destacada indicando a seleção.
2. **Defina o Início:** * Preencha o campo **Início** com a data e horário desejados, **OU**
   * Marque a caixa **"Iniciar agora"** para que o bloqueio entre em vigor imediatamente.
3. **Defina o Fim:** Preencha obrigatoriamente o campo **Fim** (marcado com `*`).
4. **Confirmar:** Clique no botão **"Agendar bloqueio"**.

#### Meus Agendamentos
Tabela localizada no rodapé da página que lista o histórico e o status dos pedidos do usuário logado:
* **Status possíveis:** `pendente`, `ativo`, `concluído` ou `cancelado`.
* **Cancelamento:** Se um agendamento estiver com o status `pendente` ou `ativo`, um botão **"Cancelar"** estará disponível para interromper a ação imediatamente.
<img width="1600" height="860" alt="login" src="https://github.com/user-attachments/assets/368c67c6-6b52-409a-b434-3411dc4033b2" />

---

### 3. Painel do Administrador
Interface avançada de monitoramento global e gerenciamento de infraestrutura/usuários, esse painel só pode ser acessado pela CINF.

#### Portas dos Switches
Esta tabela realiza o cruzamento de dados entre o pretendido pelo sistema e o estado físico real do equipamento via SNMP.

| Coluna | Descrição |
| :--- | :--- |
| **Banco** | O estado que o sistema *pretende* que a porta esteja (Reservada, Liberada ou Bloqueada). |
| **Switch (ao vivo)** | A leitura real capturada diretamente do hardware por SNMP. |
| **Confere?** | Exibe `OK` (se os estados forem iguais) ou `Divergente` (caso haja atraso ou falha na aplicação do comando no switch). |
| **Ação** | Botões rápidos para **Bloquear** ou **Liberar** a porta manualmente sem necessidade de agendamento. |

#### Agendamentos Globais
Exibe os agendamentos de **todos** os professores cadastrados no sistema. 
* O administrador possui a permissão de **Cancelar** qualquer agendamento `pendente` ou `ativo` do sistema, independente de quem o criou.

#### Gerenciamento de Professores
Permite o controle de quem pode acessar a plataforma e o vínculo com os endereços físicos das máquinas.
* **Remover:** Clique em **"Remover"** ao lado do professor para revogar seus acessos.
* **Cadastrar Novo:** Preencha os campos `Login`, `Senha` e o endereço `MAC` (Formato: `AA:BB:CC:DD:EE:FF`) no formulário inferior e clique em **"Cadastrar professor"**.

---
--

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
