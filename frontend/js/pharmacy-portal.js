function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
// Pharmacy Portal (Pharmacist) Functionality
let allMedicines = [];
let medicinesById = {};
let pendingOrders = [];
let lowStockMedicines = [];

let allPatients = [];
let allDoctors = [];
let patientsById = {};
let doctorsById = {};

let allWards = [];
let allBeds = [];
let wardsById = {};
let bedsById = {};

function patientLabel(patientId) {
  const patient = patientsById[patientId];
  return patient ? Utils.escapeHtml(patient.name) : `Patient #${patientId}`;
}

function doctorLabel(doctorId) {
  if (!doctorId) return '—';
  const doctor = doctorsById[doctorId];
  const name = doctor ? doctor.full_name : `#${doctorId}`;
  const clean = String(name).replace(/^Dr\.?\s+/i, '');
  return `Dr. ${Utils.escapeHtml(clean)}`;
}

function staffLabel(userId) {
  return userId ? `Staff #${userId}` : '—';
}

async function ensureDirectoriesLoaded() {
  try {
    const [patients, doctors, wards, beds] = await Promise.all([
      API.get('/patients/').catch(() => []),
      API.get('/doctors/').catch(() => []),
      API.get('/admissions/wards').catch(() => []),
      API.get('/admissions/beds').catch(() => []),
    ]);
    allPatients = patients || [];
    allDoctors = doctors || [];
    allWards = wards || [];
    allBeds = beds || [];
    patientsById = Object.fromEntries(allPatients.map(p => [p.id, p]));
    doctorsById = Object.fromEntries(allDoctors.map(d => [d.id, d]));
    wardsById = Object.fromEntries(allWards.map(w => [w.id, w]));
    bedsById = Object.fromEntries(allBeds.map(b => [b.id, b]));
  } catch (error) {
    console.error('Failed to load directories:', error);
  }
}

document.addEventListener('DOMContentLoaded', async function() {
  const isRedirecting = sessionStorage.getItem('auth_redirecting');

  const role = Auth.getRole();
  if (!Auth.isAuthenticated() || (role !== 'pharmacist' && role !== 'admin')) {
    if (!isRedirecting) {
      sessionStorage.setItem('auth_redirecting', 'true');
      window.location.replace('login.html?redirect=pharmacy-portal.html');
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
  await ensureDirectoriesLoaded();
  loadDashboard();
});

function loadUserInfo() {
  const user = Auth.getUser();
  if (user) {
    document.getElementById('user-name').textContent = user.username;
    document.getElementById('user-role').textContent = 'Pharmacist';
    document.getElementById('user-info').style.display = 'block';
  }
}

function setupNotificationBanner() {
  const banner = document.getElementById('notif-permission-banner');
  if (!banner) return;

  const dismissed = sessionStorage.getItem('pp_notif_banner_dismissed');
  const canAsk = ('Notification' in window) && Notification.permission === 'default';
  if (canAsk && !dismissed) {
    banner.style.display = 'flex';
  }

  document.getElementById('notif-enable-btn')?.addEventListener('click', async () => {
    if (window.enableNotifications) {
      await window.enableNotifications();
    }
    banner.style.display = 'none';
  });

  document.getElementById('notif-dismiss-btn')?.addEventListener('click', () => {
    sessionStorage.setItem('pp_notif_banner_dismissed', 'true');
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

  document.getElementById('search-inventory')?.addEventListener('input', renderInventoryList);
}

function showPage(pageName) {
  document.querySelectorAll('.sidebar-link').forEach(link => {
    link.classList.toggle('active', link.dataset.page === pageName);
  });

  document.querySelectorAll('.page').forEach(page => {
    page.classList.toggle('active', page.id === `page-${pageName}`);
  });

  switch (pageName) {
    case 'dashboard':
      loadDashboard();
      break;
    case 'orders':
      loadPendingOrders();
      break;
    case 'inventory':
      loadInventory();
      break;
    case 'lowstock':
      loadLowStock();
      break;
    case 'ipd':
      loadIPDPatients();
      break;
    case 'history':
      loadHistory();
      break;
    case 'walkin':
      loadWalkInPage();
      break;
  }
}

function formatDateTime(dtStr) {
  if (!dtStr) return '—';
  try {
    const d = new Date(dtStr);
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return dtStr;
  }
}

function isToday(dtStr) {
  if (!dtStr) return false;
  const d = new Date(dtStr);
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
}

function orderStatusBadge(status) {
  const map = {
    pending: 'badge-warning',
    dispensed: 'badge-success',
    out_of_stock: 'badge-danger',
    cancelled: 'badge-info',
  };
  const cls = map[status] || 'badge-info';
  return `<span class="badge ${cls}">${Utils.escapeHtml((status || '').replace(/_/g, ' ').toUpperCase())}</span>`;
}

function stockBadge(medicine) {
  if (!medicine) return '<span class="badge badge-info">Not in inventory</span>';
  if (medicine.stock_qty <= 0) return '<span class="badge badge-danger">Out of stock</span>';
  if (medicine.stock_qty <= medicine.reorder_threshold) return `<span class="badge badge-warning">${medicine.stock_qty} ${Utils.escapeHtml(medicine.unit)} — low</span>`;
  return `<span class="badge badge-success">${medicine.stock_qty} ${Utils.escapeHtml(medicine.unit)}</span>`;
}

// ═════════════════════════════════════════════════════════════
// Dashboard
// ═════════════════════════════════════════════════════════════
async function loadDashboard() {
  try {
    const [medicines, orders, lowStock] = await Promise.all([
      API.get('/pharmacy/medicines'),
      API.get('/pharmacy/orders/pending'),
      API.get('/pharmacy/medicines/low-stock'),
    ]);
    allMedicines = medicines || [];
    medicinesById = Object.fromEntries(allMedicines.map(m => [m.id, m]));
    pendingOrders = orders || [];
    lowStockMedicines = lowStock || [];

    document.getElementById('stat-total-medicines').textContent = allMedicines.length;
    document.getElementById('stat-pending-orders').textContent = pendingOrders.length;
    document.getElementById('stat-low-stock').textContent = lowStockMedicines.length;

    if (window.PortalUI) {
      PortalUI.ensureChartJs(function () {
        try {
          const weekly = PortalUI.weeklyCounts(pendingOrders || [], 'created_at');
          PortalUI.lineChart('portal-trend-chart', weekly.labels, weekly.data, 'Orders');
          PortalUI.doughnutChart(
            'portal-status-chart',
            ['Pending orders', 'Low stock', 'In catalog'],
            [
              (pendingOrders || []).length,
              (lowStockMedicines || []).length,
              (allMedicines || []).length
            ]
          );
        } catch (e) {
          console.warn('Pharmacy dashboard charts failed:', e);
        }
      });
    }

    updatePendingBadge();
    updateLowStockBadge();
    renderDashboardOrders();
    renderDashboardLowStock();

    // "Dispensed today" needs to be built from every patient's order
    // history — there's no single "all orders" endpoint — so it loads
    // in the background without blocking the rest of the dashboard.
    loadDispensedTodayStat();
  } catch (error) {
    console.error('Failed to load dashboard:', error);
    Utils.showToast('Failed to load dashboard', 'error');
  }
}

async function loadDispensedTodayStat() {
  try {
    const results = await Promise.all(
      allPatients.map(p => API.get(`/pharmacy/orders/patient/${p.id}`).catch(() => []))
    );
    const dispensedToday = results.flat().filter(o => o.status === 'dispensed' && isToday(o.dispensed_at));
    document.getElementById('stat-dispensed-today').textContent = dispensedToday.length;
  } catch (error) {
    console.error('Failed to compute dispensed-today stat:', error);
  }
}

function updatePendingBadge() {
  const badge = document.getElementById('pending-count-badge');
  if (!badge) return;
  if (pendingOrders.length > 0) {
    badge.textContent = pendingOrders.length;
    badge.style.display = 'inline-flex';
  } else {
    badge.style.display = 'none';
  }
}

function updateLowStockBadge() {
  const badge = document.getElementById('lowstock-count-badge');
  if (!badge) return;
  if (lowStockMedicines.length > 0) {
    badge.textContent = lowStockMedicines.length;
    badge.style.display = 'inline-flex';
  } else {
    badge.style.display = 'none';
  }
}

function renderDashboardOrders() {
  const el = document.getElementById('dashboard-orders-list');
  const top = pendingOrders.slice(0, 5);
  if (top.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No pending orders. All caught up!</p>';
    return;
  }
  el.innerHTML = renderOrdersTable(top);
}

function renderDashboardLowStock() {
  const el = document.getElementById('dashboard-lowstock-list');
  const top = lowStockMedicines.slice(0, 5);
  if (top.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">Nothing low on stock right now.</p>';
    return;
  }
  el.innerHTML = `
    <div class="table-responsive">
      <table class="table">
        <thead><tr><th>Medicine</th><th>Stock</th><th>Threshold</th><th>Action</th></tr></thead>
        <tbody>
          ${top.map(m => `
            <tr>
              <td><strong>${Utils.escapeHtml(m.name)}</strong></td>
              <td>${stockBadge(m)}</td>
              <td>${m.unit_price != null ? Number(m.unit_price).toFixed(2) : '—'}</td>
              <td>${m.reorder_threshold} ${Utils.escapeHtml(m.unit)}</td>
              <td><button class="btn btn-primary btn-sm" onclick="openRestockModal(${m.id})">Restock</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

// ═════════════════════════════════════════════════════════════
// Pending Orders Queue
// ═════════════════════════════════════════════════════════════
async function loadPendingOrders() {
  try {
    pendingOrders = await API.get('/pharmacy/orders/pending');
    updatePendingBadge();
    renderPendingOrders();
  } catch (error) {
    console.error('Failed to load pending orders:', error);
    document.getElementById('orders-list').innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">Failed to load orders.</p>';
  }
}

function renderPendingOrders() {
  const el = document.getElementById('orders-list');
  if (pendingOrders.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No pending orders.</p>';
    return;
  }
  el.innerHTML = renderOrdersTable(pendingOrders);
}

function renderOrdersTable(orders) {
  return `
    <div class="table-responsive">
      <table class="table">
        <thead>
          <tr>
            <th>Patient</th><th>Where</th><th>Medicine</th><th>Form</th><th>Qty</th>
            <th>Dosage</th><th>Frequency</th><th>Duration</th><th>Stock</th><th>Ordered</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${orders.map(o => {
            const medicine = o.medicine_id ? medicinesById[o.medicine_id] : null;
            const qty = Number(o.quantity || 1);
            const canDispense = !!medicine && medicine.stock_qty >= qty;
            const isCourse = o.order_source === 'course' || o.source === 'course';
            const isIpd = o.care_setting === 'ipd' || o.source === 'ipd';
            const where = isCourse
              ? `<span class="badge badge-warning">WARD COURSE</span> ${Utils.escapeHtml(o.ward_bed_label || '')}`
              : isIpd
                ? `<span class="badge badge-info">IPD</span> ${Utils.escapeHtml(o.ward_bed_label || 'Ward')}`
                : `<span class="badge badge-success">OPD</span>`;
            const form = (o.form || (medicine && medicine.form) || '—');
            return `
              <tr>
                <td><strong>${Utils.escapeHtml(o.patient_name || patientLabel(o.patient_id))}</strong></td>
                <td>${where}</td>
                <td>${Utils.escapeHtml(o.medicine_name || '—')}</td>
                <td><span class="badge">${Utils.escapeHtml(String(form).toUpperCase())}</span></td>
                <td><strong>${qty}</strong></td>
                <td>${Utils.escapeHtml(o.dosage || '—')}</td>
                <td>${Utils.escapeHtml(o.frequency || '—')}</td>
                <td>${Utils.escapeHtml(o.duration || '—')}</td>
                <td>${stockBadge(medicine)}</td>
                <td>${formatDateTime(o.created_at)}</td>
                <td style="display:flex; gap:6px; flex-wrap:wrap;">
                  ${canDispense
                    ? `<button class="btn btn-primary btn-sm" onclick="dispenseOrder(${o.id}, ${qty})">Dispense ×${qty}</button>`
                    : `<button class="btn btn-ghost btn-sm" onclick="openAddMedicineFromOrder(${o.id})">${medicine ? 'Restock (need '+qty+')' : 'Add to inventory'}</button>`
                  }
                </td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>
  `;
}

async function dispenseOrder(orderId, qty) {
  if (!confirm('Dispense this order? Stock will decrease by the ordered quantity.\nAfter ward-course dispense, nurses can mark doses as given.')) return;
  try {
    await API.put(`/pharmacy/orders/${orderId}/dispense`, { note: null });
    Utils.showToast('Order dispensed', 'success');
    await loadPendingOrders();
    const medicines = await API.get('/pharmacy/medicines').catch(() => allMedicines);
    allMedicines = medicines || allMedicines;
    medicinesById = Object.fromEntries(allMedicines.map(m => [m.id, m]));
    if (document.getElementById('page-dashboard').classList.contains('active')) loadDashboard();
    if (document.getElementById('page-inventory').classList.contains('active')) renderInventoryList();
  } catch (error) {
    console.error('Failed to dispense order:', error);
    Utils.showToast(error.message || 'Failed to dispense order', 'error');
    loadPendingOrders();
  }
}

// If a medicine isn't in inventory yet (or is out of stock), the
// pharmacist adds/restocks it here. Adding a medicine here matches it
// by name against any pending/out-of-stock orders that pre-date it in
// inventory and links + reopens them automatically (see add_medicine
// in pharmacy_service.py), so this order and any others for the same
// drug become dispensable right away.
let linkMedicineTargetOrderId = null;

function normalizeMedicineForm(form) {
  const f = String(form || 'other').toLowerCase().trim();
  const allowed = ['tablet','capsule','syrup','injection','drip','ointment','drops','other'];
  if (allowed.includes(f)) return f;
  const map = { oral: 'tablet', iv: 'drip', im: 'injection', sc: 'injection', tab: 'tablet', inj: 'injection' };
  return map[f] || 'other';
}

function findInventoryByName(name) {
  if (!name || !Array.isArray(allMedicines)) return null;
  const key = String(name).trim().toLowerCase();
  return allMedicines.find(m => String(m.name || '').trim().toLowerCase() === key) || null;
}


function openAddMedicineFromOrder(orderId) {
  const order =
    (typeof pendingOrders !== 'undefined' && pendingOrders.find(o => o.id === orderId)) ||
    (typeof allOrders !== 'undefined' && allOrders.find(o => o.id === orderId)) ||
    null;

  const name = order?.medicine_name || '';
  const form = (order?.form || 'tablet').toString().toLowerCase();
  const dosage = order?.dosage || '';
  const needQty = Math.max(1, Number(order?.quantity || 1));

  // Prefer full inventory form (has dosage + unit price), not the small modal
  if (typeof showPage === 'function') showPage('inventory');

  // Wait a tick so inventory page is visible
  setTimeout(() => {
    const editId = document.getElementById('medicine-edit-id');
    if (editId) editId.value = '';
    const title = document.getElementById('medicine-form-title');
    if (title) title.textContent = 'Add Medicine (from order)';

    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val != null ? val : '';
    };
    set('medicine-name', name);
    set('medicine-form-type', form);
    set('medicine-dosage', dosage);
    set('medicine-unit', 'units');
    set('medicine-stock-qty', String(needQty));
    set('medicine-threshold', '10');
    set('medicine-unit-price', '50');
    set('medicine-batch', '');
    set('medicine-expiry', '');

    const formEl = document.getElementById('medicine-form');
    if (formEl) formEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    const nameEl = document.getElementById('medicine-name');
    if (nameEl) nameEl.focus();

    Utils.showToast(
      'Review name, form, dosage & price, then save. Order will match after inventory is saved.',
      'info'
    );
  }, 50);
}

function openLinkMedicineModal(orderId, medicineName) {
  linkMedicineTargetOrderId = orderId;
  const order = pendingOrders.find(o => o.id === orderId);
  // Prefer linked row; otherwise same product name already on the shelf
  // (common for course meds where form differs but name is unique).
  let existing = order?.medicine_id ? medicinesById[order.medicine_id] : null;
  if (!existing) {
    existing = findInventoryByName(medicineName || order?.medicine_name);
  }
  const orderForm = normalizeMedicineForm(order?.form || existing?.form || 'other');

  const body = document.getElementById('link-medicine-modal-body');

  if (existing) {
    // Already in inventory — restock (and align form) instead of "already exists".
    body.innerHTML = `
      <p style="font-size:14px; margin-bottom:16px;">
        <strong>${Utils.escapeHtml(existing.name)}</strong>
        ${existing.stock_qty > 0 ? `(current stock: ${existing.stock_qty})` : 'is out of stock'}.
        Add quantity to fulfil this order
        ${orderForm ? `(form: <strong>${Utils.escapeHtml(orderForm)}</strong>)` : ''}.
      </p>
      <div class="form-group">
        <label class="form-label">Quantity to Add</label>
        <input type="number" class="form-input" id="link-restock-quantity" min="1" placeholder="e.g. 100" value="${Math.max(1, Number(order?.quantity || 1))}">
      </div>
      <div class="form-group">
        <label class="form-label">Form</label>
        <select class="form-select" id="link-restock-form">
          ${['tablet','capsule','syrup','injection','drip','ointment','drops','other'].map(f =>
            `<option value="${f}" ${f === orderForm ? 'selected' : ''}>${f}</option>`
          ).join('')}
        </select>
      </div>
    `;
  } else {
    body.innerHTML = `
      <p style="font-size:14px; margin-bottom:16px;">
        <strong>${Utils.escapeHtml(medicineName || 'This medicine')}</strong> isn't in the inventory master list yet.
        Add it below — this order (and any other pending orders for the same name) will be matched to it automatically and become dispensable.
      </p>
      <div class="form-group">
        <label class="form-label">Medicine Name</label>
        <input type="text" class="form-input" id="link-medicine-name" value="${Utils.escapeHtml(medicineName || '')}">
      </div>
      <div class="form-group">
        <label class="form-label">Form</label>
        <select class="form-select" id="link-medicine-form">
          ${['tablet','capsule','syrup','injection','drip','ointment','drops','other'].map(f =>
            `<option value="${f}" ${f === orderForm ? 'selected' : ''}>${f}</option>`
          ).join('')}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Initial Stock Qty</label>
        <input type="number" class="form-input" id="link-medicine-stock" min="0" value="${Math.max(1, Number(order?.quantity || 1))}">
      </div>
      <div class="form-group">
        <label class="form-label">Reorder Threshold</label>
        <input type="number" class="form-input" id="link-medicine-threshold" min="0" value="10">
      </div>
    `;
  }

  document.getElementById('link-medicine-modal').classList.add('active');
}

function closeLinkMedicineModal() {
  document.getElementById('link-medicine-modal').classList.remove('active');
  linkMedicineTargetOrderId = null;
}

async function confirmAddMissingMedicine() {
  const order = pendingOrders.find(o => o.id === linkMedicineTargetOrderId);
  let existing = order?.medicine_id ? medicinesById[order.medicine_id] : null;
  if (!existing) {
    existing = findInventoryByName(order?.medicine_name);
  }

  try {
    if (existing) {
      const qty = parseInt(document.getElementById('link-restock-quantity').value, 10);
      if (!qty || qty <= 0) {
        Utils.showToast('Please enter a quantity to add', 'error');
        return;
      }
      await API.put(`/pharmacy/medicines/${existing.id}/restock`, { quantity: qty });
      // Align form on inventory when pharmacist sets it (name is unique).
      const formEl = document.getElementById('link-restock-form');
      const form = formEl ? normalizeMedicineForm(formEl.value) : null;
      if (form && form !== String(existing.form || '').toLowerCase()) {
        try {
          await API.put(`/pharmacy/medicines/${existing.id}`, {
            name: existing.name,
            form,
            unit: existing.unit || 'units',
            stock_qty: existing.stock_qty,
            reorder_threshold: existing.reorder_threshold,
          });
        } catch (e) {
          // Restock already succeeded; form update is best-effort.
          console.warn('Form update after restock failed', e);
        }
      }
      Utils.showToast('Stock added — order can be dispensed', 'success');
    } else {
      const name = document.getElementById('link-medicine-name').value.trim();
      const stockQty = parseInt(document.getElementById('link-medicine-stock').value, 10) || 0;
      const threshold = parseInt(document.getElementById('link-medicine-threshold').value, 10) || 10;
      const formEl = document.getElementById('link-medicine-form');
      const form = normalizeMedicineForm(formEl ? formEl.value : (order?.form || 'other'));
      if (!name) {
        Utils.showToast('Please enter a medicine name', 'error');
        return;
      }
      await API.post('/pharmacy/medicines', {
        name,
        form,
        unit: 'units',
        stock_qty: stockQty,
        reorder_threshold: threshold,
      });
      Utils.showToast('Medicine added to inventory', 'success');
    }
    closeLinkMedicineModal();
    const medicines = await API.get('/pharmacy/medicines').catch(() => allMedicines);
    allMedicines = medicines || allMedicines;
    medicinesById = Object.fromEntries(allMedicines.map(m => [m.id, m]));
    await loadPendingOrders();
  } catch (error) {
    console.error('Failed to add/restock medicine:', error);
    // If backend still returns "already exists", fall back to restock by name.
    const msg = (error && error.message) || '';
    if (/already exists/i.test(msg)) {
      const name = (document.getElementById('link-medicine-name')?.value || order?.medicine_name || '').trim();
      const hit = findInventoryByName(name);
      const qty = parseInt(document.getElementById('link-medicine-stock')?.value || document.getElementById('link-restock-quantity')?.value || '0', 10);
      if (hit && qty > 0) {
        try {
          await API.put(`/pharmacy/medicines/${hit.id}/restock`, { quantity: qty });
          Utils.showToast('Medicine was already in inventory — stock increased', 'success');
          closeLinkMedicineModal();
          const medicines = await API.get('/pharmacy/medicines').catch(() => allMedicines);
          allMedicines = medicines || allMedicines;
          medicinesById = Object.fromEntries(allMedicines.map(m => [m.id, m]));
          await loadPendingOrders();
          return;
        } catch (e2) {
          console.error(e2);
        }
      }
    }
    Utils.showToast(error.message || 'Failed to save medicine', 'error');
  }
}

// ═════════════════════════════════════════════════════════════
// Inventory Management
// ═════════════════════════════════════════════════════════════
async function loadInventory() {
  try {
    allMedicines = await API.get('/pharmacy/medicines');
    medicinesById = Object.fromEntries(allMedicines.map(m => [m.id, m]));
    renderInventoryList();
  } catch (error) {
    console.error('Failed to load inventory:', error);
    document.getElementById('inventory-list').innerHTML = '<p style="color: var(--text-light); text-align:center; padding:20px;">Failed to load inventory.</p>';
  }
}

function renderInventoryList() {
  const search = document.getElementById('search-inventory')?.value.toLowerCase() || '';
  const filtered = allMedicines.filter(m => m.name.toLowerCase().includes(search));

  const el = document.getElementById('inventory-list');
  if (filtered.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No medicines found. Add one above.</p>';
    return;
  }

  el.innerHTML = `
    <div class="table-responsive">
      <table class="table">
        <thead>
          <tr><th>Name</th><th>Form</th><th>Dosage</th><th>Stock</th><th>Unit Price</th><th>Reorder at</th><th>Batch</th><th>Expiry</th><th>Actions</th></tr>
        </thead>
        <tbody>
          ${filtered.map(m => `
            <tr>
              <td><strong>${Utils.escapeHtml(m.name)}</strong></td>
              <td style="text-transform:capitalize;">${Utils.escapeHtml(m.form)}</td>
              <td>${Utils.escapeHtml(m.dosage || '—')}</td>
              <td>${stockBadge(m)}</td>
              <td>${m.unit_price != null ? Number(m.unit_price).toFixed(2) : '—'}</td>
              <td>${m.reorder_threshold}</td>
              <td>${Utils.escapeHtml(m.batch_number || '—')}</td>
              <td>${m.expiry_date ? Utils.formatDate(m.expiry_date) : '—'}</td>
              <td style="display:flex; gap:6px; flex-wrap:wrap;">
                <button class="btn btn-ghost btn-sm" onclick="editMedicine(${m.id})">Edit</button>
                <button class="btn btn-primary btn-sm" onclick="openRestockModal(${m.id})">Restock</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function editMedicine(medicineId) {
  const medicine = medicinesById[medicineId];
  if (!medicine) return;

  document.getElementById('medicine-edit-id').value = medicine.id;
  document.getElementById('medicine-name').value = medicine.name;
  document.getElementById('medicine-form-type').value = medicine.form;
  const _d = document.getElementById('medicine-dosage');
  if (_d) _d.value = medicine.dosage || '';
  document.getElementById('medicine-unit').value = medicine.unit;
  document.getElementById('medicine-threshold').value = medicine.reorder_threshold;
  const _up = document.getElementById('medicine-unit-price');
  if (_up) _up.value = medicine.unit_price != null ? medicine.unit_price : 50;
  document.getElementById('medicine-batch').value = medicine.batch_number || '';
  document.getElementById('medicine-expiry').value = medicine.expiry_date || '';

  // Stock quantity can only change via Restock, not via the edit form —
  // hide it while editing so it isn't mistaken for an editable total.
  document.getElementById('medicine-stock-group').style.display = 'none';

  document.getElementById('medicine-form-title').textContent = `Edit ${medicine.name}`;
  document.getElementById('medicine-submit-btn').textContent = 'Save Changes';
  document.getElementById('medicine-cancel-btn').style.display = 'inline-flex';

  document.getElementById('page-inventory').scrollIntoView({ behavior: 'smooth' });
}

function cancelMedicineEdit() {
  document.getElementById('medicine-form').reset();
  document.getElementById('medicine-edit-id').value = '';
  document.getElementById('medicine-unit').value = 'units';
  document.getElementById('medicine-threshold').value = 10;
  document.getElementById('medicine-stock-qty').value = 0;
  document.getElementById('medicine-stock-group').style.display = '';
  document.getElementById('medicine-form-title').textContent = 'Add Medicine';
  document.getElementById('medicine-submit-btn').textContent = 'Add Medicine';
  document.getElementById('medicine-cancel-btn').style.display = 'none';
}

async function submitMedicineForm(e) {
  e.preventDefault();
  const editId = document.getElementById('medicine-edit-id').value;
  const name = document.getElementById('medicine-name').value.trim();
  const form = document.getElementById('medicine-form-type').value;
  const dosage = (document.getElementById('medicine-dosage')?.value || '').trim() || null;
  const unit = (document.getElementById('medicine-unit')?.value || 'units').trim() || 'units';
  const threshold = parseInt(document.getElementById('medicine-threshold').value, 10) || 0;
  const unit_price = parseFloat(document.getElementById('medicine-unit-price')?.value);
  const batch = (document.getElementById('medicine-batch')?.value || '').trim();
  const expiry = document.getElementById('medicine-expiry')?.value || '';

  if (!name) { Utils.showToast('Please enter a medicine name', 'error'); return; }
  if (isNaN(unit_price) || unit_price < 0) { Utils.showToast('Enter a valid unit price', 'error'); return; }

  const payload = {
    name, form, dosage, unit,
    reorder_threshold: threshold,
    unit_price,
    batch_number: batch || null,
    expiry_date: expiry || null,
  };

  (async () => {
    try {
      if (editId) {
        await API.put(`/pharmacy/medicines/${editId}`, payload);
        Utils.showToast('Medicine updated', 'success');
      } else {
        const stockQty = parseInt(document.getElementById('medicine-stock-qty')?.value, 10) || 0;
        await API.post('/pharmacy/medicines', { ...payload, stock_qty: stockQty });
        Utils.showToast('Medicine added', 'success');
      }
      if (typeof cancelMedicineEdit === 'function') cancelMedicineEdit();
      await loadInventory();
    } catch (error) {
      console.error(error);
      Utils.showToast(error.message || 'Failed to save medicine', 'error');
    }
  })();
}


function openRestockModal(medicineId) {
  restockTargetId = medicineId;
  const medicine = medicinesById[medicineId];
  document.getElementById('restock-modal-title').textContent = medicine ? `Restock ${medicine.name}` : 'Restock Medicine';
  document.getElementById('restock-quantity').value = '';
  document.getElementById('restock-modal').classList.add('active');
}

function closeRestockModal() {
  document.getElementById('restock-modal').classList.remove('active');
  restockTargetId = null;
}

async function confirmRestock() {
  if (!restockTargetId) return;
  const qty = parseInt(document.getElementById('restock-quantity').value, 10);
  if (!qty || qty <= 0) {
    Utils.showToast('Please enter a valid quantity', 'error');
    return;
  }

  try {
    await API.put(`/pharmacy/medicines/${restockTargetId}/restock`, { quantity: qty });
    Utils.showToast('Stock added', 'success');
    closeRestockModal();
    const medicines = await API.get('/pharmacy/medicines').catch(() => allMedicines);
    allMedicines = medicines || allMedicines;
    medicinesById = Object.fromEntries(allMedicines.map(m => [m.id, m]));
    if (document.getElementById('page-inventory').classList.contains('active')) renderInventoryList();
    if (document.getElementById('page-lowstock').classList.contains('active')) loadLowStock();
    if (document.getElementById('page-orders').classList.contains('active')) renderPendingOrders();
    if (document.getElementById('page-dashboard').classList.contains('active')) loadDashboard();
  } catch (error) {
    console.error('Failed to restock medicine:', error);
    Utils.showToast(error.message || 'Failed to restock medicine', 'error');
  }
}

// ═════════════════════════════════════════════════════════════
// Low Stock
// ═════════════════════════════════════════════════════════════
async function loadLowStock() {
  try {
    lowStockMedicines = await API.get('/pharmacy/medicines/low-stock');
    updateLowStockBadge();
    renderLowStockList();
  } catch (error) {
    console.error('Failed to load low stock medicines:', error);
    document.getElementById('lowstock-list').innerHTML = '<p style="color: var(--text-light); text-align:center; padding:20px;">Failed to load low stock list.</p>';
  }
}

function renderLowStockList() {
  const el = document.getElementById('lowstock-list');
  if (lowStockMedicines.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">Nothing low on stock right now.</p>';
    return;
  }
  el.innerHTML = `
    <div class="table-responsive">
      <table class="table">
        <thead><tr><th>Medicine</th><th>Form</th><th>Stock</th><th>Threshold</th><th>Action</th></tr></thead>
        <tbody>
          ${lowStockMedicines.map(m => `
            <tr>
              <td><strong>${Utils.escapeHtml(m.name)}</strong></td>
              <td style="text-transform:capitalize;">${Utils.escapeHtml(m.form)}</td>
              <td>${stockBadge(m)}</td>
              <td>${m.unit_price != null ? Number(m.unit_price).toFixed(2) : '—'}</td>
              <td>${m.reorder_threshold} ${Utils.escapeHtml(m.unit)}</td>
              <td><button class="btn btn-primary btn-sm" onclick="openRestockModal(${m.id})">Restock</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

// ═════════════════════════════════════════════════════════════
// IPD Medication (MAR) — ongoing dosing for admitted patients
// ═════════════════════════════════════════════════════════════
let currentAdmittedEntries = [];

async function loadIPDPatients() {
  const el = document.getElementById('ipd-list');
  el.innerHTML = '<div class="loading-spinner">Loading admitted patients...</div>';
  try {
    // No single "currently admitted" endpoint is open to the pharmacist
    // role (the bed-map is Admission Head/Admin only) — build the list
    // from each patient's admission history and keep the ones still
    // status=admitted, same fallback pattern used elsewhere in this app.
    const results = await Promise.all(
      allPatients.map(p => API.get(`/admissions/patient/${p.id}`).catch(() => []))
    );
    currentAdmittedEntries = results.flat().filter(a => a.status === 'admitted');
    renderIPDList();
  } catch (error) {
    console.error('Failed to load admitted patients:', error);
    el.innerHTML = '<p style="color: var(--text-light); text-align:center; padding:20px;">Failed to load admitted patients.</p>';
  }
}

function bedLabel(bedId) {
  const bed = bedsById[bedId];
  if (!bed) return '—';
  const ward = wardsById[bed.ward_id];
  return `${ward ? Utils.escapeHtml(ward.name) : 'Ward'} &middot; Bed ${Utils.escapeHtml(bed.bed_number)}`;
}

function renderIPDList() {
  const el = document.getElementById('ipd-list');
  if (currentAdmittedEntries.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No patients currently admitted.</p>';
    return;
  }
  el.innerHTML = `
    <div class="table-responsive">
      <table class="table">
        <thead><tr><th>Patient</th><th>Ward / Bed</th><th>Admitting Doctor</th><th>Since</th><th>Actions</th></tr></thead>
        <tbody>
          ${currentAdmittedEntries.map(a => `
            <tr>
              <td><strong>${patientLabel(a.patient_id)}</strong></td>
              <td>${bedLabel(a.bed_id)}</td>
              <td>${doctorLabel(a.admitting_doctor_id)}</td>
              <td>${formatDateTime(a.admitted_at)}</td>
              <td style="display:flex; gap:6px; flex-wrap:wrap;">
                <button class="btn btn-primary btn-sm" onclick="openMarHistory(${a.id})">View MAR</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

let administerTargetAdmissionId = null;

function openAdministerModal(admissionId) {
  administerTargetAdmissionId = admissionId;
  const select = document.getElementById('administer-medicine-select');
  const inStock = allMedicines.filter(m => m.stock_qty > 0);
  select.innerHTML = inStock.length
    ? inStock.map(m => `<option value="${m.id}">${Utils.escapeHtml(m.name)} (${m.stock_qty} ${Utils.escapeHtml(m.unit)} left)</option>`).join('')
    : '<option value="">No medicines in stock</option>';
  document.getElementById('administer-scheduled-time').value = '';
  const __admModal = document.getElementById('administer-modal');
  if (__admModal) {
    __admModal.style.zIndex = '2600';
    document.body.appendChild(__admModal);
    __admModal.classList.add('active');
  }
}

function closeAdministerModal() {
  document.getElementById('administer-modal').classList.remove('active');
  administerTargetAdmissionId = null;
}

async function confirmAdminister() {
  if (!administerTargetAdmissionId) return;
  const medicineId = document.getElementById('administer-medicine-select').value;
  const scheduledTime = document.getElementById('administer-scheduled-time').value;

  if (!medicineId) {
    Utils.showToast('Please select a medicine', 'error');
    return;
  }

  try {
    await API.post(`/pharmacy/admissions/${administerTargetAdmissionId}/administer`, {
      medicine_id: parseInt(medicineId, 10),
      scheduled_time: scheduledTime ? new Date(scheduledTime).toISOString() : null,
    });
    Utils.showToast('Dose logged', 'success');
    const admissionId = administerTargetAdmissionId;
    closeAdministerModal();
    const medicines = await API.get('/pharmacy/medicines').catch(() => allMedicines);
    allMedicines = medicines || allMedicines;
    medicinesById = Object.fromEntries(allMedicines.map(m => [m.id, m]));
    if (document.getElementById('mar-history-modal').classList.contains('active')) {
      openMarHistory(admissionId);
    }
  } catch (error) {
    console.error('Failed to log administration:', error);
    Utils.showToast(error.message || 'Failed to log administration', 'error');
  }
}

let currentMarAdmissionId = null;

async function openMarHistory(admissionId) {
  currentMarAdmissionId = admissionId;
  const admission = currentAdmittedEntries.find(a => a.id === admissionId);
  document.getElementById('mar-history-title').textContent = admission
    ? `${patientLabel(admission.patient_id)} — Ward MAR (today)`
    : 'Medication Administration Record';

  const body = document.getElementById('mar-history-body');
  body.innerHTML = '<div class="loading-spinner">Loading nursing MAR...</div>';
  document.getElementById('mar-history-modal').classList.add('active');

  try {
    // Live MAR from nursing course doses (not the old empty administrations log)
    let doses = [];
    let summary = null;
    try {
      const res = await API.get(`/nursing/admissions/${admissionId}/doses`);
      const data = res?.data || res;
      doses = Array.isArray(data) ? data : (data?.doses || []);
    } catch (e) {
      const res = await API.get(`/nursing/admissions/${admissionId}/compliance`).catch(() => null);
      summary = res?.data || res || {};
      doses = summary.doses || [];
    }
    if (!Array.isArray(doses)) doses = [];

    // Also show pending pharmacy orders for this patient
    let pendingForPatient = [];
    try {
      const patientId = admission?.patient_id;
      if (patientId) {
        const orders = await API.get(`/pharmacy/orders/patient/${patientId}`).catch(() => []);
        const list = Array.isArray(orders) ? orders : (orders?.data || []);
        pendingForPatient = list.filter(o => (o.status || '') === 'pending');
      }
    } catch (e) { /* ignore */ }

    if (!doses.length && !pendingForPatient.length) {
      body.innerHTML = `
        <p style="color: var(--text-light); text-align:center; padding:20px;">
          No ward course doses for today and no pending pharmacy lines.<br>
          <span style="font-size:13px;">Doctor must set a medication course first; then dispense from Pending Orders.</span>
        </p>`;
      return;
    }

    const given = doses.filter(d => d.status === 'given').length;
    const pending = doses.filter(d => d.status === 'pending').length;
    const held = doses.filter(d => d.status === 'held').length;
    const missed = doses.filter(d => d.status === 'missed' || d.status === 'skipped').length;

    let html = `
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
        <span class="badge badge-success">Given ${given}</span>
        <span class="badge badge-warning">Pending nurse ${pending}</span>
        <span class="badge">Held ${held}</span>
        <span class="badge badge-danger">Missed ${missed}</span>
        <span class="badge badge-info">Pharmacy pending ${pendingForPatient.length}</span>
      </div>`;

    if (pendingForPatient.length) {
      html += `<h4 style="font-size:14px;margin:8px 0;">Awaiting your dispense</h4>
        <div class="table-responsive"><table class="table">
          <thead><tr><th>Medicine</th><th>Form</th><th>Qty</th><th>Status</th></tr></thead>
          <tbody>
            ${pendingForPatient.map(o => `
              <tr>
                <td><strong>${Utils.escapeHtml(o.medicine_name || '—')}</strong></td>
                <td>${Utils.escapeHtml((o.form || '—').toString().toUpperCase())}</td>
                <td>${o.quantity || 1}</td>
                <td><span class="badge badge-warning">PENDING DISPENSE</span></td>
              </tr>`).join('')}
          </tbody></table></div>
          <p style="font-size:13px;color:var(--text-light);">Go to <strong>Pending Orders</strong> and dispense — nurses cannot mark Given until you do.</p>`;
    }

    if (doses.length) {
      html += `<h4 style="font-size:14px;margin:12px 0 8px;">Today's nursing MAR</h4>
        <div class="table-responsive"><table class="table">
          <thead><tr><th>Time</th><th>Medicine</th><th>Dose</th><th>Status</th><th>Pharmacy</th><th>Given at</th></tr></thead>
          <tbody>
            ${doses.map(d => {
              const st = (d.status || 'pending').toLowerCase();
              const badge = st === 'given' ? 'badge-success' : st === 'pending' ? 'badge-warning' : 'badge-info';
              const ph = d.pharmacy_ready === false
                ? '<span class="badge badge-warning">Awaiting dispense</span>'
                : (d.pharmacy_status === 'dispensed' || d.pharmacy_ready
                    ? '<span class="badge badge-success">Dispensed</span>'
                    : '—');
              return `<tr>
                <td>${Utils.escapeHtml(d.scheduled_time || '—')}</td>
                <td><strong>${Utils.escapeHtml(d.medicine_name || '—')}</strong></td>
                <td>${Utils.escapeHtml(d.dosage || '')} · ${Utils.escapeHtml(d.route || '')}</td>
                <td><span class="badge ${badge}">${Utils.escapeHtml(st.toUpperCase())}</span></td>
                <td>${ph}</td>
                <td style="font-size:12px;">${d.given_at ? formatDateTime(d.given_at) : '—'}</td>
              </tr>`;
            }).join('')}
          </tbody></table></div>`;
    }

    body.innerHTML = html;
  } catch (error) {
    console.error('Failed to load MAR history:', error);
    body.innerHTML = '<p style="color: var(--text-light); text-align:center; padding:20px;">Failed to load MAR. ' + Utils.escapeHtml(error.message || '') + '</p>';
  }
}

function closeMarHistoryModal() {
  document.getElementById('mar-history-modal').classList.remove('active');
  currentMarAdmissionId = null;
}

function openAdministerModalForCurrent() {
  if (!currentMarAdmissionId) return;
  openAdministerModal(currentMarAdmissionId);
}

// ═════════════════════════════════════════════════════════════
// Dispense History
// ═════════════════════════════════════════════════════════════
async function loadHistory() {
  const el = document.getElementById('history-list');
  el.innerHTML = '<div class="loading-spinner">Loading history...</div>';
  try {
    // No single "all orders" endpoint is exposed — build history from
    // every patient this clinic knows about, same fallback pattern used
    // for admission discharge history.
    const results = await Promise.all(
      allPatients.map(p => API.get(`/pharmacy/orders/patient/${p.id}`).catch(() => []))
    );
    const history = results.flat().filter(o => o.status === 'dispensed' || o.status === 'out_of_stock' || o.status === 'cancelled');
    history.sort((a, b) => new Date(b.dispensed_at || b.created_at) - new Date(a.dispensed_at || a.created_at));
    renderHistory(history);
  } catch (error) {
    console.error('Failed to load dispense history:', error);
    el.innerHTML = '<p style="color: var(--text-light); text-align:center; padding:20px;">Failed to load history.</p>';
  }
}

function renderHistory(history) {
  const el = document.getElementById('history-list');
  if (history.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No dispense history yet.</p>';
    return;
  }
  el.innerHTML = `
    <div class="table-responsive">
      <table class="table">
        <thead><tr><th>Patient</th><th>Medicine</th><th>Status</th><th>Dispensed By</th><th>Dispensed At</th></tr></thead>
        <tbody>
          ${history.map(o => `
            <tr>
              <td><strong>${Utils.escapeHtml(o.patient_name || patientLabel(o.patient_id))}</strong></td>
              <td>${Utils.escapeHtml(o.medicine_name || '—')}</td>
              <td>${orderStatusBadge(o.status)}</td>
              <td>${staffLabel(o.dispensed_by)}</td>
              <td>${o.dispensed_at ? formatDateTime(o.dispensed_at) : '—'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function logout() {
  Auth.clear();
  window.location.replace('login.html?force=1');
}

// ═════════════════════════════════════════════════════════════
// Walk-in / OTC counter sale
// ═════════════════════════════════════════════════════════════
async function loadWalkInPage() {
  await Promise.all([populateWalkInDoctors(), populateWalkInMedicines(), loadWalkInSales()]);
  await populateWalkInPatients(); // after doctors; filters when doctor changes
}



let _walkinAllPatients = [];
let _walkinAllAppointments = [];

async function populateWalkInDoctors() {
  const sel = document.getElementById('walkin-doctor');
  if (!sel) return;
  try {
    const res = await API.get('/doctors');
    const doctors = Array.isArray(res) ? res : (res?.data || []);
    const cur = sel.value;
    sel.innerHTML = '<option value="">— All patients / guest —</option>' +
      doctors.map(d => {
        const name = d.full_name || d.name || ('Doctor #' + d.id);
        const spec = d.specialization ? ` — ${d.specialization}` : '';
        return `<option value="${d.id}">${escapeHtml(name)}${escapeHtml(spec)}</option>`;
      }).join('');
    if (cur) sel.value = cur;
    sel.onchange = () => populateWalkInPatients();
  } catch (e) {
    console.warn('walkin doctors', e);
  }
}

async function populateWalkInPatients() {
  const sel = document.getElementById('walkin-patient');
  if (!sel) return;
  try {
    if (!_walkinAllPatients.length) {
      const res = await API.get('/patients');
      _walkinAllPatients = Array.isArray(res) ? res : (res?.data || []);
    }
    try {
      if (!_walkinAllAppointments.length) {
        const ar = await API.get('/appointments');
        _walkinAllAppointments = Array.isArray(ar) ? ar : (ar?.data || []);
      }
    } catch (_) { /* appointments optional for filter */ }

    const doctorId = document.getElementById('walkin-doctor')?.value || '';
    let patients = _walkinAllPatients.slice();
    if (doctorId) {
      const ids = new Set(
        (_walkinAllAppointments || [])
          .filter(a => String(a.doctor_id) === String(doctorId) || String(a.doctorId) === String(doctorId))
          .map(a => a.patient_id || a.patientId)
          .filter(Boolean)
          .map(String)
      );
      // If appointment filter finds anyone, use it; else show all (still selectable)
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
      const p = _walkinAllPatients.find(x => String(x.id) === String(id));
      if (!p) return;
      const nameEl = document.getElementById('walkin-customer');
      const phoneEl = document.getElementById('walkin-phone');
      if (nameEl) nameEl.value = p.name || p.full_name || '';
      if (phoneEl) phoneEl.value = p.phone || p.phone_number || '';
    };
  } catch (e) {
    console.warn('walkin patients', e);
  }
}

async function populateWalkInMedicines() {
  const sel = document.getElementById('walkin-medicine');
  if (!sel) return;
  try {
    const meds = await API.get('/pharmacy/medicines');
    const list = Array.isArray(meds) ? meds : (meds?.data || []);
    const cur = sel.value;
    sel.innerHTML = '<option value="">Select medicine</option>' +
      list
        .slice()
        .sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')))
        .map(m => {
          const stock = m.stock_qty ?? 0;
          const form = m.form ? ` · ${m.form}` : '';
          return `<option value="${m.id}" data-stock="${stock}">${escapeHtml(m.name)}${form} (stock: ${stock})</option>`;
        })
        .join('');
    if (cur) sel.value = cur;
  } catch (e) {
    console.warn('walkin medicines', e);
  }
}

async function loadWalkInSales() {
  const el = document.getElementById('walkin-list');
  if (!el) return;
  el.innerHTML = '<div class="loading-spinner">Loading...</div>';
  try {
    const rows = await API.get('/pharmacy/walk-in?limit=50');
    const list = Array.isArray(rows) ? rows : (rows?.data || []);
    if (!list.length) {
      el.innerHTML = '<div class="empty-state">No walk-in sales yet.</div>';
      return;
    }
    el.innerHTML = `<div class="table-responsive"><table class="table">
      <thead><tr>
        <th>#</th><th>When</th><th>Medicine</th><th>Qty</th>
        <th>Customer</th><th>Total</th><th>Notes</th>
      </tr></thead>
      <tbody>${list.map(s => {
        const when = s.created_at ? new Date(s.created_at).toLocaleString() : '—';
        const cust = s.customer_name || (s.patient_id ? ('Patient #' + s.patient_id) : '—');
        const phone = s.customer_phone ? ` · ${escapeHtml(s.customer_phone)}` : '';
        const reg = s.patient_id ? ` <span class="badge badge-info">Registered #${s.patient_id}</span>` : '';
        return `<tr>
          <td>${s.id}</td>
          <td>${escapeHtml(when)}</td>
          <td><strong>${escapeHtml(s.medicine_name || ('#' + s.medicine_id))}</strong>
            ${s.form ? `<div style="font-size:12px;color:var(--text-light)">${escapeHtml(s.form)}</div>` : ''}</td>
          <td>${s.quantity}</td>
          <td>${escapeHtml(cust)}${phone}${reg}</td>
          <td>${Number(s.total_price || 0).toFixed(2)}</td>
          <td>${escapeHtml(s.notes || '—')}</td>
        </tr>`;
      }).join('')}</tbody></table></div>`;
  } catch (e) {
    el.innerHTML = `<div class="empty-state">${escapeHtml(e.message || String(e))}</div>`;
  }
}

async function submitWalkInSale(e) {
  e.preventDefault();
  const msg = document.getElementById('walkin-msg');
  const btn = document.getElementById('walkin-submit-btn');
  const patientVal = document.getElementById('walkin-patient')?.value || '';
  const medicine_id = parseInt(document.getElementById('walkin-medicine').value, 10);
  const quantity = parseInt(document.getElementById('walkin-qty').value, 10);
  const customer_name = document.getElementById('walkin-customer').value.trim();
  const customer_phone = document.getElementById('walkin-phone').value.trim();
  const notes = document.getElementById('walkin-notes').value.trim();

  if (!medicine_id || !quantity || quantity < 1) {
    if (msg) {
      msg.style.display = 'block';
      msg.className = 'alert alert-error';
      msg.textContent = 'Select a medicine and enter quantity.';
    }
    return;
  }

  if (btn) btn.disabled = true;
  try {
    const res = await API.post('/pharmacy/walk-in', {
      medicine_id,
      quantity,
      patient_id: patientVal ? parseInt(patientVal, 10) : null,
      customer_name: customer_name || null,
      customer_phone: customer_phone || null,
      notes: notes || null,
    });
    if (msg) {
      msg.style.display = 'block';
      msg.className = 'alert alert-success';
      const name = res?.medicine_name || 'Medicine';
      msg.textContent = `Dispensed ${quantity} × ${name}. Stock updated. Total: ${Number(res?.total_price || 0).toFixed(2)}`;
    }
    document.getElementById('walkin-qty').value = '1';
    document.getElementById('walkin-customer').value = '';
    document.getElementById('walkin-phone').value = '';
    document.getElementById('walkin-notes').value = '';
    const psel = document.getElementById('walkin-patient');
    if (psel) psel.value = '';
    const dsel = document.getElementById('walkin-doctor');
    if (dsel) dsel.value = '';
    await populateWalkInMedicines();
    await loadWalkInSales();
    if (typeof loadInventory === 'function') {
      try { loadInventory(); } catch (_) {}
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

