async function loadStats() {
  const el = {
    total: document.getElementById('stat-total'),
    rejected: document.getElementById('stat-rejected'),
    rate: document.getElementById('stat-rate'),
    updated: document.getElementById('stat-updated'),
    n8nProcessed: document.getElementById('n8n-processed'),
    n8nWarning: document.getElementById('n8n-warning'),
    n8nCritical: document.getElementById('n8n-critical'),
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
  } catch (err) {
    console.warn('Stats fetch failed:', err);
    ['total', 'rejected', 'rate'].forEach(k => el[k].textContent = '---');
    el.updated.textContent = 'API unreachable';
    el.n8nProcessed.textContent = '---';
    el.n8nWarning.textContent = '---';
    el.n8nCritical.textContent = '---';
  }
}

// Reset demo
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('reset-demo-btn');
  if (btn) {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      btn.textContent = 'Resetting...';
      try {
        const res = await fetch('/api/demo/reset', { method: 'POST' });
        const body = await res.json();
        if (body.success) {
          btn.textContent = '✓ Reset OK';
          loadStats();
          setTimeout(() => btn.textContent = 'Reset Demo', 2000);
        } else {
          btn.textContent = 'Reset failed';
        }
      } catch {
        btn.textContent = 'Reset failed';
      }
    });
  }
});

async function loadDevices() {
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
  }
}

loadStats();
loadDevices();
setInterval(loadStats, 8000);
setInterval(loadDevices, 10000);
