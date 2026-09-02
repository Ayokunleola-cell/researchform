import json, sqlite3
from config import settings

db_path = getattr(settings, "DATABASE_URL", "").replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT results, html_tables FROM analysis_jobs WHERE id='af63c05b-4757-43a3-81eb-8e1d0f9772e2'")
results_raw, html_raw = cur.fetchone()
r = json.loads(results_raw or "{}")
ht = json.loads(html_raw or "{}")

ca = r["reliability"]["cronbach_alpha"]
print("cronbach keys:", list(ca.keys()))
print("additional_stats:", ca.get("additional_stats"))
print("effect_size:", ca.get("effect_size"))
print("conclusion:", ca.get("conclusion", "")[:200])
print("normality keys:", list(r.get("normality", {}).keys()) if isinstance(r.get("normality"), dict) else r.get("normality"))
print("posthoc keys:", list(r.get("posthoc", {}).keys()))
print("html_tables keys:", list(ht.keys()))
if ht.get("reliability"):
    print("html reliability snippet:", ht["reliability"][:300])
conn.close()
