let selectedPatient = null;
let currentPreview = null;
let currentBill = null;
let searchCache = {};

const CATEGORY_LABELS = {
  consultation: 'Doctor Fees',
  medicine: 'Medicines',
  lab: 'Laboratory Tests',
  bed: 'Bed / Ward Charges',
  nursing: 'Nursing Services',
  other: 'Other',
};

document.addEventListener('DOMContentLoaded', () => {
  if (!Auth.isAuthenticated()) {
    window.location.replace('login.html?redirect=billing-portal.html');
    return;
  }
  const role = Auth.getRole();
  if (!['billing', 'admin', 'receptionist'].includes(role)) {
    alert('Billing access only');
    window.location.replace('login.html?force=1');
    return;
  }
  if (typeof injectAdminBackButton === 'function') injectAdminBackButton();
  if (typeof setupSessionGuards === 'function') setupSessionGuards();
  const user = Auth.getUser();
  if (user) {
    document.getElementById('user-name').textContent = user.username || 'Billing';
    const greet = document.getElementById('dashboard-greeting-name');
    if (greet) greet.textContent = user.username || user.name || greet.textContent;
    const dateEl = document.getElementById('dashboard-date');
    if (dateEl) {
      dateEl.textContent = new Date().toLocaleDateString(undefined, {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
      });
    }

    document.getElementById('user-role').textContent = (user.role || 'billing').toUpperCase();
    document.getElementById('user-info').style.display = 'block';
  }

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

  document.getElementById('patient-query')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') searchPatients();
  });
});

function logout() {
  Auth.clear();
  window.location.replace('login.html?force=1');
}

function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
  const page = document.getElementById('page-' + name);
  if (page) page.classList.add('active');
  const link = document.querySelector(`.sidebar-link[data-page="${name}"]`);
  if (link) link.classList.add('active');
  if (name === 'bills') loadBills();
}

function money(n) {
  const v = Number(n) || 0;
  return 'PKR ' + v.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function searchPatients() {
  const q = document.getElementById('patient-query')?.value?.trim();
  if (!q) {
    Utils.showToast('Enter a name, phone, or patient ID', 'error');
    return;
  }
  const el = document.getElementById('patient-results');
  el.innerHTML = '<div class="loading-spinner">Searching...</div>';
  try {
    const res = await API.get(`/billing/patients/search?q=${encodeURIComponent(q)}`);
    const list = Array.isArray(res) ? res : (res?.data || []);
    if (window.PortalUI && list) {
      PortalUI.ensureChartJs(function () {
        const weekly = PortalUI.weeklyCounts(list, 'issued_at');
        PortalUI.lineChart('portal-trend-chart', weekly.labels, weekly.data, 'Bills');
        let issued = 0, paid = 0, cancelled = 0;
        list.forEach(b => {
          const s = (b.status || '').toLowerCase();
          if (s === 'paid') paid++;
          else if (s === 'cancelled') cancelled++;
          else issued++;
        });
        PortalUI.doughnutChart('portal-status-chart', ['Issued', 'Paid', 'Cancelled'], [issued, paid, cancelled]);
      });
    }

    if (!list.length) {
      el.innerHTML = '<p style="color:var(--text-light);">No patients matched. Check the phone number or name.</p>';
      return;
    }
    searchCache = {};
    list.forEach(p => { searchCache[p.id] = p; });
    el.innerHTML = list.map(p => `
      <div class="patient-chip ${selectedPatient && selectedPatient.id === p.id ? 'active' : ''}"
           onclick="selectPatient(${p.id})">
        <div>
          <div style="font-weight:600;">${escapeHtml(p.name)}</div>
          <div style="font-size:12px;color:var(--text-light);">
            #${p.id} · ${escapeHtml(p.phone || '—')}
            ${p.email ? ' · ' + escapeHtml(p.email) : ''}
            ${p.care_type ? ' · ' + escapeHtml(String(p.care_type).toUpperCase()) : ''}
          </div>
        </div>
        <span class="btn btn-ghost btn-sm">Select</span>
      </div>
    `).join('');
  } catch (e) {
    el.innerHTML = '';
    Utils.showToast(e.message || String(e), 'error');
  }
}

function selectPatient(id) {
  const p = searchCache[id];
  if (!p) return;
  selectedPatient = p;
  document.querySelectorAll('.patient-chip').forEach(c => c.classList.remove('active'));
  document.getElementById('preview-panel').style.display = 'block';
  loadEpisodes().then(() => loadPreview());
}

async function loadEpisodes() {
  if (!selectedPatient) return;
  try {
    const res = await API.get(`/billing/patients/${selectedPatient.id}/episodes`);
    const data = res?.data || res || {};
    const apptSel = document.getElementById('bill-appointment');
    const admSel = document.getElementById('bill-admission');
    if (apptSel) {
      apptSel.innerHTML = '<option value="">All unbilled OPD visits</option>' +
        (data.appointments || []).map(a =>
          `<option value="${a.id}">#${a.id} · ${a.date || ''} ${a.time || ''} · ${a.doctor_name || ''} (${a.status})</option>`
        ).join('');
    }
    if (admSel) {
      admSel.innerHTML = '<option value="">No admission filter</option>' +
        (data.admissions || []).map(a =>
          `<option value="${a.id}">Admission #${a.id} · ${a.status}${a.admitted_at ? ' · ' + a.admitted_at.slice(0,10) : ''}</option>`
        ).join('');
    }
  } catch (e) {
    console.warn('episodes', e);
  }
}


async function loadPreview() {
  if (!selectedPatient) return;
  const discount = Number(document.getElementById('bill-discount')?.value || 0);
  const tax = Number(document.getElementById('bill-tax')?.value || 0);
  const appointment_id = document.getElementById('bill-appointment')?.value || '';
  const admission_id = document.getElementById('bill-admission')?.value || '';
  const unbilled = document.getElementById('bill-unbilled-only')?.checked !== false;
  try {
    let url = `/billing/patients/${selectedPatient.id}/preview?discount=${discount}&tax=${tax}&unbilled_only=${unbilled}`;
    if (appointment_id) url += `&appointment_id=${appointment_id}`;
    if (admission_id) url += `&admission_id=${admission_id}`;
    const res = await API.get(url);
    currentPreview = res?.data || res;
    renderPreview(currentPreview);
  } catch (e) {
    Utils.showToast(e.message || String(e), 'error');
  }
}

function renderItemsTable(items) {
  if (!items || !items.length) {
    return '<p style="color:var(--text-light); text-align:center; padding:24px;">No chargeable services found for this patient yet.</p>';
  }
  // Group by category for readability
  const groups = {};
  items.forEach(i => {
    const c = i.category || 'other';
    if (!groups[c]) groups[c] = [];
    groups[c].push(i);
  });
  let html = '';
  for (const [cat, rows] of Object.entries(groups)) {
    html += `<div style="margin:14px 0 6px; font-weight:700; font-size:13px; color:var(--charcoal);">
      ${escapeHtml(CATEGORY_LABELS[cat] || cat)}
    </div>`;
    html += `<table><thead><tr>
      <th style="width:42%;">Description</th>
      <th>Details</th>
      <th style="text-align:right;">Qty</th>
      <th style="text-align:right;">Unit</th>
      <th style="text-align:right;">Amount</th>
    </tr></thead><tbody>`;
    rows.forEach(i => {
      html += `<tr>
        <td><strong>${escapeHtml(i.description)}</strong></td>
        <td style="color:var(--text-light); font-size:12px;">${escapeHtml(i.details || '')}</td>
        <td style="text-align:right;" class="money">${escapeHtml(i.quantity)}</td>
        <td style="text-align:right;" class="money">${money(i.unit_price)}</td>
        <td style="text-align:right;" class="money">${money(i.amount)}</td>
      </tr>`;
    });
    html += '</tbody></table>';
  }
  return html;
}

function renderTotals(data) {
  const cats = data.category_totals || {};
  let catRows = Object.entries(cats).map(([k, v]) =>
    `<div class="row"><span>${escapeHtml(CATEGORY_LABELS[k] || k)}</span><span class="money">${money(v)}</span></div>`
  ).join('');
  return `
    ${catRows}
    <div class="row"><span>Subtotal</span><span class="money">${money(data.subtotal)}</span></div>
    <div class="row"><span>Discount</span><span class="money">− ${money(data.discount)}</span></div>
    <div class="row"><span>Tax</span><span class="money">${money(data.tax)}</span></div>
    <div class="row grand"><span>Total Due</span><span class="money">${money(data.total)}</span></div>
  `;
}

function renderPreview(data) {
  document.getElementById('preview-patient-block').innerHTML = `
    <strong>Patient:</strong> ${escapeHtml(data.patient_name)} (#${data.patient_id})<br>
    <strong>Phone:</strong> ${escapeHtml(data.patient_phone || '—')}<br>
    ${data.patient_email ? `<strong>Email:</strong> ${escapeHtml(data.patient_email)}<br>` : ''}
  `;
  document.getElementById('preview-items').innerHTML = renderItemsTable(data.items);
  document.getElementById('preview-totals').innerHTML = renderTotals(data);

  const warn = document.getElementById('preview-warnings');
  if (data.warnings && data.warnings.length) {
    warn.innerHTML = `<div style="background:#fff8e6; border:1px solid #f0d78c; border-radius:8px; padding:10px 12px; font-size:13px;">
      <strong>Pricing notes:</strong>
      <ul style="margin:6px 0 0 18px;">${data.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}</ul>
    </div>`;
  } else {
    warn.innerHTML = '';
  }
}

async function issueBill() {
  if (!selectedPatient) {
    Utils.showToast('Select a patient first', 'error');
    return;
  }
  if (!currentPreview || !currentPreview.items || !currentPreview.items.length) {
    Utils.showToast('Nothing to bill for this patient', 'error');
    return;
  }
  const btn = document.getElementById('btn-issue');
  if (btn) btn.disabled = true;
  try {
    const appt = document.getElementById('bill-appointment')?.value;
    const adm = document.getElementById('bill-admission')?.value;
    const body = {
      patient_id: selectedPatient.id,
      discount: Number(document.getElementById('bill-discount')?.value || 0),
      tax: Number(document.getElementById('bill-tax')?.value || 0),
      notes: document.getElementById('bill-notes')?.value || null,
      appointment_id: appt ? Number(appt) : null,
      admission_id: adm ? Number(adm) : null,
      unbilled_only: document.getElementById('bill-unbilled-only')?.checked !== false,
    };
    const res = await API.post('/billing/bills', body);
    currentBill = res?.data || res;
    Utils.showToast('Bill issued: ' + (currentBill.bill_number || ''), 'success');
    showReceipt(currentBill);
  } catch (e) {
    Utils.showToast(e.message || String(e), 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function loadBills() {
  const status = document.getElementById('bills-status-filter')?.value || '';
  const el = document.getElementById('bills-list');
  el.innerHTML = '<div class="loading-spinner">Loading...</div>';
  try {
    const qs = status ? `?status=${encodeURIComponent(status)}` : '';
    const res = await API.get(`/billing/bills${qs}`);
    const list = Array.isArray(res) ? res : (res?.data || []);
    if (!list.length) {
      el.innerHTML = '<p style="color:var(--text-light); text-align:center; padding:32px;">No bills yet</p>';
      return;
    }
    el.innerHTML = `<div class="table-wrap"><table class="table">
      <thead><tr>
        <th>Bill #</th><th>Patient</th><th>Phone</th><th>Total</th><th>Status</th><th>Issued</th><th></th>
      </tr></thead>
      <tbody>
        ${list.map(b => `<tr>
          <td><strong>${escapeHtml(b.bill_number)}</strong></td>
          <td>${escapeHtml(b.patient_name)} <span style="color:var(--text-light);font-size:12px;">#${b.patient_id}</span></td>
          <td>${escapeHtml(b.patient_phone || '—')}</td>
          <td class="money">${money(b.total)}</td>
          <td><span class="badge ${b.status === 'paid' ? 'badge-success' : b.status === 'cancelled' ? 'badge-danger' : 'badge-warning'}">${escapeHtml((b.status || '').toUpperCase())}</span></td>
          <td style="font-size:12px;">${b.issued_at ? new Date(b.issued_at).toLocaleString() : '—'}</td>
          <td style="white-space:nowrap;">
            <button class="btn btn-ghost btn-sm" type="button" onclick="openBill(${b.id})">View Receipt</button>
            ${b.status === 'issued' ? `<button class="btn btn-primary btn-sm" type="button" onclick="markBillPaid(${b.id})">Mark Paid</button>` : ''}
          </td>
        </tr>`).join('')}
      </tbody></table></div>`;
  } catch (e) {
    el.innerHTML = '<p style="color:var(--text-light);">Failed to load bills</p>';
    Utils.showToast(e.message || String(e), 'error');
  }
}

async function openBill(id) {
  try {
    const res = await API.get(`/billing/bills/${id}`);
    currentBill = res?.data || res;
    showReceipt(currentBill);
  } catch (e) {
    Utils.showToast(e.message || String(e), 'error');
  }
}

function showReceipt(bill) {
  currentBill = bill;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-receipt').classList.add('active');

  document.getElementById('receipt-number').textContent = bill.bill_number || '';
  document.getElementById('receipt-status').innerHTML =
    `<span class="badge ${bill.status === 'paid' ? 'badge-success' : bill.status === 'cancelled' ? 'badge-danger' : 'badge-warning'}">${escapeHtml((bill.status || '').toUpperCase())}</span>`
    + (bill.payment_method ? ` · ${escapeHtml(bill.payment_method)}` : '')
    + (bill.paid_at ? ` · Paid ${new Date(bill.paid_at).toLocaleString()}` : '');

  document.getElementById('receipt-patient').innerHTML = `
    <strong>Patient:</strong> ${escapeHtml(bill.patient_name)} (#${bill.patient_id})<br>
    <strong>Phone:</strong> ${escapeHtml(bill.patient_phone || '—')}<br>
    ${bill.patient_email ? `<strong>Email:</strong> ${escapeHtml(bill.patient_email)}<br>` : ''}
    <strong>Issued:</strong> ${bill.issued_at ? new Date(bill.issued_at).toLocaleString() : '—'}
    ${bill.notes ? `<br><strong>Notes:</strong> ${escapeHtml(bill.notes)}` : ''}
  `;
  document.getElementById('receipt-items').innerHTML = renderItemsTable(bill.items);
  document.getElementById('receipt-totals').innerHTML = renderTotals(bill);

  const payBtn = document.getElementById('btn-mark-paid');
  if (payBtn) {
    payBtn.style.display = bill.status === 'issued' ? '' : 'none';
  }
}

async function markCurrentPaid() {
  if (!currentBill) return;
  await markBillPaid(currentBill.id);
}


async function markBillPaid(billId) {
  try {
    const method = prompt('Payment method (cash / card / transfer / insurance):', 'cash');
    if (method === null) return; // cancelled
    const res = await API.post(`/billing/bills/${billId}/pay`, {
      payment_method: (method || 'cash').trim() || 'cash',
    });
    Utils.showToast('Bill marked as PAID', 'success');
    const bill = res?.data || res;
    // refresh list if on bills page
    if (document.getElementById('page-bills')?.classList.contains('active')) {
      loadBills();
    }
    if (currentBill && currentBill.id === billId) {
      showReceipt(bill);
    }
  } catch (e) {
    Utils.showToast(e.message || String(e), 'error');
  }
}
