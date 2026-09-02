import sqlite3, json
conn = sqlite3.connect('researchform_dev.db')
c = conn.cursor()
c.execute("SELECT results FROM analysis_jobs WHERE id='8e655168-2557-4fca-b7c1-90865377a855'")
res = json.loads(c.fetchone()[0])
print(json.dumps(res.get('descriptive', {}), indent=2))
