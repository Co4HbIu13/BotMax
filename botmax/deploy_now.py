"""Streamlined deployment of BotMAX to VPS"""

import io
import os
import sys
import tarfile
import time
from pathlib import Path
import paramiko

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

SERVER_IP = "195.170.163.176"
SERVER_USER = "root"
SERVER_PASS = "wDJwM6SVBAr75"
DOMAIN = "anussai.duckdns.org"

LOCAL_DIR = Path(__file__).resolve().parent

EXCLUDE_DIRS = {"venv", "temp_venv", "__pycache__", ".git", ".idea"}
EXCLUDE_FILES = {"test_botmax.db", "deploy_remote.py", "deploy.ps1", "botmax.db", "botmax.db-shm", "botmax.db-wal"}


def create_tarball():
    print("-> Packing project files...")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for root, dirs, files in os.walk(LOCAL_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for file in files:
                if file in EXCLUDE_FILES or file.endswith(".pyc"):
                    continue
                full_path = Path(root) / file
                rel_path = full_path.relative_to(LOCAL_DIR)
                tar.add(full_path, arcname=str(rel_path).replace("\\", "/"))

    buffer.seek(0)
    size_mb = len(buffer.getvalue()) / (1024 * 1024)
    print(f"[OK] Tarball ready: {size_mb:.2f} MB")
    return buffer


def main():
    print(f"Connecting to {SERVER_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASS, timeout=15)
    print("[OK] Connected!")

    # 1. Upload files
    tarball = create_tarball()
    print("Uploading to /root/botmax.tar.gz via SFTP...")
    sftp = ssh.open_sftp()
    sftp.putfo(tarball, "/root/botmax.tar.gz")
    sftp.close()
    print("[OK] Upload complete!")

    # 2. Extract and launch
    print("Extracting and building containers via Docker Compose...")
    cmd = """
    mkdir -p /root/botmax
    tar -xzf /root/botmax.tar.gz -C /root/botmax
    rm -f /root/botmax.tar.gz
    cd /root/botmax
    mkdir -p data/uploads logs
    docker compose down --remove-orphans || true
    docker compose up -d --build
    """
    stdin, stdout, stderr = ssh.exec_command(cmd)
    # Drain output
    out = stdout.read().decode()
    err = stderr.read().decode()
    print("Build Output:")
    print(out)
    if err:
        print("Build Log/Notes:")
        print(err)

    # 3. Check status
    print("\nWaiting 10s for Caddy to obtain Let's Encrypt certificate...")
    time.sleep(10)

    cmd_check = """
    docker ps
    echo "--- Testing Local HTTP ---"
    curl -s http://localhost:8000/health || true
    echo ""
    echo "--- Testing Public HTTPS ---"
    curl -I -s https://anussai.duckdns.org/health || true
    """
    stdin, stdout, stderr = ssh.exec_command(cmd_check)
    print("\n--- Container & HTTPS Status ---")
    print(stdout.read().decode())

    ssh.close()
    print("\n==================================================")
    print("🎉 DEPLOYMENT TO VPS COMPLETE!")
    print(f"🌐 Mini-App: https://{DOMAIN}/")
    print(f"💚 Health Check: https://{DOMAIN}/health")
    print(f"🎁 API Raffles: https://{DOMAIN}/api/raffles")
    print("==================================================")


if __name__ == "__main__":
    main()
