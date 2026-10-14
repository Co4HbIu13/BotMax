"""Remote deployment script for BotMAX on Ubuntu VPS with Let's Encrypt HTTPS"""

import io
import os
import sys
import tarfile
import time
from pathlib import Path
import paramiko

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Server Details
SERVER_IP = "195.170.163.176"
SERVER_USER = "root"
SERVER_PASS = "wDJwM6SVBAr75"
DOMAIN = "anussai.duckdns.org"

LOCAL_DIR = Path(__file__).resolve().parent

EXCLUDE_DIRS = {"venv", "temp_venv", "__pycache__", ".git", ".idea"}
EXCLUDE_FILES = {"test_botmax.db"}


def run_remote_cmd(ssh, cmd, timeout=300):
    """Run command over SSH and stream output"""
    print(f"\n[REMOTE $] {cmd.strip()}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    while True:
        line = stdout.readline()
        if not line:
            break
        print(line.rstrip())
    exit_status = stdout.channel.recv_exit_status()
    err_content = stderr.read().decode().strip()
    if err_content and exit_status != 0:
        print(f"[ERR] {err_content}")
    if exit_status != 0:
        raise RuntimeError(f"Command failed with exit code {exit_status}: {cmd}")
    return exit_status


def create_tarball():
    """Create in-memory tarball of project files"""
    print("-> Creating project tarball...")
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
    print(f"[OK] Tarball ready ({size_mb:.2f} MB)")
    return buffer


def main():
    print("==================================================")
    print(f">>> STARTING DEPLOYMENT TO {SERVER_IP} ({DOMAIN})")
    print("==================================================")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"-> Connecting to {SERVER_USER}@{SERVER_IP}...")
    ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASS, timeout=15)
    print("[OK] SSH connected successfully")

    # Step 1: Configure SWAP (2GB)
    print("\n--- STEP 1: Configuring SWAP ---")
    swap_cmd = """
    if [ ! -f /swapfile ]; then
        echo "Creating 2GB swapfile..."
        fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
        chmod 600 /swapfile
        mkswap /swapfile
        swapon /swapfile
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
        echo "Swap created and enabled successfully."
    else
        echo "Swap already exists."
    fi
    free -h
    """
    run_remote_cmd(ssh, swap_cmd)

    # Step 2: Install Docker and Docker Compose
    print("\n--- STEP 2: Installing Docker & Compose ---")
    docker_check_cmd = """
    if ! command -v docker >/dev/null 2>&1; then
        echo "Installing Docker Engine..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        systemctl enable docker
        systemctl start docker
        rm get-docker.sh
        echo "Docker installed successfully."
    else
        echo "Docker is already installed:" $(docker --version)
    fi
    """
    run_remote_cmd(ssh, docker_check_cmd, timeout=300)

    # Step 3: Upload files
    print("\n--- STEP 3: Uploading Project Files ---")
    tarball_buffer = create_tarball()
    sftp = ssh.open_sftp()
    remote_tar = "/root/botmax.tar.gz"
    print(f"-> Uploading to {remote_tar}...")
    sftp.putfo(tarball_buffer, remote_tar)
    sftp.close()
    print("[OK] Files uploaded successfully")

    # Step 4: Extract and Deploy with Docker Compose
    print("\n--- STEP 4: Extracting & Building Containers ---")
    deploy_cmd = """
    mkdir -p /root/botmax
    tar -xzf /root/botmax.tar.gz -C /root/botmax
    rm -f /root/botmax.tar.gz
    cd /root/botmax
    mkdir -p data logs
    echo "Starting Docker Compose build & up..."
    docker compose down --remove-orphans || true
    docker compose up -d --build
    """
    run_remote_cmd(ssh, deploy_cmd, timeout=600)

    # Step 5: Wait for Caddy & Let's Encrypt SSL
    print("\n--- STEP 5: Verifying SSL & Healthcheck ---")
    print("Waiting 12 seconds for Caddy to obtain Let's Encrypt certificate...")
    time.sleep(12)

    verify_cmd = """
    echo "--- Docker Containers ---"
    docker ps
    echo ""
    echo "--- Local Curl Test ---"
    curl -s http://localhost:8000/health || echo "Local health check waiting..."
    echo ""
    echo "--- Public HTTPS Curl Test ---"
    curl -I -s https://anussai.duckdns.org/health || echo "Waiting for domain..."
    """
    run_remote_cmd(ssh, verify_cmd, timeout=60)

    ssh.close()
    print("\n==================================================")
    print("SUCCESS: DEPLOYMENT FINISHED!")
    print(f"Mini-App: https://{DOMAIN}/")
    print(f"Health Check: https://{DOMAIN}/health")
    print(f"API Raffles: https://{DOMAIN}/api/raffles")
    print("==================================================")


if __name__ == "__main__":
    main()
