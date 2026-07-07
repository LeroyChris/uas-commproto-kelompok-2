"""
mock/sensor.py — Mock Sensor HTTP.

Mensimulasikan IoT device yang mengirim data ke REST API.
Cross-platform (Python murni).

Mode:
    valid   → kirim payload benar (termasuk suhu tinggi untuk alert)
    invalid → kirim payload salah (field hilang, tipe salah)
    stress  → kirim request ke endpoint rate-limit (memicu 429)

Cara jalan:
    python sensor.py valid
    python sensor.py invalid
    python sensor.py stress
"""

import sys
import time

import requests

BASE_URL = "http://localhost:8000/api"
DEVICE_ID = "sensor-iot-01"


def send_valid(delay: float = 0.3) -> None:
    payloads = [
        {"device_id": DEVICE_ID, "temperature": 26.5, "humidity": 60, "location": "Lab Data"},
        {"device_id": DEVICE_ID, "temperature": 38.0, "humidity": 55, "location": "Lab Data"},    # warning
        {"device_id": DEVICE_ID, "temperature": 47.0, "humidity": 50, "location": "Lab Data"},    # critical
    ]
    for i, p in enumerate(payloads, 1):
        r = requests.post(f"{BASE_URL}/telemetry", json=p)
        print(f"[VALID #{i}] POST /telemetry -> {r.status_code}")
        print(f"           body: {r.json()}")
        time.sleep(delay)


def send_invalid(delay: float = 0.3) -> None:
    payloads = [
        {"device_id": DEVICE_ID, "humidity": 60},                          # temperature hilang
        {"device_id": DEVICE_ID, "temperature": "panas", "humidity": 60},  # tipe salah
    ]
    for i, p in enumerate(payloads, 1):
        r = requests.post(f"{BASE_URL}/telemetry", json=p)
        print(f"[INVALID #{i}] POST /telemetry -> {r.status_code}")
        print(f"           body: {r.json()}")
        time.sleep(delay)


def send_stress(n: int = 8, delay: float = 0.1) -> None:
    for i in range(1, n + 1):
        r = requests.get(f"{BASE_URL}/reliability/rate-limit")
        print(f"[STRESS #{i}] GET /reliability/rate-limit -> {r.status_code}")
        time.sleep(delay)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1]
    print(f"Mock Sensor HTTP — mode: {mode}")
    print(f"Target: {BASE_URL}")
    print("-" * 50)

    if mode == "valid":
        send_valid()
    elif mode == "invalid":
        send_invalid()
    elif mode == "stress":
        send_stress()
    else:
        print(f"Mode tidak dikenal: {mode}. Gunakan: valid | invalid | stress")
        sys.exit(1)


if __name__ == "__main__":
    main()
