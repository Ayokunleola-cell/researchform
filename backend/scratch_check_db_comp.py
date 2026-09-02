import sqlite3
import json

conn = sqlite3.connect("researchform_dev.db")
cursor = conn.cursor()
cursor.execute("SELECT results FROM analysis_jobs ORDER BY created_at DESC LIMIT 1")
row = cursor.fetchone()

if row and row[0]:
    results = json.loads(row[0])
    print("comparison:", json.dumps(results.get("comparison", {}), indent=2))
else:
    print("No jobs found")
