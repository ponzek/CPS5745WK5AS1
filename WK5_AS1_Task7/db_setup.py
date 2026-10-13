
import os
import getpass
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

load_dotenv()

host = os.getenv("DB_HOST", "127.0.0.1")
port = os.getenv("DB_PORT", "5432")
dbname = os.getenv("DB_NAME", "cps5745_lab")

admin = input(
    "PostgreSQL administrator username [postgres]: "
).strip() or "postgres"

pw = getpass.getpass("Administrator password (hidden): ")

# Connect to PostgreSQL without starting a transaction
conn = psycopg2.connect(
    host=host,
    port=port,
    dbname="postgres",
    user=admin,
    password=pw
)

try:
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s",
            (dbname,)
        )

        if not cur.fetchone():
            cur.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(dbname)
                )
            )
            print("Created database:", dbname)
        else:
            print("Database already exists:", dbname)
finally:
    conn.close()

# Set up roles and permissions in the lab database
with psycopg2.connect(
    host=host,
    port=port,
    dbname=dbname,
    user=admin,
    password=pw
) as conn:

    with conn.cursor() as cur:

        for kind in ("LOADER", "READER"):
            user = os.environ["DB_" + kind]
            password = os.environ["DB_" + kind + "_PASSWORD"]

            cur.execute(
                "SELECT 1 FROM pg_roles WHERE rolname=%s",
                (user,)
            )

            if cur.fetchone():
                print("Role already exists:", user)
            else:
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN PASSWORD %s"
                    ).format(sql.Identifier(user)),
                    (password,)
                )
                print("Created role:", user)

        loader = os.environ["DB_LOADER"]
        reader = os.environ["DB_READER"]

        cur.execute("CREATE SCHEMA IF NOT EXISTS lab")

        cur.execute(
            sql.SQL(
                "GRANT CONNECT ON DATABASE {} TO {}, {}"
            ).format(
                sql.Identifier(dbname),
                sql.Identifier(loader),
                sql.Identifier(reader)
            )
        )

        cur.execute(
            sql.SQL(
                "GRANT USAGE ON SCHEMA lab TO {}, {}"
            ).format(
                sql.Identifier(loader),
                sql.Identifier(reader)
            )
        )

        cur.execute(
            sql.SQL(
                "GRANT CREATE ON SCHEMA lab TO {}"
            ).format(sql.Identifier(loader))
        )

        cur.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} "
                "IN SCHEMA lab GRANT SELECT ON TABLES TO {}"
            ).format(
                sql.Identifier(loader),
                sql.Identifier(reader)
            )
        )

        cur.execute(
            sql.SQL(
                "GRANT SELECT ON ALL TABLES IN SCHEMA lab TO {}"
            ).format(sql.Identifier(reader))
        )

print("Database setup successful. Now run load_postgres.py.")
