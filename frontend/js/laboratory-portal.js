/**
 * Laboratory Portal — Lumina Health
 * Roles: lab_technician, admin (and doctor for viewing/creating orders)
 */

let allTests = [];
let queueOrders = [];
let allPatients = [];
let allDoctors = [];
let currentOrderDetail = null;

// ─────────────────────────────────────────────────────────────
// Boot
// ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async function () {
  const isRedirecting = sessionStorage.getItem('auth_redirecting');
  const role = Auth.getRole();

  if (!Auth.isAuthenticated() || !['lab_technician', 'admin', 'doctor'].includes(role)) {
    if (!isRedirecting) {
      sessionStorage.setItem('auth_redirecting', 'true');
      window.location.replace('login.html?redirect=laboratory-portal.html');
    }
    return;
  }
  sessionStorage.removeItem('auth_redirecting');

  if (typeof injectAdminBackButton === 'function') injectAdminBackButton();
  if (typeof setupSessionGuards === 'function') setupSessionGuards();


  if (window.sendFCMTokenToBackend) {
    window.sendFCMTokenToBackend();
  }
  setupNotificationBanner();
  loadUserInfo();
  setupNavigation();

  await Promise.all([loadDirectories(), loadCatalog(true)]);
  loadDashboard();
});

function loadUserInfo() {
  const user = Auth.getUser();
  const box = document.getElementById('user-info');
  if (!user || !box) return;
  document.getElementById('user-name').textContent = user.username || user.sub || 'User';
    const greet = document.getElementById('dashboard-greeting-name');
    if (greet) greet.textContent = user.username || user.name || greet.textContent;
    const dateEl = document.getElementById('dashboard-date');
    if (dateEl) {
      dateEl.textContent = new Date().toLocaleDateString(undefined, {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
      });
    }

  const role = Auth.getRole();
  const labels = {
    lab_technician: 'Lab Technician',
    admin: 'Administrator',
    doctor: 'Doctor',
  };
  document.getElementById('user-role').textContent = labels[role] || role || 'Staff';
  box.style.display = 'block';
}

function setupNotificationBanner() {
  const banner = document.getElementById('notif-permission-banner');
  if (!banner) return;
  const dismissed = sessionStorage.getItem('lp_notif_banner_dismissed');
  const canAsk = ('Notification' in window) && Notification.permission === 'default';
  if (canAsk && !dismissed) banner.style.display = 'flex';

  document.getElementById('notif-enable-btn')?.addEventListener('click', async () => {
    if (window.enableNotifications) await window.enableNotifications();
    banner.style.display = 'none';
  });
  document.getElementById('notif-dismiss-btn')?.addEventListener('click', () => {
    sessionStorage.setItem('lp_notif_banner_dismissed', 'true');
    banner.style.display = 'none';
  });
}

function setupNavigation() {
  document.querySelectorAll('.sidebar-link').forEach(link => {
    link.addEventListener('click', (e) => {
      // Real navigation links (e.g. Back to Admin Portal) have no data-page
      if (!link.dataset.page || link.dataset.external) {
        return;
      }
      e.preventDefault();
      showPage(link.dataset.page);
    });
  });
}

function showPage(pageName) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
  const page = document.getElementById('page-' + pageName);
  if (page) page.classList.add('active');
  const link = document.querySelector(`.sidebar-link[data-page="${pageName}"]`);
  if (link) link.classList.add('active');

  if (pageName === 'dashboard') loadDashboard();
  else if (pageName === 'queue') loadQueue();
  else if (pageName === 'catalog') loadCatalog();
  else if (pageName === 'orders') loadAllOrders();
  else if (pageName === 'walkin') loadWalkInLabPage();
}

// ─────────────────────────────────────────────────────────────
// Directories
// ─────────────────────────────────────────────────────────────
let allAppointments = [];

async function loadDirectories() {
  try {
    const [patients, doctors, appointments] = await Promise.all([
      API.get('/patients/').catch((e) => { console.warn('patients', e); return []; }),
      API.get('/doctors/').catch((e) => { console.warn('doctors', e); return []; }),
      API.get('/appointments/').catch((e) => { console.warn('appointments', e); return []; }),
    ]);
    allPatients = Array.isArray(patients) ? patients : (patients?.data || []);
    allDoctors = Array.isArray(doctors) ? doctors : (doctors?.data || []);
    allAppointments = Array.isArray(appointments) ? appointments : (appointments?.data || []);
  } catch (e) {
    console.error('Failed to load directories', e);
  }
}

// ─────────────────────────────────────────────────────────────
// Dashboard
// ─────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const [queueRes, allRes] = await Promise.all([
      API.get('/laboratory/orders/queue'),
      API.get('/laboratory/orders'),
    ]);
    const queue = unwrapList(queueRes);
    const all = unwrapList(allRes);
    queueOrders = queue;

    const pending = queue.filter(o => o.status === 'pending').length;
    const sample = queue.filter(o => o.status === 'sample_collected').length;
    const processing = queue.filter(o => o.status === 'processing').length;
    const completed = all.filter(o => o.status === 'completed').length;

    document.getElementById('stat-pending').textContent = pending;
    document.getElementById('stat-sample').textContent = sample;
    document.getElementById('stat-processing').textContent = processing;
    document.getElementById('stat-completed').textContent = completed;

    if (window.PortalUI) {
      PortalUI.ensureChartJs(function () {
        const orders = typeof all !== 'undefined' ? all : (typeof queue !== 'undefined' ? queue : []);
        const weekly = PortalUI.weeklyCounts(orders, 'created_at');
        PortalUI.lineChart('portal-trend-chart', weekly.labels, weekly.data, 'Lab orders');
        PortalUI.doughnutChart(
          'portal-status-chart',
          ['Pending', 'Sample', 'Processing', 'Completed'],
          [pending || 0, sample || 0, processing || 0, completed || 0]
        );
      });
    }

    const badge = document.getElementById('queue-count-badge');
    if (queue.length) {
      badge.style.display = 'inline-flex';
      badge.textContent = queue.length;
    } else {
      badge.style.display = 'none';
    }

    renderOrderCards('dashboard-queue-list', queue.slice(0, 8), true);
  } catch (e) {
    console.error(e);
    document.getElementById('dashboard-queue-list').innerHTML =
      `<div class="empty-state">Failed to load dashboard: ${e.message || e}</div>`;
  }
}

// ─────────────────────────────────────────────────────────────
// Queue / Orders list
// ─────────────────────────────────────────────────────────────
async function loadQueue() {
  const el = document.getElementById('queue-list');
  el.innerHTML = '<div class="loading-spinner">Loading queue...</div>';
  try {
    const res = await API.get('/laboratory/orders/queue');
    queueOrders = unwrapList(res);
    const badge = document.getElementById('queue-count-badge');
    if (queueOrders.length) {
      badge.style.display = 'inline-flex';
      badge.textContent = queueOrders.length;
    } else badge.style.display = 'none';
    renderOrderCards('queue-list', queueOrders, true);
  } catch (e) {
    el.innerHTML = `<div class="empty-state">Failed to load queue: ${e.message || e}</div>`;
  }
}

async function loadAllOrders() {
  const el = document.getElementById('all-orders-list');
  el.innerHTML = '<div class="loading-spinner">Loading...</div>';
  const status = document.getElementById('orders-status-filter')?.value || '';
  try {
    const q = status ? `?status=${encodeURIComponent(status)}` : '';
    const res = await API.get('/laboratory/orders' + q);
    renderOrderCards('all-orders-list', unwrapList(res), false);
  } catch (e) {
    el.innerHTML = `<div class="empty-state">Failed to load orders: ${e.message || e}</div>`;
  }
}

function renderOrderCards(containerId, orders, showActions) {
  const el = document.getElementById(containerId);
  if (!orders || !orders.length) {
    el.innerHTML = '<div class="empty-state">No orders to show.</div>';
    return;
  }

  el.innerHTML = orders.map(o => {
    const statusCls = statusBadgeClass(o.status);
    const tests = (o.results || []).map(r => r.test_name || r.test_code || ('Test #' + r.lab_test_id)).join(', ');
    const source = o.source === 'ipd'
      ? `<span class="badge badge-info">IPD${o.ward_bed_label ? ' · ' + escapeHtml(o.ward_bed_label) : ''}</span>`
      : `<span class="badge">OPD</span>`;
    const priority = o.priority && o.priority !== 'routine'
      ? `<span class="badge badge-warning">${escapeHtml(o.priority.toUpperCase())}</span>`
      : '';

    let actions = `<button class="btn btn-ghost btn-sm" onclick="openOrderDetail(${o.id})">Open</button>`;
    if (showActions) {
      if (o.status === 'pending') {
        actions += ` <button class="btn btn-primary btn-sm" onclick="collectSample(${o.id})">Collect Sample</button>`;
      } else if (o.status === 'sample_collected' || o.status === 'processing') {
        actions += ` <button class="btn btn-primary btn-sm" onclick="openOrderDetail(${o.id})">Enter Results</button>`;
      } else if (o.status === 'completed') {
        actions += ` <button class="btn btn-primary btn-sm" onclick="viewLabReport(${o.id})">View Report</button>`;
        actions += ` <button class="btn btn-ghost btn-sm" onclick="downloadLabReportFile(${o.id})">Download</button>`;
        actions += ` <button class="btn btn-ghost btn-sm" onclick="openOrderDetail(${o.id})">Details</button>`;
      }
    }

    return `
      <div class="list-item" style="align-items:flex-start;">
        <div style="flex:1;">
          <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:4px;">
            <strong>#${o.id}</strong>
            <span class="badge ${statusCls}">${formatStatus(o.status)}</span>
            ${priority}
            ${source}
          </div>
          <div style="font-size:14px;">${escapeHtml(o.patient_name || 'Patient #' + o.patient_id)}</div>
          <div style="font-size:13px; color:var(--text-light); margin-top:2px;">
            Dr. ${escapeHtml(o.doctor_name || String(o.ordered_by_doctor_id))}
            ${tests ? ' · ' + escapeHtml(tests) : ''}
          </div>
          <div style="font-size:12px; color:var(--text-light); margin-top:4px;">
            Ordered ${formatDateTime(o.created_at)}
          </div>
        </div>
        <div style="display:flex; gap:6px; flex-wrap:wrap;">${actions}</div>
      </div>`;
  }).join('');
}

// ─────────────────────────────────────────────────────────────
// Order detail + results entry
// ─────────────────────────────────────────────────────────────
async function openOrderDetail(orderId) {
  const body = document.getElementById('order-modal-body');
  const footer = document.getElementById('order-modal-footer');
  document.getElementById('order-modal-title').textContent = `Lab Order #${orderId}`;
  body.innerHTML = '<div class="loading-spinner">Loading...</div>';
  footer.innerHTML = '<button class="btn btn-ghost" onclick="closeOrderModal()">Close</button>';
  document.getElementById('order-modal').classList.add('active');

  try {
    const res = await API.get(`/laboratory/orders/${orderId}`);
    const order = unwrapOne(res);
    currentOrderDetail = order;
    renderOrderDetail(order);
  } catch (e) {
    body.innerHTML = `<div class="empty-state">${e.message || e}</div>`;
  }
}

function renderOrderDetail(order) {
  const body = document.getElementById('order-modal-body');
  const footer = document.getElementById('order-modal-footer');
  const canEnter = ['sample_collected', 'processing', 'pending'].includes(order.status);
  const canComplete = ['sample_collected', 'processing'].includes(order.status);
  const canCollect = order.status === 'pending';

  let resultsHtml = (order.results || []).map(r => {
    const abnormal = r.is_abnormal ? '<span class="badge badge-danger">Abnormal</span>' : '';
    if (canEnter && order.status !== 'completed' && order.status !== 'cancelled') {
      return `
        <div class="card" style="margin-bottom:12px; padding:14px;" data-result-id="${r.id}">
          <div style="display:flex; justify-content:space-between; gap:8px; margin-bottom:8px;">
            <div>
              <strong>${escapeHtml(r.test_name || 'Test')}</strong>
              ${r.test_code ? `<span class="badge">${escapeHtml(r.test_code)}</span>` : ''}
              ${abnormal}
            </div>
            <span class="badge ${r.status === 'pending' ? 'badge-warning' : 'badge-success'}">${r.status}</span>
          </div>
          <div style="font-size:12px; color:var(--text-light); margin-bottom:8px;">
            Sample: ${escapeHtml(r.sample_type || '—')}
            ${r.normal_range_text ? ' · Normal: ' + escapeHtml(r.normal_range_text) : ''}
          </div>
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">Numeric value</label>
              <input type="number" step="any" class="form-input result-numeric" value="${r.value_numeric ?? ''}" placeholder="Optional">
            </div>
            <div class="form-group">
              <label class="form-label">Text value</label>
              <input type="text" class="form-input result-text" value="${escapeAttr(r.value_text || '')}" placeholder="Optional">
            </div>
            <div class="form-group">
              <label class="form-label">Unit</label>
              <input type="text" class="form-input result-unit" value="${escapeAttr(r.unit || '')}">
            </div>
            <div class="form-group">
              <label class="form-label">Abnormal?</label>
              <select class="form-select result-abnormal">
                <option value="false" ${!r.is_abnormal ? 'selected' : ''}>No</option>
                <option value="true" ${r.is_abnormal ? 'selected' : ''}>Yes</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Remarks</label>
            <input type="text" class="form-input result-remarks" value="${escapeAttr(r.remarks || '')}">
          </div>
          <button class="btn btn-primary btn-sm" onclick="saveResult(${r.id}, this)">Save Result</button>
        </div>`;
    }

    // Read-only view
    const val = r.value_numeric != null ? r.value_numeric : (r.value_text || '—');
    return `
      <div class="list-item" style="flex-direction:column; align-items:stretch;">
        <div style="display:flex; justify-content:space-between; gap:8px;">
          <div>
            <strong>${escapeHtml(r.test_name || 'Test')}</strong>
            ${r.test_code ? `<span class="badge">${escapeHtml(r.test_code)}</span>` : ''}
            ${abnormal}
          </div>
          <span class="badge ${r.status === 'verified' || r.status === 'entered' ? 'badge-success' : 'badge-warning'}">${r.status}</span>
        </div>
        <div style="margin-top:6px; font-size:15px;">
          <strong>${escapeHtml(String(val))}</strong> ${escapeHtml(r.unit || '')}
        </div>
        ${r.normal_range_text ? `<div style="font-size:12px; color:var(--text-light);">Normal: ${escapeHtml(r.normal_range_text)}</div>` : ''}
        ${r.remarks ? `<div style="font-size:13px; margin-top:4px;">${escapeHtml(r.remarks)}</div>` : ''}
      </div>`;
  }).join('') || '<div class="empty-state">No tests on this order.</div>';

  body.innerHTML = `
    <div style="margin-bottom:16px;">
      <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:8px;">
        <span class="badge ${statusBadgeClass(order.status)}">${formatStatus(order.status)}</span>
        <span class="badge">${escapeHtml((order.priority || 'routine').toUpperCase())}</span>
        <span class="badge">${order.source === 'ipd' ? 'IPD' : 'OPD'}</span>
      </div>
      <div><strong>Patient:</strong> ${escapeHtml(order.patient_name || '#' + order.patient_id)}</div>
      <div><strong>Doctor:</strong> ${escapeHtml(order.doctor_name || String(order.ordered_by_doctor_id))}</div>
      ${order.ward_bed_label ? `<div><strong>Location:</strong> ${escapeHtml(order.ward_bed_label)}</div>` : ''}
      ${order.clinical_notes ? `<div style="margin-top:6px;"><strong>Notes:</strong> ${escapeHtml(order.clinical_notes)}</div>` : ''}
      <div style="font-size:12px; color:var(--text-light); margin-top:6px;">Ordered ${formatDateTime(order.created_at)}</div>
    </div>
    <h3 style="font-size:16px; margin-bottom:10px;">Results</h3>
    ${resultsHtml}
  `;

  let footerBtns = '<button class="btn btn-ghost" onclick="closeOrderModal()">Close</button>';
  if (order.status === 'completed') {
    footerBtns += ` <button class="btn btn-primary" onclick="viewLabReport(${order.id})">View Formal Report</button>`;
  }
  if (canCollect) {
    footerBtns += ` <button class="btn btn-primary" onclick="collectSample(${order.id})">Mark Sample Collected</button>`;
  }
  if (canComplete) {
    footerBtns += ` <button class="btn btn-primary" onclick="completeOrder(${order.id})">Complete &amp; Verify</button>`;
  }
  if (order.status !== 'completed' && order.status !== 'cancelled') {
    footerBtns += ` <button class="btn btn-ghost" style="color:var(--danger,#b91c1c);" onclick="cancelOrder(${order.id})">Cancel Order</button>`;
  }
  footer.innerHTML = footerBtns;
}

function closeOrderModal() {
  document.getElementById('order-modal').classList.remove('active');
  currentOrderDetail = null;
}

async function collectSample(orderId) {
  if (!confirm('Mark sample as collected for this order?')) return;
  try {
    await API.post(`/laboratory/orders/${orderId}/collect-sample`, {});
    toast('Sample collected');
    await openOrderDetail(orderId);
    loadQueue();
    loadDashboard();
  } catch (e) {
    alert(e.message || e);
  }
}

async function saveResult(resultId, btn) {
  const card = btn.closest('[data-result-id]');
  if (!card) return;
  const payload = {
    value_numeric: parseOptionalNumber(card.querySelector('.result-numeric')?.value),
    value_text: card.querySelector('.result-text')?.value || null,
    unit: card.querySelector('.result-unit')?.value || null,
    is_abnormal: card.querySelector('.result-abnormal')?.value === 'true',
    remarks: card.querySelector('.result-remarks')?.value || null,
  };
  btn.disabled = true;
  try {
    await API.patch(`/laboratory/results/${resultId}`, payload);
    toast('Result saved');
    if (currentOrderDetail) await openOrderDetail(currentOrderDetail.id);
  } catch (e) {
    alert(e.message || e);
  } finally {
    btn.disabled = false;
  }
}

async function completeOrder(orderId) {
  if (!confirm('Complete this order and verify all entered results?')) return;
  try {
    await API.post(`/laboratory/orders/${orderId}/complete`, {});
    toast('Order completed — notifications sent');
    await openOrderDetail(orderId);
    loadQueue();
    loadDashboard();
  } catch (e) {
    alert(e.message || e);
  }
}

async function cancelOrder(orderId) {
  if (!confirm('Cancel this lab order? The doctor and patient will be notified so a new request can be made if needed.')) return;
  try {
    await API.post(`/laboratory/orders/${orderId}/cancel`, {});
    toast('Order cancelled — doctor/patient alerted');
    closeOrderModal();
    loadQueue();
    loadAllOrders();
    loadDashboard();
  } catch (e) {
    alert(e.message || e);
  }
}

// ─────────────────────────────────────────────────────────────
// Catalog
// ─────────────────────────────────────────────────────────────
async function loadCatalog(silent) {
  const el = document.getElementById('catalog-list');
  if (!silent && el) el.innerHTML = '<div class="loading-spinner">Loading catalog...</div>';
  try {
    const res = await API.get('/laboratory/tests');
    allTests = unwrapList(res);
    if (el) renderCatalog(allTests);
  } catch (e) {
    if (el) el.innerHTML = `<div class="empty-state">${e.message || e}</div>`;
  }
}

function renderCatalog(tests) {
  const el = document.getElementById('catalog-list');
  if (!tests.length) {
    el.innerHTML = '<div class="empty-state">No lab tests in catalog yet. Add one above.</div>';
    return;
  }
  el.innerHTML = `
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Name</th><th>Code</th><th>Category</th><th>Sample</th>
            <th>Unit</th><th>Normal</th><th>Price</th><th>Active</th><th></th>
          </tr>
        </thead>
        <tbody>
          ${tests.map(t => `
            <tr>
              <td><strong>${escapeHtml(t.name)}</strong></td>
              <td>${escapeHtml(t.code || '—')}</td>
              <td>${escapeHtml(t.category)}</td>
              <td>${escapeHtml(t.sample_type)}</td>
              <td>${escapeHtml(t.unit || '—')}</td>
              <td>${escapeHtml(t.normal_range_text || rangeText(t))}</td>
              <td>${t.price != null ? t.price : '—'}</td>
              <td>${t.is_active ? '<span class="badge badge-success">Yes</span>' : '<span class="badge">No</span>'}</td>
              <td><button class="btn btn-ghost btn-sm" onclick="editTest(${t.id})">Edit</button></td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

function rangeText(t) {
  if (t.normal_range_min != null && t.normal_range_max != null) {
    return `${t.normal_range_min} – ${t.normal_range_max}`;
  }
  return '—';
}

function editTest(id) {
  const t = allTests.find(x => x.id === id);
  if (!t) return;
  document.getElementById('test-edit-id').value = t.id;
  document.getElementById('test-name').value = t.name || '';
  document.getElementById('test-code').value = t.code || '';
  document.getElementById('test-category').value = t.category || 'other';
  document.getElementById('test-sample-type').value = t.sample_type || 'blood';
  document.getElementById('test-unit').value = t.unit || '';
  document.getElementById('test-range-min').value = t.normal_range_min ?? '';
  document.getElementById('test-range-max').value = t.normal_range_max ?? '';
  document.getElementById('test-range-text').value = t.normal_range_text || '';
  document.getElementById('test-price').value = t.price ?? 0;
  document.getElementById('test-turnaround').value = t.turnaround_hours ?? 24;
  document.getElementById('test-description').value = t.description || '';
  document.getElementById('test-form-title').textContent = 'Edit Lab Test';
  document.getElementById('test-submit-btn').textContent = 'Save Changes';
  document.getElementById('test-cancel-btn').style.display = 'inline-flex';
  showPage('catalog');
  document.getElementById('test-form').scrollIntoView({ behavior: 'smooth' });
}

function resetTestForm() {
  document.getElementById('test-form').reset();
  document.getElementById('test-edit-id').value = '';
  document.getElementById('test-form-title').textContent = 'Add Lab Test';
  document.getElementById('test-submit-btn').textContent = 'Add Test';
  document.getElementById('test-cancel-btn').style.display = 'none';
}

async function submitTestForm(e) {
  e.preventDefault();
  const editId = document.getElementById('test-edit-id').value;
  const payload = {
    name: document.getElementById('test-name').value.trim(),
    code: document.getElementById('test-code').value.trim() || null,
    category: document.getElementById('test-category').value,
    sample_type: document.getElementById('test-sample-type').value,
    unit: document.getElementById('test-unit').value.trim() || null,
    normal_range_min: parseOptionalNumber(document.getElementById('test-range-min').value),
    normal_range_max: parseOptionalNumber(document.getElementById('test-range-max').value),
    normal_range_text: document.getElementById('test-range-text').value.trim() || null,
    price: parseOptionalNumber(document.getElementById('test-price').value) ?? 0,
    turnaround_hours: parseInt(document.getElementById('test-turnaround').value, 10) || 24,
    description: document.getElementById('test-description').value.trim() || null,
  };
  try {
    if (editId) {
      await API.patch(`/laboratory/tests/${editId}`, payload);
      toast('Test updated');
    } else {
      await API.post('/laboratory/tests', payload);
      toast('Test added');
    }
    resetTestForm();
    await loadCatalog();
  } catch (err) {
    alert(err.message || err);
  }
}

// ─────────────────────────────────────────────────────────────
// New Order
// ─────────────────────────────────────────────────────────────
function prepareNewOrderForm() {
  const pSel = document.getElementById('order-patient');
  const dSel = document.getElementById('order-doctor');

  dSel.innerHTML = '<option value="">Select doctor first...</option>' +
    allDoctors.map(d => `<option value="${d.id}">${escapeHtml(d.full_name)} — ${escapeHtml(d.specialization || '')}</option>`).join('');

  // Reset patient list until a doctor is chosen
  pSel.innerHTML = '<option value="">Select a doctor to load patients...</option>';
  pSel.disabled = true;

  dSel.onchange = () => populatePatientsForDoctor(dSel.value);

  // If a doctor was already selected, refresh patients
  if (dSel.value) populatePatientsForDoctor(dSel.value);

  const box = document.getElementById('order-tests-checklist');
  const active = allTests.filter(t => t.is_active !== false);
  if (!active.length) {
    box.innerHTML = '<div class="empty-state">No active tests in catalog. Add tests first.</div>';
    return;
  }
  box.innerHTML = active.map(t => `
    <label style="display:flex; gap:8px; align-items:flex-start; font-size:14px; padding:6px 8px; border-radius:8px; background:var(--bg-soft, rgba(0,0,0,0.03));">
      <input type="checkbox" name="order-test" value="${t.id}" style="margin-top:3px;">
      <span>
        <strong>${escapeHtml(t.name)}</strong>
        ${t.code ? `<span class="badge">${escapeHtml(t.code)}</span>` : ''}
        <div style="font-size:12px; color:var(--text-light);">${escapeHtml(t.category)} · ${escapeHtml(t.sample_type)}</div>
      </span>
    </label>`).join('');
}

function populatePatientsForDoctor(doctorId) {
  const pSel = document.getElementById('order-patient');
  if (!pSel) return;

  if (!doctorId) {
    pSel.innerHTML = '<option value="">Select a doctor to load patients...</option>';
    pSel.disabled = true;
    return;
  }

  const docId = Number(doctorId);
  // Patients who have (or had) an appointment with this doctor
  const patientIds = new Set(
    (allAppointments || [])
      .filter(a => Number(a.doctor_id) === docId)
      .map(a => Number(a.patient_id))
  );

  let list = (allPatients || []).filter(p => patientIds.has(Number(p.id)));

  // Fallback: if no appointments found, show full patient list so lab can still order
  if (!list.length && (allPatients || []).length) {
    list = allPatients.slice();
  }

  if (!list.length) {
    pSel.innerHTML = '<option value="">No patients found for this doctor</option>';
    pSel.disabled = true;
    return;
  }

  pSel.disabled = false;
  pSel.innerHTML = '<option value="">Select patient...</option>' +
    list
      .slice()
      .sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')))
      .map(p => `<option value="${p.id}">${escapeHtml(p.name)} (${escapeHtml(p.phone || '')})</option>`)
      .join('');
}

async function submitOrderForm(e) {
  e.preventDefault();
  const patientId = parseInt(document.getElementById('order-patient').value, 10);
  const doctorId = parseInt(document.getElementById('order-doctor').value, 10);
  const testIds = [...document.querySelectorAll('input[name="order-test"]:checked')].map(c => parseInt(c.value, 10));
  if (!patientId || !doctorId) {
    alert('Please select patient and doctor.');
    return;
  }
  if (!testIds.length) {
    alert('Select at least one test.');
    return;
  }
  const payload = {
    patient_id: patientId,
    ordered_by_doctor_id: doctorId,
    test_ids: testIds,
    priority: document.getElementById('order-priority').value,
    clinical_notes: document.getElementById('order-notes').value.trim() || null,
  };
  try {
    const res = await API.post('/laboratory/orders', payload);
    const order = unwrapOne(res);
    toast(`Lab order #${order.id} created`);
    document.getElementById('order-form').reset();
    showPage('queue');
  } catch (err) {
    alert(err.message || err);
  }
}

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────
function unwrapList(res) {
  if (Array.isArray(res)) return res;
  if (res && Array.isArray(res.data)) return res.data;
  return [];
}

function unwrapOne(res) {
  if (res && res.data && typeof res.data === 'object') return res.data;
  return res;
}

function formatStatus(s) {
  return (s || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function statusBadgeClass(s) {
  switch (s) {
    case 'pending': return 'badge-warning';
    case 'sample_collected': return 'badge-info';
    case 'processing': return 'badge-info';
    case 'completed': return 'badge-success';
    case 'cancelled': return 'badge-danger';
    default: return '';
  }
}

function formatDateTime(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function parseOptionalNumber(v) {
  if (v === '' || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function escapeAttr(str) {
  return escapeHtml(str).replace(/'/g, '&#39;');
}

function toast(msg) {
  // lightweight fallback
  console.log('[lab]', msg);
  const existing = document.getElementById('lab-toast');
  if (existing) existing.remove();
  const el = document.createElement('div');
  el.id = 'lab-toast';
  el.textContent = msg;
  el.style.cssText = 'position:fixed;bottom:24px;right:24px;background:#111827;color:#fff;padding:12px 18px;border-radius:10px;z-index:9999;font-size:14px;box-shadow:0 8px 24px rgba(0,0,0,.25);';
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2800);
}


async function viewLabReport(orderId) {
  try {
    const res = await API.get(`/laboratory/orders/${orderId}/report`);
    const data = res?.data || res;
    const html = data.html || data;
    if (!html) throw new Error('No report HTML returned');
    const w = window.open('', '_blank');
    if (!w) {
      alert('Please allow pop-ups to view the report');
      return;
    }
    w.document.open();
    w.document.write(html);
    w.document.close();
  } catch (e) {
    alert(e.message || e);
  }
}



function logout() {
  Auth.clear();
  window.location.replace('login.html?force=1');
}


async function downloadLabReportFile(orderId) {
  try {
    const response = await fetch(API.config + `/laboratory/orders/${orderId}/report/download`, {
      headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
    });
    if (!response.ok) throw new Error('Download failed');
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Lab_Report_${orderId}.html`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e) {
    alert(e.message || e);
  }
}


// ═════════════════════════════════════════════════════════════
// Walk-in lab orders (counter — no doctor)
// ═════════════════════════════════════════════════════════════
async function loadWalkInLabPage() {
  await Promise.all([populateWalkInLabDoctors(), populateWalkInLabTests(), loadWalkInLabOrders()]);
  await populateWalkInLabPatients();
}


async function populateWalkInLabDoctors() {
  const sel = document.getElementById('walkin-lab-doctor');
  if (!sel) return;
  try {
    let doctors = (typeof allDoctors !== 'undefined' && Array.isArray(allDoctors)) ? allDoctors : [];
    if (!doctors.length) {
      const res = await API.get('/doctors');
      doctors = Array.isArray(res) ? res : (res?.data || []);
    }
    const cur = sel.value;
    sel.innerHTML = '<option value="">— No doctor / pure walk-in —</option>' +
      doctors.map(d => {
        const name = d.full_name || d.name || ('Doctor #' + d.id);
        const spec = d.specialization ? ` — ${d.specialization}` : '';
        return `<option value="${d.id}">${escapeHtml(name)}${escapeHtml(spec)}</option>`;
      }).join('');
    if (cur) sel.value = cur;
    sel.onchange = () => populateWalkInLabPatients();
  } catch (e) {
    console.warn('walkin lab doctors', e);
  }
}

async function populateWalkInLabPatients() {
  const sel = document.getElementById('walkin-lab-patient');
  if (!sel) return;
  try {
    let patients = [];
    if (typeof allPatients !== 'undefined' && Array.isArray(allPatients) && allPatients.length) {
      patients = allPatients.slice();
    } else {
      const res = await API.get('/patients');
      patients = Array.isArray(res) ? res : (res?.data || []);
    }
    const doctorId = document.getElementById('walkin-lab-doctor')?.value || '';
    if (doctorId) {
      const appts = (typeof allAppointments !== 'undefined' && Array.isArray(allAppointments)) ? allAppointments : [];
      const ids = new Set(
        appts
          .filter(a => String(a.doctor_id) === String(doctorId) || String(a.doctorId) === String(doctorId))
          .map(a => a.patient_id || a.patientId)
          .filter(Boolean)
          .map(String)
      );
      if (ids.size) {
        patients = patients.filter(p => ids.has(String(p.id)));
      }
    }
    const cur = sel.value;
    sel.innerHTML = '<option value="">— Guest / not registered —</option>' +
      patients.map(p => {
        const label = p.name || p.full_name || ('Patient #' + p.id);
        return `<option value="${p.id}">${escapeHtml(label)}</option>`;
      }).join('');
    if (cur && [...sel.options].some(o => o.value === cur)) sel.value = cur;
    else sel.value = '';

    sel.onchange = () => {
      const id = sel.value;
      if (!id) return;
      const p = patients.find(x => String(x.id) === String(id)) ||
        ((typeof allPatients !== 'undefined' ? allPatients : []) || []).find(x => String(x.id) === String(id));
      if (!p) return;
      const nameEl = document.getElementById('walkin-lab-name');
      const phoneEl = document.getElementById('walkin-lab-phone');
      if (nameEl) nameEl.value = p.name || p.full_name || '';
      if (phoneEl && (p.phone || p.phone_number)) phoneEl.value = p.phone || p.phone_number || '';
    };
  } catch (e) {
    console.warn('walkin lab patients', e);
  }
}

async function populateWalkInLabTests() {
  const box = document.getElementById('walkin-lab-tests-checklist');
  if (!box) return;
  try {
    let tests = [];
    if (typeof allTests !== 'undefined' && Array.isArray(allTests) && allTests.length) {
      tests = allTests.filter(t => t.is_active !== false);
    } else {
      const res = await API.get('/laboratory/tests');
      const raw = Array.isArray(res) ? res : (res?.data || []);
      tests = raw.filter(t => t.is_active !== false);
    }
    if (!tests.length) {
      box.innerHTML = '<div class="empty-state">No active tests in catalog. Add tests first.</div>';
      return;
    }
    box.innerHTML = tests.map(t => `
      <label style="display:flex; gap:8px; align-items:flex-start; font-size:14px; padding:8px 10px; border-radius:10px; background:var(--bg-soft, rgba(0,0,0,0.03)); cursor:pointer;">
        <input type="checkbox" name="walkin-lab-test" value="${t.id}" style="margin-top:3px;">
        <span>
          <strong>${escapeHtml(t.name)}</strong>
          ${t.code ? `<span class="badge">${escapeHtml(t.code)}</span>` : ''}
          <div style="font-size:12px; color:var(--text-light);">${escapeHtml(t.category || '')} · ${escapeHtml(t.sample_type || '')}${t.price != null ? ' · ' + t.price : ''}</div>
        </span>
      </label>`).join('');
  } catch (e) {
    console.warn('walkin tests', e);
    box.innerHTML = '<div class="empty-state">Could not load tests.</div>';
  }
}

async function loadWalkInLabOrders() {
  const el = document.getElementById('walkin-lab-list');
  if (!el) return;
  el.innerHTML = '<div class="loading-spinner">Loading...</div>';
  try {
    const res = await API.get('/laboratory/orders');
    const list = Array.isArray(res) ? res : (res?.data || []);
    const walkins = list.filter(o =>
      o.order_source === 'walk_in' || o.source === 'walk_in' ||
      (!o.ordered_by_doctor_id && (o.customer_name || o.source === 'walk_in'))
    );
    if (!walkins.length) {
      el.innerHTML = '<div class="empty-state">No walk-in orders yet.</div>';
      return;
    }
    // reuse card renderer if available
    if (typeof renderOrderCards === 'function') {
      renderOrderCards('walkin-lab-list', walkins, true);
      return;
    }
    el.innerHTML = '<div class="order-list">' + walkins.map(o => {
      const name = o.patient_name || o.customer_name || ('#' + (o.patient_id || o.id));
      const tests = (o.results || []).map(r => r.test_name || r.test_code || '').filter(Boolean).join(', ');
      return `<div class="order-list-item">
        <div class="order-list-main">
          <div class="order-list-top">
            <strong>#${o.id}</strong>
            <span class="badge badge-info">WALK-IN</span>
            <span class="badge">${escapeHtml((o.status || '').toString())}</span>
          </div>
          <div class="order-list-patient">${escapeHtml(name)}</div>
          <div class="order-list-meta">${escapeHtml(tests || '—')}</div>
        </div>
        <div class="order-list-actions">
          <button type="button" class="btn btn-ghost btn-sm" onclick="openOrderDetail(${o.id})">Open</button>
        </div>
      </div>`;
    }).join('') + '</div>';
  } catch (e) {
    el.innerHTML = `<div class="empty-state">${escapeHtml(e.message || String(e))}</div>`;
  }
}

async function submitWalkInLabOrder(e) {
  e.preventDefault();
  const msg = document.getElementById('walkin-lab-msg');
  const btn = document.getElementById('walkin-lab-submit');
  const patientVal = document.getElementById('walkin-lab-patient').value;
  const customer_name = document.getElementById('walkin-lab-name').value.trim();
  const customer_phone = document.getElementById('walkin-lab-phone').value.trim();
  const priority = document.getElementById('walkin-lab-priority').value || 'routine';
  const notes = document.getElementById('walkin-lab-notes').value.trim();
  const test_ids = Array.from(document.querySelectorAll('input[name="walkin-lab-test"]:checked'))
    .map(el => parseInt(el.value, 10))
    .filter(Boolean);

  if (!test_ids.length) {
    if (msg) { msg.style.display = 'block'; msg.className = 'alert alert-error'; msg.textContent = 'Select at least one test.'; }
    return;
  }
  if (!patientVal && !customer_name) {
    if (msg) { msg.style.display = 'block'; msg.className = 'alert alert-error'; msg.textContent = 'Enter customer name or select a patient.'; }
    return;
  }

  if (btn) btn.disabled = true;
  try {
    const doctorVal = document.getElementById('walkin-lab-doctor')?.value || '';
    const body = {
      test_ids,
      patient_id: patientVal ? parseInt(patientVal, 10) : null,
      ordered_by_doctor_id: doctorVal ? parseInt(doctorVal, 10) : null,
      customer_name: customer_name || null,
      customer_phone: customer_phone || null,
      priority,
      clinical_notes: notes || null,
    };
    const res = await API.post('/laboratory/walk-in', body);
    const data = res?.data || res;
    if (msg) {
      msg.style.display = 'block';
      msg.className = 'alert alert-success';
      msg.textContent = `Walk-in order #${data?.id || ''} created and sent to the work queue.`;
    }
    document.getElementById('walkin-lab-name').value = '';
    document.getElementById('walkin-lab-phone').value = '';
    document.getElementById('walkin-lab-notes').value = '';
    document.getElementById('walkin-lab-patient').value = '';
    const dsel = document.getElementById('walkin-lab-doctor');
    if (dsel) dsel.value = '';
    document.querySelectorAll('input[name="walkin-lab-test"]').forEach(el => { el.checked = false; });
    await loadWalkInLabOrders();
    if (typeof loadQueue === 'function') {
      try { loadQueue(); } catch (_) {}
    }
  } catch (err) {
    if (msg) {
      msg.style.display = 'block';
      msg.className = 'alert alert-error';
      msg.textContent = err.message || String(err);
    }
  } finally {
    if (btn) btn.disabled = false;
  }
}

