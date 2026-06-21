import sqlite3

DB_NAME = "database.db"

def get_db_connection():
    conn =  sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def start_db(): 
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript("""

    CREATE TABLE IF NOT EXISTS "sala" (
        "id" INTEGER NOT NULL,
        "bloco" VARCHAR NOT NULL,
        "desc " INTEGER NOT NULL,
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
        PRIMARY KEY("id")
    );

    CREATE TABLE IF NOT EXISTS "agendamento_porta" (
        "id" INTEGER NOT NULL,
        "id_porta" INTEGER NOT NULL,
        "id_agendamento" INTEGER NOT NULL,
        PRIMARY KEY("id"),
        FOREIGN KEY ("id_porta") REFERENCES "porta"("Id")
        ON UPDATE NO ACTION ON DELETE NO ACTION,
        FOREIGN KEY ("id_agendamento") REFERENCES "agendamento"("id")
        ON UPDATE NO ACTION ON DELETE NO ACTION
    );

    CREATE TABLE IF NOT EXISTS "agendamento" (
        "id" INTEGER NOT NULL,
        "inicio" DATETIME NOT NULL,
        "fim" DATETIME NOT NULL,
        "criado_por" INTEGER NOT NULL,
        PRIMARY KEY("id"),
        FOREIGN KEY ("criado_por") REFERENCES "usuario"("id")
        ON UPDATE NO ACTION ON DELETE NO ACTION
    );  """ )


    conn.commit()
    conn.close()

def popular_tabelas():
    # Conecta ao seu arquivo de banco de dados
    conn = get_db_connection() # Altere para o nome real do seu arquivo .db
    cursor = conn.cursor()
    
    # Coloque aqui todas as queries de inserção
    sql_inserts = """
    INSERT INTO "sala" ("id", "bloco", "desc ") VALUES 
    (1, 'Bloco A', 101), (2, 'Bloco A', 102), (3, 'Bloco B', 201);

    INSERT INTO "usuario" ("id", "mac_addr", "login", "senha") VALUES 
    (1, 'AA:BB:CC:DD:EE:01', 'admin', 'admin123'),
    (2, 'AA:BB:CC:DD:EE:02', 'suporte_tecnico', 'senha_forte_99');

    INSERT INTO "switch" ("id", "nome", "num_portas", "mac_addr", "ip_addr", "sala") VALUES 
    (1, 'SW-CORE-01', 24, '00:1A:2B:3C:4D:5E', '192.168.1.2', 1),
    (2, 'SW-SALA-102', 24, '00:1A:2B:3C:4D:5F', '192.168.1.3', 2),
    (3, 'SW-SALA-201', 48, '00:1A:2B:3C:4D:60', '192.168.2.2', 3);

    INSERT INTO "porta" ("Id", "porta", "switch", "status", "reservada") VALUES 
    (1, 1, 1, 1, 0), (2, 2, 1, 1, 1), (3, 24, 1, 0, 0),
    (4, 1, 2, 1, 0), (5, 2, 2, 1, 1);

    INSERT INTO "maquina" ("id", "porta", "ip") VALUES 
    (1, 1, '192.168.1.50'), (2, 2, '192.168.1.51'), (3, 4, '192.168.1.60');

    INSERT INTO "agendamento" ("id", "inicio", "fim", "criado_por") VALUES 
    (1, '2026-06-22 08:00:00', '2026-06-22 12:00:00', 1),
    (2, '2026-06-23 14:00:00', '2026-06-23 18:00:00', 2);

    INSERT INTO "agendamento_porta" ("id", "id_porta", "id_agendamento") VALUES 
    (1, 1, 1), (2, 2, 1), (3, 4, 2);
    """
    
    try:
        # Executa todo o bloco de uma vez
        cursor.executescript(sql_inserts)
        conn.commit()
        print("Dados inseridos com sucesso!")
    except sqlite3.Error as e:
        print(f"Erro ao inserir dados: {e}")
    finally:
        conn.close()

def verify_admin(mac):
    conn =  get_db_connection()
    cursor = conn.cursor()
    print(mac)
    cursor.execute('SELECT * FROM usuario WHERE TRIM("mac_addr") = TRIM(?)',(mac,))

    get = cursor.fetchone()

    conn.close()
    return dict(get) if get else None

# Executa a função
# if __name__ == "__main__":
#     popular_tabelas()
