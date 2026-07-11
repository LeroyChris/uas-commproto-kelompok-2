"""
storage.py
----------
Satu-satunya tempat yang boleh membaca/menulis data. Endpoint (routes.py)
dan business logic (services.py) TIDAK boleh membuka file JSON langsung -
semua akses data harus lewat fungsi di file ini.

Format data:
    telemetry.json   -> list[dict] — data valid
    rejected.json    -> list[dict] — payload ditolak
    alert_stats.json -> dict       — agregasi n8n
    device_stats.json-> dict       — summary per-device dari n8n
"""

import json
from typing import Any, Dict, List

from config import Config

# Rate limit counter cukup di memory (direset tiap restart atau via /demo/reset).
_rate_limit_counter: int = 0


def _ensure_data_dir() -> None:
    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_json_list(path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json_list(path, data: List[Dict[str, Any]]) -> None:
    _ensure_data_dir()
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _read_json_dict(path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json_dict(path, data: Dict[str, Any]) -> None:
    _ensure_data_dir()
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---- Telemetry (valid) ----

def read_telemetry() -> List[Dict[str, Any]]:
    return _read_json_list(Config.TELEMETRY_FILE)


def add_telemetry(record: Dict[str, Any]) -> None:
    data = read_telemetry()
    data.append(record)
    _write_json_list(Config.TELEMETRY_FILE, data)


def next_telemetry_id() -> int:
    data = read_telemetry()
    return max((item["id"] for item in data), default=0) + 1


# ---- Rejected (invalid) ----

def read_rejected() -> List[Dict[str, Any]]:
    return _read_json_list(Config.REJECTED_FILE)


def add_rejected(record: Dict[str, Any]) -> None:
    data = read_rejected()
    data.append(record)
    _write_json_list(Config.REJECTED_FILE, data)


# ---- Alert stats (dari n8n callback / server lokal) ----

def read_alert_stats() -> Dict[str, Any]:
    data = _read_json_dict(Config.ALERT_STATS_FILE)
    # Normalize: pastikan bentuknya dict, bukan list (default dari clean state)
    if isinstance(data, list):
        data = {}
    return data


def write_alert_stats(data: Dict[str, Any]) -> None:
    _write_json_dict(Config.ALERT_STATS_FILE, data)


# ---- Device stats (dari n8n callback) ----

def read_device_stats() -> Dict[str, Any]:
    data = _read_json_dict(Config.DEVICE_STATS_FILE)
    if isinstance(data, list):
        data = {}
    return data


def write_device_stats(data: Dict[str, Any]) -> None:
    _write_json_dict(Config.DEVICE_STATS_FILE, data)


# ---- Rate limit counter ----

def increment_rate_limit_counter() -> int:
    global _rate_limit_counter
    _rate_limit_counter += 1
    return _rate_limit_counter


def get_rate_limit_counter() -> int:
    return _rate_limit_counter


def reset_rate_limit_counter() -> None:
    global _rate_limit_counter
    _rate_limit_counter = 0


# ---- Demo reset ----

def reset_all() -> None:
    _write_json_list(Config.TELEMETRY_FILE, [])
    _write_json_list(Config.REJECTED_FILE, [])
    write_alert_stats({
        "total_processed": 0, "total_normal": 0,
        "total_warning": 0, "total_critical": 0,
        "last_alert_status": None, "last_alert_time": None,
    })
    write_device_stats({})
    reset_rate_limit_counter()
