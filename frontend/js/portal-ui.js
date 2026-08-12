/**
 * Shared portal UI helpers — charts & polish only.
 * Does not change API contracts. Safe to load on every portal.
 */
(function (global) {
  const palette = {
    green: '#2D8A62',
    greenSoft: 'rgba(45, 138, 98, 0.18)',
    gold: '#C9A227',
    goldSoft: 'rgba(201, 162, 39, 0.2)',
    cream: '#F3F0E6',
    text: '#64766D',
    danger: '#D94A4A',
    info: '#4A7C9B',
  };

  function ensureChartJs(cb) {
    if (global.Chart) return cb();
    const s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
    s.onload = cb;
    s.onerror = function () { console.warn('Chart.js failed to load'); };
    document.head.appendChild(s);
  }

  function destroyChart(canvas) {
    if (!canvas) return;
    if (canvas._mcChart) {
      try { canvas._mcChart.destroy(); } catch (e) {}
      canvas._mcChart = null;
    }
  }

  function lineChart(canvasId, labels, data, label) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !global.Chart) return;
    destroyChart(canvas);
    canvas._mcChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: label || 'Count',
          data: data,
          borderColor: palette.green,
          backgroundColor: palette.greenSoft,
          fill: true,
          tension: 0.35,
          pointRadius: 3,
          pointBackgroundColor: palette.green,
          borderWidth: 2.5,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#003D2B',
            titleFont: { family: 'Inter' },
            bodyFont: { family: 'Inter' },
            padding: 10,
            cornerRadius: 8,
          },
        },
        scales: {
          x: {
            grid: { color: 'rgba(0,61,43,0.06)' },
            ticks: { color: palette.text, font: { size: 11 } },
          },
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(0,61,43,0.06)' },
            ticks: { color: palette.text, font: { size: 11 }, precision: 0 },
          },
        },
      },
    });
  }

  function doughnutChart(canvasId, labels, data, colors) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !global.Chart) return;
    destroyChart(canvas);
    canvas._mcChart = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: data,
          backgroundColor: colors || [palette.green, palette.gold, palette.info, palette.danger, '#6F8F82'],
          borderWidth: 0,
          hoverOffset: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '68%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: { boxWidth: 10, padding: 14, color: palette.text, font: { size: 11, family: 'Inter' } },
          },
        },
      },
    });
  }

  /** Build last-7-days labels and counts from items with a date field. */
  function weeklyCounts(items, dateField) {
    const days = [];
    const counts = [];
    const map = {};
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setHours(0, 0, 0, 0);
      d.setDate(d.getDate() - i);
      const key = d.toISOString().slice(0, 10);
      map[key] = 0;
      days.push(d.toLocaleDateString(undefined, { weekday: 'short' }));
    }
    (items || []).forEach(function (it) {
      let raw = it[dateField];
      if (!raw && it.created_at) raw = it.created_at;
      if (!raw && it.appointment_date) raw = it.appointment_date;
      if (!raw) return;
      const key = String(raw).slice(0, 10);
      if (key in map) map[key] += 1;
    });
    Object.keys(map).sort().forEach(function (k) { counts.push(map[k]); });
    return { labels: days, data: counts };
  }

  function setGreeting(name) {
    const el = document.getElementById('dashboard-greeting-name');
    if (el && name) el.textContent = name;
    const dateEl = document.getElementById('dashboard-date');
    if (dateEl) {
      dateEl.textContent = new Date().toLocaleDateString(undefined, {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
      });
    }
  }

  global.PortalUI = {
    ensureChartJs: ensureChartJs,
    lineChart: lineChart,
    doughnutChart: doughnutChart,
    weeklyCounts: weeklyCounts,
    setGreeting: setGreeting,
    palette: palette,
  };
})(window);
