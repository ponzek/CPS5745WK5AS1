import os
from dotenv import load_dotenv
import psycopg2
load_dotenv()
def connect(role='reader', db=None):
    prefix='DB_READER' if role=='reader' else 'DB_LOADER'
    return psycopg2.connect(host=os.getenv('DB_HOST','127.0.0.1'),port=os.getenv('DB_PORT','5432'),dbname=db or os.getenv('DB_NAME','cps5745_lab'),user=os.environ[prefix],password=os.environ[prefix+'_PASSWORD'],sslmode=os.getenv('DB_SSLMODE','prefer'),connect_timeout=15)
