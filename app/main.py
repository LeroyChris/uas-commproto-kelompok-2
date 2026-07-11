"""
main.py
-------
Entry point aplikasi. Merakit FastAPI app: middleware, router, exception
handler untuk validasi Pydantic (supaya bentuk error tetap konsisten
dengan API Contract), dan menjalankan server lewat uvicorn.

Cara jalan (semua OS - Windows/Linux/macOS):
    pip install -r requirements.txt
    python main.py

Dokumentasi otomatis (Swagger UI): http://localhost:8088/docs
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

import services
from config import Config
from middleware import register_middleware
from n8n_client import forward_to_n8n
from responses import error_response
from routes import router

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"
STATIC_DIR = PROJECT_ROOT / "app" / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="IoT Telemetry API - UAS Communication Protocol",
        description=(
            "REST API untuk Use Case IoT Telemetry Mini. Menerima data sensor, "
            "memvalidasi payload, menyimpan data, forward ke n8n, dan "
            "menyediakan endpoint reliability (rate limiting)."
        ),
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    register_middleware(app)
    app.include_router(router)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def landing_page():
        """Landing page dashboard (bukan JSON)."""
        index_file = TEMPLATES_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "Landing page belum dibuat. Lihat /docs untuk Swagger UI."}

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """
        Exception handler untuk Pydantic validation errors.
        Mencatat payload yang gagal ke rejected.json dan meneruskannya
        ke n8n (background) dengan status "rejected" supaya n8n punya
        Execution untuk branch failure.
        """
        request_id = getattr(request.state, "request_id", "unknown")

        try:
            raw_body = await request.json()
        except Exception:
            raw_body = None

        first_error = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(loc) for loc in first_error.get("loc", []) if loc != "body")
        error_message = f"{field}: {first_error.get('msg', 'invalid payload')}" if field else "Invalid payload."

        rejected_record = services.record_rejected_payload(
            raw_body=raw_body,
            error_code="VALIDATION_ERROR",
            error_message=error_message,
            request_id=request_id,
        )

        response = error_response(
            message=error_message,
            error_code="VALIDATION_ERROR",
            request_id=request_id,
            status_code=422,
        )
        # Forward ke n8n di background supaya client tidak nunggu
        response.background = BackgroundTask(forward_to_n8n, rejected_record, request_id)
        return response

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    print(f"IoT Telemetry API running on http://{Config.HOST}:{Config.PORT}")
    print(f"Swagger UI              : http://localhost:{Config.PORT}/docs")
    print(f"Landing page            : http://localhost:{Config.PORT}/")
    print(f"n8n webhook target      : {Config.N8N_WEBHOOK_URL}")

    uvicorn.run("main:app", host=Config.HOST, port=Config.PORT, reload=Config.RELOAD)
