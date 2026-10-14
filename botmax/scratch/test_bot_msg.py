import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("195.170.163.176", username="root", password="wDJwM6SVBAr75")

remote_script = """
import asyncio
from maxapi import Bot
import aiohttp
from maxapi.client.default import DefaultConnectionProperties

async def main():
    token = 'f9LHodD0cOKlYORWpPyGoAg9P6wH1JzZeVVPSHl9Jdp4Qd6DwP8vFxU5Kvn12g6D1_7fG0VQCzkl-PRPN_kG'
    connector = aiohttp.TCPConnector(ssl=False)
    bot = Bot(token=token, default_connection=DefaultConnectionProperties(connector=connector))
    
    # 1. Try sending to group chat -79357085377885
    try:
        res = await bot.send_message(chat_id=-79357085377885, text='🔔 Тестовое оповещение: Бот успешно подключен!')
        print('Group chat send result:', res)
    except Exception as e:
        print('Group chat send error:', e)
        
    # 2. Try sending to user 916217
    try:
        res = await bot.send_message(user_id=916217, text='🔔 Тестовое оповещение администратору (ЛС)')
        print('User 916217 send result:', res)
    except Exception as e:
        print('User 916217 send error:', e)

asyncio.run(main())
"""

import base64
encoded = base64.b64encode(remote_script.encode("utf-8")).decode("ascii")
cmd = f"docker exec botmax_app python -c \"import base64; exec(base64.b64decode('{encoded}'))\""
stdin, stdout, stderr = ssh.exec_command(cmd)
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
print("STDOUT:\n", stdout.read().decode("utf-8", errors="replace"))
print("STDERR:\n", stderr.read().decode("utf-8", errors="replace"))
ssh.close()
