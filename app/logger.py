"""
logger.py
---------
Logger terpusat untuk observability evidence. Semua log ditulis ke
app/requests.log (untuk screenshot evidence) sekaligus ke console.
"""

import logging

from config import Config

Config.ROOT_DIR.mkdir(parents=True, exist_ok=True)

_logger = logging.getLogger("iot_telemetry")
_logger.setLevel(logging.INFO)
_logger.propagate = False

if not _logger.handlers:
    _file_handler = logging.FileHandler(Config.LOG_FILE, encoding="utf-8")
    _console_handler = logging.StreamHandler()
    _formatter = logging.Formatter("%(message)s")
    _file_handler.setFormatter(_formatter)
    _console_handler.setFormatter(_formatter)
    _logger.addHandler(_file_handler)
    _logger.addHandler(_console_handler)


def log_request(request_id: str, method: str, path: str) -> None:
    _logger.info(f"[{request_id}] --> {method} {path}")


def log_response(request_id: str, method: str, path: str, status_code: int, duration_ms: int) -> None:
    _logger.info(f"[{request_id}] <-- {method} {path} {status_code} {duration_ms}ms")


def log_event(request_id: str, message: str, level: str = "info") -> None:
    getattr(_logger, level, _logger.info)(f"[{request_id}] {message}")
