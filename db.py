import os
import sqlite3
from datetime import datetime

DB_NAME = "database.db"
# IP onde os switches respondem SNMP (no Docker, o serviço 'snmpsim').
SWITCH_IP = os.getenv("SWITCH_IP", "127.0.0.1")


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _column_exists(cursor, table, column):
    cursor.execute(f'PRAGMA table_info("{table}")')
    return any(row[1] == column for row in cursor.fetchall())


def start_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript("""

    CREATE TABLE IF NOT EXISTS "sala" (
        "id" INTEGER NOT NULL,
        "bloco" VARCHAR NOT NULL,
        "desc" VARCHAR NOT NULL,
        PRIMARY KEY("id")
    );

    CREATE TABLE IF NOT EXISTS "switch" (
        "id" INTEGER NOT NULL,
        "nome" VARCHAR,
        "num_portas" INTEGER NOT NULL,
        "mac_addr" VARCHAR NOT NULL UNIQUE,
        "ip_addr" VARCHAR NOT NULL,
        "sala" INTEGER NOT NULL,
        PRIMARY KEY("id"),
        FOREIGN KEY ("sala") REFERENCES "sala"("id")
        ON UPDATE NO ACTION ON DELETE NO ACTION
    );

    CREATE TABLE IF NOT EXISTS "porta" (
        "Id" INTEGER NOT NULL UNIQUE,
        "porta" INTEGER NOT NULL,
        "switch" INTEGER NOT NULL,
        "status" BOOLEAN NOT NULL DEFAULT 1,
        "reservada" BOOLEAN NOT NULL,
        PRIMARY KEY("Id"),
        FOREIGN KEY ("switch") REFERENCES "switch"("id")
        ON UPDATE NO ACTION ON DELETE NO ACTION
    );

    CREATE TABLE IF NOT EXISTS "maquina" (
        "id" INTEGER NOT NULL,
        "porta" INTEGER NOT NULL,
        "ip" VARCHAR NOT NULL,
        PRIMARY KEY("id"),
        FOREIGN KEY ("porta") REFERENCES "porta"("Id")
        ON UPDATE NO ACTION ON DELETE NO ACTION
    );

    CREATE TABLE IF NOT EXISTS "usuario" (
        "id" INTEGER NOT NULL,
        "mac_addr" VARCHAR NOT NULL UNIQUE,
        "login" VARCHAR NOT NULL UNIQUE,
        "senha" VARCHAR NOT NULL,
        "role" VARCHAR NOT NULL DEFAULT 'professor',
        PRIMARY KEY("id")
    );

    CREATE TABLE IF NOT EXISTS "agendamento" (
        "id" INTEGER NOT NULL,
        "inicio" DATETIME NOT NULL,
        "fim" DATETIME NOT NULL,
        "criado_por" INTEGER NOT NULL,
        "status" TEXT NOT NULL DEFAULT 'pendente',
        PRIMARY KEY("id"),
        FOREIGN KEY ("criado_por") REFERENCES "usuario"("id")
        ON UPDATE NO ACTION ON DELETE NO ACTION
    );

    CREATE TABLE IF NOT EXISTS "agendamento_porta" (
        "id" INTEGER NOT NULL,
        "id_porta" INTEGER NOT NULL,
        "id_agendamento" INTEGER NOT NULL,
        PRIMARY KEY("id"),
        FOREIGN KEY ("id_porta") REFERENCES "porta"("Id")
        ON UPDATE NO ACTION ON DELETE NO ACTION,
        FOREIGN KEY ("id_agendamento") REFERENCES "agendamento"("id")
        ON UPDATE NO ACTION ON DELETE CASCADE
    );
    """)

    # Migrações: garante colunas em bancos antigos.
    if not _column_exists(cursor, "usuario", "role"):
        cursor.execute(
            "ALTER TABLE usuario ADD COLUMN role VARCHAR NOT NULL DEFAULT 'professor'"
        )
    if not _column_exists(cursor, "agendamento", "status"):
        cursor.execute(
            "ALTER TABLE agendamento ADD COLUMN status TEXT NOT NULL DEFAULT 'pendente'"
        )

    conn.commit()
    conn.close()
    seed_data()


def seed_data():
    """Popula dados mockados. Usuários são sempre garantidos (ids fixos);
    a topologia (sala/switch/porta) só é criada se ainda não existir."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- Usuários mockados (MACs alinhados com data/switch.snmprec) ---
    # admin    -> IP 192.168.1.10 -> MAC A4:BF:01:23:45:67
    # professor-> IP 192.168.1.50 -> MAC B0:FC:36:9A:BC:DE
    cursor.executemany(
        """INSERT OR REPLACE INTO "usuario" ("id","mac_addr","login","senha","role")
           VALUES (?,?,?,?,?)""",
        [
            (1, "A4:BF:01:23:45:67", "admin", "admin123", "admin"),
            (2, "5C:CD:5B:22:95:DE", "professor", "prof123", "professor"),
        ],
    )

    cursor.execute('SELECT COUNT(*) FROM "switch"')
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            'INSERT INTO "sala" ("id","bloco","desc") VALUES (1, ?, ?)',
            ("Bloco A", "Laboratório 101"),
        )
        # Uma sala pode ter mais de um switch. Ambos apontam para o mesmo
        # endereço SNMP (no Docker, o simulador). Em produção cada switch
        # teria seu próprio ip_addr real.
        switches = [
            (1, "SW-LAB-01", 24, "00:11:22:33:AA:01", SWITCH_IP, 1),
            (2, "SW-LAB-02", 24, "00:11:22:33:AA:02", SWITCH_IP, 1),
        ]
        cursor.executemany(
            """INSERT INTO "switch" ("id","nome","num_portas","mac_addr","ip_addr","sala")
               VALUES (?,?,?,?,?,?)""",
            switches,
        )
        # Portas 1-3 reservadas (gateway / máquina do admin / máquina do professor).
        portas = []
        porta_id = 1
        for sw_id in (1, 2):
            for n in range(1, 25):
                portas.append((porta_id, n, sw_id, 1, 1 if n in (1, 2, 3) else 0))
                porta_id += 1
        cursor.executemany(
            """INSERT INTO "porta" ("Id","porta","switch","status","reservada")
               VALUES (?,?,?,?,?)""",
            portas,
        )

    conn.commit()
    conn.close()


# ----------------------------------------------------------------------------
# Usuários / autenticação
# ----------------------------------------------------------------------------
def get_user_by_mac(mac):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM usuario WHERE TRIM("mac_addr") = TRIM(?)', (mac,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def verify_login(login, senha):
    """Valida login/senha. Retorna o usuário (dict) ou None."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM usuario WHERE login = ? AND senha = ?', (login, senha)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def list_professores():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM usuario WHERE role = ? ORDER BY login', ("professor",))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_professor(mac, login, senha):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO usuario ("mac_addr","login","senha","role")
               VALUES (?,?,?,?)""",
            (mac, login, senha, "professor"),
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        return False, str(e)
    finally:
        conn.close()


def delete_professor(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM usuario WHERE id = ? AND role = ?', (user_id, "professor"))
    conn.commit()
    conn.close()


# ----------------------------------------------------------------------------
# Switches / portas
# ----------------------------------------------------------------------------
def list_switches():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM switch ORDER BY nome')
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_portas(switch_id=None, only_unreserved=False, only_active=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "SELECT * FROM porta"
    cond = []
    params = []
    if switch_id is not None:
        cond.append("switch = ?")
        params.append(switch_id)
    if only_unreserved:
        cond.append("reservada = 0")
    if only_active:
        # Apenas portas atualmente liberadas (esconde as já bloqueadas).
        cond.append("status = 1")
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY switch, porta"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_porta(porta_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT p.*, s.ip_addr AS switch_ip, s.nome AS switch_nome
           FROM porta p JOIN switch s ON s.id = p.switch
           WHERE p."Id" = ?""",
        (porta_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def set_porta_status(porta_id, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE porta SET status = ? WHERE "Id" = ?', (1 if status else 0, porta_id))
    conn.commit()
    conn.close()


# ----------------------------------------------------------------------------
# Agendamentos
# ----------------------------------------------------------------------------
def create_agendamento(inicio, fim, criado_por, porta_ids):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO agendamento ("inicio","fim","criado_por") VALUES (?,?,?)',
        (inicio, fim, criado_por),
    )
    agendamento_id = cursor.lastrowid
    cursor.executemany(
        'INSERT INTO agendamento_porta ("id_porta","id_agendamento") VALUES (?,?)',
        [(pid, agendamento_id) for pid in porta_ids],
    )
    conn.commit()
    conn.close()
    return agendamento_id


def get_agendamento(agendamento_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM agendamento WHERE id = ?', (agendamento_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_agendamento_portas(agendamento_id):
    """Retorna as portas (Id + número físico) ligadas a um agendamento."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT p."Id" as id, p.porta as porta, p.switch as switch,
                  s.ip_addr as switch_ip, s.nome as switch_nome
           FROM agendamento_porta ap
           JOIN porta p ON p."Id" = ap.id_porta
           JOIN switch s ON s.id = p.switch
           WHERE ap.id_agendamento = ?""",
        (agendamento_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_agendamento_by_porta(porta_id):
    """Retorna o agendamento pendente ou ativo que envolve uma porta (se houver)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT a.* FROM agendamento a
           JOIN agendamento_porta ap ON ap.id_agendamento = a.id
           WHERE ap.id_porta = ? AND a.status IN ('pendente', 'ativo')
           ORDER BY a.inicio LIMIT 1""",
        (porta_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def list_agendamentos(criado_por=None, apenas_ativos=False):
    """Lista agendamentos com o login do criador, lista de portas e status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = """SELECT a.*, u.login as criador
             FROM agendamento a JOIN usuario u ON u.id = a.criado_por"""
    cond = []
    params = []
    if criado_por is not None:
        cond.append("a.criado_por = ?")
        params.append(criado_por)
    if apenas_ativos:
        cond.append("a.status IN ('pendente', 'ativo')")
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY a.inicio DESC LIMIT 100"
    cursor.execute(sql, params)
    ags = [dict(r) for r in cursor.fetchall()]
    for ag in ags:
        cursor.execute(
            """SELECT s.nome AS switch_nome, p.porta AS porta
               FROM agendamento_porta ap
               JOIN porta p ON p."Id" = ap.id_porta
               JOIN switch s ON s.id = p.switch
               WHERE ap.id_agendamento = ? ORDER BY s.nome, p.porta""",
            (ag["id"],),
        )
        ag["portas"] = [f"{r['switch_nome']} p{r['porta']}" for r in cursor.fetchall()]
    conn.close()
    return ags


def mark_agendamento_status(agendamento_id, status):
    """Atualiza o status de um agendamento (pendente/ativo/concluido/cancelado)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE agendamento SET status = ? WHERE id = ?', (status, agendamento_id))
    conn.commit()
    conn.close()


def list_pending_agendamentos():
    """Agendamentos que ainda não terminaram (para reagendar no startup)."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM agendamento WHERE fim > ? AND status IN ('pendente', 'ativo')",
        (agora,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_agendamento(agendamento_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM agendamento_porta WHERE id_agendamento = ?', (agendamento_id,))
    cursor.execute('DELETE FROM agendamento WHERE id = ?', (agendamento_id,))
    conn.commit()
    conn.close()
