// Admission Portal (Admission Head / Bed Manager) Functionality
let allWards = [];
let allBeds = [];
let bedMap = [];
let pendingRequests = [];
let allDoctors = [];
let allPatients = [];

let patientsById = {};
let doctorsById = {};

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

async function ensureDirectoriesLoaded() {
  try {
    const [patients, doctors] = await Promise.all([
      API.get('/patients/').catch(() => []),
      API.get('/doctors/').catch(() => []),
    ]);
    allPatients = patients || [];
    allDoctors = doctors || [];
    patientsById = Object.fromEntries(allPatients.map(p => [p.id, p]));
    doctorsById = Object.fromEntries(allDoctors.map(d => [d.id, d]));
  } catch (error) {
    console.error('Failed to load patient/doctor directory:', error);
  }
}

document.addEventListener('DOMContentLoaded', async function() {
  const isRedirecting = sessionStorage.getItem('auth_redirecting');

  const role = Auth.getRole();
  if (!Auth.isAuthenticated() || (role !== 'admission_head' && role !== 'admin')) {
    if (!isRedirecting) {
      sessionStorage.setItem('auth_redirecting', 'true');
      window.location.replace('login.html?redirect=admission-portal.html');
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
    const greet = document.getElementById('dashboard-greeting-name');
    if (greet) greet.textContent = user.username || user.name || greet.textContent;
    const dateEl = document.getElementById('dashboard-date');
    if (dateEl) {
      dateEl.textContent = new Date().toLocaleDateString(undefined, {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
      });
    }

    document.getElementById('user-role').textContent = 'Admission Head';
    document.getElementById('user-info').style.display = 'block';
  }
}

function setupNotificationBanner() {
  const banner = document.getElementById('notif-permission-banner');
  if (!banner) return;

  const dismissed = sessionStorage.getItem('ap_notif_banner_dismissed');
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
    sessionStorage.setItem('ap_notif_banner_dismissed', 'true');
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

  document.getElementById('search-admitted')?.addEventListener('input', renderAdmittedList);
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
    case 'requests':
      loadPendingRequests();
      break;
    case 'bedmap':
      loadBedMap();
      break;
    case 'wards':
      loadWardsAndBeds();
      break;
    case 'admitted':
      loadAdmitted();
      break;
    case 'nurses':
      loadNursePage();
      break;
    case 'history':
      loadHistory();
      break;
  }
}

// ═════════════════════════════════════════════════════════════
// Dashboard
// ═════════════════════════════════════════════════════════════
async function loadDashboard() {
  try {
    const [wards, beds, bedMapData, pending] = await Promise.all([
      API.get('/admissions/wards'),
      API.get('/admissions/beds'),
      API.get('/admissions/bed-map'),
      API.get('/admissions/requests/pending'),
    ]);
    allWards = wards || [];
    allBeds = beds || [];
    bedMap = bedMapData || [];
    pendingRequests = pending || [];

    document.getElementById('stat-total-wards').textContent = allWards.length;
    document.getElementById('stat-total-beds').textContent = allBeds.length;
    document.getElementById('stat-vacant-beds').textContent = allBeds.filter(b => b.status === 'vacant').length;
    document.getElementById('stat-occupied-beds').textContent = allBeds.filter(b => b.status === 'occupied').length;
    document.getElementById('stat-pending-requests').textContent = pendingRequests.length;

    if (window.PortalUI) {
      PortalUI.ensureChartJs(function () {
        const vacant = allBeds.filter(b => b.status === 'vacant').length;
        const occupied = allBeds.filter(b => b.status === 'occupied').length;
        PortalUI.lineChart(
          'portal-trend-chart',
          ['Wards', 'Beds', 'Vacant', 'Occupied', 'Requests'],
          [allWards.length, allBeds.length, vacant, occupied, pendingRequests.length],
          'Capacity'
        );
        PortalUI.doughnutChart(
          'portal-status-chart',
          ['Vacant', 'Occupied', 'Other'],
          [vacant, occupied, Math.max(0, allBeds.length - vacant - occupied)]
        );
        // occupancy scale under charts if container exists
        let scaleHost = document.getElementById('occupancy-scale');
        if (!scaleHost) {
          const grid = document.querySelector('#page-dashboard .dashboard-grid');
          if (grid) {
            scaleHost = document.createElement('div');
            scaleHost.id = 'occupancy-scale';
            scaleHost.className = 'card';
            scaleHost.style.marginTop = '16px';
            scaleHost.style.padding = '18px 22px';
            grid.parentElement.insertBefore(scaleHost, grid.nextSibling);
          }
        }
        if (scaleHost && allBeds.length) {
          const pct = Math.round((occupied / allBeds.length) * 100);
          const cls = pct >= 90 ? 'is-danger' : pct >= 70 ? 'is-warn' : '';
          scaleHost.innerHTML = `
            <div class="metric-scale">
              <div class="metric-scale-label"><span>Bed occupancy</span><span>${pct}% · ${occupied}/${allBeds.length}</span></div>
              <div class="metric-scale-track"><div class="metric-scale-fill ${cls}" style="width:${pct}%"></div></div>
            </div>`;
        }
      });
    }

    updatePendingBadge();
    renderDashboardPending();
    renderDashboardBedMapPreview();
  } catch (error) {
    console.error('Failed to load dashboard:', error);
    Utils.showToast('Failed to load dashboard', 'error');
  }
}

function updatePendingBadge() {
  const badge = document.getElementById('pending-count-badge');
  if (!badge) return;
  if (pendingRequests.length > 0) {
    badge.textContent = pendingRequests.length;
    badge.style.display = 'inline-flex';
  } else {
    badge.style.display = 'none';
  }
}

function urgencyBadge(urgency) {
  const map = { routine: 'badge-info', urgent: 'badge-warning', emergency: 'badge-danger' };
  const cls = map[urgency] || 'badge-info';
  return `<span class="badge ${cls}">${Utils.escapeHtml((urgency || '').toUpperCase())}</span>`;
}

function conditionBadge(flag) {
  if (!flag) return '<span class="badge badge-info">—</span>';
  const cls = flag === 'critical' ? 'badge-danger' : 'badge-success';
  return `<span class="badge ${cls}">${Utils.escapeHtml(flag.toUpperCase())}</span>`;
}

function renderDashboardPending() {
  const el = document.getElementById('dashboard-pending-list');
  const top = pendingRequests.slice(0, 5);
  if (top.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No pending admission requests. All caught up!</p>';
    return;
  }
  el.innerHTML = `
    <div class="table-responsive">
      <table class="table">
        <thead>
          <tr><th>Patient</th><th>Requesting Doctor</th><th>Urgency</th><th>Preferred Ward</th><th>Requested</th><th>Action</th></tr>
        </thead>
        <tbody>
          ${top.map(r => `
            <tr>
              <td><strong>${patientLabel(r.patient_id)}</strong></td>
              <td>${doctorLabel(r.requesting_doctor_id)}</td>
              <td>${urgencyBadge(r.urgency)}</td>
              <td>${Utils.escapeHtml(r.preferred_ward_type || 'Any')}</td>
              <td>${formatDateTime(r.requested_at)}</td>
              <td><button class="btn btn-primary btn-sm" onclick="openAllocateModal(${r.id})">Allocate Bed</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderDashboardBedMapPreview() {
  const el = document.getElementById('dashboard-bedmap-preview');
  if (bedMap.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No beds configured yet. Add wards and beds under "Wards &amp; Beds".</p>';
    return;
  }
  el.innerHTML = renderBedGrid(bedMap.slice(0, 12));
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

// ═════════════════════════════════════════════════════════════
// Admission Requests Queue
// ═════════════════════════════════════════════════════════════
async function loadPendingRequests() {
  try {
    pendingRequests = await API.get('/admissions/requests/pending');
    updatePendingBadge();
    renderPendingRequests();
  } catch (error) {
    console.error('Failed to load pending requests:', error);
    document.getElementById('requests-list').innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">Failed to load requests.</p>';
  }
}

function renderPendingRequests() {
  const el = document.getElementById('requests-list');
  if (pendingRequests.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No pending admission requests.</p>';
    return;
  }

  el.innerHTML = `
    <div class="table-responsive">
      <table class="table">
        <thead>
          <tr>
            <th>Patient</th><th>Requesting Doctor</th><th>Reason</th><th>Urgency</th>
            <th>Preferred Ward</th><th>Requested</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${pendingRequests.map(r => `
            <tr>
              <td><strong>${patientLabel(r.patient_id)}</strong></td>
              <td>${doctorLabel(r.requesting_doctor_id)}</td>
              <td>${Utils.escapeHtml(r.reason || '—')}</td>
              <td>${urgencyBadge(r.urgency)}</td>
              <td>${Utils.escapeHtml(r.preferred_ward_type || 'Any')}</td>
              <td>${formatDateTime(r.requested_at)}</td>
              <td style="display:flex; gap:6px; flex-wrap:wrap;">
                <button class="btn btn-ghost btn-sm" onclick="viewRequestContext(${r.id})">View EMR</button>
                <button class="btn btn-primary btn-sm" onclick="openAllocateModal(${r.id})">Allocate Bed</button>
                <button class="btn btn-ghost btn-sm" style="color:var(--danger,#b91c1c);" onclick="cancelAdmissionRequest(${r.id})">Cancel</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

async function viewRequestContext(admissionId) {
  const request = pendingRequests.find(r => r.id === admissionId) || (await API.get(`/admissions/${admissionId}`));
  await showAdmissionDetail(request, { readOnly: true });
}

// Read-only EMR context pulled from the existing EMR service — never
// re-entered by the Admission Head. Mirrors everything the treating doctor
// can see for this patient (prescriptions, diagnoses, doctor notes, and
// reports shared to that doctor), not just allergies/history/vitals, so the
// Admission Head has the full clinical picture before allocating a bed.
async function buildEMRContextHtml(patientId) {
  try {
    const timeline = await API.get(`/emr/patients/${patientId}/timeline`);
    currentAdmissionEMRData = timeline;
    const latestVital = (timeline.vitals || [])[0];
    return `
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(220px,1fr)); gap:16px; margin-top:12px;">
        <div>
          <h4 style="font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:var(--text-light); margin-bottom:8px;">Allergies</h4>
          ${(timeline.allergies || []).length
            ? `<ul style="padding-left:18px; font-size:14px;">${timeline.allergies.map(a => `<li>${Utils.escapeHtml(a.allergy_name)}${a.reaction ? ` — ${Utils.escapeHtml(a.reaction)}` : ''}</li>`).join('')}</ul>`
            : '<p style="color:var(--text-light); font-size:14px;">No known allergies recorded.</p>'}
        </div>
        <div>
          <h4 style="font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:var(--text-light); margin-bottom:8px;">Medical History</h4>
          ${(timeline.medical_history || []).length
            ? `<ul style="padding-left:18px; font-size:14px;">${timeline.medical_history.map(h => `<li>${Utils.escapeHtml(h.condition || h.notes || 'Record')}</li>`).join('')}</ul>`
            : '<p style="color:var(--text-light); font-size:14px;">No medical history recorded.</p>'}
        </div>
        <div>
          <h4 style="font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:var(--text-light); margin-bottom:8px;">Latest Vitals</h4>
          ${latestVital
            ? `<p style="font-size:14px; line-height:1.7;">
                 BP: ${Utils.escapeHtml(latestVital.blood_pressure || '—')}<br>
                 Pulse: ${latestVital.pulse ?? '—'}<br>
                 Temp: ${latestVital.temperature ?? '—'}&deg;<br>
                 O₂: ${latestVital.oxygen_level ?? '—'}%
               </p>`
            : '<p style="color:var(--text-light); font-size:14px;">No vitals recorded.</p>'}
        </div>
      </div>

      <div style="margin-top:20px;">
        <h4 style="font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:var(--text-light); margin-bottom:8px;">Diagnoses</h4>
        ${(timeline.diagnoses || []).length
          ? `<div class="table-responsive"><table class="table">
               <thead><tr><th>Date</th><th>Diagnosis</th><th>Severity</th><th>Notes</th></tr></thead>
               <tbody>
                 ${timeline.diagnoses.map(d => `
                   <tr>
                     <td>${Utils.formatDate(d.diagnosis_date)}</td>
                     <td><strong>${Utils.escapeHtml(d.diagnosis_name)}</strong></td>
                     <td><span class="badge badge-${d.severity === 'critical' || d.severity === 'severe' ? 'danger' : d.severity === 'moderate' ? 'warning' : 'info'}">${Utils.escapeHtml(d.severity || '—')}</span></td>
                     <td>${Utils.escapeHtml(d.notes || '—')}</td>
                   </tr>
                 `).join('')}
               </tbody>
             </table></div>`
          : '<p style="color:var(--text-light); font-size:14px;">No diagnoses recorded.</p>'}
      </div>

      <div style="margin-top:20px;">
        <h4 style="font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:var(--text-light); margin-bottom:8px;">Prescriptions</h4>
        ${(timeline.prescriptions || []).length
          ? `<div class="table-responsive"><table class="table">
               <thead><tr><th>Date</th><th>Medication</th><th>Dosage</th><th>Frequency</th><th>Duration</th><th>Doctor</th></tr></thead>
               <tbody>
                 ${timeline.prescriptions.flatMap(p => {
                   const items = (p.items && p.items.length) ? p.items : [{ medicine_name: '—', dosage: '', frequency: '', duration: '' }];
                   return items.map(item => `
                     <tr>
                       <td>${Utils.formatDate(p.created_at)}</td>
                       <td><strong>${Utils.escapeHtml(item.medicine_name)}</strong></td>
                       <td>${Utils.escapeHtml(item.dosage || '—')}</td>
                       <td>${Utils.escapeHtml(item.frequency || '—')}</td>
                       <td>${Utils.escapeHtml(item.duration || '—')}</td>
                       <td>${doctorLabel(p.doctor_id)}</td>
                     </tr>
                   `);
                 }).join('')}
               </tbody>
             </table></div>`
          : '<p style="color:var(--text-light); font-size:14px;">No prescriptions recorded.</p>'}
      </div>

      <div style="margin-top:20px;">
        <h4 style="font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:var(--text-light); margin-bottom:8px;">Doctor Notes</h4>
        ${(timeline.doctor_notes || []).length
          ? timeline.doctor_notes.map(n => `
              <div style="padding: 12px 14px; background: var(--bg-alt); border-radius: 8px; margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                  <strong style="font-size: 13px;">${doctorLabel(n.doctor_id)}</strong>
                  <span style="font-size: 12px; color: var(--text-light);">${Utils.formatDate(n.note_date)}</span>
                </div>
                <p style="font-size: 13px; line-height: 1.6; white-space: pre-wrap;">${Utils.escapeHtml(n.note_text)}</p>
              </div>
            `).join('')
          : '<p style="color:var(--text-light); font-size:14px;">No doctor notes recorded.</p>'}
      </div>

      <div style="margin-top:20px;">
        <h4 style="font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:var(--text-light); margin-bottom:8px;">Reports Shared With Doctors</h4>
        ${(timeline.reports || []).length
          ? `<div class="table-responsive"><table class="table">
               <thead><tr><th>Name</th><th>Type</th><th>Uploaded</th><th>Actions</th></tr></thead>
               <tbody>
                 ${timeline.reports.map(r => `
                   <tr>
                     <td><strong>${Utils.escapeHtml(r.report_name)}</strong></td>
                     <td><span class="badge badge-info">${Utils.escapeHtml(r.report_type)}</span></td>
                     <td>${Utils.formatDate(r.uploaded_at)}</td>
                     <td><button class="btn btn-ghost btn-sm" onclick="downloadAdmissionReport(${r.id})">Download</button></td>
                   </tr>
                 `).join('')}
               </tbody>
             </table></div>`
          : '<p style="color:var(--text-light); font-size:14px;">No reports uploaded.</p>'}
      </div>
    `;
  } catch (error) {
    console.error('Failed to load EMR context:', error);
    return '<p style="color: var(--text-light); font-size: 14px;">Could not load EMR context.</p>';
  }
}

let currentAdmissionEMRData = null;

async function downloadAdmissionReport(reportId) {
  try {
    const response = await fetch(API.config + `/emr/reports/${reportId}/download`, {
      headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
    });
    if (!response.ok) throw new Error('Download failed');
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (error) {
    console.error('Failed to download report:', error);
    Utils.showToast('Failed to download report', 'error');
  }
}

// ═════════════════════════════════════════════════════════════
// Bed Allocation
// ═════════════════════════════════════════════════════════════
let allocateTargetRequest = null;

async function openAllocateModal(admissionId) {
  allocateTargetRequest = pendingRequests.find(r => r.id === admissionId);
  if (!allocateTargetRequest) {
    try {
      allocateTargetRequest = await API.get(`/admissions/${admissionId}`);
    } catch (e) {
      Utils.showToast('Could not load admission request', 'error');
      return;
    }
  }

  try {
    const beds = await API.get('/admissions/beds');
    const wards = await API.get('/admissions/wards');
    const wardsById = Object.fromEntries(wards.map(w => [w.id, w]));
    const vacantBeds = beds.filter(b => b.status === 'vacant');
    const preferred = allocateTargetRequest.preferred_ward_type;

    const body = document.getElementById('allocate-modal-body');
    body.innerHTML = `
      <div class="alert alert-info" style="margin-bottom:16px;">
        <strong>${patientLabel(allocateTargetRequest.patient_id)}</strong> —
        ${urgencyBadge(allocateTargetRequest.urgency)}
        ${preferred ? ` &middot; Preferred ward type: <strong>${Utils.escapeHtml(preferred)}</strong>` : ''}
        <br>Requested by ${doctorLabel(allocateTargetRequest.requesting_doctor_id)}
        ${allocateTargetRequest.reason ? `<br>Reason: ${Utils.escapeHtml(allocateTargetRequest.reason)}` : ''}
        ${allocateTargetRequest.diagnosis ? `<br>Provisional diagnosis: ${Utils.escapeHtml(allocateTargetRequest.diagnosis)}` : ''}
      </div>
      <div class="form-group">
        <label class="form-label">Select a Vacant Bed</label>
        <select class="form-select" id="allocate-bed-select">
          <option value="">— Choose a bed —</option>
          ${vacantBeds.map(b => {
            const ward = wardsById[b.ward_id];
            const isPreferredMatch = preferred && ward && ward.type === preferred;
            return `<option value="${b.id}" ${isPreferredMatch ? 'selected' : ''}>
              ${ward ? Utils.escapeHtml(ward.name) : 'Ward'} (${ward ? ward.type : ''}) — Bed ${Utils.escapeHtml(b.bed_number)}
            </option>`;
          }).join('')}
        </select>
        ${vacantBeds.length === 0 ? '<p style="color: var(--danger, #96493a); font-size: 13px; margin-top: 6px;">No vacant beds available right now.</p>' : ''}
      </div>
      <div class="form-group">
        <label class="form-label">Admitting Doctor</label>
        <select class="form-select" id="allocate-doctor-select">
          <option value="">Same as requesting doctor (${doctorLabel(allocateTargetRequest.requesting_doctor_id)})</option>
          ${allDoctors.map(d => `<option value="${d.id}">${Utils.escapeHtml(d.full_name)}</option>`).join('')}
        </select>
      </div>
    `;

    document.getElementById('allocate-modal').classList.add('active');
  } catch (error) {
    console.error('Failed to open allocate modal:', error);
    Utils.showToast('Failed to load beds', 'error');
  }
}

function closeAllocateModal() {
  document.getElementById('allocate-modal').classList.remove('active');
  allocateTargetRequest = null;
}

async function confirmAllocateBed() {
  if (!allocateTargetRequest) return;
  const bedId = document.getElementById('allocate-bed-select').value;
  const doctorId = document.getElementById('allocate-doctor-select').value;

  if (!bedId) {
    Utils.showToast('Please select a bed', 'error');
    return;
  }

  try {
    await API.put(`/admissions/${allocateTargetRequest.id}/allocate-bed`, {
      bed_id: parseInt(bedId, 10),
      admitting_doctor_id: doctorId ? parseInt(doctorId, 10) : null,
    });
    Utils.showToast('Bed allocated. Patient is now admitted (IPD).', 'success');
    closeAllocateModal();
    await loadPendingRequests();
    loadDashboard();
  } catch (error) {
    console.error('Failed to allocate bed:', error);
    Utils.showToast(error.message || 'Failed to allocate bed', 'error');
  }
}

// ═════════════════════════════════════════════════════════════
// Bed Map
// ═════════════════════════════════════════════════════════════
async function loadBedMap() {
  try {
    const [bedMapData, wards] = await Promise.all([
      API.get('/admissions/bed-map'),
      API.get('/admissions/wards'),
    ]);
    bedMap = bedMapData || [];
    allWards = wards || [];

    const filter = document.getElementById('bedmap-ward-filter');
    filter.innerHTML = '<option value="">All Wards</option>' +
      allWards.map(w => `<option value="${w.id}">${Utils.escapeHtml(w.name)}</option>`).join('');

    renderBedMap();
  } catch (error) {
    console.error('Failed to load bed map:', error);
    document.getElementById('bedmap-grid').innerHTML = '<p style="color: var(--text-light); text-align:center; padding:20px;">Failed to load bed map.</p>';
  }
}

function renderBedMap() {
  const filterVal = document.getElementById('bedmap-ward-filter')?.value || '';
  const filtered = filterVal ? bedMap.filter(b => String(b.ward_id) === filterVal) : bedMap;
  const grid = document.getElementById('bedmap-grid');

  if (filtered.length === 0) {
    grid.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No beds to show. Add wards and beds under "Wards &amp; Beds".</p>';
    return;
  }

  grid.innerHTML = renderBedGrid(filtered);
}

function renderBedGrid(entries) {
  const statusColor = { vacant: 'var(--success)', occupied: 'var(--warning)', maintenance: 'var(--text-light)' };
  return `
    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px;">
      ${entries.map(b => `
        <div class="card" style="padding:16px; border-left: 4px solid ${statusColor[b.status] || 'var(--border)'};">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
            <div>
              <div style="font-weight:700; font-size:15px;">${Utils.escapeHtml(b.ward_name)} &middot; Bed ${Utils.escapeHtml(b.bed_number)}</div>
              <div style="font-size:12px; color:var(--text-light); text-transform:capitalize;">${Utils.escapeHtml(b.ward_type)}</div>
            </div>
            <span class="badge ${b.status === 'vacant' ? 'badge-success' : b.status === 'occupied' ? 'badge-warning' : 'badge-info'}">${Utils.escapeHtml(b.status)}</span>
          </div>
          ${b.status === 'occupied' ? `
            <div style="font-size:13px; line-height:1.7; border-top:1px solid var(--border); padding-top:8px; margin-top:8px;">
              <strong>${patientLabel(b.patient_id)}</strong><br>
              Under ${doctorLabel(b.admitting_doctor_id)}<br>
              Since ${formatDateTime(b.admitted_since)}<br>
              ${conditionBadge(b.condition_flag)}
              <div style="margin-top:8px;">
                <button class="btn btn-ghost btn-sm" onclick="viewAdmissionById(${b.admission_id})">View</button>
              </div>
            </div>
          ` : ''}
        </div>
      `).join('')}
    </div>
  `;
}

async function viewAdmissionById(admissionId) {
  try {
    const admission = await API.get(`/admissions/${admissionId}`);
    await showAdmissionDetail(admission, { readOnly: false });
  } catch (error) {
    console.error('Failed to load admission:', error);
    Utils.showToast('Failed to load admission', 'error');
  }
}

// ═════════════════════════════════════════════════════════════
// Wards & Beds Management
// ═════════════════════════════════════════════════════════════
async function loadWardsAndBeds() {
  try {
    const [wards, beds] = await Promise.all([
      API.get('/admissions/wards'),
      API.get('/admissions/beds'),
    ]);
    allWards = wards || [];
    allBeds = beds || [];

    const bedWardSelect = document.getElementById('bed-ward-id');
    const bedsFilterSelect = document.getElementById('beds-list-ward-filter');
    const wardOptions = allWards.map(w => `<option value="${w.id}">${Utils.escapeHtml(w.name)} (${w.type})</option>`).join('');
    bedWardSelect.innerHTML = wardOptions;
    bedsFilterSelect.innerHTML = '<option value="">All Wards</option>' + wardOptions;

    renderWardsList();
    renderBedsList();
  } catch (error) {
    console.error('Failed to load wards/beds:', error);
    Utils.showToast('Failed to load wards and beds', 'error');
  }
}

function renderWardsList() {
  const el = document.getElementById('wards-list');
  if (allWards.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No wards yet. Add one above.</p>';
    return;
  }
  el.innerHTML = `
    <div class="table-responsive">
      <table class="table">
        <thead><tr><th>Name</th><th>Type</th><th>Total Beds</th><th>Daily Rate</th><th>Actions</th></tr></thead>
        <tbody>
          ${allWards.map(w => `
            <tr>
              <td><strong>${Utils.escapeHtml(w.name)}</strong></td>
              <td style="text-transform:capitalize;">${Utils.escapeHtml(w.type)}</td>
              <td>${w.total_beds}</td>
              <td>${w.daily_rate != null ? Number(w.daily_rate).toFixed(2) : '—'}</td>
              <td><button class="btn btn-ghost btn-sm" onclick="editWard(${w.id})">Edit</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function editWard(wardId) {
  const ward = allWards.find(w => w.id === wardId);
  if (!ward) return;
  document.getElementById('ward-edit-id').value = ward.id;
  document.getElementById('ward-name').value = ward.name;
  document.getElementById('ward-type').value = ward.type;
  const _rate = document.getElementById('ward-daily-rate');
  if (_rate) _rate.value = ward.daily_rate != null ? ward.daily_rate : 2000;
  document.getElementById('ward-form-title').textContent = `Edit Ward: ${ward.name}`;
  document.getElementById('ward-submit-btn').textContent = 'Save Changes';
  document.getElementById('ward-cancel-btn').style.display = 'inline-block';
  document.getElementById('ward-form').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function cancelWardEdit() {
  document.getElementById('ward-edit-id').value = '';
  document.getElementById('ward-form').reset();
  document.getElementById('ward-form-title').textContent = 'Add Ward';
  document.getElementById('ward-submit-btn').textContent = 'Add Ward';
  document.getElementById('ward-cancel-btn').style.display = 'none';
}

async function submitWardForm(e) {
  e.preventDefault();
  const editId = document.getElementById('ward-edit-id').value;
  const data = {
    name: document.getElementById('ward-name').value.trim(),
    type: document.getElementById('ward-type').value,
    daily_rate: parseFloat(document.getElementById('ward-daily-rate')?.value) || 0,
  };

  try {
    if (editId) {
      await API.put(`/admissions/wards/${editId}`, data);
      Utils.showToast('Ward updated', 'success');
    } else {
      await API.post('/admissions/wards', { ...data, total_beds: 0 });
      Utils.showToast('Ward created', 'success');
    }
    cancelWardEdit();
    loadWardsAndBeds();
  } catch (error) {
    console.error('Failed to save ward:', error);
    Utils.showToast(error.message || 'Failed to save ward', 'error');
  }
}

function renderBedsList() {
  const filterVal = document.getElementById('beds-list-ward-filter')?.value || '';
  const filtered = filterVal ? allBeds.filter(b => String(b.ward_id) === filterVal) : allBeds;
  const wardsById = Object.fromEntries(allWards.map(w => [w.id, w]));
  const el = document.getElementById('beds-list');

  if (filtered.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No beds yet. Add one above.</p>';
    return;
  }

  el.innerHTML = `
    <div class="table-responsive">
      <table class="table">
        <thead><tr><th>Ward</th><th>Bed Number</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>
          ${filtered.map(b => {
            const ward = wardsById[b.ward_id];
            return `
              <tr>
                <td>${ward ? Utils.escapeHtml(ward.name) : `#${b.ward_id}`}</td>
                <td><strong>${Utils.escapeHtml(b.bed_number)}</strong></td>
                <td><span class="badge ${b.status === 'vacant' ? 'badge-success' : b.status === 'occupied' ? 'badge-warning' : 'badge-info'}">${Utils.escapeHtml(b.status)}</span></td>
                <td><button class="btn btn-ghost btn-sm" onclick="editBed(${b.id})">Edit</button></td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function editBed(bedId) {
  const bed = allBeds.find(b => b.id === bedId);
  if (!bed) return;
  document.getElementById('bed-edit-id').value = bed.id;
  document.getElementById('bed-ward-id').value = bed.ward_id;
  document.getElementById('bed-number').value = bed.bed_number;
  document.getElementById('bed-status').value = bed.status;
  document.getElementById('bed-form-title').textContent = `Edit Bed: ${bed.bed_number}`;
  document.getElementById('bed-submit-btn').textContent = 'Save Changes';
  document.getElementById('bed-cancel-btn').style.display = 'inline-block';
  document.getElementById('bed-form').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function cancelBedEdit() {
  document.getElementById('bed-edit-id').value = '';
  document.getElementById('bed-form').reset();
  document.getElementById('bed-form-title').textContent = 'Add Bed';
  document.getElementById('bed-submit-btn').textContent = 'Add Bed';
  document.getElementById('bed-cancel-btn').style.display = 'none';
}

async function submitBedForm(e) {
  e.preventDefault();
  const editId = document.getElementById('bed-edit-id').value;
  const data = {
    ward_id: parseInt(document.getElementById('bed-ward-id').value, 10),
    bed_number: document.getElementById('bed-number').value.trim(),
    status: document.getElementById('bed-status').value,
  };

  try {
    if (editId) {
      await API.put(`/admissions/beds/${editId}`, { bed_number: data.bed_number, status: data.status });
      Utils.showToast('Bed updated', 'success');
    } else {
      await API.post('/admissions/beds', data);
      Utils.showToast('Bed created', 'success');
    }
    cancelBedEdit();
    loadWardsAndBeds();
  } catch (error) {
    console.error('Failed to save bed:', error);
    Utils.showToast(error.message || 'Failed to save bed', 'error');
  }
}

// ═════════════════════════════════════════════════════════════
// Admitted Patients
// ═════════════════════════════════════════════════════════════
let currentAdmittedEntries = [];

async function loadAdmitted() {
  try {
    bedMap = await API.get('/admissions/bed-map');
    currentAdmittedEntries = (bedMap || []).filter(b => b.status === 'occupied' && b.admission_id);
    renderAdmittedList();
  } catch (error) {
    console.error('Failed to load admitted patients:', error);
    document.getElementById('admitted-list').innerHTML = '<p style="color: var(--text-light); text-align:center; padding:20px;">Failed to load admitted patients.</p>';
  }
}

function renderAdmittedList() {
  const search = document.getElementById('search-admitted')?.value.toLowerCase() || '';
  const filtered = currentAdmittedEntries.filter(b => {
    const name = (patientsById[b.patient_id]?.name || '').toLowerCase();
    return name.includes(search) || String(b.patient_id).includes(search);
  });

  const el = document.getElementById('admitted-list');
  if (filtered.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No patients currently admitted.</p>';
    return;
  }

  el.innerHTML = `
    <div class="table-responsive">
      <table class="table">
        <thead>
          <tr><th>Patient</th><th>Ward / Bed</th><th>Admitting Doctor</th><th>Since</th><th>Condition</th><th>Actions</th></tr>
        </thead>
        <tbody>
          ${filtered.map(b => `
            <tr>
              <td><strong>${patientLabel(b.patient_id)}</strong></td>
              <td>${Utils.escapeHtml(b.ward_name)} &middot; Bed ${Utils.escapeHtml(b.bed_number)}</td>
              <td>${doctorLabel(b.admitting_doctor_id)}</td>
              <td>${formatDateTime(b.admitted_since)}</td>
              <td>${conditionBadge(b.condition_flag)}</td>
              <td style="display:flex; gap:6px; flex-wrap:wrap;">
                <button class="btn btn-ghost btn-sm" onclick="viewAdmissionById(${b.admission_id})">View / Discharge</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

// ═════════════════════════════════════════════════════════════
// Discharge History
// ═════════════════════════════════════════════════════════════
async function loadHistory() {
  try {
    // No single "all admissions" endpoint is exposed; build history from
    // every patient this clinic knows about, since discharge records live
    // per-patient. Cheap enough at clinic scale and avoids a backend change.
    const results = await Promise.all(
      allPatients.map(p => API.get(`/admissions/patient/${p.id}`).catch(() => []))
    );
    const history = results.flat().filter(a => a.status === 'discharged' || a.status === 'cancelled');
    history.sort((a, b) => new Date(b.discharged_at || b.requested_at) - new Date(a.discharged_at || a.requested_at));
    renderHistory(history);
  } catch (error) {
    console.error('Failed to load history:', error);
    document.getElementById('history-list').innerHTML = '<p style="color: var(--text-light); text-align:center; padding:20px;">Failed to load history.</p>';
  }
}

function renderHistory(history) {
  const el = document.getElementById('history-list');
  if (history.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No discharge history yet.</p>';
    return;
  }
  el.innerHTML = `
    <div class="table-responsive">
      <table class="table">
        <thead><tr><th>Patient</th><th>Admitted</th><th>Discharged</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>
          ${history.map(a => `
            <tr>
              <td><strong>${patientLabel(a.patient_id)}</strong></td>
              <td>${formatDateTime(a.admitted_at)}</td>
              <td>${formatDateTime(a.discharged_at)}</td>
              <td><span class="badge ${a.status === 'discharged' ? 'badge-info' : 'badge-danger'}">${Utils.escapeHtml(a.status)}</span></td>
              <td><button class="btn btn-ghost btn-sm" onclick="viewAdmissionById(${a.id})">View</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

// ═════════════════════════════════════════════════════════════
// Admission Detail Modal (context + notes + discharge)
// ═════════════════════════════════════════════════════════════
let currentDetailAdmission = null;

async function showAdmissionDetail(admission, { readOnly }) {
  currentDetailAdmission = admission;
  document.getElementById('admission-detail-title').textContent = `${patientLabel(admission.patient_id)} — Admission #${admission.id}`;

  const body = document.getElementById('admission-detail-body');
  body.innerHTML = `
    <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px;">
      ${urgencyBadge(admission.urgency)}
      <span class="badge badge-info">${Utils.escapeHtml(admission.status.toUpperCase())}</span>
      ${admission.condition_flag ? conditionBadge(admission.condition_flag) : ''}
    </div>
    <div style="font-size:14px; line-height:1.8; margin-bottom:16px;">
      <strong>Requesting Doctor:</strong> ${doctorLabel(admission.requesting_doctor_id)}<br>
      ${admission.admitting_doctor_id ? `<strong>Admitting Doctor:</strong> ${doctorLabel(admission.admitting_doctor_id)}<br>` : ''}
      ${admission.reason ? `<strong>Reason:</strong> ${Utils.escapeHtml(admission.reason)}<br>` : ''}
      ${admission.diagnosis ? `<strong>Provisional Diagnosis:</strong> ${Utils.escapeHtml(admission.diagnosis)}<br>` : ''}
      ${admission.preferred_ward_type ? `<strong>Preferred Ward:</strong> ${Utils.escapeHtml(admission.preferred_ward_type)}<br>` : ''}
      <strong>Requested:</strong> ${formatDateTime(admission.requested_at)}<br>
      ${admission.admitted_at ? `<strong>Admitted:</strong> ${formatDateTime(admission.admitted_at)}<br>` : ''}
      ${admission.discharged_at ? `<strong>Discharged:</strong> ${formatDateTime(admission.discharged_at)}<br>` : ''}
      ${admission.discharge_summary ? `<strong>Discharge Summary:</strong> ${Utils.escapeHtml(admission.discharge_summary)}<br>` : ''}
    </div>

    <div style="border-top:1px solid var(--border); padding-top:12px; margin-bottom:16px;">
      <h4 style="font-size:14px; font-weight:700; margin-bottom:8px;">Patient Medical Record (read-only — same EMR the treating doctor sees)</h4>
      <div id="detail-emr-context"><div class="loading-spinner">Loading...</div></div>
    </div>

    <div style="border-top:1px solid var(--border); padding-top:12px; margin-bottom:16px;">
      <h4 style="font-size:14px; font-weight:700; margin-bottom:8px;">Rounds / Progress Notes</h4>
      <div id="detail-notes-list"><div class="loading-spinner">Loading notes...</div></div>
    </div>

    <div style="border-top:1px solid var(--border); padding-top:12px; margin-bottom:16px;">
      <h4 style="font-size:14px; font-weight:700; margin-bottom:8px;">Medication Administration Record (MAR) — today</h4>
      <p style="font-size:12px; color:var(--text-light); margin-bottom:8px;">Live from nursing — updates when doses are marked given / held / missed</p>
      <div id="detail-mar-list"><div class="loading-spinner">Loading MAR...</div></div>
    </div>

    ${(!readOnly && admission.status === 'admitted') ? `
      <div style="border-top:1px solid var(--border); padding-top:16px;">
        <h4 style="font-size:14px; font-weight:700; margin-bottom:8px;">Discharge Patient</h4>
        <div class="form-group">
          <textarea class="form-textarea" id="discharge-summary-input" placeholder="Discharge summary..."></textarea>
        </div>
        <button class="btn btn-danger" onclick="submitDischarge()">Discharge &amp; Free Bed</button>
      </div>
    ` : ''}
  `;

  document.getElementById('admission-detail-modal').classList.add('active');
  loadAdmissionMAR(admission.id);

  buildEMRContextHtml(admission.patient_id).then(html => {
    const target = document.getElementById('detail-emr-context');
    if (target) target.innerHTML = html;
  });

  API.get(`/admissions/${admission.id}/notes`).then(notes => {
    const target = document.getElementById('detail-notes-list');
    if (!target) return;
    if (!notes || notes.length === 0) {
      target.innerHTML = '<p style="color: var(--text-light); font-size: 14px;">No rounds notes yet.</p>';
      return;
    }
    target.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:10px;">
        ${notes.map(n => `
          <div style="background: var(--bg-alt); border-radius: 10px; padding: 10px 14px; font-size: 13px;">
            <div style="font-weight:600; margin-bottom:4px;">${doctorLabel(n.doctor_id)} &middot; ${formatDateTime(n.created_at)}</div>
            <div>${Utils.escapeHtml(n.note)}</div>
            ${n.vitals ? `<div style="color: var(--text-light); margin-top:4px;">Vitals: ${Utils.escapeHtml(n.vitals)}</div>` : ''}
          </div>
        `).join('')}
      </div>
    `;
  }).catch(() => {
    const target = document.getElementById('detail-notes-list');
    if (target) target.innerHTML = '<p style="color: var(--text-light); font-size: 14px;">Could not load notes.</p>';
  });
}

function closeAdmissionDetailModal() {
  document.getElementById('admission-detail-modal').classList.remove('active');
  currentDetailAdmission = null;
}

async function submitDischarge() {
  if (!currentDetailAdmission) return;
  const summary = document.getElementById('discharge-summary-input').value.trim();
  if (!summary) {
    Utils.showToast('Please enter a discharge summary', 'error');
    return;
  }

  try {
    await API.put(`/admissions/${currentDetailAdmission.id}/discharge`, { discharge_summary: summary });
    Utils.showToast('Patient discharged and bed freed', 'success');
    closeAdmissionDetailModal();
    loadDashboard();
    if (document.getElementById('page-admitted').classList.contains('active')) loadAdmitted();
    if (document.getElementById('page-bedmap').classList.contains('active')) loadBedMap();
    if (document.getElementById('page-history').classList.contains('active')) loadHistory();
  } catch (error) {
    console.error('Failed to discharge patient:', error);
    Utils.showToast(error.message || 'Failed to discharge patient', 'error');
  }
}

function logout() {
  Auth.clear();
  window.location.replace('login.html?force=1');
}


async function loadNursePage() {
  await Promise.all([loadNurseSelect(), loadBedSelectForAssign(), loadNurseAssignments(), loadMedCompliance()]);
}

async function loadNurseSelect() {
  const sel = document.getElementById('assign-nurse-select');
  if (!sel) return;
  try {
    const res = await API.get('/nursing/nurses');
    const nurses = Array.isArray(res) ? res : (res?.data || []);
    sel.innerHTML = nurses.length
      ? nurses.map(n => `<option value="${n.id}">${n.username} (${n.email || ''})</option>`).join('')
      : '<option value="">No nurse accounts found — create a user with role nurse</option>';
  } catch (e) {
    sel.innerHTML = '<option value="">Failed to load nurses</option>';
  }
}

async function loadBedSelectForAssign() {
  const sel = document.getElementById('assign-beds-select');
  if (!sel) return;
  try {
    let wardById = {};
    try {
      const wardsRes = await API.get('/admissions/wards');
      const wards = Array.isArray(wardsRes) ? wardsRes : (wardsRes?.data || []);
      wards.forEach(w => { wardById[w.id] = w.name; });
    } catch (_) {}
    const bedLabel = (b) => {
      const wardName = b.ward_name || b.ward?.name || wardById[b.ward_id] || 'Ward';
      return `${wardName} — Bed ${b.bed_number}`;
    };
    let options = [];
    const bedsRes = await API.get('/admissions/beds').catch(() => []);
    const beds = Array.isArray(bedsRes) ? bedsRes : (bedsRes?.data || []);
    if (beds.length) {
      options = beds.map(b => `<option value="${b.id}">${bedLabel(b)}</option>`);
    } else {
      const mapRes = await API.get('/admissions/bed-map').catch(() => []);
      const map = Array.isArray(mapRes) ? mapRes : (mapRes?.data || []);
      options = map.map(b => `<option value="${b.bed_id || b.id}">${b.ward_name || wardById[b.ward_id] || 'Ward'} — Bed ${b.bed_number}</option>`);
    }
    sel.innerHTML = options.length ? options.join('') : '<option value="">No beds found</option>';
  } catch (e) {
    console.error(e);
    sel.innerHTML = '<option value="">Failed to load beds</option>';
  }
}


async function submitNurseAssignment() {
  const nurseId = parseInt(document.getElementById('assign-nurse-select')?.value, 10);
  const bedSel = document.getElementById('assign-beds-select');
  const bedIds = [...(bedSel?.selectedOptions || [])].map(o => parseInt(o.value, 10)).filter(Boolean);
  if (!nurseId || !bedIds.length) {
    Utils.showToast('Select a nurse and at least one bed', 'error');
    return;
  }
  try {
    await API.post('/nursing/assignments', { nurse_user_id: nurseId, bed_ids: bedIds });
    Utils.showToast('Beds assigned', 'success');
    loadNurseAssignments();
  } catch (e) {
    Utils.showToast(e.message || String(e), 'error');
  }
}

async function loadNurseAssignments() {
  const el = document.getElementById('nurse-assignments-list');
  if (!el) return;
  try {
    const res = await API.get('/nursing/assignments');
    const rows = Array.isArray(res) ? res : (res?.data || []);
    if (!rows.length) {
      el.innerHTML = '<p style="color:var(--text-light); text-align:center; padding:20px;">No assignments yet</p>';
      return;
    }
    el.innerHTML = `<table class="table"><thead><tr><th>Nurse</th><th>Ward</th><th>Bed</th><th>Patient</th><th></th></tr></thead><tbody>
      ${rows.map(a => `<tr>
        <td>${a.nurse_username || a.nurse_user_id}</td>
        <td>${a.ward_name || '—'}</td>
        <td>${a.bed_number || a.bed_id}</td>
        <td>${a.patient_name || 'Vacant'}</td>
        <td><button class="btn btn-ghost btn-sm" onclick="unassignNurseBed(${a.id})">Remove</button></td>
      </tr>`).join('')}
    </tbody></table>`;
  } catch (e) {
    el.innerHTML = '<p style="color:var(--text-light);">Failed to load assignments</p>';
  }
}

async function unassignNurseBed(id) {
  try {
    await API.delete(`/nursing/assignments/${id}`);
    Utils.showToast('Assignment removed', 'success');
    loadNurseAssignments();
  } catch (e) {
    Utils.showToast(e.message || String(e), 'error');
  }
}


async function loadAdmissionMAR(admissionId) {
  const target = document.getElementById('detail-mar-list');
  if (!target) return;
  target.innerHTML = '<div class="loading-spinner">Loading MAR...</div>';
  try {
    let doses = [];
    let summary = null;
    try {
      const res = await API.get(`/nursing/admissions/${admissionId}/doses`);
      const data = res?.data || res;
      doses = Array.isArray(data) ? data : (data?.doses || []);
      if (!Array.isArray(doses)) doses = [];
    } catch (e) {
      const res = await API.get(`/nursing/admissions/${admissionId}/compliance`).catch(() => null);
      const c = res?.data || res || {};
      summary = c;
      doses = c.doses || [];
    }
    if (!doses.length) {
      const sumHtml = summary
        ? `<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
            <span class="badge badge-success">Given ${summary.given || 0}</span>
            <span class="badge badge-warning">Pending ${summary.pending || 0}</span>
            <span class="badge">Held ${summary.held || 0}</span>
            <span class="badge">Missed ${summary.missed || 0}</span>
          </div>`
        : '';
      target.innerHTML = sumHtml + '<p style="color:var(--text-light);font-size:13px;">No scheduled doses for today.</p>';
      return;
    }
    const given = doses.filter(d => d.status === 'given').length;
    const pending = doses.filter(d => d.status === 'pending').length;
    const held = doses.filter(d => d.status === 'held').length;
    const missed = doses.filter(d => d.status === 'missed' || d.status === 'skipped').length;
    target.innerHTML = `
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px;align-items:center;">
        <span class="badge badge-success">Given ${given}</span>
        <span class="badge badge-warning">Pending ${pending}</span>
        <span class="badge">Held ${held}</span>
        <span class="badge">Missed ${missed}</span>
        <button type="button" class="btn btn-ghost btn-sm" onclick="loadAdmissionMAR(${admissionId})">Refresh</button>
      </div>
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Medicine</th><th>Dose</th><th>Schedule</th><th>Status</th><th>Given at</th></tr></thead>
        <tbody>
          ${doses.map(d => {
            const st = (d.status || 'pending').toLowerCase();
            const badge = st === 'given' ? 'badge-success' : st === 'pending' ? 'badge-warning' : st === 'held' ? 'badge-info' : 'badge-danger';
            const when = [d.scheduled_date, d.scheduled_time].filter(Boolean).join(' ');
            const givenAt = d.given_at ? new Date(d.given_at).toLocaleString() : '—';
            return `<tr>
              <td><strong>${Utils.escapeHtml(d.medicine_name || 'Medicine')}</strong></td>
              <td>${Utils.escapeHtml(d.dosage || '—')} · ${Utils.escapeHtml(d.route || '')}</td>
              <td style="font-size:12px;">${Utils.escapeHtml(when || '—')}</td>
              <td><span class="badge ${badge}">${Utils.escapeHtml(st.toUpperCase())}</span></td>
              <td style="font-size:12px;">${Utils.escapeHtml(givenAt)}</td>
            </tr>`;
          }).join('')}
        </tbody>
      </table></div>`;
  } catch (e) {
    console.error(e);
    target.innerHTML = '<p style="color:var(--text-light);font-size:13px;">Unable to load MAR</p>';
  }
}

async function loadMedCompliance() {
  const el = document.getElementById('med-compliance-list');
  if (!el) return;
  el.innerHTML = '<div class="loading-spinner">Loading compliance...</div>';
  try {
    // Same source as Admitted Patients / bed map — reliable occupied beds with admissions
    let map = [];
    try {
      const mapRes = await API.get('/admissions/bed-map');
      map = Array.isArray(mapRes) ? mapRes : (mapRes?.data || []);
    } catch (_) {
      map = [];
    }

    let admitted = (map || []).filter(
      b => b.admission_id && String(b.status || '').toLowerCase() === 'occupied'
    );

    // Fallback: doctor/admission list endpoints if bed-map empty
    if (!admitted.length) {
      const tryUrls = [
        '/admissions/requests/pending',
        '/admissions/?status=admitted',
      ];
      for (const url of tryUrls) {
        try {
          const res = await API.get(url);
          const list = Array.isArray(res) ? res : (res?.data || []);
          const filtered = list.filter(a =>
            ['admitted', 'pending'].includes(String(a.status || '').toLowerCase())
          );
          if (filtered.length) {
            admitted = filtered.map(a => ({
              admission_id: a.id,
              patient_name: a.patient_name || a.patient?.name,
              patient_id: a.patient_id,
              ward_name: a.ward_name,
              bed_number: a.bed_number || a.bed?.bed_number,
              status: 'occupied',
            }));
            break;
          }
        } catch (_) {}
      }
    }

    // Also include patients from nurse assignments (occupied beds)
    try {
      const assignRes = await API.get('/nursing/assignments').catch(() =>
        API.get('/nursing/assignments/all').catch(() => [])
      );
      const assigns = Array.isArray(assignRes) ? assignRes : (assignRes?.data || []);
      const byAdmission = new Set(admitted.map(a => a.admission_id || a.id));
      for (const a of assigns) {
        const aid = a.admission_id;
        if (!aid || byAdmission.has(aid)) continue;
        if (a.patient_name || a.patient_id) {
          admitted.push({
            admission_id: aid,
            patient_name: a.patient_name,
            patient_id: a.patient_id,
            ward_name: a.ward_name,
            bed_number: a.bed_number,
            status: 'occupied',
          });
          byAdmission.add(aid);
        }
      }
    } catch (_) {}

    if (!admitted.length) {
      el.innerHTML = '<p style="color:var(--text-light); text-align:center; padding:20px;">No admitted patients</p>';
      return;
    }

    let html = `<div class="table-responsive"><table class="table">
      <thead><tr>
        <th>Patient</th><th>Ward / Bed</th><th>Given</th><th>Pending</th><th>Held</th><th>Missed</th><th></th>
      </tr></thead><tbody>`;

    for (const a of admitted.slice(0, 40)) {
      const admissionId = a.admission_id || a.id;
      if (!admissionId) continue;
      const res = await API.get(`/nursing/admissions/${admissionId}/compliance`).catch(() => null);
      const c = res?.data || res || {};
      const patient = a.patient_name || a.patient?.name || (a.patient_id ? ('#' + a.patient_id) : '—');
      const bed = [a.ward_name, a.bed_number != null ? ('Bed ' + a.bed_number) : (a.bed_label || '')]
        .filter(Boolean).join(' — ') || '—';
      html += `<tr>
        <td><strong>${Utils.escapeHtml(String(patient))}</strong></td>
        <td>${Utils.escapeHtml(String(bed))}</td>
        <td><span class="badge badge-success">${c.given || 0}</span></td>
        <td><span class="badge badge-warning">${c.pending || 0}</span></td>
        <td>${c.held || 0}</td>
        <td>${c.missed || c.skipped || 0}</td>
        <td><button type="button" class="btn btn-ghost btn-sm" onclick="viewAdmissionById(${admissionId})">View MAR</button></td>
      </tr>`;
    }
    html += '</tbody></table></div>';
    el.innerHTML = html;
  } catch (e) {
    console.error(e);
    el.innerHTML = '<p style="color:var(--text-light); text-align:center; padding:20px;">Unable to load compliance</p>';
  }
}


// Refresh MAR compliance periodically while on admitted patients page
let marRefreshTimer = null;
function startMarAutoRefresh() {
  stopMarAutoRefresh();
  marRefreshTimer = setInterval(() => {
    const page = document.getElementById('page-admitted');
    if (page && page.classList.contains('active') && typeof loadMedCompliance === 'function') {
      loadMedCompliance();
  startMarAutoRefresh();
    }
    // If detail modal open with MAR, refresh it
    const modal = document.getElementById('admission-detail-modal');
    if (modal && modal.classList.contains('active') && currentDetailAdmission) {
      loadAdmissionMAR(currentDetailAdmission.id);
    }
  }, 20000);
}
function stopMarAutoRefresh() {
  if (marRefreshTimer) clearInterval(marRefreshTimer);
  marRefreshTimer = null;
}


async function cancelAdmissionRequest(admissionId) {
  if (!confirm('Cancel this admission request? The requesting doctor and patient will be notified so they can submit a new request if needed.')) return;
  try {
    await API.post(`/admissions/${admissionId}/cancel`, {});
    Utils.showToast('Admission request cancelled — doctor/patient alerted', 'success');
    if (typeof loadPendingRequests === 'function') await loadPendingRequests();
    if (typeof loadDashboard === 'function') try { loadDashboard(); } catch (_) {}
  } catch (e) {
    Utils.showToast(e.message || String(e), 'error');
  }
}
