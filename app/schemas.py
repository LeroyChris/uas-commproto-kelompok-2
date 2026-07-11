"""
schemas.py
----------
Model Pydantic untuk validasi payload dan bentuk response.

Kenapa terpisah dari routes.py:
    Supaya definisi "bentuk data" (schema) tidak bercampur dengan
    "logika endpoint" (routing). Validasi field otomatis dilakukan
    oleh Pydantic berdasarkan type hint dan Field(...) di bawah ini.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class TelemetryPayload(BaseModel):
    """Payload yang dikirim sensor lewat POST /api/telemetry."""

    device_id: str = Field(..., min_length=1, max_length=100, description="ID unik perangkat sensor")
    temperature: float = Field(..., ge=-50, le=100, description="Suhu Celsius, -50..100")
    humidity: float = Field(..., ge=0, le=100, description="Kelembapan persen, 0..100")
    location: Optional[str] = Field(None, max_length=200, description="Lokasi sensor (opsional)")


class AlertStatsPayload(BaseModel):
    """Payload alert stats dari n8n callback."""

    total_processed: int = 0
    total_normal: int = 0
    total_warning: int = 0
    total_critical: int = 0
    last_alert_status: Optional[str] = None
    last_alert_time: Optional[str] = None


class ApiMeta(BaseModel):
    request_id: str
    timestamp: str
    processing_time_ms: Optional[int] = None


class SuccessEnvelope(BaseModel):
    """Bentuk response sukses yang konsisten di semua endpoint."""

    success: bool = True
    message: str
    data: Any
    meta: ApiMeta


class ErrorDetail(BaseModel):
    code: str


class ErrorEnvelope(BaseModel):
    """Bentuk response error yang konsisten di semua endpoint."""

    success: bool = False
    message: str
    error: ErrorDetail
    meta: ApiMeta
