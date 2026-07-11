# Kontribusi Anggota Kelompok 2

Berdasarkan pembagian peran dari instruksi UAS (Communication Protocol - Sains Data Reguler), berikut adalah laporan kontribusi masing-masing anggota kelompok:

### 1. Zahir Ali Izzaturrahman (25110500021) — Role 1: API & Postman Tester
* **Apa yang dikerjakan:** 
  - Mendesain endpoint REST API untuk *IoT Telemetry Mini* menggunakan FastAPI dan validasi Pydantic.
  - Membuat *mock sensor script* berbasis CLI untuk memudahkan *testing* payload *valid, invalid,* dan *stress test*.
  - Menyusun Postman Collection & Environment yang siap di-*import*.
  - Menjalankan *success scenario* (HTTP 201) dan *error scenario* (HTTP 422) serta mendokumentasikan hasilnya.
* **Kendala:** Memastikan format error 422 dari Pydantic konsisten dengan *API contract* dan menangani *rate-limit testing*.
* **Pelajaran:** Memahami pentingnya struktur JSON yang valid dan respons error yang jelas agar sistem hilir (n8n) atau *client* mengerti bagian mana yang gagal.

### 2. Enrico Lazuardi (25110500027) — Role 2: Protocol & Traffic Analyst
* **Apa yang dikerjakan:** 
  - Melakukan observasi lalu lintas data (traffic) HTTP menggunakan Wireshark.
  - Menganalisis *headers* (`Content-Type`, `X-Request-ID`) dan *payload* JSON saat data dikirim dari Postman ke Backend.
  - Membantu menyusun antarmuka *Dashboard/Landing Page* untuk memonitor status *telemetry*.
* **Kendala:** Memfilter _noise_ jaringan di Wireshark (karena berjalan di localhost/loopback) agar hanya menangkap *traffic* port 8088.
* **Pelajaran:** Bisa melihat langsung bagaimana paket HTTP disusun di layer jaringan, membuktikan bahwa komunikasi REST berjalan di atas TCP, dan pentingnya menyertakan *Correlation ID* untuk *tracing*.

### 3. Stepanus Teo (25110500013) — Role 3: Integration/Workflow Engineer
* **Apa yang dikerjakan:** 
  - Mengonfigurasi dan menjalankan *container* n8n menggunakan Docker.
  - Membangun *workflow automation* di n8n yang menerima *Webhook* dari FastAPI.
  - Membuat logika percabangan di n8n untuk mengevaluasi *Alert Status* (Normal/Warning/Critical) berdasarkan suhu.
  - Menyimpan *execution history* dari n8n sebagai *evidence* bahwa *workflow* berjalan sesuai skenario.
* **Kendala:** Menghubungkan *container* n8n dengan server FastAPI yang berjalan di *host* (menggunakan `host.docker.internal`).
* **Pelajaran:** Memahami pola asinkron menggunakan *Webhook* dan bagaimana *microservices/workflow engine* bisa memisahkan beban komputasi dari API utama.

### 4. Leroy Christopher Gerson (25110500025) — Role 4: Documentation & Presenter Lead
* **Apa yang dikerjakan:** 
  - Bertanggung jawab penuh atas kualitas repositori, struktur folder, dan dokumentasi `README.md`.
  - Membuat *Architecture Canvas* dan *Data Flow Diagram* (*sequence diagram*) secara terstruktur.
  - Menyatukan semua komponen *end-to-end*, mengecek kesesuaian dengan 15+ poin rubrik UAS.
  - Mengumpulkan *evidence* observabilitas (*logging/requests.log*) dan menyusun Laporan final (DOCX & PDF) serta PPT Presentasi.
* **Kendala:** Mengintegrasikan seluruh *evidence* dari anggota lain menjadi satu alur cerita laporan yang kohesif dan analitis.
* **Pelajaran:** Mendapatkan gambaran helikopter (*helicopter view*) tentang arsitektur sistem, pentingnya *observability* (logs), dan bagaimana menyajikan *technical engineering* menjadi sebuah presentasi yang terstruktur.