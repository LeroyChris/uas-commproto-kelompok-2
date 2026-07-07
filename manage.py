#!/usr/bin/env python3
"""
manage.py — Cross-platform launcher untuk UAS IoT Telemetry Mini.

Berfungsi SAMA di Windows, Linux, dan macOS — karena Python murni,
tidak bergantung pada bash (.sh) atau PowerShell (.ps1).

Pemakaian:
    python manage.py backend              # install deps + jalankan REST API (foreground, Ctrl+C)
    python manage.py sensor valid         # mock sensor mode valid
    python manage.py sensor invalid       # mock sensor mode invalid
    python manage.py sensor stress        # mock sensor mode stress (rate limit)
    python manage.py n8n start            # jalankan n8n via Docker Compose (foreground, Ctrl+C)
    python manage.py n8n stop             # hentikan n8n
    python manage.py n8n logs             # lihat log n8n (real-time)
"""

import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "app"
MOCK_DIR = ROOT / "mock"


def run(cmd: list, cwd: Path = None) -> int:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd).returncode


def run_foreground(cmd: list, cwd: Path = None) -> None:
    """
    Jalankan command di foreground. Ctrl+C akan menghentikan process.
    Menggunakan sys.executable agar inherit terminal.
    """
    print(f"$ {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=cwd)
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")


def pip_install(req_file: Path, cwd: Path) -> None:
    base = [sys.executable, "-m", "pip", "install", "-r", str(req_file)]
    result = subprocess.run(base, cwd=cwd)
    if result.returncode != 0:
        print("[INFO] Retrying with --break-system-packages ...")
        subprocess.run(base + ["--break-system-packages"], cwd=cwd)


def _kill_port(port: int) -> None:
    """Matikan proses yang menggunakan port tertentu. Cross-platform."""
    import subprocess
    import platform

    try:
        if platform.system() == "Windows":
            # Windows: netstat + taskkill
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    pid = parts[-1] if parts else ""
                    if pid:
                        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                        print(f"[INFO] Killed process on port {port} (PID {pid})")
        else:
            # Unix: lsof + kill
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=3
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split("\n")
                for pid in pids:
                    subprocess.run(["kill", pid], capture_output=True)
                    print(f"[INFO] Killed process on port {port} (PID {pid})")
    except Exception:
        pass


def cmd_backend() -> None:
    print(f"[INFO] OS: {platform.system()}")
    _kill_port(8000)
    req = APP_DIR / "requirements.txt"
    pip_install(req, APP_DIR)
    print("[INFO] Starting FastAPI backend on http://localhost:8000")
    print("[INFO] Swagger UI: http://localhost:8000/docs")
    print("[INFO] Landing page: http://localhost:8000/")
    print("[INFO] Press Ctrl+C to stop.\n")
    run_foreground([sys.executable, "server.py"], cwd=APP_DIR)


def cmd_sensor(mode: str) -> None:
    # Pastikan requests terinstall
    pip_install(APP_DIR / "requirements.txt", APP_DIR)
    run_foreground([sys.executable, "sensor.py", mode], cwd=MOCK_DIR)


def _compose_cmd() -> list:
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return ["docker", "compose"]


def _docker_ps() -> str:
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=uas-n8n", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return ""


def cmd_n8n(action: str) -> None:
    if not shutil.which("docker"):
        print("[ERROR] Docker tidak ditemukan.")
        sys.exit(1)

    if action == "start":
        if _docker_ps():
            print("[INFO] n8n sudah berjalan. Hentikan dulu: python manage.py n8n stop")
            return

        # Pastikan container tidak dalam status 'exited'
        subprocess.run(["docker", "rm", "uas-n8n"], capture_output=True)

        print("[INFO] Menjalankan n8n via Docker Compose (foreground)...")
        print("[INFO] Dashboard: http://localhost:5678")
        print("[INFO] Press Ctrl+C to stop.\n")
        compose = _compose_cmd()
        run_foreground(compose + ["up", "n8n"], cwd=ROOT)

    elif action == "stop":
        if not _docker_ps():
            print("[INFO] n8n sudah berhenti.")
            return
        print("[INFO] Menghentikan n8n...")
        subprocess.run(["docker", "stop", "uas-n8n"], capture_output=True)
        print("[OK] n8n dihentikan.")

    elif action == "logs":
        if not _docker_ps():
            print("[INFO] n8n tidak berjalan. Jalankan dulu: python manage.py n8n start")
            return
        print("[INFO] n8n logs (Ctrl+C to exit):\n")
        subprocess.run(["docker", "logs", "-f", "uas-n8n"])

    else:
        print(f"Aksi tidak dikenal: {action}")
        print("Gunakan: start | stop | logs")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "backend":
        cmd_backend()
    elif cmd == "sensor":
        mode = sys.argv[2] if len(sys.argv) > 2 else "valid"
        cmd_sensor(mode)
    elif cmd == "n8n":
        action = sys.argv[2] if len(sys.argv) > 2 else "start"
        cmd_n8n(action)
    else:
        print(f"Perintah tidak dikenal: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
