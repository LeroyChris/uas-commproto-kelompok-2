"""
server.py — IoT Telemetry Mini REST API
===========================================
Monolitik. 1 file = semua logika backend.

Use Case UAS:
    IoT Telemetry Mini — REST API menerima data sensor dummy,
    validasi Pydantic, simpan data, forward ke n8n, logging,
    rate limiting, dan rejected payload recording.

n8n purpose:
    1. Alert Stats Aggregator — accumulate telemetry stats
    2. Rate Limiter — decide accept/reject

Landing page:
    http://localhost:8000/ — dashboard statistik
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# =========================================================================
# CONFIG
# =========================================================================

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DATA_DIR = ROOT / "data"
TELEMETRY_FILE = DATA_DIR / "telemetry.json"
REJECTED_FILE = DATA_DIR / "rejected.json"
ALERT_STATS_FILE = DATA_DIR / "alert_stats.json"
DEVICE_STATS_FILE = DATA_DIR / "device_stats.json"
LOG_FILE = ROOT / "requests.log"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

HOST = os.environ.get("API_HOST", "0.0.0.0")
PORT = int(os.environ.get("API_PORT", "8000"))
N8N_WEBHOOK_URL = os.environ.get(
    "N8N_WEBHOOK_URL", "http://localhost:5678/webhook/iot-telemetry"
)
TEMP_WARNING = 35.0
TEMP_CRITICAL = 45.0
RATE_LIMIT_MAX = 5

# =========================================================================
# SETUP LOGGING
# =========================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("iot-telemetry")

# =========================================================================
# PYDANTIC SCHEMAS
# =========================================================================


class TelemetryPayload(BaseModel):
    """Payload sensor — validasi otomatis oleh Pydantic."""

    device_id: str = Field(..., min_length=1, max_length=100)
    temperature: float = Field(..., ge=-50, le=100)
    humidity: float = Field(..., ge=0, le=100)
    location: str | None = Field(None, max_length=200)


class AlertStatsPayload(BaseModel):
    """Payload alert stats dari n8n."""

    total_processed: int = 0
    total_normal: int = 0
    total_warning: int = 0
    total_critical: int = 0
    last_alert_status: str | None = None
    last_alert_time: str | None = None


# =========================================================================
# STORAGE HELPERS (file JSON)
# =========================================================================


def _read_json(path: Path) -> list | dict:
    if not path.exists():
        return [] if path.suffix == '.json' else {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: list | dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _next_id(data: list) -> int:
    return max((item["id"] for item in data), default=0) + 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_request_id() -> str:
    return f"req-{uuid.uuid4().hex[:8]}"


# =========================================================================
# APP FACTORY
# =========================================================================

app = FastAPI(
    title="IoT Telemetry API — UAS Communication Protocol",
    description=(
        "REST API untuk IoT Telemetry Mini. "
        "Menerima data sensor dummy, validasi, simpan, forward ke n8n."
    ),
    version="3.0.0",
    docs_url="/docs",
    redoc_url=None,
)

# ------------------------------------------------------------------
# GLOBAL STATE (rate limit, di-reset via /api/demo/reset)
# ------------------------------------------------------------------
_rate_limit_counter = 0


# =========================================================================
# MOUNT STATIC FILES
# =========================================================================

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# =========================================================================
# EXCEPTION HANDLER — RequestValidationError
# =========================================================================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Tangkap error validasi Pydantic, catat payload yang ditolak ke rejected.json,
    kembalikan response error sesuai API contract.
    """
    request_id = getattr(request.state, "request_id", "unknown")

    try:
        raw_body = await request.json()
    except Exception:
        raw_body = None

    first = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
    msg = first.get("msg", "invalid payload")
    error_message = f"{loc}: {msg}" if loc else msg

    rejected = _read_json(REJECTED_FILE)
    rejected.append({
        "request_id": request_id,
        "reason_code": "VALIDATION_ERROR",
        "reason_message": error_message,
        "raw_payload": raw_body,
        "rejected_at": _now_iso(),
    })
    _write_json(REJECTED_FILE, rejected)

    logger.warning(f"[{request_id}] REJECTED: {error_message} | payload={raw_body}")

    return error_response(error_message, "VALIDATION_ERROR", request_id, 422)


# =========================================================================
# RESPONSE BUILDERS (konsisten)
# =========================================================================


def success_response(data, message, request_id, status_code=200, processing_time_ms=0):
    body = {
        "success": True,
        "message": message,
        "data": data,
        "meta": {
            "request_id": request_id,
            "timestamp": _now_iso(),
            "processing_time_ms": processing_time_ms,
        },
    }
    return JSONResponse(content=jsonable_encoder(body), status_code=status_code)


def error_response(message, error_code, request_id, status_code=400, extra=None):
    error_obj = {"code": error_code}
    if extra:
        error_obj.update(extra)
    body = {
        "success": False,
        "message": message,
        "error": error_obj,
        "meta": {
            "request_id": request_id,
            "timestamp": _now_iso(),
        },
    }
    return JSONResponse(content=jsonable_encoder(body), status_code=status_code)


# =========================================================================
# MIDDLEWARE
# =========================================================================


@app.middleware("http")
async def request_id_and_logging(request: Request, call_next):
    """Request ID, timing, logging, dan CORS otomatis."""
    request_id = _new_request_id()
    request.state.request_id = request_id

    logger.info(f"[{request_id}] --> {request.method} {request.url.path}")
    start = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Processing-Time-Ms"] = str(duration_ms)

    logger.info(f"[{request_id}] <-- {request.method} {request.url.path} {response.status_code} {duration_ms}ms")
    return response


@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        response = JSONResponse(content={})
    else:
        response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Request-ID"
    return response


# =========================================================================
# BUSINESS LOGIC
# =========================================================================


def _determine_alert(temp: float) -> str:
    if temp > TEMP_CRITICAL:
        return "critical"
    if temp > TEMP_WARNING:
        return "warning"
    return "normal"


async def _forward_to_n8n(record: dict, request_id: str) -> str | None:
    """Forward record ke n8n. Return response JSON atau None."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(N8N_WEBHOOK_URL, json=record)
            logger.info(f"[{request_id}] n8n forward: HTTP {resp.status_code}")
            if resp.status_code == 200:
                return resp.json()
    except httpx.RequestError as exc:
        logger.warning(f"[{request_id}] n8n unreachable: {exc}")
    return None


# =========================================================================
# ENDPOINTS
# =========================================================================


@app.get("/", include_in_schema=False)
async def landing_page():
    """Landing page dashboard (bukan JSON)."""
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(content={"message": "Landing page belum tersedia. Buka /docs untuk Swagger UI."})


@app.get("/api/health", tags=["System"])
async def health(request: Request):
    """Cek server hidup. Success scenario 1."""
    return success_response(
        data={"status": "ok", "service": "iot-telemetry-api"},
        message="Service is healthy.",
        request_id=request.state.request_id,
    )


@app.post("/api/telemetry", tags=["Telemetry"], status_code=201)
async def post_telemetry(payload: TelemetryPayload, request: Request):
    """
    Terima data sensor.
    Validasi otomatis Pydantic. Forward ke n8n.
    """
    request_id = request.state.request_id
    start = time.perf_counter()

    data = _read_json(TELEMETRY_FILE)
    record = {
        "id": _next_id(data),
        "request_id": request_id,
        "device_id": payload.device_id,
        "temperature": payload.temperature,
        "humidity": payload.humidity,
        "location": payload.location,
        "alert_status": _determine_alert(payload.temperature),
        "timestamp": _now_iso(),
    }
    data.append(record)
    _write_json(TELEMETRY_FILE, data)

    logger.info(
        f"[{request_id}] Telemetry stored: "
        f"device={record['device_id']} temp={record['temperature']} "
        f"hum={record['humidity']} alert={record['alert_status']}"
    )

    # Forward ke n8n
    n8n_result = await _forward_to_n8n(record, request_id)
    if n8n_result:
        record["n8n_alert"] = n8n_result.get("alertStatus", "unknown")
        record["n8n_status"] = "n8n_200"
    else:
        record["n8n_status"] = "unreachable"
        record["n8n_alert"] = record["alert_status"]

    duration = round((time.perf_counter() - start) * 1000)
    return success_response(
        data=record,
        message="Telemetry data received and stored.",
        request_id=request_id,
        status_code=201,
        processing_time_ms=duration,
    )


@app.get("/api/telemetry/latest", tags=["Telemetry"])
async def get_latest(request: Request, device_id: str | None = None):
    """Data telemetry terbaru."""
    data = _read_json(TELEMETRY_FILE)
    if device_id:
        data = [r for r in data if r["device_id"] == device_id]
    if not data:
        return error_response(
            message="No telemetry data available yet.",
            error_code="NO_DATA",
            request_id=request.state.request_id,
            status_code=404,
        )
    latest = max(data, key=lambda r: r["id"])
    return success_response(
        data=latest,
        message="Latest telemetry data.",
        request_id=request.state.request_id,
    )


@app.get("/api/telemetry/history", tags=["Telemetry"])
async def get_history(request: Request, limit: int = 50, device_id: str | None = None):
    """Semua histori telemetry."""
    data = _read_json(TELEMETRY_FILE)
    if device_id:
        data = [r for r in data if r["device_id"] == device_id]
    data.sort(key=lambda r: r["id"], reverse=True)
    return success_response(
        data={"count": len(data[:limit]), "total": len(data), "items": data[:limit]},
        message="Telemetry history.",
        request_id=request.state.request_id,
    )


@app.get("/api/telemetry/rejected", tags=["Telemetry"])
async def get_rejected(request: Request):
    """Payload yang gagal validasi — evidence error path."""
    data = _read_json(REJECTED_FILE)
    return success_response(
        data={"count": len(data), "items": data},
        message="Rejected telemetry payloads.",
        request_id=request.state.request_id,
    )


@app.get("/api/telemetry/device-summary", tags=["Telemetry"])
async def device_summary(request: Request, device_id: str | None = None):
    """
    Ringkasan perangkat — data per-device dengan human-readable summary.
    n8n summary ikut ditampilkan kalau ada.
    """
    data = _read_json(TELEMETRY_FILE)
    n8n_data = _read_json(DEVICE_STATS_FILE)
    if isinstance(n8n_data, list):
        n8n_data = {}

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

        summary = n8n_info.get("summary") or _build_summary(did, readings, latest)
        icon = "🚨" if latest["alert_status"] == "critical" else "⚠️" if latest["alert_status"] == "warning" else "✅"

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
        result = [d for d in result if d["device_id"] == device_id]

    return success_response(
        data={"device_count": len(result), "devices": result},
        message="Device summary.",
        request_id=request.state.request_id,
    )


def _build_summary(device_id: str, readings: list, latest: dict) -> str:
    """Buat human-readable summary dari data mentah."""
    count = len(readings)
    temps = [r["temperature"] for r in readings]
    avg_temp = round(sum(temps) / len(temps), 1)
    alert_msg = {
        "critical": "butuh perhatian segera!",
        "warning": "perlu diwaspadai.",
        "normal": "dalam batas normal.",
    }
    return f"Device {device_id}: {count}x pembacaan, suhu rata-rata {avg_temp}°C, terakhir {latest['temperature']}°C ({latest['alert_status']}) — {alert_msg.get(latest['alert_status'], '')}"


@app.post("/api/demo/reset", tags=["Demo"])
async def demo_reset(request: Request):
    """Reset semua data (telemetry, rejected, rate limit, alert stats)."""
    global _rate_limit_counter
    _write_json(TELEMETRY_FILE, [])
    _write_json(REJECTED_FILE, [])
    _write_json(ALERT_STATS_FILE, {
        "total_processed": 0, "total_normal": 0,
        "total_warning": 0, "total_critical": 0,
        "last_alert_status": None, "last_alert_time": None,
    })
    _write_json(DEVICE_STATS_FILE, {})
    _rate_limit_counter = 0
    logger.info(f"[{request.state.request_id}] Demo state reset")
    return success_response(
        data={"reset": True},
        message="Demo state has been reset.",
        request_id=request.state.request_id,
    )


@app.get("/api/reliability/rate-limit", tags=["Reliability"])
async def rate_limit(request: Request):
    """
    Rate limiting demo.
    5 request pertama → 200. Request ke-6 dst → 429.
    """
    global _rate_limit_counter
    request_id = request.state.request_id
    _rate_limit_counter += 1
    count = _rate_limit_counter

    if count <= RATE_LIMIT_MAX:
        logger.info(f"[{request_id}] Rate limit OK ({count}/{RATE_LIMIT_MAX})")
        return success_response(
            data={
                "request_number": count,
                "limit": RATE_LIMIT_MAX,
                "remaining": RATE_LIMIT_MAX - count,
            },
            message="Request accepted within rate limit.",
            request_id=request_id,
        )

    logger.warning(f"[{request_id}] Rate limit EXCEEDED ({count}/{RATE_LIMIT_MAX})")
    return error_response(
        message="Too many requests. Rate limit exceeded.",
        error_code="RATE_LIMIT_EXCEEDED",
        request_id=request_id,
        status_code=429,
        extra={
            "request_number": count,
            "limit": RATE_LIMIT_MAX,
            "remaining": 0,
            "retry_after_seconds": 10,
        },
    )


@app.get("/api/reliability/n8n-rate-limit", tags=["Reliability"])
async def n8n_rate_limit(request: Request):
    """
    Rate limiting via n8n — n8n yang decide accept/reject.
    Server hanya pencatat. n8n akan POST hasilnya ke /api/n8n/rate-result.
    """
    request_id = request.state.request_id
    n8n_result = await _forward_to_n8n({
        "type": "rate_limit",
        "request_id": request_id,
        "timestamp": _now_iso(),
    }, request_id)

    if n8n_result and n8n_result.get("decision") == "allowed":
        return success_response(
            data={"decision": "allowed", "remaining": n8n_result.get("remaining", 0)},
            message="Rate limit OK (decided by n8n).",
            request_id=request_id,
        )
    return error_response(
        message="Too many requests (decided by n8n).",
        error_code="RATE_LIMIT_EXCEEDED",
        request_id=request_id,
        status_code=429,
    )


# =========================================================================
# N8N ENDPOINTS — Alert Stats Aggregator
# =========================================================================


@app.post("/api/n8n/alert-stats", tags=["n8n"])
async def n8n_alert_stats(payload: AlertStatsPayload, request: Request):
    """Terima alert stats yang diakumulasi n8n. n8n → POST → server simpan."""
    request_id = request.state.request_id
    _write_json(ALERT_STATS_FILE, payload.model_dump())
    logger.info(f"[{request_id}] n8n alert stats updated: {payload.total_processed} processed")
    return success_response(
        data={"stored": True},
        message="Alert stats received from n8n.",
        request_id=request_id,
    )


@app.post("/api/n8n/device-summary", tags=["n8n"])
async def n8n_device_summary(request: Request):
    """Terima summary per-device dari n8n. n8n → POST → server simpan."""
    request_id = request.state.request_id
    body = await request.json()
    device_id = body.get("device_id", "unknown")
    summary = body.get("summary", "")

    stats = {}
    if DEVICE_STATS_FILE.exists():
        stats = _read_json(DEVICE_STATS_FILE)
    if isinstance(stats, list):
        stats = {}

    stats[device_id] = {
        "summary": summary,
        "last_n8n_process": _now_iso(),
        "count": body.get("count", 0),
        "alert_status": body.get("alert_status", "unknown"),
    }
    _write_json(DEVICE_STATS_FILE, stats)

    logger.info(f"[{request_id}] n8n device summary for {device_id}: {summary}")
    return success_response(
        data={"stored": True},
        message="Device summary received from n8n.",
        request_id=request_id,
    )


@app.get("/api/n8n/alert-stats", tags=["n8n"])
async def get_alert_stats(request: Request):
    """Baca alert stats yang sudah diakumulasi n8n."""
    data = _read_json(ALERT_STATS_FILE)
    if not data or isinstance(data, list):
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


@app.post("/api/n8n/rate-result", tags=["n8n"])
async def n8n_rate_result(request: Request):
    """Terima keputusan rate limit dari n8n. n8n → POST → server catat."""
    request_id = request.state.request_id
    body = await request.json()
    logger.info(f"[{request_id}] n8n rate decision: {body.get('decision')}")
    return success_response(
        data={"stored": True},
        message="Rate decision received from n8n.",
        request_id=request_id,
    )


# =========================================================================
# STATS (untuk landing page)
# =========================================================================


@app.get("/api/stats", tags=["System"])
async def get_stats(request: Request):
    """Statistik ringkasan untuk dashboard/laporan."""
    telemetry = _read_json(TELEMETRY_FILE)
    rejected = _read_json(REJECTED_FILE)
    alert_stats = _read_json(ALERT_STATS_FILE)
    if isinstance(alert_stats, list):
        alert_stats = {}

    total_req = len(telemetry) + len(rejected)
    success_rate = round((len(telemetry) / total_req) * 100, 1) if total_req else 0.0
    last_update = max(telemetry, key=lambda r: r["id"])["timestamp"] if telemetry else None

    return success_response(
        data={
            "total_telemetry": len(telemetry),
            "total_rejected": len(rejected),
            "success_rate": success_rate,
            "last_update": last_update,
            "n8n_alert_stats": alert_stats,
        },
        message="Statistics summary.",
        request_id=request.state.request_id,
    )


# =========================================================================
# ENTRY POINT
# =========================================================================

if __name__ == "__main__":
    print(f"Starting IoT Telemetry API on {HOST}:{PORT}")
    print(f"Swagger UI: http://localhost:{PORT}/docs")
    print(f"Landing page: http://localhost:{PORT}/")
    print(f"n8n target: {N8N_WEBHOOK_URL}")
    uvicorn.run("server:app", host=HOST, port=PORT)
