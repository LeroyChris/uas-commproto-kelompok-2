const statusDot = document.querySelector('.status-dot');

function pauseApiAnimation() {
  if (statusDot) {
    statusDot.classList.add('paused');
  }
}

function resumeApiAnimation() {
  if (statusDot) {
    statusDot.classList.remove('paused');
  }
}

// ===== Pipeline animation state (Sensor -> FastAPI -> n8n -> Storage) =====
// Aturan:
//  - Saat halaman pertama kali dimuat: animasi tetap berjalan (default CSS).
//  - Saat POST /api/demo/reset sukses -> titik hijau HILANG TOTAL.
//  - Saat ada data sensor baru yang berhasil diproses -> titik hijau muncul lagi.
const pipelineEl = document.getElementById('pipeline');
let lastKnownUpdate = undefined;

function stopPipelineAnimation() {
  if (pipelineEl) {
    pipelineEl.classList.add('idle');
  }
}

function startPipelineAnimation() {
  if (pipelineEl) {
    pipelineEl.classList.remove('idle');
  }
}

async function loadStats() {
  resumeApiAnimation();
  const el = {
    total: document.getElementById('stat-total'),
    rejected: document.getElementById('stat-rejected'),
    rate: document.getElementById('stat-rate'),
    updated: document.getElementById('stat-updated'),
    n8nProcessed: document.getElementById('n8n-processed'),
    n8nWarning: document.getElementById('n8n-warning'),
    n8nCritical: document.getElementById('n8n-critical'),
    n8nNormal: document.getElementById('n8n-normal'),
  };

  try {
    const res = await fetch('/api/stats');
    const body = await res.json();
    if (!body.success) throw new Error('API error');

    const d = body.data;
    el.total.textContent = d.total_telemetry;
    el.rejected.textContent = d.total_rejected;
    el.rate.textContent = d.success_rate + '%';
    el.updated.textContent = d.last_update
      ? new Date(d.last_update).toLocaleString('id-ID')
      : 'No data yet';

    // n8n alert stats
    const s = d.n8n_alert_stats || {};
    el.n8nProcessed.textContent = s.total_processed ?? '0';
    el.n8nWarning.textContent = s.total_warning ?? '0';
    el.n8nCritical.textContent = s.total_critical ?? '0';
    el.n8nNormal.textContent = s.total_normal ?? '0';

    // Deteksi reset dari luar (mis. Postman) — total_telemetry === 0 = baru direset
    if (d.total_telemetry === 0) {
      stopPipelineAnimation();
      lastKnownUpdate = undefined;
    } else if (lastKnownUpdate !== undefined && d.last_update && d.last_update !== lastKnownUpdate) {
      // Data sensor baru masuk -> jalankan lagi animasi pipeline
      startPipelineAnimation();
      lastKnownUpdate = d.last_update;
    } else {
      lastKnownUpdate = d.last_update;
    }
  } catch (err) {
    console.warn('Stats fetch failed:', err);
    ['total', 'rejected', 'rate'].forEach(k => el[k].textContent = '---');
    el.updated.textContent = 'API unreachable';
    el.n8nProcessed.textContent = '---';
    el.n8nWarning.textContent = '---';
    el.n8nCritical.textContent = '---';
    el.n8nNormal.textContent = '---';
    pauseApiAnimation();
  }
}

// Reset demo
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('reset-demo-btn');
  if (btn) {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      pauseApiAnimation();

      btn.textContent = 'Resetting...';
      try {
        const res = await fetch('/api/demo/reset', { method: 'POST' });
        const body = await res.json();
        if (body.success) {
          btn.textContent = '✓ Reset OK';
          // Reset berhasil -> hentikan animasi pipeline
          stopPipelineAnimation();
          lastKnownUpdate = undefined;
          setTimeout(() => {
              loadStats();
              loadDevices();
          }, 1000);
          setTimeout(() => btn.textContent = 'Reset Demo Data', 2000);
        } else {
          btn.textContent = 'Reset failed';
          resumeApiAnimation();
        }
      } catch {
        btn.textContent = 'Reset failed';
        resumeApiAnimation();
      }
    });
  }
});

async function loadDevices() {
  resumeApiAnimation();
  const container = document.getElementById('device-list');
  if (!container) return;

  try {
    const res = await fetch('/api/telemetry/device-summary');
    const body = await res.json();
    if (!body.success) throw new Error('API error');

    const devices = body.data.devices || [];
    container.innerHTML = devices.map(d => {
      const icon = d.latest_alert === 'critical' ? '🚨' : d.latest_alert === 'warning' ? '⚠️' : '✅';
      return `<div class="device-card">
        <div class="device-header">
          <span class="device-icon">${icon}</span>
          <span class="device-id mono">${d.device_id}</span>
        </div>
        <div class="device-summary">${d.summary}</div>
        <div class="device-meta">
          <span>${d.total_readings}x baca</span>
          <span>${d.latest_temperature}°C terakhir</span>
          <span>${d.latest_alert}</span>
        </div>
        ${d.n8n_processed ? `<div class="device-n8n">⚙️ n8n: ${new Date(d.n8n_processed).toLocaleString('id-ID')}</div>` : ''}
      </div>`;
    }).join('');

    if (devices.length === 0) {
      container.innerHTML = '<div class="empty-state">Belum ada device. Kirim data sensor via Postman.</div>';
    }
  } catch (err) {
    container.innerHTML = '<div class="empty-state">Gagal memuat data device.</div>';
    pauseApiAnimation();
  }
}

loadStats();
loadDevices();
setInterval(loadStats, 8000);
setInterval(loadDevices, 10000);
