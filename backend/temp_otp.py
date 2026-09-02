import sqlite3
import json

try:
    conn = sqlite3.connect('researchform_dev.db')
    c = conn.cursor()
    c.execute('PRAGMA table_info(user_otps)')
    print('Columns:', [col[1] for col in c.fetchall()])
    c.execute('SELECT * FROM user_otps ORDER BY created_at DESC LIMIT 5')
    print('OTPs:', c.fetchall())
except Exception as e:
    print('Error:', e)
