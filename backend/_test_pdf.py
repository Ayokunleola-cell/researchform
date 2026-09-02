import json, os, sqlite3, traceback
from config import settings
from analysis.pipeline import _build_raw_pdf

db_path = getattr(settings, "DATABASE_URL", "").replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
if not os.path.exists(db_path):
    db_path = "researchform_dev.db"

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute(
    "SELECT id, results, html_tables, chart_paths, project_brief FROM analysis_jobs "
    "WHERE id='af63c05b-4757-43a3-81eb-8e1d0f9772e2'"
)
row = cur.fetchone()
jid, results, html_tables, charts, brief = row
r = json.loads(results or "{}")
ht = json.loads(html_tables or "{}")
cp = json.loads(charts or "[]")
brief = json.loads(brief or "{}")

desc = r.get("descriptive", {})
print("descriptive type:", type(desc), "keys:", list(desc.keys())[:5] if isinstance(desc, dict) else desc)
freq = r.get("frequencies", {})
print("frequencies keys:", list(freq.keys())[:5] if isinstance(freq, dict) else freq)

try:
    path = _build_raw_pdf(r, cp, jid, brief)
    print("pdf path:", path, "size:", os.path.getsize(path))
except Exception as e:
    traceback.print_exc()

conn.close()
