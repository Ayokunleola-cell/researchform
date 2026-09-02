import sqlite3
import random
import string
import uuid
from datetime import datetime, timedelta

conn = sqlite3.connect('researchform_dev.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get the most recently active/created users
cur.execute("SELECT id, email, full_name FROM users ORDER BY created_at DESC LIMIT 5")
users = cur.fetchall()

if not users:
    print("[!] No users found in database.")
    conn.close()
    exit()

print("=" * 60)
print("RESEARCHFORM OTP GENERATOR")
print("=" * 60)

for user in users:
    new_code = ''.join(random.choices(string.digits, k=6))
    expires = datetime.now() + timedelta(minutes=60)  # 60 minute window

    # Clean old OTPs
    cur.execute("DELETE FROM user_otps WHERE user_id = ?", (user['id'],))

    # Insert login, register, and verification OTP records
    for purpose in ['login', 'register', 'verification']:
        cur.execute(
            "INSERT INTO user_otps (id, user_id, otp_code, purpose, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), user['id'], new_code, purpose, expires.isoformat(), datetime.now().isoformat())
        )

    print(f"\nUser    : {user['full_name']} ({user['email']})")
    print(f">> OTP Code : {new_code}")
    print(f"   Expires  : {expires.strftime('%Y-%m-%d %H:%M:%S')} (valid for 60 mins)")

conn.commit()
conn.close()
print("\n" + "=" * 60)
print("[OK] Verification code active and ready to enter!")
print("=" * 60)
