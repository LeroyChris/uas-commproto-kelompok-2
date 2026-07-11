"""
utils.py
--------
Fungsi bantuan generik yang dipakai lintas file.
"""

import uuid
from datetime import datetime, timezone


def new_request_id() -> str:
    """Format pendek 'req-XXXXXXXX', mudah dibaca saat presentasi/demo."""
    return f"req-{uuid.uuid4().hex[:8]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def elapsed_ms(start_seconds: float, end_seconds: float) -> int:
    return round((end_seconds - start_seconds) * 1000)
