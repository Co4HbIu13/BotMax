import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("195.170.163.176", username="root", password="wDJwM6SVBAr75")

remote_script = """
import sqlite3
conn = sqlite3.connect('data/botmax.db')
cur = conn.cursor()
print('=== ALL USERS IN DB ===')
try:
    for r in cur.execute('SELECT user_id, username, first_name, phone, last_seen_at FROM users').fetchall():
        print(f"ID={r[0]}, user={r[1]}, name={r[2]}, phone={r[3]}, last_seen={r[4]}")
except Exception as e:
    print('Users error:', e)

print('=== ALL ADMINS IN DB ===')
try:
    for r in cur.execute('SELECT id, username, display_name, sbp_phone, sbp_bank FROM admins').fetchall():
        print(f"ID={r[0]}, user={r[1]}, name={r[2]}, phone={r[3]}, bank={r[4]}")
except Exception as e:
    print('Admins error:', e)

print('=== ADMINS ===')
try:
    for r in cur.execute('SELECT id, username, display_name, sbp_phone, sbp_bank FROM admins').fetchall():
        print(r)
except Exception as e:
    print('Admins error:', e)

print('=== RECENT ORDERS ===')
try:
    for r in cur.execute('SELECT id, raffle_id, user_id, amount, status, recipient_admin_id FROM orders ORDER BY created_at DESC LIMIT 5').fetchall():
        print(r)
except Exception as e:
    print('Orders error:', e)
"""

import base64

encoded = base64.b64encode(remote_script.encode("utf-8")).decode("ascii")
cmd = f"docker exec botmax_app python -c \"import base64; exec(base64.b64decode('{encoded}'))\""
stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode("utf-8"))
print("STDERR:\n", stderr.read().decode("utf-8"))
ssh.close()
