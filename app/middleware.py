"""
middleware.py
-------------
Middleware global: Request ID, timing, logging otomatis, dan CORS untuk
SETIAP request tanpa perlu ditulis ulang di setiap endpoint.
"""

import time

from fastapi import FastAPI, Request

from config import Config
from logger import log_request, log_response
from utils import elapsed_ms, new_request_id


def register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_and_logging(request: Request, call_next):
        request_id = new_request_id()
        request.state.request_id = request_id

        log_request(request_id, request.method, request.url.path)
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = elapsed_ms(start, time.perf_counter())
        response.headers[Config.REQUEST_ID_HEADER] = request_id
        response.headers["X-Processing-Time-Ms"] = str(duration_ms)

        log_response(request_id, request.method, request.url.path, response.status_code, duration_ms)
        return response

    @app.middleware("http")
    async def cors_middleware(request: Request, call_next):
        if request.method == "OPTIONS":
            from fastapi.responses import JSONResponse

            response = JSONResponse(content={})
        else:
            response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Request-ID"
        return response

    @app.middleware("http")
    async def no_cache_dashboard_assets(request: Request, call_next):
        """
        Paksa browser selalu ambil ulang halaman dashboard dan asset
        statisnya dari server (no heuristic caching).
        """
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
