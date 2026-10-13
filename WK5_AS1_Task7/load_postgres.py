from pathlib import Path
from io import StringIO
import hashlib,json
import pandas as pd
from database import connect
p=Path('data/uszips.csv')
if not p.exists(): raise SystemExit('Missing data/uszips.csv: copy the exact CSV from Colab first.')
raw=p.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
df=pd.read_csv(p,dtype={'zip':'string','county_fips':'string'},low_memory=False)
expected=['zip','lat','lng','city','state_id','state_name','zcta','parent_zcta','population','density','county_fips','county_name','county_weights','county_names_all','county_fips_all','imprecise','military','timezone']
if list(df.columns)!=expected: raise SystemExit(f'Unexpected CSV columns: {df.columns.tolist()}')
if not df.zip.str.fullmatch(r'\d{5}').all() or df.zip.duplicated().any(): raise SystemExit('Invalid or duplicate ZIP identifiers')
if len(df)!=33782: raise SystemExit(f'Expected full CSV with 33782 rows; got {len(df)}')
if df.population.isna().sum()!=19 or df.density.isna().sum()!=19: raise SystemExit('Missing-value counts differ from lab checkpoint')
print('CSV checked:',len(df),'rows; SHA-256:',digest)
with connect('loader') as conn:
    with conn.cursor() as cur:
        cur.execute('''CREATE TABLE IF NOT EXISTS lab.uszips (
        zip TEXT PRIMARY KEY, lat DOUBLE PRECISION, lng DOUBLE PRECISION,
        city TEXT, state_id TEXT, state_name TEXT, zcta BOOLEAN, parent_zcta TEXT,
        population DOUBLE PRECISION, density DOUBLE PRECISION, county_fips TEXT,
        county_name TEXT, county_weights TEXT, county_names_all TEXT,
        county_fips_all TEXT, imprecise BOOLEAN, military BOOLEAN, timezone TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS lab.import_manifest (id INTEGER PRIMARY KEY,
        csv_sha256 TEXT NOT NULL, row_count INTEGER NOT NULL, imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
        cur.execute('SELECT csv_sha256 FROM lab.import_manifest WHERE id=1')
        previous=cur.fetchone()
        if previous:
            if previous[0]!=digest: raise SystemExit('A DIFFERENT CSV was previously imported. Stop; do not overwrite without review.')
            cur.execute('SELECT COUNT(*) FROM lab.uszips'); count=cur.fetchone()[0]
            if count==len(df): print('Same file already imported, no changes made.'); quit()
            raise SystemExit('Manifest and imported row counts disagree; inspect database before retrying.')
        cur.execute('SELECT COUNT(*) FROM lab.uszips')
        if cur.fetchone()[0]: raise SystemExit('Table contains rows but has no manifest. Stop for inspection.')
        buffer=StringIO();df.to_csv(buffer,index=False,na_rep='');buffer.seek(0)
        cur.copy_expert('''COPY lab.uszips (zip,lat,lng,city,state_id,state_name,zcta,parent_zcta,population,density,county_fips,county_name,county_weights,county_names_all,county_fips_all,imprecise,military,timezone) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')''',buffer)
        cur.execute('INSERT INTO lab.import_manifest(id,csv_sha256,row_count) VALUES (1,%s,%s)',(digest,len(df)))
print('Imported exactly',len(df),'records into lab.uszips.')
