import sqlite3
import json

conn = sqlite3.connect("researchform_dev.db")
cursor = conn.cursor()
cursor.execute("SELECT results FROM analysis_jobs ORDER BY created_at DESC LIMIT 1")
row = cursor.fetchone()

if row and row[0]:
    results = json.loads(row[0])
    summary = results.get("summary", [])
    print(f"Summary length: {len(summary)}")
    if len(summary) > 0:
        print("First summary item:", json.dumps(summary[0], indent=2))
        print("Third summary item:", json.dumps(summary[2], indent=2) if len(summary) > 2 else "N/A")
    else:
        print("Results keys:", list(results.keys()))
else:
    print("No jobs found")
