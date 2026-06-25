# TF_Switch

Plataforma web para controle de acesso à internet em laboratórios de informática da UDESC. O professor ou administrador pode bloquear e liberar portas de um switch gerenciável diretamente pelo navegador, sem a necessidade de acessar o equipamento físico ou digitar linhas de comando.

Desenvolvido como Trabalho Final da disciplina de **Gerência e Mobilidade de Redes** — UDESC.

---
## Manual de Utilização da Interface Gráfica (UI)
---

### 1. Tela de Login e Acesso à Rede

A tela de login é o ponto de partida para professores e administradores. 

* **Como acessar:** Insira o seu **Usuário** e **Senha** padrão nos campos correspondentes e clique em **Entrar**.
* **Tratamento de Erros:** Se as credenciais estiverem incorretas, um alerta vermelho aparecerá no topo da caixinha informando o problema.

<img width="1600" height="860" alt="login" src="https://github.com/user-attachments/assets/368c67c6-6b52-409a-b434-3411dc4033b2" />

---

### 2. Painel do Professor

Este painel é destinado aos docentes para que possam gerenciar o uso da internet pelos alunos durante o horário de suas aulas.

#### Interface
* **Monitoramento Automático:** No topo superior direito, ao lado do botão "Sair", há um indicador de conexão (`conectando...` ou `atualizado HH:MM:SS`). A página lê o estado do switch a cada **5 segundos**, atualizando a tela para você sem que precise recarregar o navegador.
* **Mapa de Portas (Quadrados correspondentes às bancadas):**
  * <kbd>liberada</kbd> (Verde): Computadores desta porta **possuem** acesso à internet.
  * <kbd>bloqueada</kbd> (Vermelho): Computadores desta porta **estão sem** acesso à internet.
  * <kbd>reservada</kbd> (Cinza opaco/Pontilhado): Portas da mesa do professor ou de servidores da sala. São protegidas e não podem ser desligadas.

#### Como Agendar um Bloqueio de Internet (Passo a Passo)
1. **Selecione os Computadores:** Clique em cima dos quadrados das portas que deseja bloquear. Ao clicar, elas ganharão uma **borda azul**, indicando que estão selecionadas.
2. **Escolha o Horário de Início:**
   * Se quiser que o bloqueio comece imediatamente, marque a caixa **"Iniciar agora"** (o sistema mostrará o horário atual do servidor).
   * Se quiser programar para mais tarde, deixe a caixa desmarcada e digite o dia e horário no campo **Início**.
4. **Defina o Horário de Término:** No campo **Fim**, insira o horário exato em que a internet deve voltar a funcionar para os alunos.
5. **Confirmar:** Clique no botão azul **"Agendar bloqueio"**.

#### Gerenciando seus Agendamentos
Na tabela **"Meus agendamentos"** (no rodapé da página), você pode acompanhar suas solicitações:
* **Status do Processo:**
  * `pendente`: O agendamento foi salvo e aguarda o horário de início para agir.
  * `ativo`: O bloqueio está acontecendo neste exato momento no laboratório.
  * `concluído`: O horário final terminou e a internet foi liberada automaticamente.
  * `cancelado`: O agendamento foi interrompido antes da hora.
* **Como Cancelar:** Se você terminar a atividade mais cedo e quiser devolver a internet aos alunos, vá até a tabela, encontre o agendamento em estado `ativo` ou `pendente` e clique no botão vermelho **"Cancelar"**.

<img width="1600" height="860" alt="prof1" src="https://github.com/user-attachments/assets/b4579704-a695-471e-b130-f74e81f532e0" />
<img width="1600" height="860" alt="prof2" src="https://github.com/user-attachments/assets/ea290066-a4ff-4782-b8b4-b163a83742dd" />
<img width="1600" height="860" alt="prof3" src="https://github.com/user-attachments/assets/ea9fb8d5-38fe-4ddb-b42a-ba4a8267fdc0" />

---

### 3. Painel do Administrador

Restrito exclusivamente à equipe da CINF. Permite auditoria física do hardware, controle total de usuários e ações imediatas de infraestrutura.

#### Portas dos Switches 
Diferente dos professores, o administrador pode interferir na rede em tempo real sem criar agendamentos temporários. A tabela exibe um cruzamento de dados inteligente:

| Coluna | Descrição |
| :--- | :--- |
| **Banco** | O estado que o sistema *pretende* que a porta esteja (a intenção gravada no software). |
| **Switch (ao vivo)** | A leitura real capturada diretamente do hardware do switch via SNMP na hora. |
| **Confere?** | Exibe `OK` se o switch obedeceu ao sistema, ou `Divergente` caso haja falha física, cabo desconectado ou atraso no comando SNMP. |
| **Ação** | Botões **Bloquear** ou **Liberar** imediatos. Ao clicar, o comando é injetado no switch e qualquer agendamento de professor ativo para aquela porta é cancelado automaticamente. |

#### Agendamentos Globais e Gerenciamento de Professores
* **Controle de Agendamentos:** O administrador visualiza as reservas de todas as salas e de todos os professores da instituição, possuindo autoridade para **Cancelar** qualquer um deles a qualquer momento.
* **Cadastro de Professores:** No formulário inferior, insira o `Login`, `Senha` e o endereço `MAC` da máquina de trabalho do docente. 
  * **Atenção ao formato do MAC:** O caractere separador depende do sistema operacional do computador do professor:
    * No **Linux**, utilize dois-pontos (`:`). Exemplo: `AA:BB:CC:DD:EE:FF`
    * No **Windows**, utilize hífen (`-`). Exemplo: `AA-BB-CC-DD-EE-FF`
* **Remoção:** Exclua cadastros instantaneamente clicando no botão cinza **"Remover"**.
<img width="1600" height="860" alt="adm1" src="https://github.com/user-attachments/assets/b81d97f1-e135-4dd4-adf1-3256fa97bdee" />
<img width="1600" height="860" alt="adm2" src="https://github.com/user-attachments/assets/2b8e2ea9-c981-428f-8746-0a045c71c6a1" />
<img width="1600" height="860" alt="adm3" src="https://github.com/user-attachments/assets/2821979f-070a-40b6-935a-8444ecfc7b8a" />

---
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
