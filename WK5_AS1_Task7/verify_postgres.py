from pathlib import Path
from hashlib import sha256
import pandas as pd
from database import connect
with connect() as c:
    with c.cursor() as cur:
        cur.execute('''SELECT count(*), count(*) FILTER (WHERE population IS NULL), count(*) FILTER (WHERE density IS NULL), count(DISTINCT zip) FROM lab.uszips''')
        stats=cur.fetchone()
        cur.execute("SELECT zip,state_id,county_fips,county_name,population,density,timezone FROM lab.uszips WHERE zip='00601'")
        sample=cur.fetchone()
        cur.execute('SELECT csv_sha256,row_count,imported_at FROM lab.import_manifest WHERE id=1')
        manifest=cur.fetchone()
        cur.execute("SELECT COUNT(*), SUM(population), AVG(population), AVG(density) FROM lab.uszips WHERE state_id IN ('NJ','NY') AND county_fips='36047'")
        kings=cur.fetchone()
print('Database rows, missing population, missing density, unique ZIPs:',stats)
print('ZIP 00601:',sample)
print('Manifest:',manifest)
print('Kings County ZIP count, population sum, mean population, mean density:',kings)
assert stats==(33782,19,19,33782), 'Row/missing/unique counts mismatch'
assert sample and sample[0]=='00601', 'Leading-zero ZIP missing'
assert kings[0]==38 and abs(float(kings[1])-2631396)<.01, 'Kings County population check failed'
p=Path('data/uszips.csv')
if p.exists():
    assert sha256(p.read_bytes()).hexdigest()==manifest[0], 'CSV fingerprint mismatch'
    print('Local CSV fingerprint matches PostgreSQL manifest')
else:
    print('CSV absent (this is fine for the app persistence test)')
print('ALL POSTGRESQL VERIFICATION CHECKS PASSED')
