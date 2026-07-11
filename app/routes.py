"""
routes.py
---------
Definisi endpoint HTTP. Hanya mengurus concern HTTP: ambil request_id
dari request.state (di-set middleware.py), panggil services.py untuk
business logic, dan kembalikan response lewat helper di responses.py.
Tidak ada logika bisnis di sini, dan tidak ada akses langsung ke file
storage (harus lewat services.py / storage.py).

14 endpoint — menggabungkan semua endpoint dari kedua project:
    - final:  health, telemetry CRUD, stats, reset, rate-limit
    - commproto: device-summary, n8n callbacks, n8n rate-limit
"""

import time

from fastapi import APIRouter, BackgroundTasks, Request

import services
from logger import log_event
from n8n_client import forward_to_n8n
from responses import error_response, success_response
from schemas import AlertStatsPayload, TelemetryPayload
from storage import read_alert_stats, read_device_stats, write_device_stats, write_alert_stats
from utils import elapsed_ms, now_iso

router = APIRouter(prefix="/api")


# =========================================================================
# SYSTEM
# =========================================================================


@router.get("/health", tags=["System"])
async def health(request: Request):
    start = time.perf_counter()
    return success_response(
        data={"status": "ok", "service": "iot-telemetry-api"},
        message="Service is healthy.",
        request_id=request.state.request_id,
        processing_time_ms=elapsed_ms(start, time.perf_counter()),
    )


@router.get("/stats", tags=["System"])
async def get_stats(request: Request):
    start = time.perf_counter()
    result = services.get_stats()
    return success_response(
        data=result,
        message="Statistics summary.",
        request_id=request.state.request_id,
        processing_time_ms=elapsed_ms(start, time.perf_counter()),
    )


# =========================================================================
# TELEMETRY
# =========================================================================


@router.post("/telemetry", tags=["Telemetry"], status_code=201)
async def post_telemetry(payload: TelemetryPayload, request: Request):
    """
    Terima data sensor. Validasi field (device_id, temperature, humidity,
    location) dilakukan otomatis oleh Pydantic (schemas.py) sebelum
    fungsi ini dipanggil - kalau gagal, request tidak sampai ke sini.
    Data diferuskan ke n8n dan response menyertakan hasil n8n.
    """
    start = time.perf_counter()
    request_id = request.state.request_id

    record = await services.ingest_telemetry(payload, request_id)

    return success_response(
        data=record,
        message="Telemetry data received and stored.",
        request_id=request_id,
        processing_time_ms=elapsed_ms(start, time.perf_counter()),
        status_code=201,
    )


@router.get("/telemetry/latest", tags=["Telemetry"])
async def get_telemetry_latest(request: Request, device_id: str | None = None):
    start = time.perf_counter()
    latest = services.get_latest_telemetry(device_id)

    if latest is None:
        return error_response(
            message="No telemetry data available yet.",
            error_code="NO_DATA",
            request_id=request.state.request_id,
            status_code=404,
        )

    return success_response(
        data=latest,
        message="Latest telemetry data.",
        request_id=request.state.request_id,
        processing_time_ms=elapsed_ms(start, time.perf_counter()),
    )


@router.get("/telemetry/history", tags=["Telemetry"])
async def get_telemetry_history(request: Request, limit: int = 50, device_id: str | None = None):
    start = time.perf_counter()
    result = services.get_telemetry_history(limit=limit, device_id=device_id)

    return success_response(
        data=result,
        message="Telemetry history.",
        request_id=request.state.request_id,
        processing_time_ms=elapsed_ms(start, time.perf_counter()),
    )


@router.get("/telemetry/rejected", tags=["Telemetry"])
async def get_telemetry_rejected(request: Request):
    start = time.perf_counter()
    result = services.get_rejected_payloads()

    return success_response(
        data=result,
        message="Rejected telemetry payloads.",
        request_id=request.state.request_id,
        processing_time_ms=elapsed_ms(start, time.perf_counter()),
    )


@router.get("/telemetry/device-summary", tags=["Telemetry"])
async def get_device_summary(request: Request, device_id: str | None = None):
    """
    Ringkasan perangkat — data per-device dengan human-readable summary
    dari n8n (kalau ada). Menunjukkan komunikasi dua arah server ↔ n8n.
    """
    start = time.perf_counter()
    result = services.get_device_summary(device_id)

    return success_response(
        data=result,
        message="Device summary.",
        request_id=request.state.request_id,
        processing_time_ms=elapsed_ms(start, time.perf_counter()),
    )


# =========================================================================
# DEMO
# =========================================================================


@router.post("/demo/reset", tags=["Demo"])
async def post_demo_reset(request: Request):
    start = time.perf_counter()
    services.reset_demo(request.state.request_id)

    return success_response(
        data={"reset": True},
        message="Demo state has been reset.",
        request_id=request.state.request_id,
        processing_time_ms=elapsed_ms(start, time.perf_counter()),
    )


# =========================================================================
# RELIABILITY
# =========================================================================


@router.get("/reliability/rate-limit", tags=["Reliability"])
async def get_reliability_rate_limit(request: Request):
    """
    Demo rate limiting server-side. 5 request pertama 200, ke-6 dst 429.
    """
    start = time.perf_counter()
    is_allowed, result = services.check_rate_limit(request.state.request_id)

    if not is_allowed:
        return error_response(
            message="Too many requests. Rate limit exceeded.",
            error_code="RATE_LIMIT_EXCEEDED",
            request_id=request.state.request_id,
            status_code=429,
            extra=result,
        )

    return success_response(
        data=result,
        message="Request accepted within rate limit.",
        request_id=request.state.request_id,
        processing_time_ms=elapsed_ms(start, time.perf_counter()),
    )


@router.get("/reliability/n8n-rate-limit", tags=["Reliability"])
async def get_n8n_rate_limit(request: Request):
    """
    Rate limiting via n8n — n8n yang decide accept/reject.
    Server hanya pencatat. n8n akan POST hasilnya ke /api/n8n/rate-result.
    """
    from n8n_client import forward_to_n8n

    start = time.perf_counter()
    request_id = request.state.request_id

    n8n_result = await forward_to_n8n({
        "type": "rate_limit",
        "request_id": request_id,
        "timestamp": time.time(),
    }, request_id)

    if n8n_result and n8n_result.get("decision") == "allowed":
        return success_response(
            data={"decision": "allowed", "remaining": n8n_result.get("remaining", 0)},
            message="Rate limit OK (decided by n8n).",
            request_id=request_id,
            processing_time_ms=elapsed_ms(start, time.perf_counter()),
        )
    return error_response(
        message="Too many requests (decided by n8n).",
        error_code="RATE_LIMIT_EXCEEDED",
        request_id=request_id,
        status_code=429,
    )


# =========================================================================
# N8N CALLBACKS (n8n → server)
# =========================================================================


@router.post("/n8n/alert-stats", tags=["n8n"])
async def n8n_alert_stats(payload: AlertStatsPayload, request: Request):
    """Terima alert stats yang diakumulasi n8n. n8n → POST → server simpan."""
    request_id = request.state.request_id
    write_alert_stats(payload.model_dump())
    log_event(request_id, f"n8n alert stats updated: {payload.total_processed} processed")
    return success_response(
        data={"stored": True},
        message="Alert stats received from n8n.",
        request_id=request_id,
    )


@router.get("/n8n/alert-stats", tags=["n8n"])
async def get_n8n_alert_stats(request: Request):
    """Baca alert stats yang sudah diakumulasi n8n."""
    data = read_alert_stats()
    if not data:
        data = {
            "total_processed": 0, "total_normal": 0,
            "total_warning": 0, "total_critical": 0,
            "last_alert_status": None, "last_alert_time": None,
        }
    return success_response(
        data=data,
        message="Alert statistics from n8n.",
        request_id=request.state.request_id,
    )


@router.post("/n8n/device-summary", tags=["n8n"])
async def n8n_device_summary(request: Request):
    """Terima summary per-device dari n8n. n8n → POST → server simpan."""
    request_id = request.state.request_id
    body = await request.json()
    device_id = body.get("device_id", "unknown")
    summary = body.get("summary", "")

    stats = read_device_stats()
    stats[device_id] = {
        "summary": summary,
        "last_n8n_process": now_iso(),
        "count": body.get("count", 0),
        "alert_status": body.get("alert_status", "unknown"),
    }
    write_device_stats(stats)

    log_event(request_id, f"n8n device summary for {device_id}: {summary}")
    return success_response(
        data={"stored": True},
        message="Device summary received from n8n.",
        request_id=request_id,
    )


@router.post("/n8n/rate-result", tags=["n8n"])
async def n8n_rate_result(request: Request):
    """Terima keputusan rate limit dari n8n. n8n → POST → server catat."""
    request_id = request.state.request_id
    body = await request.json()
    log_event(request_id, f"n8n rate decision: {body.get('decision')}")
    return success_response(
        data={"stored": True},
        message="Rate decision received from n8n.",
        request_id=request_id,
    )
