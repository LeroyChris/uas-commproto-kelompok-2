# UAS Communication Protocol — Kelompok 2

**Kelas:** Sains Data Reguler

**Tugas yang Dikerjakan:**

| No | Tugas | Jenis | Stack |
|----|-------|------|-------|
| A | REST API Telemetry (FastAPI) | Utama | FastAPI + Pydantic |
| B | Mock Sensor CLI | Tambahan | Python script |
| C | n8n Workflow Integration | Tambahan | n8n + Docker |


---

## Anggota Kelompok & Role

| No | Nama | NIM | Role (sesuai soal) | Kontribusi |
|----|------|-----|-------------------|------------|
| 1 | Zahir Ali Izzaturrahman | 25110500021 | Role 1 — API & Postman Tester | Desain endpoint REST API, Postman Collection, request success & error scenario, mock sensor script |
| 2 | Enrico Lazuardi | 25110500027 | Role 2 — Protocol & Traffic Analyst | Observasi Wireshark, analisis HTTP header/payload, protocol flow, landing page dashboard |
| 3 | Stepanus Teo | 25110500013 | Role 3 — Integration/Workflow Engineer | n8n workflow (webhook, alert, device summary), Docker integration, diagram flow, execution evidence |
| 4 | Leroy Christopher Gerson | 25110500025 | Role 4 — Documentation & Presenter Lead | README, laporan PDF/DOCX, PPT, folder evidence, narasi presentasi, architecture & data flow diagram |

---

## Arsitektur Sistem

```text
┌──────────┐      REST/JSON      ┌──────────┐     HTTP POST      ┌──────────┐
│  Postman │ ──────────────────> │ FastAPI  │ ──────────────────> │   n8n    │
│  / Mock  │     POST /api/      │  Server  │    /webhook/iot-    │  Docker  │
│  Sensor  │     telemetry       │ :8088    │    telemetry        │  :5678   │
└──────────┘ <────────────────── └──────────┘                     └──────────┘
                201 / 422 JSON         │  ↑                          │
                                       │  │                          │
                                       ▼  │                          ▼
                                 ┌────────────┐              ┌──────────────┐
                                 │  JSON Files │              │  Execution    │
                                 │ telemetry   │              │  History      │
                                 │ rejected    │              │  + Callback   │
                                 │ alert_stats │              └──────┬───────┘
                                 │ device_stats│                     │
                                 └─────────────┘          POST /api/n8n/alert-stats
                                                         POST /api/n8n/device-summary
                                                                 │
                                                                 ▼
                                                          ┌──────────────┐
                                                          │ Landing Page │
                                                          │ Dashboard UI │
                                                          └──────────────┘
```

### Alur Komunikasi Protocol

1. **Postman/Mock Sensor → Server** : REST/JSON (POST /api/telemetry)
2. **Server → n8n** : HTTP POST (webhook /iot-telemetry)
3. **n8n → Server** : REST/JSON (POST /api/n8n/alert-stats, /api/n8n/device-summary)
4. **Server → Client** : REST/JSON (response 201/422/200)
5. **Browser → Server** : REST/JSON (GET /api/stats, /api/telemetry/device-summary)

**Error path:** Kalau server mati, n8n mendeteksi lewat `IF Backend Reachable` → response failure 502.

---

## Cara Menjalankan (Cross-Platform)

### Prasyarat
- **Python 3.10+** — cek dengan `python --version`
- **pip** — biasanya sudah termasuk di Python
- **Docker Engine** (hanya untuk n8n, opsional)
- **Postman** (opsional, untuk testing manual)
- **Git** (untuk clone repo)

### 0. Instalasi (Pertama Kali)

```bash
# Clone repo
git clone <url-repo> && cd uas-commproto-kelompok-2

# Buat virtual environment
python -m venv .venv

# Aktifkan virtual environment
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r app/requirements.txt
```

### 1. REST API Backend

```bash
python manage.py backend
```

Atau manual:
```bash
cd app
pip install -r requirements.txt
python main.py
```

Server berjalan di **http://localhost:8088** (port mengikuti standar dosen)
- Landing page: http://localhost:8088/
- Swagger UI: http://localhost:8088/docs

### 2. Mock Sensor

```bash
# Kirim payload valid (normal, warning, critical)
python manage.py sensor valid

# Kirim payload invalid (field hilang, tipe salah → 422)
python manage.py sensor invalid

# Kirim banyak request ke endpoint rate-limit (5x 200 → 3x 429)
python manage.py sensor stress
```

### 3. n8n Workflow

```bash
# Start n8n
python manage.py n8n start

# Dashboard: http://localhost:5678
# Import n8n/workflow.json → Activate

# Lihat log n8n real-time
python manage.py n8n logs

# Stop n8n
python manage.py n8n stop
```

### 4. Testing via Postman

1. Buka Postman
2. Import `postman/collection.json` dan `postman/environment.json`
3. Pilih environment **"IoT Telemetry Mini - Local"**
4. Jalankan request sesuai folder

### 5. Testing via curl (Tanpa Postman)

```bash
# Kirim data sensor valid → expect 201
curl -X POST http://localhost:8088/api/telemetry \
  -H "Content-Type: application/json" \
  -d '{"device_id":"sensor-01","temperature":28.5,"humidity":55,"location":"Lab Sains Data"}'

# Kirim data invalid (tanpa humidity) → expect 422
curl -X POST http://localhost:8088/api/telemetry \
  -H "Content-Type: application/json" \
  -d '{"device_id":"sensor-01","temperature":28.5}'

# Cek server hidup → expect 200
curl http://localhost:8088/api/health

# Lihat data terbaru
curl http://localhost:8088/api/telemetry/latest

# Lihat semua histori
curl http://localhost:8088/api/telemetry/history

# Lihat statistik
curl http://localhost:8088/api/stats

# Test rate-limit (jalankan berulang, setelah 5x → 429)
curl http://localhost:8088/api/reliability/rate-limit
```

---

## API Endpoints

| Method | Path | Status | Deskripsi |
|---|---|---|---|
| GET | `/` | 200 | Landing page dashboard |
| GET | `/api/health` | 200 | Cek server hidup |
| POST | `/api/telemetry` | 201/422 | Kirim data sensor |
| GET | `/api/telemetry/latest` | 200/404 | Data terbaru |
| GET | `/api/telemetry/history` | 200 | Semua histori |
| GET | `/api/telemetry/rejected` | 200 | Payload gagal validasi |
| GET | `/api/telemetry/device-summary` | 200 | Ringkasan per-device + n8n enriched |
| GET | `/api/stats` | 200 | Statistik + n8n alert stats |
| POST | `/api/demo/reset` | 200 | Reset semua data |
| GET | `/api/reliability/rate-limit` | 200/429 | Rate limiting server-side |
| GET | `/api/reliability/n8n-rate-limit` | 200/429 | Rate limiting via n8n |
| POST | `/api/n8n/alert-stats` | 200 | n8n → server: alert stats |
| GET | `/api/n8n/alert-stats` | 200 | Baca alert stats n8n |
| POST | `/api/n8n/device-summary` | 200 | n8n → server: device summary |
| POST | `/api/n8n/rate-result` | 200 | n8n → server: rate decision |

### Payload POST /api/telemetry

```json
{
  "device_id": "sensor-iot-01",
  "temperature": 30.5,
  "humidity": 72,
  "location": "Lab Sains Data"
}
```

### Validasi (Pydantic)

| Field | Aturan | Contoh Error |
|---|---|---|
| `device_id` | string, wajib, 1-100 karakter | `device_id: Field required` |
| `temperature` | number, wajib, -50..100 | `temperature: Input should be a valid number` |
| `humidity` | number, wajib, 0..100 | `humidity: Input should be >= 0 and <= 100` |
| `location` | string, opsional, max 200 | - |

### Alert Status

| Suhu | Status |
|---|---|
| `<= 35°C` | `normal` |
| `> 35°C` | `warning` |
| `> 45°C` | `critical` |

### Response Format

**Success (200/201):**
```json
{
  "success": true,
  "message": "Telemetry data received and stored.",
  "data": { ... },
  "meta": {
    "request_id": "req-a1b2c3d4",
    "timestamp": "2026-07-08T10:00:00",
    "processing_time_ms": 12
  }
}
```

**Error (422/400/429):**
```json
{
  "success": false,
  "message": "humidity: Field required",
  "error": { "code": "VALIDATION_ERROR" },
  "meta": {
    "request_id": "req-a1b2c3d4",
    "timestamp": "2026-07-08T10:00:00"
  }
}
```

---

## n8n Workflow

```text
Webhook (POST /webhook/iot-telemetry)
    → HTTP Request Check Backend (GET /api/health via host.docker.internal:8088)
        → IF Backend Reachable?
            ├─ No → Build Failure Response → Respond Failure (502)
            └─ Yes → Normalize Payload
                   → IF Alert Status Normal?
                       ├─ Yes → POST /api/n8n/alert-stats → Build Normal Response → Respond Success
                       └─ No → POST /api/n8n/alert-stats
                             → POST /api/n8n/device-summary
                             → Build Alert Response → Respond Success
```

---

## Observability

Setiap request dicatat di `app/requests.log`:

```text
[req-a1b2c3d4] --> POST /api/telemetry
[req-a1b2c3d4] Telemetry stored: device=sensor-01 temp=38.0 hum=65 alert=warning
[req-a1b2c3d4] n8n forward: HTTP 200
[req-a1b2c3d4] <-- POST /api/telemetry 201 12ms
```

Request ID muncul di:
- Response JSON (`meta.request_id`)
- Response header (`X-Request-ID`)
- Log (`requests.log`)
- n8n execution history

---

## Struktur Folder

```text
uas-commproto-kelompok-2/
├── manage.py               # Launcher cross-platform (Python murni)
├── docker-compose.yml      # n8n container (+ extra_hosts untuk Linux)
├── README.md
├── app/
│   ├── main.py             # Entry point FastAPI (factory pattern)
│   ├── config.py           # Konfigurasi terpusat
│   ├── logger.py           # Logger ke file + console
│   ├── middleware.py       # Request ID, timing, CORS
│   ├── responses.py        # Response helper (success/error)
│   ├── schemas.py          # Pydantic models
│   ├── services.py         # Business logic
│   ├── routes.py           # Semua endpoint
│   ├── storage.py          # File JSON CRUD
│   ├── n8n_client.py       # Forward ke n8n
│   ├── utils.py            # Helper functions
│   ├── requirements.txt    # Python dependencies
│   ├── data/               # JSON storage (auto-generated)
│   ├── templates/          # Landing page HTML
│   └── static/             # CSS + JS
├── mock/
│   └── sensor.py           # Mock sensor (3 mode)
├── n8n/
│   └── workflow.json       # n8n workflow
├── postman/
│   ├── collection.json     # Postman Collection
│   └── environment.json    # Environment variables
├── docs/                   # Laporan, PPT, diagram
├── evidence/               # Screenshot testing
└── reflection/
    └── kontribusi-anggota.md
```

---

## Catatan Penting

- **Port 8088** — mengikuti standar yang digunakan dosen
- **host.docker.internal** — n8n di Docker pake ini buat akses server di host (Linux: `extra_hosts`)
- **0.0.0.0** — server bind di semua interface supaya bisa diakses dari container Docker
- **n8n bersifat opsional** — REST API tetap berfungsi penuh tanpa n8n
- **Data storage** via file JSON — cukup untuk demo dan evidence
- **pathlib.Path** — semua path cross-platform (Windows/Linux/macOS)
- **Tidak ada hardware IoT** — sensor disimulasikan via Postman / mock sensor
