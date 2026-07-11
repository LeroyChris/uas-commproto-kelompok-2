"""
services.py
-----------
Business logic. Menjembatani routes.py (HTTP concern) dengan storage.py
(data concern). routes.py tidak boleh mengandung logika bisnis - akses
data harus lewat fungsi di sini, bukan langsung ke storage.py.

Service ini menggabungkan fitur dari kedua project:
    - final: modular error handling, correlation ID, rate limiting
    - commproto: device-summary dengan enriched n8n data, alert stats
"""

import time
from typing import Any, Dict, Optional, Tuple

from config import Config
from logger import log_event
from schemas import TelemetryPayload
from storage import (
    add_rejected,
    add_telemetry,
    get_rate_limit_counter,
    increment_rate_limit_counter,
    next_telemetry_id,
    read_alert_stats,
    read_device_stats,
    read_rejected,
    read_telemetry,
    reset_all,
    write_alert_stats,
    write_device_stats,
)
from utils import now_iso


def determine_alert_status(temperature: float) -> str:
    """Klasifikasi suhu jadi normal/warning/critical."""
    if temperature > Config.TEMP_CRITICAL_THRESHOLD:
        return "critical"
    if temperature > Config.TEMP_WARNING_THRESHOLD:
        return "warning"
    return "normal"


def _build_alert_stats(alert_status: str) -> dict:
    """Bangun dict alert stats berdasarkan alert_status yang baru masuk."""
    stats = read_alert_stats()
    stats["total_processed"] = stats.get("total_processed", 0) + 1
    key = f"total_{alert_status}"
    stats[key] = stats.get(key, 0) + 1
    stats["last_alert_status"] = alert_status
    stats["last_alert_time"] = now_iso()
    return stats


async def ingest_telemetry(payload: TelemetryPayload, request_id: str) -> Dict[str, Any]:
    """
    Simpan payload yang SUDAH divalidasi Pydantic.
    Forward ke n8n secara synchronous (nunggu response) supaya bisa
    menyertakan n8n_alert / n8n_summary di response ke client.
    Kalau n8n mati, fallback graceful — server tetap return 201.
    """
    from n8n_client import forward_to_n8n

    alert_status = determine_alert_status(payload.temperature)

    record = {
        "id": next_telemetry_id(),
        "request_id": request_id,
        "device_id": payload.device_id,
        "temperature": payload.temperature,
        "humidity": payload.humidity,
        "location": payload.location,
        "alert_status": alert_status,
        "status": "valid",
        "timestamp": now_iso(),
    }
    add_telemetry(record)

    # Update alert stats lokal
    stats = _build_alert_stats(alert_status)
    write_alert_stats(stats)

    log_event(
        request_id,
        f"Telemetry stored: device={record['device_id']} temp={record['temperature']} "
        f"hum={record['humidity']} alert={alert_status}",
    )

    # Forward ke n8n — nunggu response biar data n8n bisa disertakan
    n8n_result = await forward_to_n8n(record, request_id)
    if n8n_result:
        record["n8n_alert"] = n8n_result.get("alertStatus", alert_status)
        record["n8n_status"] = "n8n_200"
    else:
        record["n8n_status"] = "unreachable"
        record["n8n_alert"] = alert_status

    return record


def record_rejected_payload(raw_body: Any, error_code: str, error_message: str, request_id: str) -> Dict[str, Any]:
    """
    Dipanggil oleh exception handler saat validasi Pydantic gagal (422).
    Payload yang ditolak tetap diteruskan ke n8n dengan status "rejected"
    supaya n8n bisa mendemokan branch Build Failure Response / Respond Failure.
    """
    record = {
        "request_id": request_id,
        "reason_code": error_code,
        "reason_message": error_message,
        "raw_payload": raw_body,
        "rejected_at": now_iso(),
    }
    add_rejected(record)
    log_event(request_id, f"Payload ditolak ({error_code}): {error_message}", level="warning")

    # Best-effort ambil field dari raw_body buat n8n display
    raw_dict = raw_body if isinstance(raw_body, dict) else {}
    return {
        "request_id": request_id,
        "device_id": raw_dict.get("device_id"),
        "temperature": raw_dict.get("temperature"),
        "humidity": raw_dict.get("humidity"),
        "location": raw_dict.get("location"),
        "alert_status": None,
        "status": "rejected",
        "reason_code": error_code,
        "reason_message": error_message,
        "timestamp": record["rejected_at"],
    }


def get_latest_telemetry(device_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    data = read_telemetry()
    if device_id:
        data = [r for r in data if r["device_id"] == device_id]
    if not data:
        return None
    return max(data, key=lambda r: r["id"])


def get_telemetry_history(limit: int = 50, device_id: Optional[str] = None) -> Dict[str, Any]:
    data = read_telemetry()
    if device_id:
        data = [r for r in data if r["device_id"] == device_id]
    data.sort(key=lambda r: r["id"], reverse=True)
    return {"count": len(data[:limit]), "total": len(data), "items": data[:limit]}


def get_rejected_payloads() -> Dict[str, Any]:
    data = read_rejected()
    return {"count": len(data), "items": data}


def check_rate_limit(request_id: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Simulasi fixed-window rate limiting: 5 request pertama -> True (200),
    request ke-6 dst -> False (429). Direset lewat POST /demo/reset.
    """
    current_count = increment_rate_limit_counter()
    limit = Config.RATE_LIMIT_MAX_REQUESTS

    if current_count <= limit:
        log_event(request_id, f"Rate limit check OK ({current_count}/{limit})")
        return True, {"request_number": current_count, "limit": limit, "remaining": limit - current_count}

    log_event(request_id, f"Rate limit terlampaui ({current_count}/{limit})", level="warning")
    return False, {
        "request_number": current_count,
        "limit": limit,
        "remaining": 0,
        "retry_after_seconds": Config.RATE_LIMIT_RETRY_AFTER_SECONDS,
    }


def reset_demo(request_id: str) -> None:
    reset_all()
    log_event(request_id, "Demo state direset (telemetry, rejected, alert stats, rate limit)")


def get_stats() -> Dict[str, Any]:
    """Ringkasan untuk landing page + n8n alert stats."""
    telemetry = read_telemetry()
    rejected = read_rejected()
    alert_stats = read_alert_stats()

    total_valid = len(telemetry)
    total_rejected = len(rejected)
    total_requests = total_valid + total_rejected
    success_rate = round((total_valid / total_requests) * 100, 1) if total_requests else 0.0

    last_update = None
    if telemetry:
        last_update = max(telemetry, key=lambda r: r["id"])["timestamp"]

    return {
        "total_telemetry": total_valid,
        "total_rejected": total_rejected,
        "success_rate": success_rate,
        "last_update": last_update,
        "n8n_alert_stats": alert_stats,
    }


def get_device_summary(device_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Ringkasan perangkat — data per-device dengan human-readable summary.
    n8n summary ikut ditampilkan kalau ada (dari n8n callback).
    """
    data = read_telemetry()
    n8n_data = read_device_stats()

    # Group by device_id
    devices = {}
    for r in data:
        did = r["device_id"]
        if did not in devices:
            devices[did] = []
        devices[did].append(r)

    result = []
    for did, readings in devices.items():
        latest = max(readings, key=lambda r: r["id"])
        n8n_info = n8n_data.get(did, {})

        # fallback summary lokal kalau n8n belum kirim data
        summary = n8n_info.get("summary") or _build_local_summary(did, readings, latest)

        entry = {
            "device_id": did,
            "total_readings": len(readings),
            "latest_temperature": latest["temperature"],
            "latest_alert": latest["alert_status"],
            "summary": summary,
            "latest_timestamp": latest["timestamp"],
            "n8n_processed": n8n_info.get("last_n8n_process"),
            "readings": sorted(readings, key=lambda r: r["id"], reverse=True)[:10],
        }
        result.append(entry)

    if device_id:
        result = [r for r in result if r["device_id"] == device_id]

    return {"device_count": len(result), "devices": result}


def _build_local_summary(device_id: str, readings: list, latest: dict) -> str:
    """Buat human-readable summary dari data mentah (fallback kalau n8n belum ngirim)."""
    count = len(readings)
    temps = [r["temperature"] for r in readings]
    avg_temp = round(sum(temps) / len(temps), 1) if temps else 0
    alert_msg = {
        "critical": "butuh perhatian segera!",
        "warning": "perlu diwaspadai.",
        "normal": "dalam batas normal.",
    }
    return (
        f"Device {device_id}: {count}x pembacaan, suhu rata-rata {avg_temp}°C, "
        f"terakhir {latest['temperature']}°C ({latest['alert_status']}) — "
        f"{alert_msg.get(latest['alert_status'], '')}"
    )
