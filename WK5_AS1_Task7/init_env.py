from pathlib import Path
from secrets import token_urlsafe
p=Path('.env')
if p.exists():
    print('Existing .env preserved; no credentials overwritten.')
else:
    p.write_text(f'DB_HOST=127.0.0.1\nDB_PORT=5432\nDB_NAME=cps5745_lab\nDB_LOADER=cps5745_loader\nDB_LOADER_PASSWORD={token_urlsafe(24)}\nDB_READER=cps5745_reader\nDB_READER_PASSWORD={token_urlsafe(24)}\n',encoding='utf-8')
    print('Created .env with private randomized loader and reader credentials.')
print('Keep .env private and out of submitted ZIP files.')
