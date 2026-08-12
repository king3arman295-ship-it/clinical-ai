// Admin Portal Functionality
let allDoctors = [];
let allPatients = [];
let allAppointments = [];
let allSchedules = [];
let currentFilter = 'all';

// Show a real name instead of a raw id wherever we only have one.
function doctorLabel(doctorId) {
  const doctor = allDoctors.find(d => d.id === doctorId);
  const name = doctor ? doctor.full_name : `#${doctorId}`;
  const clean = String(name).replace(/^Dr\.?\s+/i, '');
  return `Dr. ${Utils.escapeHtml(clean)}`;
}

function patientLabel(patientId) {
  const patient = allPatients.find(p => p.id === patientId);
  return patient ? Utils.escapeHtml(patient.name) : `Patient #${patientId}`;
}

document.addEventListener('DOMContentLoaded', async function() {
  // Prevent redirect loop
  const isRedirecting = sessionStorage.getItem('auth_redirecting');
  
  // Check authentication
  const role = Auth.getRole();
  if (!Auth.isAuthenticated() || (role !== 'admin' && role !== 'receptionist')) {
    if (!isRedirecting) {
      sessionStorage.setItem('auth_redirecting', 'true');
      window.location.replace('login.html?redirect=admin-portal.html');
    }
    return;
  }

  // Clear redirect flag
  sessionStorage.removeItem('auth_redirecting');

    if (typeof setupSessionGuards === 'function') setupSessionGuards();


  // Register FCM token for push notifications
  if (window.sendFCMTokenToBackend) {
    window.sendFCMTokenToBackend();
  }

  loadUserInfo();
  setupNavigation();
  setupForms();
  loadDashboard();
});

function loadUserInfo() {
  const user = Auth.getUser();
  if (user) {
    document.getElementById('user-name').textContent = user.username;
    document.getElementById('user-role').textContent = user.role.toUpperCase();
    const greet = document.getElementById('dashboard-greeting-name');
    if (greet) greet.textContent = user.username || 'Admin';
    const dateEl = document.getElementById('dashboard-date');
    if (dateEl) {
      dateEl.textContent = new Date().toLocaleDateString(undefined, {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
      });
    }
  }
}

function setupNavigation() {
  document.querySelectorAll('.sidebar-link').forEach(link => {
    // Links like "Admission Desk" point to a real separate page
    // (admission-portal.html) and have no data-page attribute — they
    // must navigate normally. Intercepting them with preventDefault()
    // called showPage(undefined), which deactivated every in-page
    // section and left the main content area blank instead of leaving
    // the current page (or letting the browser navigate away).
    if (!link.dataset.page) return;

    link.addEventListener('click', (e) => {
      e.preventDefault();
      const page = link.dataset.page;
      showPage(page);
    });
  });
}

function setupForms() {
  document.getElementById('add-doctor-form').addEventListener('submit', addDoctor);
  document.getElementById('add-schedule-form').addEventListener('submit', addSchedule);
  document.getElementById('add-patient-form').addEventListener('submit', addPatient);
  document.getElementById('add-appointment-form').addEventListener('submit', addAppointment);
  
  // Search functionality
  document.getElementById('search-doctors')?.addEventListener('input', renderDoctors);
  document.getElementById('search-patients')?.addEventListener('input', renderPatients);
  document.getElementById('search-appointments')?.addEventListener('input', renderAppointments);
}

function showPage(pageName) {
  document.querySelectorAll('.sidebar-link').forEach(link => {
    link.classList.toggle('active', link.dataset.page === pageName);
  });
  
  document.querySelectorAll('.page').forEach(page => {
    page.classList.toggle('active', page.id === `page-${pageName}`);
  });
  
  switch(pageName) {
    case 'dashboard':
      loadDashboard();
      break;
    case 'doctors':
      loadDoctors();
      break;
    case 'patients':
      loadPatients();
      break;
    case 'appointments':
      loadAppointments();
      break;
    case 'schedules':
      loadSchedules();
      break;
    case 'staff':
      loadStaffAccounts();
      break;
    case 'pricing':
      loadServicePricing();
      break;
  }
}

// Dashboard Functions
async function loadDashboard() {
  try {
    const [doctors, patients, appointments] = await Promise.all([
      API.get('/doctors/'),
      API.get('/patients/'),
      API.get('/appointments/')
    ]);

    allDoctors = doctors || [];
    allPatients = patients || [];
    allAppointments = appointments || [];

    const today = Utils.todayLocalDateStr();
    const todayAppts = appointments.filter(a => a.appointment_date === today);

    document.getElementById('total-doctors').textContent = doctors.length;
    document.getElementById('total-patients').textContent = patients.length;
    document.getElementById('total-appointments').textContent = appointments.length;
    document.getElementById('today-appointments').textContent = todayAppts.length;

    if (window.PortalUI) {
      PortalUI.ensureChartJs(function () {
        const weekly = PortalUI.weeklyCounts(appointments, 'appointment_date');
        PortalUI.lineChart('portal-trend-chart', weekly.labels, weekly.data, 'Appointments');
        const statuses = {};
        appointments.forEach(a => {
          const s = (a.status || 'unknown').toLowerCase();
          statuses[s] = (statuses[s] || 0) + 1;
        });
        const labels = Object.keys(statuses);
        const data = labels.map(k => statuses[k]);
        if (labels.length) PortalUI.doughnutChart('portal-status-chart', labels, data);
      });
    }

    renderDoctorAvailability();

    // Show recent appointments
    const recent = appointments.slice(0, 10);
    const recentDiv = document.getElementById('recent-appointments');
    
    if (recent.length === 0) {
      recentDiv.innerHTML = '<p style="text-align: center; padding: 20px; color: var(--text-light);">No appointments yet</p>';
    } else {
      recentDiv.innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Patient</th>
              <th>Doctor</th>
              <th>Date</th>
              <th>Time</th>
              <th>Type</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${recent.map(a => `
              <tr>
                <td>#${a.id}</td>
                <td>${patientLabel(a.patient_id)}</td>
                <td>${doctorLabel(a.doctor_id)}</td>
                <td>${Utils.formatDate(a.appointment_date)}</td>
                <td>${Utils.formatTime(a.appointment_time)}</td>
                <td>${a.appointment_type === 'video' ? `${Icons.video} Video` : `${Icons.hospital} Physical`}</td>
                <td><span class="badge badge-${getStatusBadge(a.status)}">${a.status}</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }
  } catch (error) {
    console.error('Failed to load dashboard:', error);
    Utils.showToast('Failed to load dashboard', 'error');
  }
}

function renderDoctorAvailability() {
  const container = document.getElementById('doctor-availability-overview');
  if (!container) return;

  if (allDoctors.length === 0) {
    container.innerHTML = '<p style="text-align: center; padding: 20px; color: var(--text-light);">No doctors added yet</p>';
    return;
  }

  const available = allDoctors.filter(d => d.available);
  const unavailable = allDoctors.filter(d => !d.available);

  const renderChip = (d) => `
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--bg-alt); border-radius: 8px; margin-bottom: 8px;">
      <div>
        <strong style="font-size: 14px;">${Utils.escapeHtml(d.full_name)}</strong>
        <div style="font-size: 12px; color: var(--text-light);">${Utils.escapeHtml(d.specialization)}</div>
      </div>
      <span class="badge ${d.available ? 'badge-success' : 'badge-danger'}">${d.available ? 'Available' : 'Unavailable'}</span>
    </div>
  `;

  container.innerHTML = `
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px;">
      <div>
        <h3 style="font-size: 15px; margin-bottom: 12px; color: var(--success);">${Icons.checkCircle} Available (${available.length})</h3>
        ${available.length ? available.map(renderChip).join('') : '<p style="color: var(--text-light); font-size: 13px;">No doctors currently available</p>'}
      </div>
      <div>
        <h3 style="font-size: 15px; margin-bottom: 12px; color: var(--rust, #B4614C);">${Icons.banCircle} Unavailable (${unavailable.length})</h3>
        ${unavailable.length ? unavailable.map(renderChip).join('') : '<p style="color: var(--text-light); font-size: 13px;">All doctors are currently available</p>'}
      </div>
    </div>
  `;
}

// Doctors Management
async function loadDoctors() {
  try {
    allDoctors = await API.get('/doctors/');
    renderDoctors();
  } catch (error) {
    console.error('Failed to load doctors:', error);
    Utils.showToast('Failed to load doctors', 'error');
  }
}

function renderDoctors() {
  const search = document.getElementById('search-doctors')?.value.toLowerCase() || '';
  const filtered = allDoctors.filter(d => 
    d.full_name.toLowerCase().includes(search) ||
    d.specialization.toLowerCase().includes(search)
  );

  const listDiv = document.getElementById('doctors-list');
  
  if (filtered.length === 0) {
    listDiv.innerHTML = '<p style="text-align: center; padding: 20px; color: var(--text-light);">No doctors found</p>';
    return;
  }

  listDiv.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Specialization</th>
          <th>Experience</th>
          <th>Fee</th>
          <th>Phone</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${filtered.map(d => `
          <tr>
            <td><strong>${Utils.escapeHtml(d.full_name)}</strong></td>
            <td>${Utils.escapeHtml(d.specialization)}</td>
            <td>${d.experience_years || 0} years</td>
            <td>Rs. ${d.consultation_fee || 0}</td>
            <td>${Utils.escapeHtml(d.phone || '—')}</td>
            <td><span class="badge ${d.available ? 'badge-success' : 'badge-danger'}">${d.available ? 'Available' : 'Unavailable'}</span></td>
            <td>
              <button class="btn btn-ghost btn-sm" onclick="openEditDoctorModal(${d.id})">Edit</button>
              <button class="btn btn-ghost btn-sm" onclick="toggleDoctorAvailability(${d.id}, ${!d.available})">
                ${d.available ? 'Mark Unavailable' : 'Mark Available'}
              </button>
              <button class="btn btn-danger btn-sm" onclick="deleteDoctor(${d.id})">Delete</button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function toggleDoctorForm() {
  const m = document.getElementById('add-doctor-modal');
  if (m && m.classList.contains('active')) closeAddDoctorModal();
  else openAddDoctorModal();
}

async function addDoctor(e) {
  e.preventDefault();
  
  try {
    const data = {
      full_name: document.getElementById('doctor-name').value,
      specialization: document.getElementById('doctor-specialization').value,
      qualification: document.getElementById('doctor-qualification').value,
      phone: document.getElementById('doctor-phone').value,
      email: document.getElementById('doctor-email').value.trim(),
      username: document.getElementById('doctor-username').value.trim(),
      password: document.getElementById('doctor-password').value,
      experience_years: parseInt(document.getElementById('doctor-experience').value) || 0,
      consultation_fee: parseInt(document.getElementById('doctor-fee').value) || 0,
      available: document.getElementById('doctor-available').value === 'true'
    };

    await API.post('/doctors/', data);
    closeAddDoctorModal();
    Utils.showToast('Doctor profile and login account created successfully!', 'success');
    toggleDoctorForm();
    loadDoctors();
  } catch (error) {
    console.error('Failed to add doctor:', error);
    Utils.showToast(error.message || 'Failed to add doctor', 'error');
  }
}

async function toggleDoctorAvailability(id, available) {
  try {
    await API.put(`/doctors/${id}`, { available });
    Utils.showToast('Doctor status updated', 'success');
    loadDoctors();
  } catch (error) {
    console.error('Failed to update doctor:', error);
    Utils.showToast('Failed to update doctor', 'error');
  }
}

async function deleteDoctor(id) {
  if (!confirm('Are you sure you want to delete this doctor?')) return;
  
  try {
    await API.delete(`/doctors/${id}`);
    Utils.showToast('Doctor deleted successfully', 'success');
    loadDoctors();
  } catch (error) {
    console.error('Failed to delete doctor:', error);
    Utils.showToast('Failed to delete doctor', 'error');
  }
}

// ═══════════════════════════════ GENERIC EDIT MODAL ═══════════════════════════════
let currentFormModalType = null;
let currentFormModalId = null;

function openFormModal(title) {
  document.getElementById('form-modal-title').textContent = title;
  document.getElementById('form-modal').classList.add('active');
}

function closeFormModal() {
  document.getElementById('form-modal').classList.remove('active');
  currentFormModalType = null;
  currentFormModalId = null;
}

function openEditDoctorModal(id) {
  const doctor = allDoctors.find(d => d.id === id);
  if (!doctor) return;

  currentFormModalType = 'doctor';
  currentFormModalId = id;

  document.getElementById('form-modal-body').innerHTML = `
    <div class="form-group">
      <label class="form-label">Full Name</label>
      <input type="text" class="form-input" id="edit-doctor-name" value="${Utils.escapeHtml(doctor.full_name)}" required>
    </div>
    <div class="form-group">
      <label class="form-label">Specialization</label>
      <input type="text" class="form-input" id="edit-doctor-specialization" value="${Utils.escapeHtml(doctor.specialization)}" required>
    </div>
    <div class="form-group">
      <label class="form-label">Qualification</label>
      <input type="text" class="form-input" id="edit-doctor-qualification" value="${Utils.escapeHtml(doctor.qualification || '')}">
    </div>
    <div class="form-group">
      <label class="form-label">Phone</label>
      <input type="tel" class="form-input" id="edit-doctor-phone" value="${Utils.escapeHtml(doctor.phone || '')}">
    </div>
    <div class="form-group">
      <label class="form-label">Email</label>
      <input type="email" class="form-input" id="edit-doctor-email" value="${Utils.escapeHtml(doctor.email || '')}">
    </div>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
      <div class="form-group">
        <label class="form-label">Experience (years)</label>
        <input type="number" class="form-input" id="edit-doctor-experience" value="${doctor.experience_years || 0}" min="0">
      </div>
      <div class="form-group">
        <label class="form-label">Consultation Fee</label>
        <input type="number" class="form-input" id="edit-doctor-fee" value="${doctor.consultation_fee || 0}" min="0">
      </div>
    </div>
  `;
  openFormModal('Edit Doctor');
}

async function submitFormModal() {
  try {
    if (currentFormModalType === 'doctor') {
      const data = {
        full_name: document.getElementById('edit-doctor-name').value,
        specialization: document.getElementById('edit-doctor-specialization').value,
        qualification: document.getElementById('edit-doctor-qualification').value,
        phone: document.getElementById('edit-doctor-phone').value,
        email: document.getElementById('edit-doctor-email').value.trim(),
        experience_years: parseInt(document.getElementById('edit-doctor-experience').value) || 0,
        consultation_fee: parseInt(document.getElementById('edit-doctor-fee').value) || 0,
      };
      await API.put(`/doctors/${currentFormModalId}`, data);
      Utils.showToast('Doctor updated successfully', 'success');
      closeFormModal();
      loadDoctors();
    } else if (currentFormModalType === 'patient') {
      const data = {
        name: document.getElementById('edit-patient-name').value,
        phone: document.getElementById('edit-patient-phone').value,
        email: document.getElementById('edit-patient-email').value.trim() || null,
      };
      await API.put(`/patients/${currentFormModalId}`, data);
      Utils.showToast('Patient updated successfully', 'success');
      closeFormModal();
      loadPatients();
    } else if (currentFormModalType === 'schedule') {
      const startTime = document.getElementById('edit-schedule-start-time').value;
      const endTime = document.getElementById('edit-schedule-end-time').value;
      if (startTime >= endTime) {
        Utils.showToast('End time must be after start time', 'error');
        return;
      }
      const data = {
        day_of_week: document.getElementById('edit-schedule-day').value,
        start_time: startTime,
        end_time: endTime,
        slot_duration: Number(document.getElementById('edit-schedule-slot-duration').value),
        is_available: document.getElementById('edit-schedule-available').value === 'true',
      };
      await API.put(`/doctor-schedules/${currentFormModalId}`, data);
      Utils.showToast('Schedule updated successfully', 'success');
      closeFormModal();
      loadSchedules();
    }
  } catch (error) {
    console.error('Failed to save changes:', error);
    Utils.showToast(error.message || 'Failed to save changes', 'error');
  }
}

// Patients Management
async function loadPatients() {
  try {
    allPatients = await API.get('/patients/');
    renderPatients();
  } catch (error) {
    console.error('Failed to load patients:', error);
    Utils.showToast('Failed to load patients', 'error');
  }
}

function renderPatients() {
  const search = document.getElementById('search-patients')?.value.toLowerCase() || '';
  const filtered = allPatients.filter(p => 
    p.name.toLowerCase().includes(search) ||
    (p.phone && p.phone.includes(search)) ||
    (p.email && p.email.toLowerCase().includes(search))
  );

  const listDiv = document.getElementById('patients-list');
  
  if (filtered.length === 0) {
    listDiv.innerHTML = '<p style="text-align: center; padding: 20px; color: var(--text-light);">No patients found</p>';
    return;
  }

  listDiv.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Name</th>
          <th>Phone</th>
          <th>Email</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${filtered.map(p => `
          <tr>
            <td><span class="badge badge-info">#${p.id}</span></td>
            <td><strong>${Utils.escapeHtml(p.name)}</strong></td>
            <td>${Utils.escapeHtml(p.phone)}</td>
            <td>${Utils.escapeHtml(p.email || '—')}</td>
            <td>
              <button class="btn btn-ghost btn-sm" onclick="viewPatientEMR(${p.id})">View EMR</button>
              <button class="btn btn-ghost btn-sm" onclick="openEditPatientModal(${p.id})">Edit</button>
              <button class="btn btn-danger btn-sm" onclick="deletePatient(${p.id})">Delete</button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function togglePatientForm() {
  const m = document.getElementById('add-patient-modal');
  if (m && m.classList.contains('active')) closeAddPatientModal();
  else openAddPatientModal();
}

async function addPatient(e) {
  e.preventDefault();

  try {
    const data = {
      name: document.getElementById('patient-name').value,
      phone: document.getElementById('patient-phone').value,
      email: document.getElementById('patient-email').value.trim() || null,
    };

    await API.post('/patients/', data);
    Utils.showToast('Patient added successfully!', 'success');
    togglePatientForm();
    loadPatients();
  } catch (error) {
    console.error('Failed to add patient:', error);
    Utils.showToast(error.message || 'Failed to add patient', 'error');
  }
}

function openEditPatientModal(id) {
  const patient = allPatients.find(p => p.id === id);
  if (!patient) return;

  currentFormModalType = 'patient';
  currentFormModalId = id;

  document.getElementById('form-modal-body').innerHTML = `
    <div class="form-group">
      <label class="form-label">Full Name</label>
      <input type="text" class="form-input" id="edit-patient-name" value="${Utils.escapeHtml(patient.name)}" required>
    </div>
    <div class="form-group">
      <label class="form-label">Phone</label>
      <input type="tel" class="form-input" id="edit-patient-phone" value="${Utils.escapeHtml(patient.phone)}" required>
    </div>
    <div class="form-group">
      <label class="form-label">Email</label>
      <input type="email" class="form-input" id="edit-patient-email" value="${Utils.escapeHtml(patient.email || '')}">
    </div>
  `;
  openFormModal('Edit Patient');
}

async function deletePatient(id) {
  if (!confirm('Are you sure you want to delete this patient? This cannot be undone.')) return;

  try {
    await API.delete(`/patients/${id}`);
    Utils.showToast('Patient deleted successfully', 'success');
    loadPatients();
  } catch (error) {
    console.error('Failed to delete patient:', error);
    Utils.showToast(error.message || 'Failed to delete patient', 'error');
  }
}

// ═══════════════════════════════ EMR VIEWER (read-only, admin) ═══════════════════════════════
let currentEMRViewData = null;
let currentEMRViewTab = 'history';

async function viewPatientEMR(patientId) {
  document.getElementById('emr-view-patient-name').textContent = '...';
  document.getElementById('emr-view-content').innerHTML = '<div class="loading-spinner">Loading EMR...</div>';
  document.getElementById('emr-view-modal').classList.add('active');

  try {
    const timeline = await API.get(`/emr/patients/${patientId}/timeline`);
    currentEMRViewData = timeline;
    document.getElementById('emr-view-patient-name').textContent = timeline.patient_name;
    currentEMRViewTab = 'history';
    document.querySelectorAll('#emr-view-tabs [data-emr-tab]').forEach(btn => {
      btn.className = btn.dataset.emrTab === 'history' ? 'btn btn-primary btn-sm' : 'btn btn-ghost btn-sm';
    });
    renderEMRViewTab('history');
  } catch (error) {
    console.error('Failed to load EMR:', error);
    document.getElementById('emr-view-content').innerHTML = '<p style="text-align: center; padding: 40px; color: var(--text-light);">Failed to load this patient\'s EMR.</p>';
    Utils.showToast(error.message || 'Failed to load patient EMR', 'error');
  }
}

function closeEMRViewModal() {
  document.getElementById('emr-view-modal').classList.remove('active');
  currentEMRViewData = null;
}

function showEMRViewTab(tabName) {
  currentEMRViewTab = tabName;
  document.querySelectorAll('#emr-view-tabs [data-emr-tab]').forEach(btn => {
    btn.className = btn.dataset.emrTab === tabName ? 'btn btn-primary btn-sm' : 'btn btn-ghost btn-sm';
  });
  renderEMRViewTab(tabName);
}

function renderEMRViewTab(tabName) {
  const content = document.getElementById('emr-view-content');
  if (!currentEMRViewData) return;

  const empty = (msg) => `<p style="text-align: center; padding: 40px; color: var(--text-light);">${msg}</p>`;

  if (tabName === 'history') {
    const history = currentEMRViewData.medical_history || [];
    if (!history.length) return void (content.innerHTML = empty('No medical history recorded'));
    content.innerHTML = `
      <table class="table">
        <thead><tr><th>Condition</th><th>Status</th><th>Diagnosed</th><th>Notes</th></tr></thead>
        <tbody>
          ${history.map(h => `
            <tr>
              <td><strong>${Utils.escapeHtml(h.condition)}</strong></td>
              <td><span class="badge ${h.status === 'active' ? 'badge-warning' : h.status === 'resolved' ? 'badge-success' : 'badge-info'}">${h.status}</span></td>
              <td>${Utils.formatDate(h.diagnosed_date)}</td>
              <td>${Utils.escapeHtml(h.notes || '—')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } else if (tabName === 'allergies') {
    const allergies = currentEMRViewData.allergies || [];
    if (!allergies.length) return void (content.innerHTML = empty('No allergies recorded'));
    content.innerHTML = `
      <table class="table">
        <thead><tr><th>Allergy</th><th>Reaction</th><th>Notes</th></tr></thead>
        <tbody>
          ${allergies.map(a => `
            <tr>
              <td><strong>${Utils.escapeHtml(a.allergy_name)}</strong></td>
              <td>${Utils.escapeHtml(a.reaction || '—')}</td>
              <td>${Utils.escapeHtml(a.notes || '—')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } else if (tabName === 'diagnoses') {
    const diagnoses = currentEMRViewData.diagnoses || [];
    if (!diagnoses.length) return void (content.innerHTML = empty('No diagnoses recorded'));
    content.innerHTML = `
      <table class="table">
        <thead><tr><th>Diagnosis</th><th>Severity</th><th>Notes</th><th>Appointment</th></tr></thead>
        <tbody>
          ${diagnoses.map(d => `
            <tr>
              <td><strong>${Utils.escapeHtml(d.diagnosis)}</strong></td>
              <td>${d.severity ? `<span class="badge ${d.severity === 'critical' || d.severity === 'severe' ? 'badge-danger' : d.severity === 'moderate' ? 'badge-warning' : 'badge-info'}">${d.severity}</span>` : '—'}</td>
              <td>${Utils.escapeHtml(d.notes || '—')}</td>
              <td>#${d.appointment_id}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } else if (tabName === 'vitals') {
    const vitals = currentEMRViewData.vitals || [];
    if (!vitals.length) return void (content.innerHTML = empty('No vitals recorded'));
    content.innerHTML = `
      <table class="table">
        <thead><tr><th>Recorded</th><th>BP</th><th>Pulse</th><th>Temp</th><th>Weight</th><th>Height</th><th>O2</th></tr></thead>
        <tbody>
          ${vitals.map(v => `
            <tr>
              <td>${Utils.formatDate(v.recorded_at)}</td>
              <td>${v.blood_pressure || '—'}</td>
              <td>${v.pulse != null ? v.pulse + ' bpm' : '—'}</td>
              <td>${v.temperature != null ? v.temperature + '°F' : '—'}</td>
              <td>${v.weight != null ? v.weight + ' kg' : '—'}</td>
              <td>${v.height != null ? v.height + ' cm' : '—'}</td>
              <td>${v.oxygen_level != null ? v.oxygen_level + '%' : '—'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } else if (tabName === 'prescriptions') {
    const prescriptions = currentEMRViewData.prescriptions || [];
    if (!prescriptions.length) return void (content.innerHTML = empty('No prescriptions recorded'));
    content.innerHTML = prescriptions.map(p => `
      <div style="padding: 16px; background: var(--bg-alt); border-radius: 8px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
          <strong style="font-size: 14px;">${doctorLabel(p.doctor_id)} ${p.diagnosis ? '— ' + Utils.escapeHtml(p.diagnosis) : ''}</strong>
          <span style="font-size: 12px; color: var(--text-light);">${Utils.formatDate(p.created_at)}</span>
        </div>
        ${(p.items || []).length ? `
          <table class="table" style="margin-bottom: 8px;">
            <thead><tr><th>Medicine</th><th>Dosage</th><th>Frequency</th><th>Duration</th><th>Instructions</th></tr></thead>
            <tbody>
              ${p.items.map(item => `
                <tr>
                  <td><strong>${Utils.escapeHtml(item.medicine_name)}</strong></td>
                  <td>${Utils.escapeHtml(item.dosage || '—')}</td>
                  <td>${Utils.escapeHtml(item.frequency || '—')}</td>
                  <td>${Utils.escapeHtml(item.duration || '—')}</td>
                  <td>${Utils.escapeHtml(item.instructions || '—')}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        ` : '<p style="font-size: 13px; color: var(--text-light);">No items listed</p>'}
        ${p.advice ? `<p style="font-size: 13px;"><strong>Advice:</strong> ${Utils.escapeHtml(p.advice)}</p>` : ''}
      </div>
    `).join('');
  } else if (tabName === 'notes') {
    const notes = currentEMRViewData.doctor_notes || [];
    if (!notes.length) return void (content.innerHTML = empty('No doctor notes recorded'));
    content.innerHTML = notes.map(n => `
      <div style="padding: 16px; background: var(--bg-alt); border-radius: 8px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
          <strong style="font-size: 14px;">${doctorLabel(n.doctor_id)}</strong>
          <span style="font-size: 12px; color: var(--text-light);">${Utils.formatDate(n.created_at)}</span>
        </div>
        <p style="font-size: 14px; line-height: 1.6; white-space: pre-wrap;">${Utils.escapeHtml(n.note)}</p>
      </div>
    `).join('');
  } else if (tabName === 'reports') {
    const reports = currentEMRViewData.reports || [];
    if (!reports.length) return void (content.innerHTML = empty('No reports uploaded'));
    content.innerHTML = `
      <table class="table">
        <thead><tr><th>Name</th><th>Type</th><th>Uploaded</th><th>Actions</th></tr></thead>
        <tbody>
          ${reports.map(r => `
            <tr>
              <td><strong>${Utils.escapeHtml(r.report_name)}</strong></td>
              <td><span class="badge badge-info">${r.report_type}</span></td>
              <td>${Utils.formatDate(r.uploaded_at)}</td>
              <td><button class="btn btn-ghost btn-sm" onclick="downloadEMRReport(${r.id})">${Icons.download} Download</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }
}

async function downloadEMRReport(reportId) {
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

// Appointments Management
async function loadAppointments() {
  try {
    const [appointments, patients, doctors] = await Promise.all([
      API.get('/appointments/'),
      API.get('/patients/'),
      API.get('/doctors/'),
    ]);
    allAppointments = appointments || [];
    allPatients = patients || [];
    allDoctors = doctors || [];
    populateAppointmentSelects();
    renderAppointments();
  } catch (error) {
    console.error('Failed to load appointments:', error);
    Utils.showToast('Failed to load appointments', 'error');
  }
}

function populateAppointmentSelects() {
  const patientSelect = document.getElementById('appointment-patient');
  const doctorSelect = document.getElementById('appointment-doctor');
  if (patientSelect) {
    patientSelect.innerHTML = '<option value="">Select a patient</option>' + allPatients.map(p =>
      `<option value="${p.id}">${Utils.escapeHtml(p.name)} — ${Utils.escapeHtml(p.phone)}</option>`
    ).join('');
  }
  if (doctorSelect) {
    doctorSelect.innerHTML = '<option value="">Select a doctor</option>' + allDoctors.map(d =>
      `<option value="${d.id}">${Utils.escapeHtml(d.full_name)} — ${Utils.escapeHtml(d.specialization)}</option>`
    ).join('');
  }
}

function toggleAppointmentForm() {
  const m = document.getElementById('add-appointment-modal');
  if (m && m.classList.contains('active')) closeAddAppointmentModal();
  else openAddAppointmentModal();
}

async function addAppointment(e) {
  e.preventDefault();

  try {
    const data = {
      patient_id: Number(document.getElementById('appointment-patient').value),
      doctor_id: Number(document.getElementById('appointment-doctor').value),
      appointment_date: document.getElementById('appointment-date').value,
      appointment_time: document.getElementById('appointment-time').value,
      appointment_type: document.getElementById('appointment-type').value,
      reason: document.getElementById('appointment-reason').value.trim() || null,
    };

    await API.post('/appointments/', data);
    closeAddAppointmentModal();
    Utils.showToast('Appointment booked successfully!', 'success');
    toggleAppointmentForm();
    loadAppointments();
  } catch (error) {
    console.error('Failed to book appointment:', error);
    Utils.showToast(error.message || 'Failed to book appointment', 'error');
  }
}

function filterAppointments(status) {
  currentFilter = status;
  document.querySelectorAll('[data-filter-btn]').forEach(btn => {
    btn.className = btn.dataset.filterBtn === status ? 'btn btn-primary' : 'btn btn-ghost';
  });
  renderAppointments();
}

function renderAppointments() {
  const search = document.getElementById('search-appointments')?.value.toLowerCase() || '';
  let filtered = allAppointments;
  
  if (currentFilter !== 'all') {
    filtered = filtered.filter(a => a.status === currentFilter);
  }
  
  if (search) {
    filtered = filtered.filter(a => 
      a.reason?.toLowerCase().includes(search) ||
      String(a.id).includes(search)
    );
  }

  filtered = filtered.sort((a, b) => b.id - a.id);

  const listDiv = document.getElementById('appointments-list');
  
  if (filtered.length === 0) {
    listDiv.innerHTML = '<p style="text-align: center; padding: 20px; color: var(--text-light);">No appointments found</p>';
    return;
  }

  listDiv.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Patient</th>
          <th>Doctor</th>
          <th>Date</th>
          <th>Time</th>
          <th>Type</th>
          <th>Reason</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${filtered.map(a => `
          <tr>
            <td>#${a.id}</td>
            <td>${patientLabel(a.patient_id)}</td>
            <td>${doctorLabel(a.doctor_id)}</td>
            <td>${Utils.formatDate(a.appointment_date)}</td>
            <td>${Utils.formatTime(a.appointment_time)}</td>
            <td>${a.appointment_type === 'video' ? `${Icons.video} Video` : a.appointment_type === 'home' ? `${Icons.home} Home` : `${Icons.hospital} Physical`}</td>
            <td>${Utils.escapeHtml(a.reason || '—')}</td>
            <td>
              <select class="form-select" style="font-size: 12px; padding: 4px 8px;" onchange="updateAppointmentStatus(${a.id}, this.value)">
                <option value="scheduled" ${a.status === 'scheduled' ? 'selected' : ''}>Scheduled</option>
                <option value="completed" ${a.status === 'completed' ? 'selected' : ''}>Completed</option>
                <option value="cancelled" ${a.status === 'cancelled' ? 'selected' : ''}>Cancelled</option>
              </select>
            </td>
            <td>
              <button class="btn btn-danger btn-sm" onclick="deleteAppointment(${a.id})">Delete</button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

async function updateAppointmentStatus(id, status) {
  try {
    await API.put(`/appointments/${id}`, { status });
    Utils.showToast('Appointment status updated', 'success');
    loadAppointments();
  } catch (error) {
    console.error('Failed to update appointment:', error);
    Utils.showToast('Failed to update appointment', 'error');
    loadAppointments();
  }
}

async function deleteAppointment(id) {
  if (!confirm('Are you sure you want to delete this appointment?')) return;
  
  try {
    await API.delete(`/appointments/${id}`);
    Utils.showToast('Appointment deleted successfully', 'success');
    loadAppointments();
  } catch (error) {
    console.error('Failed to delete appointment:', error);
    Utils.showToast('Failed to delete appointment', 'error');
  }
}

// Schedules Management
async function loadSchedules() {
  try {
    const [schedules, doctors] = await Promise.all([
      API.get('/doctor-schedules/'),
      API.get('/doctors/')
    ]);
    allSchedules = schedules || [];
    allDoctors = doctors || [];
    populateScheduleDoctorSelect();
    renderSchedules();
  } catch (error) {
    console.error('Failed to load schedules:', error);
    Utils.showToast('Failed to load schedules', 'error');
  }
}

function populateScheduleDoctorSelect() {
  const select = document.getElementById('schedule-doctor');
  const selectedDoctorId = select.value;
  select.innerHTML = '<option value="">Select a doctor</option>' + allDoctors.map(doctor =>
    `<option value="${doctor.id}">${Utils.escapeHtml(doctor.full_name)} — ${Utils.escapeHtml(doctor.specialization)}</option>`
  ).join('');
  select.value = selectedDoctorId;
}

async function addSchedule(event) {
  event.preventDefault();

  const startTime = document.getElementById('schedule-start-time').value;
  const endTime = document.getElementById('schedule-end-time').value;
  if (startTime >= endTime) {
    Utils.showToast('End time must be after start time', 'error');
    return;
  }

  try {
    await API.post('/doctor-schedules/', {
      doctor_id: Number(document.getElementById('schedule-doctor').value),
      day_of_week: document.getElementById('schedule-day').value,
      start_time: startTime,
      end_time: endTime,
      slot_duration: Number(document.getElementById('schedule-slot-duration').value),
      is_available: document.getElementById('schedule-available').value === 'true'
    });
    Utils.showToast('Doctor schedule added successfully', 'success');
    closeAddScheduleModal();
    event.target.reset();
    loadSchedules();
  } catch (error) {
    console.error('Failed to add doctor schedule:', error);
    Utils.showToast(error.message || 'Failed to add doctor schedule', 'error');
  }
}

function renderSchedules() {
  const listDiv = document.getElementById('schedules-list');
  
  if (allSchedules.length === 0) {
    listDiv.innerHTML = '<p style="text-align: center; padding: 20px; color: var(--text-light);">No schedules found</p>';
    return;
  }

  listDiv.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th>Doctor</th>
          <th>Day</th>
          <th>Start Time</th>
          <th>End Time</th>
          <th>Slot Duration</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${allSchedules.map(s => `
          <tr>
            <td>${Utils.escapeHtml(allDoctors.find(d => d.id === s.doctor_id)?.full_name || `Doctor #${s.doctor_id}`)}</td>
            <td>${s.day_of_week}</td>
            <td>${Utils.formatTime(s.start_time)}</td>
            <td>${Utils.formatTime(s.end_time)}</td>
            <td>${s.slot_duration} min</td>
            <td><span class="badge ${s.is_available ? 'badge-success' : 'badge-danger'}">${s.is_available ? 'Available' : 'Unavailable'}</span></td>
            <td>
              <button class="btn btn-ghost btn-sm" onclick="openEditScheduleModal(${s.id})">Edit</button>
              <button class="btn btn-danger btn-sm" onclick="deleteSchedule(${s.id})">Delete</button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function openEditScheduleModal(id) {
  const schedule = allSchedules.find(s => s.id === id);
  if (!schedule) return;

  currentFormModalType = 'schedule';
  currentFormModalId = id;

  const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const durations = [15, 20, 30, 45, 60];

  document.getElementById('form-modal-body').innerHTML = `
    <div class="form-group">
      <label class="form-label">Doctor</label>
      <input type="text" class="form-input" value="${Utils.escapeHtml(allDoctors.find(d => d.id === schedule.doctor_id)?.full_name || `Doctor #${schedule.doctor_id}`)}" disabled>
    </div>
    <div class="form-group">
      <label class="form-label">Day</label>
      <select class="form-select" id="edit-schedule-day">
        ${days.map(d => `<option value="${d}" ${schedule.day_of_week === d ? 'selected' : ''}>${d}</option>`).join('')}
      </select>
    </div>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
      <div class="form-group">
        <label class="form-label">Start Time</label>
        <input type="time" class="form-input" id="edit-schedule-start-time" value="${String(schedule.start_time).slice(0,5)}" required>
      </div>
      <div class="form-group">
        <label class="form-label">End Time</label>
        <input type="time" class="form-input" id="edit-schedule-end-time" value="${String(schedule.end_time).slice(0,5)}" required>
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">Appointment Slot</label>
      <select class="form-select" id="edit-schedule-slot-duration">
        ${durations.map(d => `<option value="${d}" ${schedule.slot_duration === d ? 'selected' : ''}>${d} minutes</option>`).join('')}
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Status</label>
      <select class="form-select" id="edit-schedule-available">
        <option value="true" ${schedule.is_available ? 'selected' : ''}>Available</option>
        <option value="false" ${!schedule.is_available ? 'selected' : ''}>Unavailable</option>
      </select>
    </div>
  `;
  openFormModal('Edit Schedule');
}

async function deleteSchedule(id) {
  if (!confirm('Are you sure you want to delete this schedule?')) return;

  try {
    await API.delete(`/doctor-schedules/${id}`);
    Utils.showToast('Schedule deleted successfully', 'success');
    loadSchedules();
  } catch (error) {
    console.error('Failed to delete schedule:', error);
    Utils.showToast(error.message || 'Failed to delete schedule', 'error');
  }
}

// Helper Functions
function getStatusBadge(status) {
  const badges = {
    'scheduled': 'info',
    'completed': 'success',
    'cancelled': 'danger'
  };
  return badges[status] || 'info';
}

function logout() {
  Auth.clear();
  window.location.replace('login.html?force=1');
}

// ═══════════════════════════════ STAFF ACCOUNTS ═══════════════════════════════
// Uses the existing /auth/register endpoint (open to any role string) — this
// screen just gives admins a UI for it instead of needing raw API calls.
// Works the same way for every non-clinical role: admission_head, pharmacist,
// receptionist, or an extra admin account.
//
// Staff accounts are loaded from GET /auth/staff (backed by the users
// table), not kept only in a page-local array — the old version stored new
// accounts in an in-memory array only, so the list reset to empty on every
// refresh even though the accounts existed fine in the database.
let staffAccounts = [];

const STAFF_ROLE_LABELS = {
  admission_head: 'Admission Head',
  pharmacist: 'Pharmacist',
  lab_technician: 'Lab Technician',
  nurse: 'Nurse',
  billing: 'Billing Clerk',
  receptionist: 'Receptionist',
  admin: 'Admin',
};

async function loadStaffAccounts() {
  const el = document.getElementById('staff-list');
  if (el) el.innerHTML = '<div class="loading-spinner">Loading staff accounts...</div>';
  try {
    staffAccounts = await API.get('/auth/staff');
    renderStaffList();
  } catch (error) {
    console.error('Failed to load staff accounts:', error);
    if (el) el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">Failed to load staff accounts.</p>';
  }
}

async function submitStaffForm(e) {
  e.preventDefault();

  const username = document.getElementById('staff-username').value.trim();
  const email = document.getElementById('staff-email').value.trim();
  const password = document.getElementById('staff-password').value;
  const role = document.getElementById('staff-role').value;
  const submitBtn = e.target.querySelector('button[type="submit"]');

  if (!username || !email || !password) {
    Utils.showToast('Please fill in all fields', 'error');
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Creating...';

  try {
    await API.post('/auth/register', { username, email, password, role });
    Utils.showToast(`${STAFF_ROLE_LABELS[role] || role} account created for "${username}"`, 'success');

    document.getElementById('staff-form').reset();
    document.getElementById('staff-role').value = 'admission_head';
    await loadStaffAccounts();
  } catch (error) {
    console.error('Failed to create staff account:', error);
    Utils.showToast(error.message || 'Failed to create staff account', 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Create Account';
  }
}

function renderStaffList() {
  const el = document.getElementById('staff-list');
  if (staffAccounts.length === 0) {
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No staff accounts created yet.</p>';
    return;
  }

  el.innerHTML = `
    <div class="table-responsive">
      <table class="table">
        <thead><tr><th>Username</th><th>Email</th><th>Role</th></tr></thead>
        <tbody>
          ${staffAccounts.map(s => `
            <tr>
              <td><strong>${Utils.escapeHtml(s.username)}</strong></td>
              <td>${Utils.escapeHtml(s.email)}</td>
              <td><span class="badge badge-info">${Utils.escapeHtml(STAFF_ROLE_LABELS[s.role] || s.role)}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

// ═════════════════════════════════════════════════════════════
// Service Pricing (hospital-wide fees for billing)
// ═════════════════════════════════════════════════════════════
async function loadServicePricing() {
  const el = document.getElementById('service-pricing-list');
  if (!el) return;
  el.innerHTML = '<div class="loading-spinner">Loading...</div>';
  try {
    const res = await API.get('/billing/service-pricing');
    const rows = Array.isArray(res) ? res : (res?.data || []);
    if (!rows.length) {
      el.innerHTML = '<div class="empty-state">No pricing rows yet. They will seed on first load after migration.</div>';
      return;
    }
    el.innerHTML = `
      <div class="table-responsive">
        <table class="table">
          <thead>
            <tr><th>Fee</th><th>Key</th><th>Amount</th><th>Description</th><th>Actions</th></tr>
          </thead>
          <tbody>
            ${rows.map(r => `
              <tr>
                <td><strong>${escapeHtml(r.label || r.key)}</strong></td>
                <td><code>${escapeHtml(r.key)}</code></td>
                <td>
                  <input type="number" class="form-input" id="price-${escapeHtml(r.key)}" value="${Number(r.amount).toFixed(2)}" min="0" step="0.01" style="max-width:120px;">
                </td>
                <td style="font-size:13px;color:var(--text-light);">${escapeHtml(r.description || '—')}</td>
                <td><button type="button" class="btn btn-primary btn-sm" onclick="saveServicePrice('${escapeHtml(r.key)}')">Save</button></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
      <p style="margin-top:12px;font-size:13px;color:var(--text-light);">
        Medicine prices are set in Pharmacy inventory. Lab test prices in Laboratory catalog. Bed rates on each Ward. Doctor consultation fee on each doctor profile.
      </p>`;
  } catch (e) {
    el.innerHTML = `<div class="empty-state">${escapeHtml(e.message || String(e))}</div>`;
  }
}

async function saveServicePrice(key) {
  const input = document.getElementById('price-' + key);
  if (!input) return;
  const amount = parseFloat(input.value);
  if (isNaN(amount) || amount < 0) {
    Utils.showToast('Enter a valid amount', 'error');
    return;
  }
  try {
    await API.put('/billing/service-pricing/' + encodeURIComponent(key), { amount });
    Utils.showToast('Price updated', 'success');
    loadServicePricing();
  } catch (e) {
    Utils.showToast(e.message || String(e), 'error');
  }
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}


function openAddDoctorModal() {
  const m = document.getElementById('add-doctor-modal');
  if (m) { m.classList.add('active'); document.body.appendChild(m); }
}
function closeAddDoctorModal() {
  const m = document.getElementById('add-doctor-modal');
  const form = document.getElementById('add-doctor-form');
  if (m) m.classList.remove('active');
  if (form) form.reset();
}
function toggleDoctorForm() {
  const m = document.getElementById('add-doctor-modal');
  if (m && m.classList.contains('active')) closeAddDoctorModal();
  else openAddDoctorModal();
}

function openAddPatientModal() {
  const m = document.getElementById('add-patient-modal');
  if (m) { m.classList.add('active'); document.body.appendChild(m); }
}
function closeAddPatientModal() {
  const m = document.getElementById('add-patient-modal');
  const form = document.getElementById('add-patient-form');
  if (m) m.classList.remove('active');
  if (form) form.reset();
}
function togglePatientForm() {
  const m = document.getElementById('add-patient-modal');
  if (m && m.classList.contains('active')) closeAddPatientModal();
  else openAddPatientModal();
}

function openAddAppointmentModal() {
  const m = document.getElementById('add-appointment-modal');
  if (m) { m.classList.add('active'); document.body.appendChild(m); }
  // populate dropdowns if loaders exist
  if (typeof populateAppointmentFormSelects === 'function') {
    try { populateAppointmentFormSelects(); } catch (e) {}
  }
}
function closeAddAppointmentModal() {
  const m = document.getElementById('add-appointment-modal');
  const form = document.getElementById('add-appointment-form');
  if (m) m.classList.remove('active');
  if (form) form.reset();
}
function toggleAppointmentForm() {
  const m = document.getElementById('add-appointment-modal');
  if (m && m.classList.contains('active')) closeAddAppointmentModal();
  else openAddAppointmentModal();
}

function openAddScheduleModal() {
  const m = document.getElementById('add-schedule-modal');
  if (m) { m.classList.add('active'); document.body.appendChild(m); }
  if (typeof loadScheduleDoctorOptions === 'function') {
    try { loadScheduleDoctorOptions(); } catch (e) {}
  }
}
function closeAddScheduleModal() {
  const m = document.getElementById('add-schedule-modal');
  const form = document.getElementById('add-schedule-form');
  if (m) m.classList.remove('active');
  if (form) form.reset();
}
