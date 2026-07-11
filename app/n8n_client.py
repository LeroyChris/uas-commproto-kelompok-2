"""
n8n_client.py
-------------
Mengirim (forward) data telemetry yang sudah tersimpan ke webhook n8n.
Dipisah dari services.py supaya business logic inti (simpan data,
tentukan alert) tidak bercampur dengan detail komunikasi HTTP ke n8n.

n8n bersifat opsional (nilai tambah) - kalau n8n belum jalan, forward
akan gagal dengan aman (di-log sebagai warning), REST API tetap
berfungsi penuh tanpa n8n.
"""

from typing import Any, Dict, Optional

import httpx

from config import Config
from logger import log_event


async def forward_to_n8n(record: Dict[str, Any], request_id: str) -> Optional[Dict[str, Any]]:
    """
    Forward record ke n8n webhook. Return response JSON dari n8n atau None.
    None artinya n8n unreachable / timeout — server tetap jalan.
    """
    try:
        async with httpx.AsyncClient(timeout=Config.N8N_FORWARD_TIMEOUT_SECONDS) as client:
            response = await client.post(Config.N8N_WEBHOOK_URL, json=record)
            log_event(request_id, f"n8n forward: HTTP {response.status_code}")
            if response.status_code == 200:
                return response.json()
    except httpx.RequestError as exc:
        log_event(request_id, f"n8n unreachable: {exc}", level="warning")
    return None
