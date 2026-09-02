import sqlite3
import json

conn = sqlite3.connect("researchform_dev.db")
cursor = conn.cursor()
cursor.execute("SELECT selected_tests FROM analysis_jobs ORDER BY created_at DESC LIMIT 1")
row = cursor.fetchone()

if row and row[0]:
    tests = json.loads(row[0])
    print(json.dumps(tests, indent=2))
else:
    print("No tests found")
