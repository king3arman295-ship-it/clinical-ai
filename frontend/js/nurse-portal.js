let todayDoses = [];
let myAssignments = [];
/** id -> dose; kept in sync from dashboard + tasks so Record always works */
const doseById = new Map();

function cacheDoses(doses) {
  (doses || []).forEach(d => {
    if (d && d.id != null) doseById.set(Number(d.id), d);
  });
}

function getDose(doseId) {
  const id = Number(doseId);
  return doseById.get(id) || todayDoses.find(x => Number(x.id) === id) || null;
}

document.addEventListener('DOMContentLoaded', async function () {
  if (!Auth.isAuthenticated()) {
    window.location.replace('login.html?force=1');
    return;
  }
  const role = Auth.getRole();
  if (!['nurse', 'admin'].includes(role)) {
    alert('Nurse access only');
    window.location.replace('login.html?force=1');
    return;
  }
  if (typeof injectAdminBackButton === 'function') injectAdminBackButton();
  if (typeof setupSessionGuards === 'function') setupSessionGuards();
  loadUserInfo();
  const dateInput = document.getElementById('tasks-date');
  if (dateInput) dateInput.value = new Date().toISOString().slice(0, 10);

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

  await Promise.all([loadDashboard(), loadTodayDoses(), loadMyBeds()]);
});

function loadUserInfo() {
  const user = Auth.getUser();
  const box = document.getElementById('user-info');
  if (!user || !box) return;
  document.getElementById('user-name').textContent = user.username || 'Nurse';
    const greet = document.getElementById('dashboard-greeting-name');
    if (greet) greet.textContent = user.username || user.name || greet.textContent;
    const dateEl = document.getElementById('dashboard-date');
    if (dateEl) {
      dateEl.textContent = new Date().toLocaleDateString(undefined, {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
      });
    }

  document.getElementById('user-role').textContent = 'Nurse';
  box.style.display = 'block';
}

function logout() {
  Auth.clear();
  window.location.replace('login.html?force=1');
}

function showPage(pageName) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
  const page = document.getElementById('page-' + pageName);
  if (page) page.classList.add('active');
  const link = document.querySelector(`.sidebar-link[data-page="${pageName}"]`);
  if (link) link.classList.add('active');

  if (pageName === 'dashboard') loadDashboard();
  if (pageName === 'tasks') loadTodayDoses();
  if (pageName === 'beds') loadMyBeds();
  if (pageName === 'patients') loadPatientsCourses();
}

function escapeHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function loadDashboard() {
  try {
    const res = await API.get('/nursing/dashboard');
    const d = res?.data || res || {};
    document.getElementById('stat-beds').textContent = d.assigned_beds ?? 0;
    document.getElementById('stat-patients').textContent = d.active_patients ?? 0;
    document.getElementById('stat-pending').textContent = d.doses_pending_today ?? 0;
    document.getElementById('stat-given').textContent = d.doses_given_today ?? 0;

    if (window.PortalUI) {
      PortalUI.ensureChartJs(function () {
        PortalUI.lineChart(
          'portal-trend-chart',
          ['Beds', 'Patients', 'Pending', 'Given'],
          [d.assigned_beds || 0, d.assigned_patients || 0, d.doses_pending_today || 0, d.doses_given_today || 0],
          'Nursing load'
        );
        PortalUI.doughnutChart(
          'portal-status-chart',
          ['Pending doses', 'Given today'],
          [d.doses_pending_today || 0, d.doses_given_today || 0]
        );
      });
    }
    const badge = document.getElementById('pending-dose-badge');
    if (badge) {
      const n = d.doses_pending_today || 0;
      badge.style.display = n ? 'inline-flex' : 'none';
      badge.textContent = n;
    }
  } catch (e) {
    console.error(e);
  }
  // preview doses — cache so Record works from the dashboard too
  try {
    const res = await API.get('/nursing/today-doses');
    const doses = Array.isArray(res) ? res : (res?.data || []);
    cacheDoses(doses);
    if (!todayDoses.length) todayDoses = doses;
    const pending = doses.filter(d => d.status === 'pending').slice(0, 8);
    const el = document.getElementById('dashboard-doses');
    if (!pending.length) {
      el.innerHTML = '<p style="color:var(--text-light); text-align:center; padding:24px;">No pending doses right now</p>';
      return;
    }
    el.innerHTML = renderDoseTable(pending, true);
  } catch (e) {
    document.getElementById('dashboard-doses').innerHTML = '<p style="color:var(--text-light);">Unable to load doses</p>';
  }
}

async function loadTodayDoses() {
  const day = document.getElementById('tasks-date')?.value || new Date().toISOString().slice(0, 10);
  const statusFilter = document.getElementById('tasks-status-filter')?.value || '';
  try {
    const res = await API.get(`/nursing/today-doses?day=${day}`);
    todayDoses = Array.isArray(res) ? res : (res?.data || []);
    cacheDoses(todayDoses);
    let list = todayDoses;
    if (statusFilter) list = list.filter(d => d.status === statusFilter);
    const el = document.getElementById('tasks-list');
    if (!list.length) {
      el.innerHTML = '<p style="color:var(--text-light); text-align:center; padding:32px;">No doses scheduled for this day on your beds</p>';
      return;
    }
    el.innerHTML = renderDoseTable(list, false);
  } catch (e) {
    console.error(e);
    Utils.showToast(e.message || 'Failed to load doses', 'error');
  }
}

function renderDoseTable(doses, compact) {
  return `<div class="table-wrap"><table class="table">
    <thead><tr>
      <th>Time</th><th>Patient / Bed</th><th>Medicine</th><th>Dose / Route</th><th>Status</th><th>Action</th>
    </tr></thead>
    <tbody>
      ${doses.map(d => {
        const badge = statusBadge(d.status);
        const waitingPharmacy = d.pharmacy_ready === false;
        const actions = d.status === 'pending'
          ? `<button type="button" class="btn btn-primary btn-sm" onclick="openDoseAction(${Number(d.id)})">Record</button>`
            + (waitingPharmacy ? ` <span class="badge badge-warning">Awaiting pharmacy</span>` : ` <span class="badge badge-success">Stock ready</span>`)
          : `<span style="font-size:12px;color:var(--text-light);">${d.given_at ? new Date(d.given_at).toLocaleTimeString() : ''}</span>`;
        return `<tr>
          <td><strong>${escapeHtml(d.scheduled_time || '—')}</strong></td>
          <td>
            <div style="font-weight:600;">${escapeHtml(d.patient_name || 'Patient')}</div>
            <div style="font-size:12px;color:var(--text-light);">${escapeHtml(d.bed_label || '')}</div>
          </td>
          <td>
            <div>${escapeHtml(d.medicine_name || '—')}</div>
            ${d.instructions ? `<div style="font-size:12px;color:var(--text-light);">${escapeHtml(d.instructions)}</div>` : ''}
          </td>
          <td>${escapeHtml(d.dosage || '')} · <span class="badge badge-info">${escapeHtml(d.route || 'tablet')}</span>
            ${d.drip_rate ? `<div style="font-size:12px;">Rate: ${escapeHtml(d.drip_rate)}</div>` : ''}
          </td>
          <td>${badge}</td>
          <td>${actions}</td>
        </tr>`;
      }).join('')}
    </tbody></table></div>`;
}

function statusBadge(status) {
  const map = {
    pending: 'badge-warning',
    given: 'badge-success',
    held: 'badge-info',
    missed: 'badge-danger',
    skipped: 'badge-info',
  };
  return `<span class="badge ${map[status] || 'badge-info'}">${escapeHtml((status || '').toUpperCase())}</span>`;
}

function openDoseAction(doseId) {
  const id = Number(doseId);
  const d = getDose(id);
  if (!d) {
    Utils.showToast('Dose not found — refreshing list…', 'error');
    loadTodayDoses();
    return;
  }
  if (d.status && d.status !== 'pending') {
    Utils.showToast(`This dose is already marked as ${d.status}`, 'error');
    return;
  }
  document.getElementById('dose-modal-title').textContent = `${d.medicine_name || 'Dose'} @ ${d.scheduled_time || ''}`;
  document.getElementById('dose-modal-body').innerHTML = `
    <p style="margin-bottom:12px;"><strong>${escapeHtml(d.patient_name || '')}</strong> — ${escapeHtml(d.bed_label || '')}</p>
    <p style="margin-bottom:12px;">${escapeHtml(d.dosage || '')} · ${(d.route || '').toUpperCase()}
      ${d.drip_rate ? ` · Drip ${escapeHtml(d.drip_rate)}` : ''}</p>
    <div class="form-group">
      <label class="form-label">Notes (optional)</label>
      <textarea class="form-textarea" id="dose-action-notes" placeholder="Reason if held/missed..."></textarea>
    </div>
  `;
  document.getElementById('dose-modal-footer').innerHTML = `
    <button class="btn btn-ghost" type="button" onclick="closeDoseModal()">Cancel</button>
    <button class="btn btn-ghost" type="button" onclick="submitDoseAction(${id}, 'held')">Hold</button>
    <button class="btn btn-ghost" type="button" style="color:var(--danger,#B4614C);" onclick="submitDoseAction(${id}, 'missed')">Missed</button>
    <button class="btn btn-primary" type="button" onclick="submitDoseAction(${id}, 'given')">Mark Given</button>
  `;
  document.getElementById('dose-modal').classList.add('active');
}

function closeDoseModal() {
  document.getElementById('dose-modal').classList.remove('active');
}

async function submitDoseAction(doseId, status) {
  const id = Number(doseId);
  if (status === 'given' && window._currentDosePharmacyReady === false) {
    Utils.showToast('Cannot mark Given — pharmacy must dispense this course medicine first.', 'error');
    return;
  }
  const notesRaw = document.getElementById('dose-action-notes')?.value;
  const notes = notesRaw && notesRaw.trim() ? notesRaw.trim() : null;
  const footer = document.getElementById('dose-modal-footer');
  const buttons = footer ? Array.from(footer.querySelectorAll('button')) : [];
  buttons.forEach(b => { b.disabled = true; });
  try {
    await API.post(`/nursing/doses/${id}/action`, { status, notes });
    const cached = getDose(id);
    if (cached) {
      cached.status = status;
      cached.given_at = new Date().toISOString();
      if (notes) cached.notes = notes;
      doseById.set(id, cached);
    }
    todayDoses = todayDoses.map(d =>
      Number(d.id) === id
        ? { ...d, status, given_at: new Date().toISOString(), notes: notes || d.notes }
        : d
    );
    Utils.showToast(
      status === 'given' ? 'Dose marked as given' : `Dose marked as ${status}`,
      'success'
    );
    closeDoseModal();
    await Promise.all([loadTodayDoses(), loadDashboard()]);
  } catch (e) {
    console.error('Dose action failed', e);
    Utils.showToast(e.message || String(e), 'error');
    buttons.forEach(b => { b.disabled = false; });
  }
}

async function loadMyBeds() {
  try {
    const res = await API.get('/nursing/assignments');
    myAssignments = Array.isArray(res) ? res : (res?.data || []);
    const el = document.getElementById('beds-list');
    if (!myAssignments.length) {
      el.innerHTML = '<p style="color:var(--text-light); text-align:center; padding:32px;">No beds assigned yet. Ask Admission Head to assign beds to you.</p>';
      return;
    }
    el.innerHTML = `<div class="table-wrap"><table class="table">
      <thead><tr><th>Ward</th><th>Bed</th><th>Patient</th><th>Admission</th></tr></thead>
      <tbody>
        ${myAssignments.map(a => `<tr>
          <td>${escapeHtml(a.ward_name || '—')}</td>
          <td><strong>${escapeHtml(a.bed_number || a.bed_id)}</strong></td>
          <td>${escapeHtml(a.patient_name || 'Vacant')}</td>
          <td>${a.admission_id ? '#' + a.admission_id : '—'}</td>
        </tr>`).join('')}
      </tbody></table></div>`;
  } catch (e) {
    Utils.showToast(e.message || String(e), 'error');
  }
}

async function loadPatientsCourses() {
  const el = document.getElementById('patients-list');
  try {
    if (!myAssignments.length) {
      const res = await API.get('/nursing/assignments');
      myAssignments = Array.isArray(res) ? res : (res?.data || []);
    }
    const withAdmission = myAssignments.filter(a => a.admission_id);
    if (!withAdmission.length) {
      el.innerHTML = '<p style="color:var(--text-light); text-align:center; padding:32px;">No admitted patients on your beds</p>';
      return;
    }
    let html = '';
    for (const a of withAdmission) {
      const coursesRes = await API.get(`/nursing/admissions/${a.admission_id}/courses`);
      const courses = Array.isArray(coursesRes) ? coursesRes : (coursesRes?.data || []);
      const complianceRes = await API.get(`/nursing/admissions/${a.admission_id}/compliance`);
      const compliance = complianceRes?.data || complianceRes || {};
      html += `<div style="border:1px solid var(--border); border-radius:12px; padding:16px; margin-bottom:16px;">
        <div style="display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:8px;">
          <div>
            <strong style="font-size:16px;">${escapeHtml(a.patient_name || 'Patient')}</strong>
            <div style="font-size:13px; color:var(--text-light);">${escapeHtml(a.ward_name || '')} — Bed ${escapeHtml(a.bed_number || '')} · Admission #${a.admission_id}</div>
          </div>
          <div style="font-size:13px;">
            Today: <span class="badge badge-success">${compliance.given || 0} given</span>
            <span class="badge badge-warning">${compliance.pending || 0} pending</span>
            ${(compliance.held || 0) ? `<span class="badge badge-info">${compliance.held} held</span>` : ''}
          </div>
        </div>
        ${courses.length ? courses.map(c => `
          <div style="background:var(--bg-alt); border-radius:8px; padding:12px; margin-top:8px;">
            <div style="font-weight:600;">${escapeHtml(c.title)} <span class="badge">${escapeHtml(c.status)}</span></div>
            <div style="font-size:12px; color:var(--text-light); margin:4px 0;">
              ${c.start_date} → ${c.end_date || '—'} (${c.duration_days} days)
              ${c.doctor_name ? ' · Dr. ' + escapeHtml(c.doctor_name) : ''}
            </div>
            ${c.clinical_notes ? `<div style="font-size:13px;margin:8px 0;padding:8px 10px;background:#fff;border-radius:8px;border-left:3px solid var(--sage,#2d8a62);"><strong>Doctor note for nurse:</strong> ${escapeHtml(c.clinical_notes)}</div>` : ''}
            <ul style="margin:8px 0 0 18px; font-size:13px;">
              ${(c.items || []).map(i => `<li><strong>${escapeHtml(i.medicine_name)}</strong> ${escapeHtml(i.dosage)} · ${escapeHtml((i.route||'').toUpperCase())} · ${escapeHtml(i.frequency)}
                ${i.drip_rate ? ` · Drip ${escapeHtml(i.drip_rate)}` : ''}</li>`).join('')}
            </ul>
          </div>
        `).join('') : '<p style="color:var(--text-light); font-size:13px;">No medication course ordered yet</p>'}
      </div>`;
    }
    el.innerHTML = html;
  } catch (e) {
    console.error(e);
    el.innerHTML = '<p style="color:var(--text-light);">Unable to load patient courses</p>';
  }
}

document.getElementById('tasks-status-filter')?.addEventListener('change', loadTodayDoses);
document.getElementById('tasks-date')?.addEventListener('change', loadTodayDoses);


// Close dose modal when clicking the dimmed backdrop (not the dialog itself)
document.getElementById('dose-modal')?.addEventListener('click', (e) => {
  if (e.target && e.target.id === 'dose-modal') closeDoseModal();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const modal = document.getElementById('dose-modal');
    if (modal && modal.classList.contains('active')) closeDoseModal();
  }
});
