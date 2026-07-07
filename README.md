# IoT Telemetry Mini — UAS Communication Protocol

**Use Case:** IoT Telemetry Mini (REST API + n8n Workflow)

Sebuah REST API untuk menerima data sensor dummy dari IoT device, dengan integrasi workflow otomatis via n8n. Data divalidasi, diklasifikasikan (normal/warning/critical), disimpan, dan diteruskan ke n8n untuk agregasi statistik alert. Dibangun sebagai mini project UAS Communication Protocol — **fokus backend, tanpa IoT fisik**.

---

## Anggota Kelompok

| Nama | NIM | Role | Kontribusi |
|---|---|---|---|
| Anggota 1 | - | API & Postman Tester | - |
| Anggota 2 | - | Protocol & Traffic Analyst | - |
| Anggota 3 | - | Integration/Workflow Engineer | - |
| Anggota 4 | - | Documentation & Presenter Lead | - |

---

## Alasan Memilih REST

1. **Sederhana** — payload JSON mudah dibaca, diuji, dan di-debug.
2. **HTTP status code** memberikan feedback jelas (200/201/400/422/429).
3. **Cocok untuk telemetry periodik** — data sensor dikirim secara periodik (setiap 0.5-5 detik).
4. **Dapat diuji dengan Postman** tanpa hardware IoT fisik.
5. **Mudah diintegrasikan** dengan n8n workflow melalui webhook.
6. **Relevan untuk Sains Data** — REST API banyak dipakai untuk serve ML model dan data pipeline.

---

## Arsitektur Sistem

```text
┌──────────┐      REST/JSON      ┌──────────┐     HTTP POST      ┌──────────┐
│  Postman │ ──────────────────> │  FastAPI  │ ──────────────────> │   n8n    │
│  / Mock  │     POST /api/      │ server.py │    /webhook/iot-    │  Docker  │
│  Sensor  │     telemetry       │           │    telemetry        │          │
└──────────┘ <────────────────── └──────────┘                     └──────────┘
                201 / 422 JSON         │                              │
                                       ▼                              ▼
                                 telemetry.json                n8n Variables
                                 rejected.json                 (alert stats)
                                 requests.log                  (rate counter)
                                       │                              │
                                       ▼                              ▼
                                ┌──────────────┐          ┌──────────────────┐
                                │ Landing Page  │          │ n8n Alert Stats  │
                                │ /api/stats    │          │ /api/n8n/alert-  │
                                │ Dashboard UI  │          │ stats            │
                                └──────────────┘          └──────────────────┘
```

### n8n Purpose (bukan repeater server)

n8n memiliki **peran independen** — bukan sekadar penerus data:

| Role | Server | n8n |
|---|---|---|
| **Telemetry** | Validasi, simpan, log, forward | Klasifikasi alert, akumulasi statistik |
| **Rate Limit** | Counter sederhana (5 max) | Counter via workflow variables (persistent) |
| **Stats** | Total hitung dari storage | Agregasi per status (normal/warning/critical) |

Kalau server mati, n8n tetap ingat data workflow-nya. Kalau n8n mati, server tetap jalan tanpa gangguan.

---

## Cara Menjalankan (Cross-Platform)

### Prasyarat
- **Python 3.10+** (cek: `python --version`)
- **Docker Engine** (hanya untuk n8n, opsional)
- **Postman** (opsional, untuk testing manual)

### 1. REST API Backend

```bash
python manage.py backend
```

Atau manual:

```bash
cd app
pip install -r requirements.txt
python server.py
```

Server berjalan di **http://localhost:8000**

URL penting:
| URL | Fungsi |
|---|---|
| http://localhost:8000/ | Landing page dashboard |
| http://localhost:8000/docs | Swagger UI (dokumentasi API interaktif) |
| http://localhost:8000/redoc | ReDoc (alternatif dokumentasi) |

### 2. Mock Sensor (Terminal terpisah)

```bash
# Kirim payload valid (termasuk suhu warning & critical)
python manage.py sensor valid

# Kirim payload invalid (field hilang, tipe salah)
python manage.py sensor invalid

# Kirim banyak request ke endpoint rate-limit (memicu HTTP 429)
python manage.py sensor stress
```

### 3. n8n Workflow (Opsional — Nilai Tambah)

```bash
# Start n8n (foreground, Ctrl+C to stop)
python manage.py n8n start

# Buka http://localhost:5678
# Buat akun owner (first time only)
# Import n8n/workflow.json
# Klik "Activate"

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

---

## API Endpoints

| Method | Path | Status | Deskripsi | Evidence |
|---|---|---|---|---|
| GET | `/` | 200 | Landing page | Dashboard |
| GET | `/api/health` | 200 | Cek server hidup | Postman screenshot |
| POST | `/api/telemetry` | 201 / 422 | Kirim data sensor | Request/response |
| GET | `/api/telemetry/latest` | 200 / 404 | Data terbaru | Postman screenshot |
| GET | `/api/telemetry/history` | 200 | Semua histori | Postman screenshot |
| GET | `/api/telemetry/rejected` | 200 | Payload gagal validasi | Error path evidence |
| POST | `/api/demo/reset` | 200 | Reset semua data | - |
| GET | `/api/reliability/rate-limit` | 200 / 429 | Rate limiting (5 max) | 200 → 429 transisi |
| GET | `/api/reliability/n8n-rate-limit` | 200 / 429 | Rate limit via n8n | n8n execution |
| POST | `/api/n8n/alert-stats` | 200 | n8n kirim alert stats | n8n → server |
| GET | `/api/n8n/alert-stats` | 200 | Baca alert stats n8n | n8n execution |
| GET | `/api/stats` | 200 | Statistik ringkasan | Landing page data |

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

| Suhu | Status | n8n Alert |
|---|---|---|
| `<= 35°C` | `normal` | ✅ Normal |
| `> 35°C` | `warning` | ⚠️ Warning |
| `> 45°C` | `critical` | 🚨 Critical |

### Response Format

**Success (200/201):**
```json
{
  "success": true,
  "message": "Telemetry data received and stored.",
  "data": { ... },
  "meta": {
    "request_id": "req-a1b2c3d4",
    "timestamp": "2026-07-07T10:00:00",
    "processing_time_ms": 12
  }
}
```

**Error (422/400/429):**
```json
{
  "success": false,
  "message": "humidity: Field required",
  "error": {
    "code": "VALIDATION_ERROR"
  },
  "meta": {
    "request_id": "req-a1b2c3d4",
    "timestamp": "2026-07-07T10:00:00"
  }
}
```

---

## n8n Workflow

```text
Webhook (POST /webhook/iot-telemetry)
    → Process Request (Code node)
        ├── type = "rate_limit"  → hitung counter → allow/block
        └── type = "telemetry"   → threshold check → return alert + stats
    → Respond to Webhook
```

n8n menggunakan **workflow variables** untuk maintain state:
- `rateLimitCounter` — counter rate limit independen
- `alertStats` — agregasi processed, normal, warning, critical

---

## Postman Collection

Collection terbagi dalam 5 folder:

| Folder | Request | Code |
|---|---|---|
| **Health** | GET Health Check | 200 |
| **Telemetry Success** | POST Normal (<=35°C) | 201 |
| | POST Warning (>35°C) | 201 |
| | POST Critical (>45°C) | 201 |
| | GET Latest Telemetry | 200 |
| | GET All Telemetry History | 200 |
| **Telemetry Validation** | POST Missing Humidity (422) | 422 |
| | POST Invalid Temperature Type (422) | 422 |
| | POST Invalid Humidity > 100 (422) | 422 |
| | POST Missing Device ID (422) | 422 |
| | POST Malformed Body (422) | 422 |
| | GET Rejected Payloads | 200 |
| **Reliability** | GET Rate Limit Test | 200 / 429 |
| **Demo** | POST Reset Data | 200 |
| | GET Statistics | 200 |

---

## Struktur Folder

```text
uas-commproto-kelompok-xx/
├── manage.py               # Launcher cross-platform (Python murni)
├── docker-compose.yml      # n8n container
├── README.md
├── app/
│   ├── server.py           # FastAPI — 1 file monolitik
│   ├── requirements.txt    # Python dependencies
│   ├── data/
│   │   ├── telemetry.json  # Data valid (auto-generated)
│   │   ├── rejected.json   # Payload ditolak (auto-generated)
│   │   └── alert_stats.json # n8n alert stats (auto-generated)
│   └── requests.log        # Observability log (auto-generated)
├── templates/
│   └── index.html          # Landing page dashboard
├── static/
│   ├── css/style.css       # Landing page styles
│   └── js/app.js           # Landing page JavaScript
├── mock/
│   └── sensor.py           # Mock sensor (3 mode: valid/invalid/stress)
├── n8n/
│   └── workflow.json       # n8n workflow (threshold + rate limit)
├── postman/
│   ├── collection.json     # Postman Collection (15 request)
│   └── environment.json    # Environment variables
├── docs/                   # Laporan, PPT, diagram
├── evidence/               # Screenshot testing
└── reflection/
    └── kontribusi-anggota.md
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

Request ID juga muncul di:
- Response JSON (`meta.request_id`)
- Response header (`X-Request-ID`)
- Log (`requests.log`)
- n8n execution history

---

## Evidence yang Perlu Dikumpulkan

| Evidence | Cara Mendapatkan |
|---|---|
| Postman success (201) | Screenshot response POST /api/telemetry |
| Postman error (422) | Screenshot response POST missing field |
| Postman rate limit (429) | Collection Runner 8 iterasi |
| Wireshark traffic | Capture loopback interface, filter `tcp.port == 8000` |
| Log observability | Isi `app/requests.log` |
| n8n execution | Screenshot n8n Execution History |
| Architecture diagram | Buat dari pipeline ascii di README |
| Data flow diagram | Adaptasi dari arsitektur di README |

Semua screenshot disimpan di folder `evidence/`.

---

## Catatan Penting

- **Tidak ada hardware IoT** — sensor disimulasikan via Postman / mock sensor.
- **pathlib.Path** digunakan di semua path — kompatibel Windows/Linux/macOS.
- **n8n bersifat opsional** — REST API tetap berfungsi penuh tanpa n8n.
- **Data storage** menggunakan file JSON — cukup untuk demo dan evidence.
- **Pertemuan 16** — live presentasi 7 menit + 3 menit Q&A. Backup video jika waktu tidak cukup.
