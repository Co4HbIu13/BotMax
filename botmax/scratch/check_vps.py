import paramiko
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('195.170.163.176', username='root', password='wDJwM6SVBAr75', timeout=10)

py_code = """
import sqlite3
con = sqlite3.connect('data/botmax.db')
cur = con.cursor()
print('=== ADMINS ===')
try:
    cols = [d[0] for d in cur.execute('PRAGMA table_info(admins)').fetchall()]
    print('Cols:', cols)
    for row in cur.execute('SELECT * FROM admins').fetchall():
        print(row)
except Exception as e:
    print('Admins error:', e)

print('=== RAFFLES ===')
try:
    for row in cur.execute('SELECT id, title, creator_admin_id FROM raffles').fetchall():
        print(row)
except Exception as e:
    print('Raffles error:', e)

print('=== CHATS ===')
try:
    for row in cur.execute('SELECT * FROM chats').fetchall():
        print(row)
except Exception as e:
    print('Chats error:', e)

print('=== RECENT ORDERS ===')
try:
    for row in cur.execute('SELECT id, raffle_id, user_id, username, amount, status, created_at FROM orders ORDER BY created_at DESC LIMIT 5').fetchall():
        print(row)
except Exception as e:
    print('Orders error:', e)
"""

sftp = ssh.open_sftp()
with sftp.file('/root/botmax/inspect_db.py', 'w') as f:
    f.write(py_code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("cd /root/botmax && python3 inspect_db.py && docker compose logs --tail=40 bot")
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("ERR:", err)

ssh.close()
