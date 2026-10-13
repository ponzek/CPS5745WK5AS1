# CPS5745 Fall 2026 — AS1, PostgreSQL + Plotly

This is an adapted starter for the Fall 2026 lab, not the older Study1 CSV-only app. The same 18-column original CSV is analyzed in Colab, loaded into local PostgreSQL and queried by Streamlit. The CSV is NOT read by the running dashboard.

## First: copy the exact dataset from Colab

Inside Colab, once DATA_PATH is set and Drive is mounted:

```python
from google.colab import files
import zipfile
with zipfile.ZipFile(DATA_PATH) as archive:
    csv_content = archive.read('uszips.csv')
with open('/content/uszips.csv','wb') as f:
    f.write(csv_content)
files.download('/content/uszips.csv')
```

Download `uszips.csv`  Data Source: https://simplemaps.com/data/us-zips and place it at `data/uszips.csv` inside this project. Keep the original ZIP in Drive. Do NOT use `df.to_csv()` for this transfer: preserve the exact source bytes and fingerprint. Confirm Colab's SHA-256 equals local manifest later.

## Windows PowerShell

Extract this ZIP, open VS Code in the `CPS5745_AS1_Ready` folder, and run (PowerShell, each line separately):

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python init_env.py
.venv\Scripts\python db_setup.py
.venv\Scripts\python load_postgres.py
.venv\Scripts\python verify_postgres.py
.venv\Scripts\python -m streamlit run dashboard_app.py --server.address 127.0.0.1
```

If Python 3.13 is not installed, use `py -3.12` for Python 3.12. `py -0p` lists available interpreters. Do not reuse Django's old Python environment. During db_setup, supply your local PostgreSQL administrator username and hidden password. The setup only creates cps5745_lab if missing and creates two local roles. If a role already exists with a different credential, stop for reconciliation rather than guessing or resetting it.

Visit http://localhost:8501 (or http://127.0.0.1:8501). The app requires PostgreSQL; it will not silently fall back to a CSV.

## Verification evidence

- Colab: 33,782 distinct ZIP rows, 18 columns, 19 missing population and 19 missing density, SHA-256.
- PowerShell: `verify_postgres.py` output for full row counts, 00601, and Kings County.
- pgAdmin: run `sql/checks.sql` against cps5745_lab.
- Streamlit: screenshot source fingerprint, database name, all three plots; change states, min ZIP count and Top N.
- Persistence: stop Streamlit, move `data/uszips.csv` OUTSIDE the project temporarily, restart Streamlit, change a filter and show it still works, then restore CSV.
- Use the same NJ/NY, County, min 3, Top 10 filters as in Colab for numeric comparison.
- Document results and caveats in your edited Colab notebook. Use the exact dataset with no invented income/rent columns.

DO NOT submit `.env`, passwords, `.venv`, or caches; delete them from any final packaged copy. Preserve the notebook separately.
