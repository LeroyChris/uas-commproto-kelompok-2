"""
responses.py
------------
Pembangun response JSON yang konsisten di seluruh API, sesuai API
Contract di soal UAS:

Success: {success, message, data, meta: {request_id, timestamp, processing_time_ms}}
Error:   {success, message, error: {code}, meta: {request_id, timestamp}}

Semua route WAJIB memakai fungsi di file ini, tidak boleh membangun
dict response secara manual, supaya bentuknya tidak pernah berbeda-beda
antar endpoint.
"""

from typing import Any, Optional

from fastapi.responses import JSONResponse

from utils import now_iso


def success_response(
    data: Any,
    message: str,
    request_id: str,
    processing_time_ms: int = 0,
    status_code: int = 200,
) -> JSONResponse:
    body = {
        "success": True,
        "message": message,
        "data": data,
        "meta": {
            "request_id": request_id,
            "timestamp": now_iso(),
            "processing_time_ms": processing_time_ms,
        },
    }
    return JSONResponse(content=body, status_code=status_code)


def error_response(
    message: str,
    error_code: str,
    request_id: str,
    status_code: int = 400,
    extra: Optional[dict] = None,
) -> JSONResponse:
    error_obj = {"code": error_code}
    if extra:
        error_obj.update(extra)

    body = {
        "success": False,
        "message": message,
        "error": error_obj,
        "meta": {
            "request_id": request_id,
            "timestamp": now_iso(),
        },
    }
    return JSONResponse(content=body, status_code=status_code)
