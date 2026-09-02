import sqlite3
conn = sqlite3.connect('researchform_dev.db')
c = conn.cursor()

c.execute("SELECT id FROM users WHERE email = ?", ("projosconic99@gmail.com",))
user_row = c.fetchone()
if not user_row:
    print("User not found.")
else:
    user_id = user_row[0]
    c.execute("SELECT otp_code, created_at, expires_at FROM user_otps WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
    res = c.fetchone()
    if res:
        print("LATEST OTP CODE:", res[0])
        print("Created at:", res[1])
        print("Expires at:", res[2])
    else:
        print("No OTP codes found for this user.")
