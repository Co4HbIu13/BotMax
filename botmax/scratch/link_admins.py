import sys
import paramiko
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("195.170.163.176", username="root", password="wDJwM6SVBAr75", timeout=10)

update_code = """import sqlite3
con = sqlite3.connect('data/botmax.db')
cur = con.cursor()
cur.execute("UPDATE admins SET max_user_id = 916217 WHERE id = 'admin_super'")
cur.execute("UPDATE admins SET max_user_id = 916217 WHERE id = 'admin_2be90676f8e6' AND max_user_id IS NULL")
con.commit()
print("Updated admins:")
for row in cur.execute("SELECT id, username, display_name, sbp_phone, sbp_bank, max_user_id FROM admins").fetchall():
    print(row)
"""

sftp = ssh.open_sftp()
with sftp.file("/root/botmax/link_admins.py", "w") as f:
    f.write(update_code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("cd /root/botmax && python3 link_admins.py && docker compose logs --tail=25 botmax")
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("ERR:", err)

ssh.close()
