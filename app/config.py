"""
config.py
---------
Konfigurasi terpusat. Semua path memakai pathlib supaya berjalan sama
di Windows, Linux, maupun macOS (tidak ada '/' atau '\\' hardcoded).
Port 8088 mengikuti standar yang digunakan dosen di modul UAS.
Host 0.0.0.0 supaya bisa diakses dari dalam container Docker (n8n).
"""

import os
from pathlib import Path


class Config:
    # ---- Server ----
    HOST: str = os.environ.get("API_HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("API_PORT", "8088"))
    RELOAD: bool = os.environ.get("API_RELOAD", "true").lower() == "true"

    # ---- Paths (cross-platform, relatif terhadap lokasi file ini) ----
    ROOT_DIR: Path = Path(__file__).resolve().parent
    DATA_DIR: Path = ROOT_DIR / "data"
    TELEMETRY_FILE: Path = DATA_DIR / "telemetry.json"
    REJECTED_FILE: Path = DATA_DIR / "rejected.json"
    ALERT_STATS_FILE: Path = DATA_DIR / "alert_stats.json"
    DEVICE_STATS_FILE: Path = DATA_DIR / "device_stats.json"
    LOG_FILE: Path = ROOT_DIR / "requests.log"

    # ---- n8n ----
    N8N_WEBHOOK_URL: str = os.environ.get(
        "N8N_WEBHOOK_URL", "http://localhost:5678/webhook/iot-telemetry"
    )
    N8N_FORWARD_TIMEOUT_SECONDS: float = 5.0
    # URL yang dipake n8n buat callback ke server (pakai host.docker.internal
    # karena n8n jalan di Docker, localhost di container ≠ host).
    N8N_CALLBACK_BASE_URL: str = os.environ.get(
        "N8N_CALLBACK_BASE_URL", "http://host.docker.internal:8088"
    )

    # ---- Correlation / Request ID ----
    REQUEST_ID_HEADER: str = "X-Request-ID"

    # ---- Reliability / rate limiting ----
    RATE_LIMIT_MAX_REQUESTS: int = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", "5"))
    RATE_LIMIT_RETRY_AFTER_SECONDS: int = 10

    # ---- Alert threshold (klasifikasi suhu) ----
    TEMP_WARNING_THRESHOLD: float = 35.0
    TEMP_CRITICAL_THRESHOLD: float = 45.0
