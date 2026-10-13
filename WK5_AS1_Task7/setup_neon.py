import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

from dotenv import dotenv_values, set_key
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn


ROOT = Path(__file__).resolve().parent


def owner_url(project, branch, pooled=False):
    executable = shutil.which('neon')
    if not executable:
        raise SystemExit('Install the Neon CLI and run neon login first.')
    command = [executable, 'connection-string', branch, '--project-id', project,
               '--database-name', 'cps5745_lab', '--role-name', 'cps5745_lab_owner']
    if pooled:
        command.append('--pooled')
    environment = dict(os.environ, OPENSSL_CONF='')
    result = subprocess.run(command, capture_output=True, text=True, env=environment)
    if result.returncode:
        raise SystemExit('Could not obtain the Neon connection. Check CLI sign-in and project access.')
    urls = [line.strip() for line in result.stdout.splitlines()
            if line.strip().startswith(('postgres://', 'postgresql://'))]
    if len(urls) != 1:
        raise SystemExit('Unexpected Neon CLI output; no credentials were printed.')
    return urls[0]


def inspect(connection, digest):
    with connection.cursor() as cursor:
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='lab' ORDER BY tablename")
        tables = [row[0] for row in cursor.fetchall()]
        print('Existing lab tables:', tables)
        if 'uszips' in tables:
            cursor.execute('SELECT COUNT(*) FROM lab.uszips')
            count = cursor.fetchone()[0]
            print('Existing ZIP records:', count)
            if count and 'import_manifest' not in tables:
                raise SystemExit('Existing data has no manifest; stopped without replacing it.')
        if 'import_manifest' in tables:
            cursor.execute('SELECT csv_sha256 FROM lab.import_manifest WHERE id=1')
            manifest = cursor.fetchone()
            if manifest and manifest[0] != digest:
                raise SystemExit('A different dataset exists; stopped without replacing it.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', default='crimson-leaf-80998443')
    parser.add_argument('--branch', default='br-icy-glade-b55zdjcs')
    parser.add_argument('--inspect', action='store_true')
    args = parser.parse_args()
    csv_path = ROOT / 'data' / 'uszips.csv'
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    direct_url = owner_url(args.project, args.branch)
    with psycopg2.connect(direct_url, connect_timeout=15) as connection:
        inspect(connection, digest)
    if args.inspect:
        return

    env_path = ROOT / '.env.neon'
    existing = dotenv_values(env_path) if env_path.exists() else {}
    direct = parse_dsn(direct_url)
    if existing and any(existing.get(key) != value for key, value in
                        [('DB_HOST', direct['host']), ('DB_NAME', direct['dbname'])]):
        raise SystemExit('Existing .env.neon targets a different database; stopped.')
    credentials = {}
    with psycopg2.connect(direct_url, connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            for kind in ('LOADER', 'READER'):
                username = 'cps5745_' + kind.lower()
                password_key = 'DB_' + kind + '_PASSWORD'
                cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (username,))
                present = cursor.fetchone()
                password = existing.get(password_key)
                if present and not password:
                    raise SystemExit(f'Role {username} exists without saved credentials; stopped without resetting it.')
                if not present:
                    password = secrets.token_urlsafe(32)
                credentials['DB_' + kind] = username
                credentials[password_key] = password

            # Save generated credentials before committing new roles, so reruns can reuse them.
            settings = dict(DB_HOST=direct['host'], DB_PORT=direct.get('port', '5432'),
                            DB_NAME=direct['dbname'], DB_SSLMODE='require', **credentials)
            for key, value in settings.items():
                set_key(str(env_path), key, value)
            for kind in ('LOADER', 'READER'):
                username = credentials['DB_' + kind]
                cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (username,))
                if not cursor.fetchone():
                    cursor.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD %s').format(
                        sql.Identifier(username)), (credentials['DB_' + kind + '_PASSWORD'],))
            loader = sql.Identifier(credentials['DB_LOADER'])
            reader = sql.Identifier(credentials['DB_READER'])
            cursor.execute('CREATE SCHEMA IF NOT EXISTS lab')
            cursor.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}, {}').format(
                sql.Identifier(direct['dbname']), loader, reader))
            cursor.execute(sql.SQL('GRANT USAGE ON SCHEMA lab TO {}, {}').format(loader, reader))
            cursor.execute(sql.SQL('GRANT CREATE ON SCHEMA lab TO {}').format(loader))
            cursor.execute(sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA lab TO {}').format(reader))

    with psycopg2.connect(host=settings['DB_HOST'], port=settings['DB_PORT'],
                         dbname=settings['DB_NAME'], user=settings['DB_LOADER'],
                         password=settings['DB_LOADER_PASSWORD'], sslmode='require',
                         connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA lab '
                                   'GRANT SELECT ON TABLES TO {}').format(
                                       sql.Identifier(settings['DB_READER'])))

    environment = dict(os.environ, **settings)
    for script in ('load_postgres.py', 'verify_postgres.py'):
        subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT,
                       env=environment, check=True)
    with psycopg2.connect(host=settings['DB_HOST'], port=settings['DB_PORT'],
                         dbname=settings['DB_NAME'], user=settings['DB_READER'],
                         password=settings['DB_READER_PASSWORD'], sslmode='require',
                         connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*), COUNT(DISTINCT state_id) FROM lab.uszips')
            print('Hosted ZIP records and states/territories:', cursor.fetchone())
            cursor.execute("SELECT has_schema_privilege(current_user, 'lab', 'CREATE'), "
                           "has_table_privilege(current_user, 'lab.uszips', 'INSERT'), "
                           "has_table_privilege(current_user, 'lab.uszips', 'UPDATE'), "
                           "has_table_privilege(current_user, 'lab.uszips', 'DELETE')")
            assert cursor.fetchone() == (False, False, False, False), 'Reader has write privileges'

    pooled = parse_dsn(owner_url(args.project, args.branch, pooled=True))
    cloud_settings = {key: value for key, value in settings.items() if not key.startswith('DB_LOADER')}
    cloud_settings['DB_HOST'] = pooled['host']
    secrets_path = ROOT / '.streamlit' / 'neon-secrets.toml'
    secrets_path.parent.mkdir(exist_ok=True)
    secrets_path.write_text('\n'.join(f'{key} = {json.dumps(value)}' for key, value in
                                     cloud_settings.items()) + '\n', encoding='utf-8')
    print('Private Streamlit settings written to .streamlit/neon-secrets.toml (not printed).')
    print('Laptop .env unchanged. Hosted database setup and verification complete.')


if __name__ == '__main__':
    main()
