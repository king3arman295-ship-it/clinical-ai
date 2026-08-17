
/** Open the EMR form modal above View EMR (z-index stack). */
function openFormModal() {
  const el = document.getElementById('emr-modal');
  if (!el) return;
  el.style.zIndex = '2300';
  el.classList.add('active');
}
function openViewEMRModal() {
  const el = document.getElementById('emr-view-modal');
  if (!el) return;
  el.style.zIndex = '2000';
  el.classList.add('active');
}


/** Merge live pharmacy inventory names into MEDICINE_LIBRARY so prescribe/course match stock. */
async function loadPharmacyMedicineLibrary() {
  try {
    const res = await API.get('/pharmacy/medicines');
    const list = Array.isArray(res) ? res : (res?.data || []);
    const names = list.map(m => m.name).filter(Boolean);
    if (!names.length) return;
    const existing = new Set((window.MEDICINE_LIBRARY || []).map(x => String(x).toLowerCase()));
    names.forEach(n => {
      if (!existing.has(String(n).toLowerCase())) {
        (window.MEDICINE_LIBRARY = window.MEDICINE_LIBRARY || []).push(n);
        existing.add(String(n).toLowerCase());
      }
    });
    // Prefer inventory names at the front
    window.MEDICINE_LIBRARY = [
      ...names,
      ...(window.MEDICINE_LIBRARY || []).filter(
        x => !names.some(n => n.toLowerCase() === String(x).toLowerCase())
      ),
    ];
  } catch (e) {
    console.warn('Could not load pharmacy medicines for library', e);
  }
}

// Doctor Portal Functionality
let allAppointments = [];
let allPatients = [];
let mySchedule = [];
let currentFilter = 'all';

// Patient/doctor name lookups, so the UI shows "John Doe" / "Dr. Jane
// Smith" instead of "Patient #12" / "Dr. #4" everywhere a record only
// stores an id. allPatients (loaded lazily by loadPatients()) only has
// this doctor's own patients, so we keep a separate full directory here.
let patientsById = {};
let doctorsById = {};

async function ensureDirectoriesLoaded() {
  try {
    const [patients, doctors] = await Promise.all([
      Object.keys(patientsById).length ? null : API.get('/patients/').catch(() => []),
      Object.keys(doctorsById).length ? null : API.get('/doctors/').catch(() => []),
    ]);
    if (patients) patientsById = Object.fromEntries(patients.map(p => [p.id, p]));
    if (doctors) doctorsById = Object.fromEntries(doctors.map(d => [d.id, d]));
  } catch (error) {
    console.error('Failed to load patient/doctor directory:', error);
  }
}

function patientLabel(patientId) {
  const patient = patientsById[patientId];
  return patient ? Utils.escapeHtml(patient.name) : `Patient #${patientId}`;
}

function doctorLabel(doctorId) {
  const doctor = doctorsById[doctorId];
  const name = doctor ? doctor.full_name : `#${doctorId}`;
  const clean = String(name).replace(/^Dr\.?\s+/i, '');
  return `Dr. ${Utils.escapeHtml(clean)}`;
}

// Video call variables
let agoraClient = null;
let localAudioTrack = null;
let localVideoTrack = null;
let micEnabled = true;
let cameraEnabled = true;

document.addEventListener('DOMContentLoaded', async function() {
  // Prevent redirect loop
  const isRedirecting = sessionStorage.getItem('auth_redirecting');
  
  // Check authentication
  if (!Auth.isAuthenticated() || Auth.getRole() !== 'doctor') {
    if (!isRedirecting) {
      sessionStorage.setItem('auth_redirecting', 'true');
      window.location.href = 'login.html?redirect=doctor-portal.html';
    }
    return;
  }

  // Clear redirect flag
  sessionStorage.removeItem('auth_redirecting');

  // Register FCM token for push notifications
  if (window.sendFCMTokenToBackend) {
    window.sendFCMTokenToBackend();
  }
  setupNotificationBanner();

  // Initialize
  loadUserInfo();
  loadPharmacyMedicineLibrary();
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

    document.getElementById('user-role').textContent = 'Doctor';
    document.getElementById('user-info').style.display = 'block';
  }
}

// Notifications are never auto-prompted (see firebase.js) — this banner is
// the one explicit, user-initiated way to turn them on if the person didn't
// already grant permission at login.
function setupNotificationBanner() {
  const banner = document.getElementById('notif-permission-banner');
  if (!banner) return;

  const dismissed = sessionStorage.getItem('dp_notif_banner_dismissed');
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
    sessionStorage.setItem('dp_notif_banner_dismissed', 'true');
    banner.style.display = 'none';
  });
}

function setupNavigation() {
  document.querySelectorAll('.sidebar-link').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const page = link.dataset.page;
      showPage(page);
    });
  });

  // Setup search
  document.getElementById('search-appointments')?.addEventListener('input', renderAppointments);
  document.getElementById('search-patients')?.addEventListener('input', renderPatients);
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
    case 'appointments':
      loadAppointments();
      break;
    case 'patients':
      loadPatients();
      break;
    case 'schedule':
      loadSchedule();
      break;
    case 'admissions':
      loadMyAdmissions();
      break;
  }
}

// Dashboard Functions
async function loadDashboard() {
  try {
    const user = Auth.getUser();
    if (!user || !user.doctor_id) {
      Utils.showToast('Doctor profile not found', 'error');
      return;
    }

    // Load all appointments for this doctor
    const appointments = await API.get('/appointments/');
    const myAppointments = appointments.filter(a => a.doctor_id === user.doctor_id);
    
    allAppointments = myAppointments;

    // Get unique patients
    const patientIds = [...new Set(myAppointments.map(a => a.patient_id))];
    const videoAppts = myAppointments.filter(a => a.appointment_type === 'video');
    
    const today = Utils.todayLocalDateStr();
    const todayAppts = myAppointments.filter(a => a.appointment_date === today);

    // Update stats
    document.getElementById('total-appointments').textContent = myAppointments.length;
    document.getElementById('today-appointments').textContent = todayAppts.length;
    document.getElementById('total-patients').textContent = patientIds.length;
    document.getElementById('video-consultations').textContent = videoAppts.length;

    if (window.PortalUI) {
      PortalUI.ensureChartJs(function () {
        const list = typeof allAppointments !== 'undefined' ? allAppointments : [];
        const weekly = PortalUI.weeklyCounts(list, 'appointment_date');
        PortalUI.lineChart('portal-trend-chart', weekly.labels, weekly.data, 'Appointments');
        const statuses = {};
        list.forEach(a => { const s=(a.status||'unknown').toLowerCase(); statuses[s]=(statuses[s]||0)+1; });
        const labels = Object.keys(statuses);
        if (labels.length) PortalUI.doughnutChart('portal-status-chart', labels, labels.map(k=>statuses[k]));
      });
    }

    // Show today's appointments
    const todayList = document.getElementById('today-appointments-list');
    
    if (todayAppts.length === 0) {
      todayList.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No appointments scheduled for today</p>';
    } else {
      todayList.innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Patient</th>
              <th>Type</th>
              <th>Reason</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${todayAppts.map(a => `
              <tr>
                <td><strong>${Utils.formatTime(a.appointment_time)}</strong></td>
                <td>${patientLabel(a.patient_id)}</td>
                <td>${a.appointment_type === 'video' ? `${Icons.video} Video` : `${Icons.hospital} Physical`}</td>
                <td>${Utils.escapeHtml(a.reason || '—')}</td>
                <td><span class="badge badge-${getStatusBadge(a.status)}">${a.status}</span></td>
                <td>
                  ${a.appointment_type === 'video' ? 
                    `<button class="btn btn-primary btn-sm" onclick="quickJoinVideo(${a.id})">Join Call</button>` : 
                    `<button class="btn btn-ghost btn-sm" onclick="viewPatientEMR(${a.patient_id})">View EMR</button>`
                  }
                </td>
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

// Appointments Functions
async function loadAppointments() {
  try {
    const user = Auth.getUser();
    const appointments = await API.get('/appointments/');
    allAppointments = appointments.filter(a => a.doctor_id === user.doctor_id);
    renderAppointments();
  } catch (error) {
    console.error('Failed to load appointments:', error);
    Utils.showToast('Failed to load appointments', 'error');
  }
}

function filterAppointments(status) {
  currentFilter = status;
  renderAppointments();
  
  // Update button styles
  document.querySelectorAll('#page-appointments .btn').forEach(btn => {
    btn.className = 'btn btn-ghost';
  });
  event.target.className = 'btn btn-primary';
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
      String(a.id).includes(search) ||
      String(a.patient_id).includes(search)
    );
  }

  filtered = filtered.sort((a, b) => b.id - a.id);

  const listDiv = document.getElementById('appointments-list');
  
  if (filtered.length === 0) {
    listDiv.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No appointments found</p>';
    return;
  }

  listDiv.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Date</th>
          <th>Time</th>
          <th>Patient</th>
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
            <td>${Utils.formatDate(a.appointment_date)}</td>
            <td>${Utils.formatTime(a.appointment_time)}</td>
            <td>${patientLabel(a.patient_id)}</td>
            <td>${a.appointment_type === 'video' ? `${Icons.video} Video` : `${Icons.hospital} Physical`}</td>
            <td>${Utils.escapeHtml(a.reason || '—')}</td>
            <td>
              <select class="form-select" style="font-size: 12px; padding: 4px 8px;" onchange="updateAppointmentStatus(${a.id}, this.value)">
                <option value="scheduled" ${a.status === 'scheduled' ? 'selected' : ''}>Scheduled</option>
                <option value="completed" ${a.status === 'completed' ? 'selected' : ''}>Completed</option>
                <option value="cancelled" ${a.status === 'cancelled' ? 'selected' : ''}>Cancelled</option>
              </select>
            </td>
            <td>
              <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                ${a.appointment_type === 'video' && a.status !== 'cancelled' && a.status !== 'completed' ?
                  `<button class="btn btn-primary btn-sm" title="Start video call" onclick="quickJoinVideo(${a.id})">${Icons.video}</button>` :
                  ''
                }
                <button class="btn btn-ghost btn-sm" onclick="viewPatientEMR(${a.patient_id})">View EMR</button>
              </div>
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

// Patients Functions
async function loadPatients() {
  try {
    const user = Auth.getUser();
    
    // Get unique patient IDs from doctor's appointments
    const patientIds = [...new Set(allAppointments.map(a => a.patient_id))];
    
    if (patientIds.length === 0) {
      document.getElementById('patients-list').innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No patients yet</p>';
      return;
    }

    // Load all patients
    const allPatientsData = await API.get('/patients/');
    allPatients = allPatientsData.filter(p => patientIds.includes(p.id));
    
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
    String(p.id).includes(search)
  );

  const listDiv = document.getElementById('patients-list');
  
  if (filtered.length === 0) {
    listDiv.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No patients found</p>';
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
          <th>Appointments</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${filtered.map(p => {
          const apptCount = allAppointments.filter(a => a.patient_id === p.id).length;
          return `
            <tr>
              <td><span class="badge badge-info">#${p.id}</span></td>
              <td><strong>${Utils.escapeHtml(p.name)}</strong></td>
              <td>${Utils.escapeHtml(p.phone)}</td>
              <td>${Utils.escapeHtml(p.email || '—')}</td>
              <td>${apptCount} appointments</td>
              <td>
                <button class="btn btn-primary btn-sm" onclick="viewPatientEMR(${p.id})">View EMR</button>
              </td>
            </tr>
          `;
        }).join('')}
      </tbody>
    </table>
  `;
}

async function viewPatientEMR(patientId) {
  try {
    const timeline = await API.get(`/emr/patients/${patientId}/timeline`);
    currentPatientId = patientId;
    currentEMRData = timeline;
    currentEMRContext = 'view';

    const body = document.getElementById('emr-view-body');
    body.innerHTML = `
      <div id="view-emr-panel" style="padding: 4px 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 12px;">
          <h3 style="font-size: 16px; font-weight: 700;">Patient: ${Utils.escapeHtml(timeline.patient_name)}</h3>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button class="btn btn-ghost btn-sm" onclick="openAdmitPatientModal(${patientId})">Admit Patient</button>
            <button class="btn btn-primary btn-sm" onclick="openAddPrescriptionModal()"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="9" width="18" height="6" rx="3" transform="rotate(-30 12 12)"/><path d="M12 8.5v7" transform="rotate(-30 12 12)"/></svg> Add Prescription</button>
            <button class="btn btn-ghost btn-sm" onclick="openAddDiagnosisModal()"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3v6a4 4 0 0 0 8 0V3"/><path d="M6 3H4.5M14 3h1.5"/><path d="M10 13v2.5a5 5 0 0 0 10 0V13.5"/><circle cx="20" cy="12.5" r="1.7"/></svg> Add Diagnosis</button>
            <button class="btn btn-ghost btn-sm" onclick="openAddVitalsModal()"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M2 20h20"/></svg> Add Vitals</button>
            <button class="btn btn-ghost btn-sm" onclick="openAddDoctorNoteModal()"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h4L18.5 9.5a2.1 2.1 0 0 0-3-3L5 17z"/><path d="M14 7l3 3"/></svg> Add Note</button>
          </div>
        </div>

        <div style="display: flex; gap: 8px; flex-wrap: wrap; border-bottom: 1px solid var(--border); padding-bottom: 12px; margin-bottom: 12px;">
          <button class="btn btn-primary btn-sm emr-tab-btn" id="view-tab-prescriptions" onclick="showEMRViewTab('prescriptions')">Prescriptions</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="view-tab-diagnoses" onclick="showEMRViewTab('diagnoses')">Diagnoses</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="view-tab-vitals" onclick="showEMRViewTab('vitals')">Vitals</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="view-tab-history" onclick="showEMRViewTab('history')">Medical History</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="view-tab-allergies" onclick="showEMRViewTab('allergies')">Allergies</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="view-tab-notes" onclick="showEMRViewTab('notes')">Doctor Notes</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="view-tab-reports" onclick="showEMRViewTab('reports')">Reports</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="view-tab-lab" onclick="showEMRViewTab('lab')">Lab Orders</button>
        </div>

        <div id="view-emr-tab-content">
          <div class="loading-spinner">Loading EMR data...</div>
        </div>
      </div>
    `;

    openViewEMRModal();
    showEMRViewTab('prescriptions');
  } catch (error) {
    console.error('Failed to load EMR:', error);
    Utils.showToast('Failed to load patient EMR', 'error');
  }
}

// Re-fetches the timeline and re-renders just the active tab of the
// "View EMR" panel (used for physical appointments / dashboard / patient
// list), without tearing down and rebuilding the whole modal.
async function refreshViewEMRPanelData() {
  if (!currentPatientId) return;
  try {
    const timeline = await API.get(`/emr/patients/${currentPatientId}/timeline`);
    currentEMRData = timeline;
    showEMRViewTab(currentEMRActiveTab || 'prescriptions');
  } catch (error) {
    console.error('Failed to refresh EMR:', error);
  }
}

function closeEMRViewModal() {
  document.getElementById('emr-view-modal').classList.remove('active');
}

// Video Call Functions
function isFutureAppointment(a) {
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  if (a.appointment_date > today) return true;
  if (a.appointment_date < today) return false;
  const t = String(a.appointment_time || '').slice(0, 5);
  const nowT = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  return t >= nowT;
}

async function quickJoinVideo(appointmentId) {
  showPage('appointments');
  await joinVideoCall(appointmentId);
}

async function joinVideoCall(appointmentId) {
  if (!appointmentId) {
    Utils.showToast('No appointment selected', 'error');
    return;
  }

  try {
    // Get video call credentials
    const response = await API.post(`/appointments/${appointmentId}/join/doctor`);
    const meeting = response.data || response;

    document.getElementById('appointments-list-card').style.display = 'none';
    document.getElementById('video-call-container').style.display = 'block';
    document.getElementById('active-appointment-id').textContent = appointmentId;
    currentCallAppointmentId = appointmentId;

    // Load patient EMR
    const appointment = allAppointments.find(a => a.id == appointmentId);
    if (appointment) {
      loadCallEMR(appointment.patient_id);
    }

    // Initialize Agora
    await startAgoraCall(meeting);
    Utils.showToast('Connected to video call', 'success');

    // Let the patient know the call has started — this is the only way
    // they find out, since patients have no "start call" button of their
    // own. Fire-and-forget: a failed/undeliverable push shouldn't block
    // or interrupt the doctor's side of the call.
    API.post(`/appointments/${appointmentId}/notify-patient-call`).catch(error => {
      console.error('Failed to notify patient of incoming call:', error);
    });
  } catch (error) {
    console.error('Failed to join video call:', error);
    Utils.showToast(error.message || 'Failed to join video call', 'error');
  }
}

async function startAgoraCall(meeting) {
  agoraClient = AgoraRTC.createClient({ mode: 'rtc', codec: 'vp8' });

  agoraClient.on('user-published', async (user, mediaType) => {
    await agoraClient.subscribe(user, mediaType);
    if (mediaType === 'video') {
      const remoteDiv = document.getElementById('remote-video');
      remoteDiv.innerHTML = '';
      user.videoTrack.play('remote-video');
    }
    if (mediaType === 'audio') {
      user.audioTrack.play();
    }
  });

  await agoraClient.join(
    meeting.app_id,
    meeting.channel,
    meeting.token,
    meeting.uid || null
  );

  await acquireLocalTracksAndPublish();
}

// Requesting the mic and camera in one call (instead of two separate
// createMicrophoneAudioTrack()/createCameraVideoTrack() calls) avoids
// the NOT_READABLE / NotReadableError Chrome throws when two getUserMedia
// requests race for the same devices. We also fall back to audio-only
// so a busy/missing camera doesn't stop the mic (and the call) from
// working, and always publish audio if we have it so voice comes through
// even when video can't start.
async function acquireLocalTracksAndPublish() {
  try {
    [localAudioTrack, localVideoTrack] = await AgoraRTC.createMicrophoneAndCameraTracks();
    localVideoTrack.play('local-video');
    await agoraClient.publish([localAudioTrack, localVideoTrack]);
    return;
  } catch (error) {
    console.warn('Could not get camera + microphone together, retrying audio-only:', error);
  }

  // Camera unavailable (in use by another app/tab, no permission, or no
  // device). Still get the microphone on its own so voice keeps working.
  try {
    localAudioTrack = await AgoraRTC.createMicrophoneAudioTrack();
    await agoraClient.publish([localAudioTrack]);
    Utils.showToast('Camera unavailable — joined with audio only', 'warning');
  } catch (error) {
    console.error('Failed to get microphone:', error);
    Utils.showToast('Could not access your microphone. Check camera/mic permissions and that no other app is using them.', 'error');
  }
}

async function loadCallEMR(patientId) {
  currentPatientId = patientId;
  currentEMRContext = 'call';
  const panel = document.getElementById('call-emr-panel');

  try {
    const timeline = await API.get(`/emr/patients/${patientId}/timeline`);
    currentEMRData = timeline;

    panel.innerHTML = `
      <div style="padding: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 12px;">
          <h3 style="font-size: 16px; font-weight: 700;">Patient: ${Utils.escapeHtml(timeline.patient_name)}</h3>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button class="btn btn-ghost btn-sm" onclick="openAdmitPatientModal(${patientId})">Admit Patient</button>
            <button class="btn btn-primary btn-sm" onclick="openAddPrescriptionModal()"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="9" width="18" height="6" rx="3" transform="rotate(-30 12 12)"/><path d="M12 8.5v7" transform="rotate(-30 12 12)"/></svg> Add Prescription</button>
            <button class="btn btn-ghost btn-sm" onclick="openAddDiagnosisModal()"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3v6a4 4 0 0 0 8 0V3"/><path d="M6 3H4.5M14 3h1.5"/><path d="M10 13v2.5a5 5 0 0 0 10 0V13.5"/><circle cx="20" cy="12.5" r="1.7"/></svg> Add Diagnosis</button>
            <button class="btn btn-ghost btn-sm" onclick="openAddVitalsModal()"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M2 20h20"/></svg> Add Vitals</button>
            <button class="btn btn-ghost btn-sm" onclick="openAddDoctorNoteModal()"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h4L18.5 9.5a2.1 2.1 0 0 0-3-3L5 17z"/><path d="M14 7l3 3"/></svg> Add Note</button>
          </div>
        </div>

        <div style="display: flex; gap: 8px; flex-wrap: wrap; border-bottom: 1px solid var(--border); padding-bottom: 12px; margin-bottom: 12px;">
          <button class="btn btn-primary btn-sm emr-tab-btn" id="call-tab-prescriptions" onclick="showCallEMRTab('prescriptions')">Prescriptions</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="call-tab-diagnoses" onclick="showCallEMRTab('diagnoses')">Diagnoses</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="call-tab-vitals" onclick="showCallEMRTab('vitals')">Vitals</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="call-tab-history" onclick="showCallEMRTab('history')">Medical History</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="call-tab-allergies" onclick="showCallEMRTab('allergies')">Allergies</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="call-tab-notes" onclick="showCallEMRTab('notes')">Doctor Notes</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="call-tab-reports" onclick="showCallEMRTab('reports')">Reports</button>
          <button class="btn btn-ghost btn-sm emr-tab-btn" id="call-tab-lab" onclick="showCallEMRTab('lab')">Lab Orders</button>
        </div>

        <div id="call-emr-tab-content">
          <div class="loading-spinner">Loading EMR data...</div>
        </div>
      </div>
    `;

    showCallEMRTab('prescriptions');
  } catch (error) {
    console.error('Failed to load EMR:', error);
    panel.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">Failed to load patient medical record</p>';
  }
}

function showCallEMRTab(tabName) { showEMRTab('call', tabName); }
function showEMRViewTab(tabName) { showEMRTab('view', tabName); }

function showEMRTab(prefix, tabName) {
  if (prefix === 'view') currentEMRActiveTab = tabName;

  document.querySelectorAll(`#${prefix}-emr-panel .emr-tab-btn`).forEach(btn => {
    btn.className = 'btn btn-ghost btn-sm emr-tab-btn';
  });
  const active = document.getElementById(`${prefix}-tab-${tabName}`);
  if (active) active.className = 'btn btn-primary btn-sm emr-tab-btn';

  const content = document.getElementById(`${prefix}-emr-tab-content`);
  const renderers = {
    prescriptions: renderPrescriptions,
    lab: renderLabOrders,
    diagnoses: renderDiagnoses,
    vitals: renderVitals,
    history: renderMedicalHistory,
    allergies: renderAllergies,
    notes: renderDoctorNotes,
    reports: renderReports,
  };
  renderers[tabName]?.(content);
}

function preselectCallAppointment(selectId) {
  if (!currentCallAppointmentId) return;
  const select = document.getElementById(selectId);
  if (select && [...select.options].some(o => o.value == currentCallAppointmentId)) {
    select.value = currentCallAppointmentId;
  }
}

async function toggleMic() {
  if (!localAudioTrack) return;
  micEnabled = !micEnabled;
  await localAudioTrack.setEnabled(micEnabled);
  document.getElementById('mic-toggle').innerHTML = micEnabled ? `${Icons.mic} Mute` : `${Icons.mic} Unmute`;
}

async function toggleCamera() {
  if (!localVideoTrack) return;
  cameraEnabled = !cameraEnabled;
  await localVideoTrack.setEnabled(cameraEnabled);
  document.getElementById('camera-toggle').innerHTML = cameraEnabled ? `${Icons.camera} Camera Off` : `${Icons.camera} Camera On`;
}

async function endVideoCall() {
  const appointmentId = document.getElementById('active-appointment-id').textContent;
  
  try {
    await API.post(`/appointments/${appointmentId}/end`);
  } catch (error) {
    console.error('Failed to end appointment:', error);
  }

  // Clean up media
  localAudioTrack?.close();
  localVideoTrack?.close();
  
  if (agoraClient) {
    await agoraClient.leave();
  }

  // Reset UI
  currentCallAppointmentId = null;
  document.getElementById('video-call-container').style.display = 'none';
  document.getElementById('appointments-list-card').style.display = 'block';
  document.getElementById('local-video').innerHTML = '';
  document.getElementById('remote-video').innerHTML = '';

  Utils.showToast('Call ended', 'info');
  loadAppointments();
}

// Schedule Functions
async function loadSchedule() {
  try {
    const user = Auth.getUser();
    if (!user.doctor_id) {
      Utils.showToast('Doctor profile not found', 'error');
      return;
    }

    // Load current availability status
    try {
      const doctor = await API.get(`/doctors/${user.doctor_id}`);
      renderAvailabilityStatus(doctor.available);
    } catch (error) {
      console.error('Failed to load availability status:', error);
    }

    const schedules = await API.get(`/doctor-schedules/doctor/${user.doctor_id}`);
    mySchedule = schedules || [];
    
    const listDiv = document.getElementById('schedule-list');
    
    if (mySchedule.length === 0) {
      listDiv.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No schedule configured yet. Use the form above to add your weekly slots.</p>';
      return;
    }

    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    
    listDiv.innerHTML = `
      <table class="table">
        <thead>
          <tr>
            <th>Day</th>
            <th>Start Time</th>
            <th>End Time</th>
            <th>Slot Duration</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${days.map(day => {
            const daySchedule = mySchedule.find(s => s.day_of_week === day);
            if (!daySchedule) {
              return `<tr><td>${day}</td><td colspan="4" style="color: var(--text-light);">Not scheduled</td><td>—</td></tr>`;
            }
            return `
              <tr>
                <td><strong>${day}</strong></td>
                <td>${Utils.formatTime(daySchedule.start_time)}</td>
                <td>${Utils.formatTime(daySchedule.end_time)}</td>
                <td>${daySchedule.slot_duration} min</td>
                <td><span class="badge ${daySchedule.is_available ? 'badge-success' : 'badge-danger'}">${daySchedule.is_available ? 'Available' : 'Unavailable'}</span></td>
                <td>
                  <button class="btn btn-ghost btn-sm" onclick="editScheduleSlot(${daySchedule.id})">Edit</button>
                  <button class="btn btn-danger btn-sm" onclick="deleteScheduleSlot(${daySchedule.id})">Delete</button>
                </td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    `;
  } catch (error) {
    console.error('Failed to load schedule:', error);
    Utils.showToast('Failed to load schedule', 'error');
  }
}

function renderAvailabilityStatus(isAvailable) {
  const badge = document.getElementById('availability-badge');
  const btn = document.getElementById('toggle-availability-btn');
  if (!badge || !btn) return;

  badge.textContent = isAvailable ? 'Available' : 'Unavailable';
  badge.className = `badge ${isAvailable ? 'badge-success' : 'badge-danger'}`;
  btn.textContent = isAvailable ? 'Mark as Unavailable' : 'Mark as Available';
  btn.dataset.available = isAvailable ? 'true' : 'false';
}

async function toggleMyAvailability() {
  const btn = document.getElementById('toggle-availability-btn');
  const currentlyAvailable = btn.dataset.available !== 'false';
  const nextAvailable = !currentlyAvailable;

  btn.disabled = true;
  try {
    const updated = await API.patch(`/doctors/me/availability`, { available: nextAvailable });
    renderAvailabilityStatus(updated.available);
    Utils.showToast(`You are now marked as ${updated.available ? 'available' : 'unavailable'}`, 'success');
  } catch (error) {
    console.error('Failed to update availability:', error);
    Utils.showToast(error.message || 'Failed to update availability', 'error');
  } finally {
    btn.disabled = false;
  }
}

function resetScheduleForm() {
  document.getElementById('schedule-form').reset();
  document.getElementById('schedule-edit-id').value = '';
  document.getElementById('schedule-slot-duration').value = 30;
  document.getElementById('schedule-is-available').checked = true;
  document.getElementById('schedule-form-title').textContent = 'Add Schedule Slot';
  document.getElementById('schedule-submit-btn').textContent = 'Add Slot';
  document.getElementById('schedule-cancel-btn').style.display = 'none';
}

function cancelScheduleEdit() {
  resetScheduleForm();
}

function editScheduleSlot(scheduleId) {
  const slot = mySchedule.find(s => s.id === scheduleId);
  if (!slot) return;

  document.getElementById('schedule-edit-id').value = slot.id;
  document.getElementById('schedule-day').value = slot.day_of_week;
  document.getElementById('schedule-start').value = String(slot.start_time).slice(0, 5);
  document.getElementById('schedule-end').value = String(slot.end_time).slice(0, 5);
  document.getElementById('schedule-slot-duration').value = slot.slot_duration;
  document.getElementById('schedule-is-available').checked = !!slot.is_available;

  document.getElementById('schedule-form-title').textContent = `Edit ${slot.day_of_week} Slot`;
  document.getElementById('schedule-submit-btn').textContent = 'Save Changes';
  document.getElementById('schedule-cancel-btn').style.display = 'inline-block';

  document.getElementById('page-schedule').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function submitScheduleForm(e) {
  e.preventDefault();

  const user = Auth.getUser();
  const editId = document.getElementById('schedule-edit-id').value;

  const payload = {
    doctor_id: user.doctor_id,
    day_of_week: document.getElementById('schedule-day').value,
    start_time: document.getElementById('schedule-start').value,
    end_time: document.getElementById('schedule-end').value,
    slot_duration: parseInt(document.getElementById('schedule-slot-duration').value, 10),
    is_available: document.getElementById('schedule-is-available').checked,
  };

  try {
    if (editId) {
      await API.put(`/doctor-schedules/${editId}`, payload);
      Utils.showToast('Schedule slot updated', 'success');
    } else {
      await API.post('/doctor-schedules/', payload);
      Utils.showToast('Schedule slot added', 'success');
    }
    resetScheduleForm();
    loadSchedule();
  } catch (error) {
    console.error('Failed to save schedule slot:', error);
    Utils.showToast(error.message || 'Failed to save schedule slot', 'error');
  }
}

async function deleteScheduleSlot(scheduleId) {
  if (!confirm('Remove this schedule slot?')) return;

  try {
    await API.delete(`/doctor-schedules/${scheduleId}`);
    Utils.showToast('Schedule slot removed', 'success');
    loadSchedule();
  } catch (error) {
    console.error('Failed to delete schedule slot:', error);
    Utils.showToast(error.message || 'Failed to delete schedule slot', 'error');
  }
}

// Helper Functions
function getStatusBadge(status) {
  const badges = {
    'scheduled': 'info',
    'pending': 'warning',
    'completed': 'success',
    'cancelled': 'danger'
  };
  return badges[status] || 'info';
}

function logout() {
  Auth.clear();
  window.location.href = 'index.html';
}

// ═══════════════════════════════ EMR MANAGEMENT ═══════════════════════════════
let currentPatientId = null;
let currentEMRData = null;
let currentModalType = null;
let currentCallAppointmentId = null;
// Tracks which EMR panel is currently open ('call' during a video call,
// 'view' for the physical-appointment / dashboard / patient-list EMR
// modal) so saveEMRRecord() knows which panel to refresh afterwards.
let currentEMRContext = null;
// Remembers which tab was active in the "View EMR" panel so a refresh
// after saving a record doesn't bounce the doctor back to Prescriptions.
let currentEMRActiveTab = 'prescriptions';

function renderPrescriptions(content) {
  const prescriptions = currentEMRData.prescriptions || [];
  const courses = currentEMRData.courses || [];

  let html = '';

  if (courses.length) {
    html += `<h4 style="font-size:14px;margin:0 0 10px;">Ward medication courses</h4>
      <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:18px;">
        ${courses.map(c => `
          <div style="background:var(--bg-alt);border-radius:10px;padding:12px 14px;border:1px solid var(--border);">
            <div style="font-weight:600;">${Utils.escapeHtml(c.title || 'Course')} <span class="badge badge-warning">${Utils.escapeHtml(c.status || '')}</span></div>
            <div style="font-size:12px;color:var(--text-light);margin:4px 0;">
              ${Utils.escapeHtml(String(c.start_date || ''))} → ${Utils.escapeHtml(String(c.end_date || '—'))}
              (${c.duration_days || '—'} days)
              ${c.clinical_notes ? `<div style="margin-top:6px;"><strong>Note for nurse:</strong> ${Utils.escapeHtml(c.clinical_notes)}</div>` : ''}
            </div>
            <ul style="margin:6px 0 0 18px;font-size:13px;">
              ${(c.items || []).map(it => `<li><strong>${Utils.escapeHtml(it.medicine_name || '')}</strong>
                ${Utils.escapeHtml(it.dosage || '')} · ${Utils.escapeHtml((it.route || it.form || '').toString().toUpperCase())}
                · ${Utils.escapeHtml(it.frequency || '')}</li>`).join('') || '<li>No items</li>'}
            </ul>
          </div>
        `).join('')}
      </div>`;
  }

  if (!prescriptions.length && !courses.length) {
    content.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 40px;">No prescriptions or ward courses recorded</p>';
    return;
  }

  if (prescriptions.length) {
    html += `${courses.length ? '<h4 style="font-size:14px;margin:0 0 10px;">Prescriptions</h4>' : ''}
    <table class="table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Medication</th>
          <th>Dosage</th>
          <th>Frequency</th>
          <th>Duration</th>
          <th>Doctor</th>
        </tr>
      </thead>
      <tbody>
        ${prescriptions.flatMap(p => {
          const items = p.items || [];
          if (items.length === 0) {
            return [`
              <tr>
                <td>${Utils.formatDate(p.created_at)}</td>
                <td>—</td>
                <td>—</td>
                <td>—</td>
                <td>—</td>
                <td>${doctorLabel(p.doctor_id)}</td>
              </tr>
            `];
          }
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
    </table>`;
  }

  content.innerHTML = html;
}


function renderLabOrders(content) {
  const orders = currentEMRData.lab_orders || [];
  let html = `
    <div style="display:flex; justify-content:flex-end; margin-bottom:12px;">
      <button class="btn btn-primary btn-sm" onclick="openAddLabOrderModal()">+ Order Lab Tests</button>
    </div>`;

  if (!orders.length) {
    html += '<p style="color: var(--text-light); text-align: center; padding: 40px;">No lab orders yet</p>';
    content.innerHTML = html;
    return;
  }

  html += `<div class="table-wrap"><table class="data-table"><thead>
    <tr><th>Order</th><th>Tests</th><th>Status</th><th>Priority</th><th>Ordered</th></tr>
  </thead><tbody>`;

  for (const o of orders) {
    const tests = (o.results || []).map(r => r.test_name || r.test_code || ('#' + r.lab_test_id)).join(', ');
    const status = (o.status || '').replace(/_/g, ' ');
    const reportBtn = o.status === 'completed'
      ? ` <button class="btn btn-primary btn-sm" onclick="viewLabReport(${o.id})">View</button> <button class="btn btn-ghost btn-sm" onclick="downloadLabReport(${o.id})">Download</button>`
      : '';
    html += `<tr>
      <td><strong>#${o.id}</strong>${reportBtn}</td>
      <td>${Utils.escapeHtml(tests || '—')}</td>
      <td><span class="badge">${Utils.escapeHtml(status)}</span></td>
      <td>${Utils.escapeHtml((o.priority || 'routine').toUpperCase())}</td>
      <td>${o.created_at ? new Date(o.created_at).toLocaleString() : '—'}</td>
    </tr>`;
    // Show result values if completed
    if (o.status === 'completed' && o.results && o.results.length) {
      for (const r of o.results) {
        const val = r.value_numeric != null ? r.value_numeric : (r.value_text || '—');
        const abn = r.is_abnormal ? ' <span class="badge badge-danger">Abnormal</span>' : '';
        html += `<tr style="background:rgba(0,0,0,0.02);">
          <td></td>
          <td colspan="4" style="font-size:13px;">
            <strong>${Utils.escapeHtml(r.test_name || '')}</strong>:
            ${Utils.escapeHtml(String(val))} ${Utils.escapeHtml(r.unit || '')}
            ${r.normal_range_text ? ' <span style="color:var(--text-light);">(Normal: ' + Utils.escapeHtml(r.normal_range_text) + ')</span>' : ''}
            ${abn}
          </td>
        </tr>`;
      }
    }
  }
  html += '</tbody></table></div>';
  content.innerHTML = html;
}

async function openAddLabOrderModal() {
  currentModalType = 'lab_order';
  document.getElementById('modal-title').textContent = 'Order Lab Tests';
  const user = Auth.getUser();

  try {
    if (!allAppointments.length) {
      const appointments = await API.get('/appointments/');
      allAppointments = (Array.isArray(appointments) ? appointments : appointments?.data || [])
        .filter(a => a.doctor_id === user?.doctor_id);
    }
  } catch (error) {
    console.error(error);
    Utils.showToast('Unable to load appointments', 'error');
    return;
  }

  const patientAppointments = allAppointments.filter(
    a => Number(a.patient_id) === Number(currentPatientId)
  );

  if (!patientAppointments.length) {
    Utils.showToast('This patient has no appointment assigned to you', 'error');
    return;
  }

  let tests = [];
  try {
    const res = await API.get('/laboratory/tests?active_only=true');
    tests = Array.isArray(res) ? res : (res?.data || []);
    tests = tests.filter(t => t.is_active !== false);
  } catch (e) {
    Utils.showToast('Could not load lab test catalog', 'error');
    return;
  }

  if (!tests.length) {
    Utils.showToast('No active lab tests in catalog. Ask lab staff to add tests first.', 'error');
    return;
  }

  document.getElementById('modal-body').innerHTML = `
    <div class="form-group">
      <label class="form-label">Appointment</label>
      <select class="form-select" id="lab-order-appointment" required>
        ${patientAppointments.map(a => `
          <option value="${a.id}">
            ${Utils.formatDate(a.appointment_date)} at ${Utils.formatTime(a.appointment_time)}
          </option>`).join('')}
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Priority</label>
      <select class="form-select" id="lab-order-priority">
        <option value="routine">Routine</option>
        <option value="urgent">Urgent</option>
        <option value="stat">STAT</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Clinical Notes</label>
      <textarea class="form-textarea" id="lab-order-notes" placeholder="Indication / clinical notes"></textarea>
    </div>
    <div class="form-group">
      <label class="form-label">Select Tests *</label>
      <div id="lab-order-tests" style="display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:8px; max-height:240px; overflow-y:auto; padding:8px; border:1px solid var(--border); border-radius:10px;">
        ${tests.map(t => `
          <label style="display:flex; gap:8px; align-items:flex-start; font-size:13px; padding:6px 8px; border-radius:8px; background:rgba(0,0,0,0.03);">
            <input type="checkbox" name="lab-test" value="${t.id}" style="margin-top:3px;">
            <span>
              <strong>${Utils.escapeHtml(t.name)}</strong>
              ${t.code ? `<span class="badge">${Utils.escapeHtml(t.code)}</span>` : ''}
              <div style="font-size:11px; color:var(--text-light);">${Utils.escapeHtml(t.category || '')} · ${Utils.escapeHtml(t.sample_type || '')}</div>
            </span>
          </label>`).join('')}
      </div>
    </div>
  `;

  if (typeof preselectCallAppointment === 'function') {
    preselectCallAppointment('lab-order-appointment');
  }
  openFormModal();
}

async function saveLabOrderFromModal() {
  const user = Auth.getUser();
  const appointmentId = parseInt(document.getElementById('lab-order-appointment')?.value, 10);
  const testIds = [...document.querySelectorAll('input[name="lab-test"]:checked')].map(c => parseInt(c.value, 10));
  if (!appointmentId) {
    Utils.showToast('Select an appointment', 'error');
    return;
  }
  if (!testIds.length) {
    Utils.showToast('Select at least one test', 'error');
    return;
  }
  if (!user?.doctor_id) {
    Utils.showToast('Doctor account required', 'error');
    return;
  }

  const payload = {
    patient_id: Number(currentPatientId),
    ordered_by_doctor_id: user.doctor_id,
    test_ids: testIds,
    appointment_id: appointmentId,
    priority: document.getElementById('lab-order-priority')?.value || 'routine',
    clinical_notes: document.getElementById('lab-order-notes')?.value?.trim() || null,
  };

  try {
    const res = await API.post('/emr/lab-orders', payload);
    Utils.showToast(res?.message || 'Lab order sent to laboratory', 'success');
    closeEMRModal();
    // Refresh EMR panel
    if (currentEMRContext === 'call') {
      const timeline = await API.get(`/emr/patients/${currentPatientId}/timeline`);
      currentEMRData = timeline?.data || timeline;
      showCallEMRTab('lab');
    } else {
      const timeline = await API.get(`/emr/patients/${currentPatientId}/timeline`);
      currentEMRData = timeline?.data || timeline;
      showEMRViewTab('lab');
    }
  } catch (e) {
    Utils.showToast(e.message || String(e), 'error');
  }
}


function renderDiagnoses(content) {
  const diagnoses = currentEMRData.diagnoses || [];
  
  if (diagnoses.length === 0) {
    content.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 40px;">No diagnoses recorded</p>';
    return;
  }

  content.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Diagnosis</th>
          <th>ICD Code</th>
          <th>Severity</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>
        ${diagnoses.map(d => `
          <tr>
            <td>${Utils.formatDate(d.diagnosis_date)}</td>
            <td><strong>${Utils.escapeHtml(d.diagnosis_name)}</strong></td>
            <td>${Utils.escapeHtml(d.icd_code || '—')}</td>
            <td><span class="badge badge-${d.severity === 'high' ? 'danger' : d.severity === 'medium' ? 'warning' : 'info'}">${d.severity}</span></td>
            <td>${Utils.escapeHtml(d.notes || '—')}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function renderVitals(content) {
  const vitals = currentEMRData.vitals || [];
  
  if (vitals.length === 0) {
    content.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 40px;">No vitals recorded</p>';
    return;
  }

  content.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Blood Pressure</th>
          <th>Heart Rate</th>
          <th>Temperature</th>
          <th>Weight</th>
          <th>Height</th>
        </tr>
      </thead>
      <tbody>
        ${vitals.map(v => `
          <tr>
            <td>${Utils.formatDate(v.recorded_at)}</td>
            <td>${v.blood_pressure || '—'}</td>
            <td>${v.heart_rate ? v.heart_rate + ' bpm' : '—'}</td>
            <td>${v.temperature ? v.temperature + '°F' : '—'}</td>
            <td>${v.weight ? v.weight + ' kg' : '—'}</td>
            <td>${v.height ? v.height + ' cm' : '—'}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function renderMedicalHistory(content) {
  const history = currentEMRData.medical_history || [];
  
  if (history.length === 0) {
    content.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 40px;">No medical history recorded</p>';
    return;
  }

  content.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th>Condition</th>
          <th>Status</th>
          <th>Diagnosed Date</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>
        ${history.map(h => `
          <tr>
            <td><strong>${Utils.escapeHtml(h.condition)}</strong></td>
            <td><span class="badge badge-${h.status === 'active' ? 'warning' : 'success'}">${h.status}</span></td>
            <td>${Utils.formatDate(h.diagnosed_date)}</td>
            <td>${Utils.escapeHtml(h.notes || '—')}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function renderAllergies(content) {
  const allergies = currentEMRData.allergies || [];
  
  if (allergies.length === 0) {
    content.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 40px;">No allergies recorded</p>';
    return;
  }

  content.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th>Allergy</th>
          <th>Severity</th>
          <th>Reaction</th>
          <th>Recorded Date</th>
        </tr>
      </thead>
      <tbody>
        ${allergies.map(a => `
          <tr>
            <td><strong>${Utils.escapeHtml(a.allergy_name)}</strong></td>
            <td><span class="badge badge-${a.severity === 'severe' ? 'danger' : a.severity === 'moderate' ? 'warning' : 'info'}">${a.severity || 'mild'}</span></td>
            <td>${Utils.escapeHtml(a.reaction || '—')}</td>
            <td>${Utils.formatDate(a.recorded_date)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function renderDoctorNotes(content) {
  const notes = currentEMRData.doctor_notes || [];
  
  if (notes.length === 0) {
    content.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 40px;">No doctor notes recorded</p>';
    return;
  }

  content.innerHTML = notes.map(n => `
    <div style="padding: 16px; background: var(--bg-alt); border-radius: 8px; margin-bottom: 12px;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
        <strong style="font-size: 14px;">${doctorLabel(n.doctor_id)}</strong>
        <span style="font-size: 12px; color: var(--text-light);">${Utils.formatDate(n.note_date)}</span>
      </div>
      <p style="font-size: 14px; line-height: 1.6; white-space: pre-wrap;">${Utils.escapeHtml(n.note_text)}</p>
    </div>
  `).join('');
}

function renderReports(content) {
  const reports = currentEMRData.reports || [];
  
  if (reports.length === 0) {
    content.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 40px;">No reports uploaded</p>';
    return;
  }

  content.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Type</th>
          <th>Uploaded Date</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${reports.map(r => `
          <tr>
            <td><strong>${Utils.escapeHtml(r.report_name)}</strong></td>
            <td><span class="badge badge-info">${r.report_type}</span></td>
            <td>${Utils.formatDate(r.uploaded_at)}</td>
            <td style="display:flex; gap:6px; flex-wrap:wrap;">
              <button class="btn btn-primary btn-sm" onclick="viewReport(${r.id})">View</button>
              <button class="btn btn-ghost btn-sm" onclick="downloadReport(${r.id})">${Icons.download || ''} Download</button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

async function viewReport(reportId) {
  return viewOrDownloadReport(reportId, true);
}
async function downloadReport(reportId) {
  return viewOrDownloadReport(reportId, false);
}
async function viewOrDownloadReport(reportId, openInline = true) {
  try {
    const response = await fetch(API.config + `/emr/reports/${reportId}/download`, {
      headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
    });
    if (!response.ok) throw new Error('Download failed');
    const contentType = response.headers.get('content-type') || '';
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    if (openInline || contentType.includes('pdf') || contentType.includes('html') || contentType.includes('image')) {
      const w = window.open(url, '_blank');
      if (!w) Utils.showToast('Allow pop-ups to view the report', 'error');
    } else {
      const a = document.createElement('a');
      a.href = url; a.download = `report_${reportId}`;
      document.body.appendChild(a); a.click(); a.remove();
    }
    setTimeout(() => URL.revokeObjectURL(url), 120000);
  } catch (error) {
    console.error(error);
    Utils.showToast('Failed to open report', 'error');
  }
}

// Modal Functions
async function openAddPrescriptionModal() {
  currentModalType = 'prescription';
  document.getElementById('modal-title').textContent = 'Add Prescription';
  const user = Auth.getUser();

  try {
    if (!allAppointments.length) {
      const appointments = await API.get('/appointments/');
      allAppointments = appointments.filter(a => a.doctor_id === user?.doctor_id);
    }
  } catch (error) {
    console.error('Failed to load appointments for prescription:', error);
    Utils.showToast('Unable to load appointments', 'error');
    return;
  }

  const patientAppointments = allAppointments.filter(
    appointment => Number(appointment.patient_id) === Number(currentPatientId)
  );

  if (!patientAppointments.length) {
    Utils.showToast('This patient has no appointment assigned to you', 'error');
    return;
  }

  document.getElementById('modal-body').innerHTML = `
    <div class="form-group">
      <label class="form-label">Appointment</label>
      <select class="form-select" id="prescription-appointment" required>
        ${patientAppointments.map(appointment => `
          <option value="${appointment.id}">
            ${Utils.formatDate(appointment.appointment_date)} at ${Utils.formatTime(appointment.appointment_time)}
          </option>
        `).join('')}
      </select>
    </div>
    <div class="form-group autocomplete-wrapper">
      <label class="form-label">Medication Name</label>
      <input type="text" class="form-input" id="med-name" autocomplete="off" placeholder="Click or start typing (e.g. Panadol)..." required>
      <div class="autocomplete-dropdown" id="med-name-dropdown"></div>
    </div>
    <div class="form-group">
      <label class="form-label">Type / Form *</label>
      <select class="form-select" id="med-form" required>
        <option value="tablet">Tablet</option>
        <option value="capsule">Capsule</option>
        <option value="syrup">Syrup</option>
        <option value="injection">Injection</option>
        <option value="drip">Drip (IV)</option>
        <option value="ointment">Ointment</option>
        <option value="drops">Drops</option>
        <option value="other">Other</option>
      </select>
    </div>
    <div class="form-group autocomplete-wrapper">
      <label class="form-label">Dosage</label>
      <input type="text" class="form-input" id="med-dosage" autocomplete="off" placeholder="e.g. 500mg" required>
      <div class="autocomplete-dropdown" id="med-dosage-dropdown"></div>
    </div>
    <div class="form-group">
      <label class="form-label">Frequency</label>
      <select class="form-select" id="med-frequency" required>
        <option value="">Select frequency</option>
        <option value="1">1 (Once daily)</option>
        <option value="1+1">1+1 (Twice daily)</option>
        <option value="1+1+1">1+1+1 (Thrice daily)</option>
      </select>
    </div>
    <div class="form-group autocomplete-wrapper">
      <label class="form-label">Duration</label>
      <input type="text" class="form-input" id="med-duration" autocomplete="off" placeholder="e.g. 7 days" required>
      <div class="autocomplete-dropdown" id="med-duration-dropdown"></div>
    </div>
    <div class="form-group">
      <label class="form-label">Instructions</label>
      <textarea class="form-textarea" id="med-instructions" placeholder="Special instructions..."></textarea>
    </div>
    <div class="form-group">
      <label class="form-label">Diagnosis (optional)</label>
      <textarea class="form-textarea" id="prescription-diagnosis"></textarea>
    </div>
    <div class="form-group">
      <label class="form-label">Advice (optional)</label>
      <textarea class="form-textarea" id="prescription-advice"></textarea>
    </div>
  `;
  preselectCallAppointment('prescription-appointment');
  openFormModal();

  // Diagnostic: if this line never shows up in the browser console when
  // you click "Add Prescription", the browser is running an old cached
  // copy of js/doctor-portal.js — this exact function, in this exact
  // file, does not exist in any version before this one.
  console.log(
    `[prescription-modal] Wiring autocomplete. Library size: ${(window.MEDICINE_LIBRARY || []).length}`
  );

  attachAutocomplete('med-name', 'med-name-dropdown', window.MEDICINE_LIBRARY || []);
  attachAutocomplete('med-dosage', 'med-dosage-dropdown', window.DOSAGE_OPTIONS || []);
  attachAutocomplete('med-duration', 'med-duration-dropdown', window.DURATION_OPTIONS || []);
}

/**
 * Turns a plain text input into a searchable dropdown: clicking it shows
 * the full option list (Pakistan-common medicines first, see
 * medicine-library.js), typing filters it — prefix matches ("pan" ->
 * Panadol...) ranked above mid-word matches — and the field stays a
 * normal text input throughout, so the doctor can still type any custom
 * value that isn't in the list at all.
 */

/** Same as attachAutocomplete but for dynamically created elements (no fixed ids). */
function attachAutocompleteEl(input, dropdown, options) {
  if (!input || !dropdown || !options) return;

  function filterOptions(query) {
    const q = (query || '').trim().toLowerCase();
    if (!q) return options;
    const startsWith = [];
    const contains = [];
    options.forEach(option => {
      const lower = option.toLowerCase();
      if (lower.startsWith(q)) startsWith.push(option);
      else if (lower.includes(q)) contains.push(option);
    });
    return [...startsWith, ...contains];
  }

  function renderDropdown(list) {
    if (!list.length) {
      dropdown.innerHTML = '<div class="autocomplete-item-empty">No matches — you can still type a custom value</div>';
      dropdown.style.display = 'block';
      return;
    }
    dropdown.innerHTML = list.slice(0, 60).map(option =>
      `<div class="autocomplete-item" data-value="${Utils.escapeHtml(option)}">${Utils.escapeHtml(option)}</div>`
    ).join('');
    dropdown.style.display = 'block';
  }

  input.addEventListener('focus', () => renderDropdown(filterOptions(input.value)));
  input.addEventListener('input', () => renderDropdown(filterOptions(input.value)));
  input.addEventListener('blur', () => {
    setTimeout(() => { dropdown.style.display = 'none'; }, 150);
  });

  dropdown.addEventListener('mousedown', (event) => {
    const item = event.target.closest('.autocomplete-item');
    if (!item) return;
    event.preventDefault();
    input.value = item.dataset.value;
    dropdown.style.display = 'none';
  });
}

function attachAutocomplete(inputId, dropdownId, options) {
  const input = document.getElementById(inputId);
  const dropdown = document.getElementById(dropdownId);
  if (!input || !dropdown) return;

  function filterOptions(query) {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    const startsWith = [];
    const contains = [];
    options.forEach(option => {
      const lower = option.toLowerCase();
      if (lower.startsWith(q)) startsWith.push(option);
      else if (lower.includes(q)) contains.push(option);
    });
    return [...startsWith, ...contains];
  }

  function renderDropdown(list) {
    if (!list.length) {
      dropdown.innerHTML = '<div class="autocomplete-item-empty">No matches — you can still type a custom value</div>';
      dropdown.style.display = 'block';
      return;
    }
    dropdown.innerHTML = list.slice(0, 60).map(option =>
      `<div class="autocomplete-item" data-value="${Utils.escapeHtml(option)}">${Utils.escapeHtml(option)}</div>`
    ).join('');
    dropdown.style.display = 'block';
  }

  input.addEventListener('focus', () => renderDropdown(filterOptions(input.value)));
  input.addEventListener('input', () => renderDropdown(filterOptions(input.value)));
  input.addEventListener('blur', () => {
    // Delay so a click on a dropdown item registers before it disappears.
    setTimeout(() => { dropdown.style.display = 'none'; }, 150);
  });

  dropdown.addEventListener('mousedown', (event) => {
    const item = event.target.closest('.autocomplete-item');
    if (!item) return;
    event.preventDefault();
    input.value = item.dataset.value;
    dropdown.style.display = 'none';
  });
}

async function openAddDiagnosisModal() {
  currentModalType = 'diagnosis';
  document.getElementById('modal-title').textContent = 'Add Diagnosis';
  const user = Auth.getUser();

  try {
    if (!allAppointments.length) {
      const appointments = await API.get('/appointments/');
      allAppointments = appointments.filter(a => a.doctor_id === user?.doctor_id);
    }
  } catch (error) {
    console.error('Failed to load appointments for diagnosis:', error);
    Utils.showToast('Unable to load appointments', 'error');
    return;
  }

  const patientAppointments = allAppointments.filter(
    appointment => Number(appointment.patient_id) === Number(currentPatientId)
  );

  if (!patientAppointments.length) {
    Utils.showToast('This patient has no appointment assigned to you', 'error');
    return;
  }

  document.getElementById('modal-body').innerHTML = `
    <div class="form-group">
      <label class="form-label">Appointment</label>
      <select class="form-select" id="diag-appointment" required>
        ${patientAppointments.map(appointment => `
          <option value="${appointment.id}">
            ${Utils.formatDate(appointment.appointment_date)} at ${Utils.formatTime(appointment.appointment_time)}
          </option>
        `).join('')}
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Diagnosis</label>
      <input type="text" class="form-input" id="diag-name" required>
    </div>
    <div class="form-group">
      <label class="form-label">Severity</label>
      <select class="form-select" id="diag-severity" required>
        <option value="mild">Mild</option>
        <option value="moderate">Moderate</option>
        <option value="severe">Severe</option>
        <option value="critical">Critical</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <textarea class="form-textarea" id="diag-notes"></textarea>
    </div>
  `;
  preselectCallAppointment('diag-appointment');
  openFormModal();
}

async function openAddVitalsModal() {
  currentModalType = 'vitals';
  document.getElementById('modal-title').textContent = 'Add Vitals';
  const user = Auth.getUser();

  try {
    if (!allAppointments.length) {
      const appointments = await API.get('/appointments/');
      allAppointments = appointments.filter(a => a.doctor_id === user?.doctor_id);
    }
  } catch (error) {
    console.error('Failed to load appointments for vitals:', error);
    Utils.showToast('Unable to load appointments', 'error');
    return;
  }

  const patientAppointments = allAppointments.filter(
    appointment => Number(appointment.patient_id) === Number(currentPatientId)
  );

  if (!patientAppointments.length) {
    Utils.showToast('This patient has no appointment assigned to you', 'error');
    return;
  }

  document.getElementById('modal-body').innerHTML = `
    <div class="form-group">
      <label class="form-label">Appointment</label>
      <select class="form-select" id="vitals-appointment" required>
        ${patientAppointments.map(appointment => `
          <option value="${appointment.id}">
            ${Utils.formatDate(appointment.appointment_date)} at ${Utils.formatTime(appointment.appointment_time)}
          </option>
        `).join('')}
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Blood Pressure (e.g., 120/80)</label>
      <input type="text" class="form-input" id="vitals-bp" placeholder="120/80">
    </div>
    <div class="form-group">
      <label class="form-label">Pulse (bpm)</label>
      <input type="number" class="form-input" id="vitals-hr" placeholder="72">
    </div>
    <div class="form-group">
      <label class="form-label">Temperature (°F)</label>
      <input type="number" step="0.1" class="form-input" id="vitals-temp" placeholder="98.6">
    </div>
    <div class="form-group">
      <label class="form-label">Oxygen Level (%)</label>
      <input type="number" step="0.1" class="form-input" id="vitals-oxygen" placeholder="98">
    </div>
    <div class="form-group">
      <label class="form-label">Weight (kg)</label>
      <input type="number" step="0.1" class="form-input" id="vitals-weight" placeholder="70">
    </div>
    <div class="form-group">
      <label class="form-label">Height (cm)</label>
      <input type="number" class="form-input" id="vitals-height" placeholder="170">
    </div>
  `;
  preselectCallAppointment('vitals-appointment');
  openFormModal();
}

function openAddMedicalHistoryModal() {
  currentModalType = 'medical-history';
  document.getElementById('modal-title').textContent = 'Add Medical Condition';
  document.getElementById('modal-body').innerHTML = `
    <div class="form-group">
      <label class="form-label">Condition</label>
      <input type="text" class="form-input" id="hist-condition" required>
    </div>
    <div class="form-group">
      <label class="form-label">Status</label>
      <select class="form-select" id="hist-status" required>
        <option value="active">Active</option>
        <option value="resolved">Resolved</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Diagnosed Date</label>
      <input type="date" class="form-input" id="hist-date">
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <textarea class="form-textarea" id="hist-notes"></textarea>
    </div>
  `;
  openFormModal();
}

function openAddAllergyModal() {
  currentModalType = 'allergy';
  document.getElementById('modal-title').textContent = 'Add Allergy';
  document.getElementById('modal-body').innerHTML = `
    <div class="form-group">
      <label class="form-label">Allergy Name</label>
      <input type="text" class="form-input" id="allergy-name" required>
    </div>
    <div class="form-group">
      <label class="form-label">Severity</label>
      <select class="form-select" id="allergy-severity">
        <option value="mild">Mild</option>
        <option value="moderate">Moderate</option>
        <option value="severe">Severe</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Reaction</label>
      <input type="text" class="form-input" id="allergy-reaction" placeholder="e.g., Rash, Difficulty breathing">
    </div>
  `;
  openFormModal();
}

async function openAddDoctorNoteModal() {
  currentModalType = 'doctor-note';
  document.getElementById('modal-title').textContent = 'Add Doctor Note';
  const user = Auth.getUser();

  try {
    if (!allAppointments.length) {
      const appointments = await API.get('/appointments/');
      allAppointments = appointments.filter(a => a.doctor_id === user?.doctor_id);
    }
  } catch (error) {
    console.error('Failed to load appointments for doctor note:', error);
    Utils.showToast('Unable to load appointments', 'error');
    return;
  }

  const patientAppointments = allAppointments.filter(
    appointment => Number(appointment.patient_id) === Number(currentPatientId)
  );

  if (!patientAppointments.length) {
    Utils.showToast('This patient has no appointment assigned to you', 'error');
    return;
  }

  document.getElementById('modal-body').innerHTML = `
    <div class="form-group">
      <label class="form-label">Appointment</label>
      <select class="form-select" id="note-appointment" required>
        ${patientAppointments.map(appointment => `
          <option value="${appointment.id}">
            ${Utils.formatDate(appointment.appointment_date)} at ${Utils.formatTime(appointment.appointment_time)}
          </option>
        `).join('')}
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Note</label>
      <textarea class="form-textarea" id="note-text" rows="6" required placeholder="Enter your clinical notes..."></textarea>
    </div>
  `;
  preselectCallAppointment('note-appointment');
  openFormModal();
}

function openUploadReportModal() {
  currentModalType = 'report';
  document.getElementById('modal-title').textContent = 'Upload Medical Report';
  document.getElementById('modal-body').innerHTML = `
    <div class="form-group">
      <label class="form-label">Report Name</label>
      <input type="text" class="form-input" id="report-name" required>
    </div>
    <div class="form-group">
      <label class="form-label">Report Type</label>
      <select class="form-select" id="report-type" required>
        <option value="blood_test">Blood Test</option>
        <option value="xray">X-Ray</option>
        <option value="mri">MRI</option>
        <option value="ct_scan">CT Scan</option>
        <option value="ultrasound">Ultrasound</option>
        <option value="ecg">ECG</option>
        <option value="other">Other</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">File (PDF or Image)</label>
      <input type="file" class="form-input" id="report-file" accept=".pdf,image/*" required style="padding: 8px;">
    </div>
  `;
  openFormModal();
}

function closeEMRModal() {
  document.getElementById('emr-modal').classList.remove('active');
  currentModalType = null;
}

async function saveEMRRecord() {
  if (currentModalType === 'lab_order') { return saveLabOrderFromModal(); }

  try {
    const user = Auth.getUser();
    const doctorId = user.doctor_id;

    let endpoint, data;

    switch(currentModalType) {
      case 'prescription':
        endpoint = '/emr/prescriptions';
        data = {
          appointment_id: Number(document.getElementById('prescription-appointment').value),
          patient_id: currentPatientId,
          doctor_id: doctorId,
          diagnosis: document.getElementById('prescription-diagnosis').value || null,
          advice: document.getElementById('prescription-advice').value || null,
          items: [{
            medicine_name: document.getElementById('med-name').value,
            form: (document.getElementById('med-form')?.value || 'tablet'),
            dosage: document.getElementById('med-dosage').value || null,
            frequency: document.getElementById('med-frequency').value || null,
            duration: document.getElementById('med-duration').value || null,
            instructions: document.getElementById('med-instructions').value || null
          }]
        };
        await API.post(endpoint, data);
        break;

      case 'diagnosis':
        endpoint = '/emr/diagnoses';
        data = {
          appointment_id: Number(document.getElementById('diag-appointment').value),
          patient_id: currentPatientId,
          diagnosis: document.getElementById('diag-name').value,
          severity: document.getElementById('diag-severity').value,
          notes: document.getElementById('diag-notes').value || null
        };
        await API.post(endpoint, data);
        break;

      case 'vitals':
        endpoint = '/emr/vitals';
        data = {
          appointment_id: Number(document.getElementById('vitals-appointment').value),
          patient_id: currentPatientId,
          blood_pressure: document.getElementById('vitals-bp').value || null,
          pulse: document.getElementById('vitals-hr').value ? parseInt(document.getElementById('vitals-hr').value) : null,
          temperature: document.getElementById('vitals-temp').value ? parseFloat(document.getElementById('vitals-temp').value) : null,
          oxygen_level: document.getElementById('vitals-oxygen').value ? parseFloat(document.getElementById('vitals-oxygen').value) : null,
          weight: document.getElementById('vitals-weight').value ? parseFloat(document.getElementById('vitals-weight').value) : null,
          height: document.getElementById('vitals-height').value ? parseFloat(document.getElementById('vitals-height').value) : null
        };
        await API.post(endpoint, data);
        break;

      case 'medical-history':
        endpoint = '/emr/medical-history';
        data = {
          patient_id: currentPatientId,
          condition: document.getElementById('hist-condition').value,
          status: document.getElementById('hist-status').value,
          diagnosed_date: document.getElementById('hist-date').value || null,
          notes: document.getElementById('hist-notes').value || null
        };
        await API.post(endpoint, data);
        break;

      case 'allergy':
        endpoint = '/emr/allergies';
        data = {
          patient_id: currentPatientId,
          allergy_name: document.getElementById('allergy-name').value,
          reaction: document.getElementById('allergy-reaction').value || null
        };
        await API.post(endpoint, data);
        break;

      case 'doctor-note':
        endpoint = '/emr/doctor-notes';
        data = {
          appointment_id: Number(document.getElementById('note-appointment').value),
          patient_id: currentPatientId,
          doctor_id: doctorId,
          note: document.getElementById('note-text').value
        };
        await API.post(endpoint, data);
        break;

      case 'report':
        const file = document.getElementById('report-file').files[0];
        if (!file) {
          Utils.showToast('Please select a file', 'error');
          return;
        }

        const formData = new FormData();
        formData.append('patient_id', currentPatientId);
        formData.append('report_name', document.getElementById('report-name').value);
        formData.append('report_type', document.getElementById('report-type').value);
        formData.append('file', file);

        const response = await fetch(API.config + '/emr/reports/upload', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${Auth.getToken()}` },
          body: formData
        });

        if (!response.ok) throw new Error('Upload failed');
        break;
    }

    Utils.showToast('Record added successfully!', 'success');
    closeEMRModal();

    // Refresh whichever EMR panel is actually open — the video-call panel,
    // or the "View EMR" panel used for physical appointments / dashboard /
    // patient list. Using the wrong one either leaves stale data on screen
    // or throws because the other panel's elements don't exist in the DOM.
    if (currentEMRContext === 'view') {
      refreshViewEMRPanelData();
    } else {
      loadCallEMR(currentPatientId);
    }
  } catch (error) {
    console.error('Failed to save EMR record:', error);
    Utils.showToast(error.message || 'Failed to save record', 'error');
  }
}

// ═══════════════════════════════ ADMISSIONS ═══════════════════════════════
let admitPatientTargetId = null;

function openAdmitPatientModal(patientId) {
  admitPatientTargetId = patientId;
  document.getElementById('admit-reason').value = '';
  document.getElementById('admit-diagnosis').value = '';
  document.getElementById('admit-urgency').value = 'routine';
  document.getElementById('admit-ward-type').value = '';
  (function(){ const m=document.getElementById('admit-patient-modal'); if(m){ m.style.zIndex='2300'; m.classList.add('active'); } })();
}

function closeAdmitPatientModal() {
  document.getElementById('admit-patient-modal').classList.remove('active');
  admitPatientTargetId = null;
}

async function submitAdmitPatient() {
  if (!admitPatientTargetId) return;

  const payload = {
    patient_id: admitPatientTargetId,
    reason: document.getElementById('admit-reason').value.trim() || null,
    diagnosis: document.getElementById('admit-diagnosis').value.trim() || null,
    urgency: document.getElementById('admit-urgency').value,
    preferred_ward_type: document.getElementById('admit-ward-type').value || null,
  };

  try {
    const created = await API.post('/admissions/requests', payload);
    Utils.showToast('Admission request sent. You can set the medication course now.', 'success');
    closeAdmitPatientModal();
    if (typeof closeEMRViewModal === 'function') closeEMRViewModal();
    // Open admission detail so doctor can order multi-day course immediately
    const admissionId = created?.id || created?.data?.id;
    if (admissionId) {
      await viewAdmissionDetail(admissionId);
    } else if (typeof loadMyAdmissions === 'function') {
      await loadMyAdmissions();
    }
  } catch (error) {
    console.error('Failed to create admission request:', error);
    Utils.showToast(error.message || 'Failed to send admission request', 'error');
  }
}

function admissionUrgencyBadge(urgency) {
  const map = { routine: 'badge-info', urgent: 'badge-warning', emergency: 'badge-danger' };
  return `<span class="badge ${map[urgency] || 'badge-info'}">${Utils.escapeHtml((urgency || '').toUpperCase())}</span>`;
}

function admissionStatusBadge(status) {
  const map = { pending: 'badge-warning', admitted: 'badge-success', discharged: 'badge-info', cancelled: 'badge-danger' };
  return `<span class="badge ${map[status] || 'badge-info'}">${Utils.escapeHtml((status || '').toUpperCase())}</span>`;
}

function admissionConditionBadge(flag) {
  if (!flag) return '';
  const cls = flag === 'critical' ? 'badge-danger' : 'badge-success';
  return `<span class="badge ${cls}">${Utils.escapeHtml(flag.toUpperCase())}</span>`;
}

async function loadMyAdmissions() {
  const user = Auth.getUser();
  const listEl = document.getElementById('admissions-list');
  if (!user?.doctor_id) {
    listEl.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No doctor profile linked to this account.</p>';
    return;
  }

  try {
    await ensureDirectoriesLoaded();
    const admissions = await API.get(`/admissions/doctor/${user.doctor_id}`);
    renderMyAdmissions(admissions || []);
  } catch (error) {
    console.error('Failed to load admissions:', error);
    listEl.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">Failed to load admissions.</p>';
  }
}

function renderMyAdmissions(admissions) {
  const listEl = document.getElementById('admissions-list');
  if (admissions.length === 0) {
    listEl.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No admissions yet. Open a patient\'s EMR to request one.</p>';
    return;
  }

  // Most recent first
  const sorted = [...admissions].sort((a, b) => new Date(b.requested_at) - new Date(a.requested_at));

  listEl.innerHTML = `
    <div class="table-responsive">
      <table class="table">
        <thead>
          <tr><th>Patient</th><th>Status</th><th>Urgency</th><th>Condition</th><th>Requested</th><th>Actions</th></tr>
        </thead>
        <tbody>
          ${sorted.map(a => `
            <tr>
              <td><strong>${patientLabel(a.patient_id)}</strong></td>
              <td>${admissionStatusBadge(a.status)}</td>
              <td>${admissionUrgencyBadge(a.urgency)}</td>
              <td>${admissionConditionBadge(a.condition_flag)}</td>
              <td>${Utils.formatDate ? Utils.formatDate(a.requested_at) : a.requested_at}</td>
              <td style="display:flex; gap:6px; flex-wrap:wrap;">
                <button class="btn btn-ghost btn-sm" onclick="viewAdmissionDetail(${a.id})">View</button>
                ${(a.status === 'admitted' || a.status === 'pending') ? `<button class="btn btn-primary btn-sm" onclick="viewAdmissionDetail(${a.id})">Medication Course</button>` : ''}
                              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

let currentDoctorAdmission = null;

async function viewAdmissionDetail(admissionId) {
  try {
    const admission = await API.get(`/admissions/${admissionId}`);
    currentDoctorAdmission = admission;

    document.getElementById('admission-detail-title').textContent = `${patientLabel(admission.patient_id)} — Admission #${admission.id}`;

    const body = document.getElementById('admission-detail-body');
    body.innerHTML = `
      <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px;">
        ${admissionStatusBadge(admission.status)}
        ${admissionUrgencyBadge(admission.urgency)}
        ${admissionConditionBadge(admission.condition_flag)}
      </div>
      <div style="font-size:14px; line-height:1.8; margin-bottom:16px;">
        ${admission.reason ? `<strong>Reason:</strong> ${Utils.escapeHtml(admission.reason)}<br>` : ''}
        ${admission.diagnosis ? `<strong>Provisional Diagnosis:</strong> ${Utils.escapeHtml(admission.diagnosis)}<br>` : ''}
        ${admission.discharge_summary ? `<strong>Discharge Summary:</strong> ${Utils.escapeHtml(admission.discharge_summary)}<br>` : ''}
      </div>

      <div style="border-top:1px solid var(--border); padding-top:12px; margin-bottom:16px;">
        <h4 style="font-size:14px; font-weight:700; margin-bottom:8px;">Rounds / Progress Notes</h4>
        <div id="doctor-notes-list"><div class="loading-spinner">Loading...</div></div>
      </div>

      ${admission.status === 'admitted' ? `
        <div style="border-top:1px solid var(--border); padding-top:12px; margin-bottom:16px;">
          <h4 style="font-size:14px; font-weight:700; margin-bottom:8px;">Add Rounds Note</h4>
          <div class="form-group">
            <textarea class="form-textarea" id="new-note-text" placeholder="Progress note..."></textarea>
          </div>
          <div class="form-group">
            <input type="text" class="form-input" id="new-note-vitals" placeholder="Vitals (optional, e.g. BP 120/80, Pulse 76)">
          </div>
          <button class="btn btn-primary btn-sm" onclick="submitAdmissionNote()">Add Note</button>
        </div>

        <div style="border-top:1px solid var(--border); padding-top:12px; margin-bottom:16px;">
          <h4 style="font-size:14px; font-weight:700; margin-bottom:8px;">Prescribe Medicine</h4>
          <p style="color: var(--text-light); font-size: 12px; margin-bottom: 10px;">Sent straight to the Pharmacist's queue for this ward stay — the patient doesn't need to collect it themselves.</p>
          <div class="form-group autocomplete-wrapper">
            <input type="text" class="form-input" id="adm-med-name" autocomplete="off" placeholder="Medicine name (e.g. Panadol)..." required>
            <div class="autocomplete-dropdown" id="adm-med-name-dropdown"></div>
          </div>
          <div class="form-group autocomplete-wrapper">
            <input type="text" class="form-input" id="adm-med-dosage" autocomplete="off" placeholder="Dosage (e.g. 500mg)">
            <div class="autocomplete-dropdown" id="adm-med-dosage-dropdown"></div>
          </div>
          <div class="form-group">
            <select class="form-select" id="adm-med-frequency">
              <option value="">Select frequency</option>
              <option value="1">1 (Once daily)</option>
              <option value="1+1">1+1 (Twice daily)</option>
              <option value="1+1+1">1+1+1 (Thrice daily)</option>
            </select>
          </div>
          <div class="form-group autocomplete-wrapper">
            <input type="text" class="form-input" id="adm-med-duration" autocomplete="off" placeholder="Duration (e.g. 7 days)">
            <div class="autocomplete-dropdown" id="adm-med-duration-dropdown"></div>
          </div>
          <div class="form-group">
            <textarea class="form-textarea" id="adm-med-instructions" placeholder="Instructions (optional)..."></textarea>
          </div>
          <button class="btn btn-primary btn-sm" onclick="submitAdmissionPrescription()">Send to Pharmacy</button>
        </div>

        <div style="border-top:1px solid var(--border); padding-top:12px; margin-bottom:16px;">
          <h4 style="font-size:14px; font-weight:700; margin-bottom:8px;">Condition</h4>
          <div style="display:flex; gap:8px;">
            <button class="btn btn-ghost btn-sm" onclick="updateAdmissionCondition('stable')">Mark Stable</button>
            <button class="btn btn-danger btn-sm" onclick="updateAdmissionCondition('critical')">Mark Critical</button>
          </div>
        </div>
</div>

        <div style="border-top:1px solid var(--border); padding-top:12px;">
          <h4 style="font-size:14px; font-weight:700; margin-bottom:8px;">Discharge Patient</h4>
          <div class="form-group">
            <textarea class="form-textarea" id="discharge-summary-input" placeholder="Discharge summary..."></textarea>
          </div>
          <button class="btn btn-danger" onclick="submitDoctorDischarge()">Discharge &amp; Free Bed</button>
        </div>
      ` : ''}

      ${(admission.status === 'admitted' || admission.status === 'pending') ? `
        <div style="border-top:2px solid var(--primary, #3d5a40); padding-top:14px; margin-top:8px; margin-bottom:16px;">
          <h4 style="font-size:15px; font-weight:700; margin-bottom:6px;">📋 Multi-day Medication / Drip Course (for Nurses)</h4>
          <p style="color: var(--text-light); font-size: 12px; margin-bottom: 10px;">
            Set the full course of medicines and drips for several days. After a bed is assigned, nurses on that bed will see each day's doses and mark them given.
            ${admission.status === 'pending' ? '<br><strong>Note:</strong> Admission is still pending bed allocation — you can still save the course now.' : ''}
          </p>
          <div id="admission-courses-list" style="margin-bottom:12px;"><div class="loading-spinner">Loading courses...</div></div>
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">Course title</label>
              <input type="text" class="form-input" id="course-title" value="Ward Medication Course">
            </div>
            <div class="form-group">
              <label class="form-label">Start date</label>
              <input type="date" class="form-input" id="course-start">
            </div>
            <div class="form-group">
              <label class="form-label">Duration (days)</label>
              <input type="number" class="form-input" id="course-days" min="1" max="90" value="3">
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Clinical notes for nursing</label>
            <textarea class="form-textarea" id="course-notes" placeholder="Optional notes for nursing staff"></textarea>
          </div>
          <div id="course-items-builder">
            <div class="course-item-row" style="display:grid; grid-template-columns:2fr 1fr 1.2fr 1.2fr 1fr; gap:8px; margin-bottom:8px; align-items:end;">
              <div class="form-group" style="margin:0; position:relative;">
                <label class="form-label">Medicine name *</label>
                <input class="form-input" data-field="medicine_name" placeholder="Search medicine library..." autocomplete="off" required>
                <div class="autocomplete-dropdown" data-role="med-dropdown" style="display:none;"></div>
              </div>
              <div class="form-group" style="margin:0; position:relative;">
                <label class="form-label">Dosage *</label>
                <input class="form-input" data-field="dosage" placeholder="e.g. 500mg / 5ml" autocomplete="off">
                <div class="autocomplete-dropdown" data-role="dose-dropdown" style="display:none;"></div>
              </div>
              <div class="form-group" style="margin:0;">
                <label class="form-label">Frequency</label>
                <select class="form-select" data-field="frequency">
                  <option value="OD">Once daily (OD)</option>
                  <option value="BD">Twice daily (BD)</option>
                  <option value="TID">Thrice daily (TID)</option>
                  <option value="QID">Four times (QID)</option>
                  <option value="STAT">STAT (once)</option>
                </select>
              </div>
              <div class="form-group" style="margin:0;">
                <label class="form-label">Type</label>
                <select class="form-select" data-field="route" onchange="onCourseRouteChange(this)">
                  <option value="tablet">Tablet</option>
                  <option value="capsule">Capsule</option>
                  <option value="syrup">Syrup</option>
                  <option value="injection">Injection</option>
                  <option value="drip">Drip (IV)</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div class="form-group" data-role="drip-wrap" style="margin:0; display:none;">
                <label class="form-label">Drip rate (optional)</label>
                <input class="form-input" data-field="drip_rate" placeholder="e.g. 20 drops/min — optional">
              </div>
            </div>
          </div>
          <div style="display:flex; gap:8px; margin-top:8px; flex-wrap:wrap;">
            <button type="button" class="btn btn-ghost btn-sm" onclick="addCourseItemRow()">+ Add medicine line</button>
            <button type="button" class="btn btn-primary btn-sm" onclick="submitMedicationCourse()">Save Course for Nurses</button>
          </div>
        </div>
      ` : ''}

    `;

    document.getElementById('admission-detail-modal').classList.add('active');
    loadAdmissionNotesForDoctor(admission.id);
    if (admission.status === 'admitted' || admission.status === 'pending') {
      const cs = document.getElementById('course-start');
      if (cs) cs.value = new Date().toISOString().slice(0,10);
      loadAdmissionCourses(admission.id);
    wireCourseMedicineLibrary();
    }

    if (admission.status === 'admitted') {
      attachAutocomplete('adm-med-name', 'adm-med-name-dropdown', window.MEDICINE_LIBRARY || []);
      attachAutocomplete('adm-med-dosage', 'adm-med-dosage-dropdown', window.DOSAGE_OPTIONS || []);
      attachAutocomplete('adm-med-duration', 'adm-med-duration-dropdown', window.DURATION_OPTIONS || []);
    }
  } catch (error) {
    console.error('Failed to load admission:', error);
    Utils.showToast('Failed to load admission', 'error');
  }
}

async function loadAdmissionNotesForDoctor(admissionId) {
  const target = document.getElementById('doctor-notes-list');
  try {
    const notes = await API.get(`/admissions/${admissionId}/notes`);
    if (!notes || notes.length === 0) {
      target.innerHTML = '<p style="color: var(--text-light); font-size: 14px;">No rounds notes yet.</p>';
      return;
    }
    target.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:10px;">
        ${notes.map(n => `
          <div style="background: var(--bg-alt); border-radius: 10px; padding: 10px 14px; font-size: 13px;">
            <div style="font-weight:600; margin-bottom:4px;">${doctorLabel(n.doctor_id)} &middot; ${Utils.formatDate ? Utils.formatDate(n.created_at) : n.created_at}</div>
            <div>${Utils.escapeHtml(n.note)}</div>
            ${n.vitals ? `<div style="color: var(--text-light); margin-top:4px;">Vitals: ${Utils.escapeHtml(n.vitals)}</div>` : ''}
          </div>
        `).join('')}
      </div>
    `;
  } catch (error) {
    target.innerHTML = '<p style="color: var(--text-light); font-size: 14px;">Could not load notes.</p>';
  }
}

function closeAdmissionDetailModal() {
  document.getElementById('admission-detail-modal').classList.remove('active');
  currentDoctorAdmission = null;
}

async function submitAdmissionPrescription() {
  if (!currentDoctorAdmission) return;

  const medicineName = document.getElementById('adm-med-name').value.trim();
  if (!medicineName) {
    Utils.showToast('Please enter a medicine name', 'error');
    return;
  }

  const user = Auth.getUser();
  const data = {
    admission_id: currentDoctorAdmission.id,
    patient_id: currentDoctorAdmission.patient_id,
    doctor_id: user.doctor_id,
    items: [{
      medicine_name: medicineName,
      dosage: document.getElementById('adm-med-dosage').value || null,
      frequency: document.getElementById('adm-med-frequency').value || null,
      duration: document.getElementById('adm-med-duration').value || null,
      instructions: document.getElementById('adm-med-instructions').value || null
    }]
  };

  try {
    await API.post('/emr/prescriptions', data);
    Utils.showToast('Sent to Pharmacy', 'success');
    document.getElementById('adm-med-name').value = '';
    document.getElementById('adm-med-dosage').value = '';
    document.getElementById('adm-med-frequency').value = '';
    document.getElementById('adm-med-duration').value = '';
    document.getElementById('adm-med-instructions').value = '';
  } catch (error) {
    console.error('Failed to prescribe medicine:', error);
    Utils.showToast(error.message || 'Failed to send to pharmacy', 'error');
  }
}

async function submitAdmissionNote() {
  if (!currentDoctorAdmission) return;
  const note = document.getElementById('new-note-text').value.trim();
  const vitals = document.getElementById('new-note-vitals').value.trim();
  if (!note) {
    Utils.showToast('Please enter a note', 'error');
    return;
  }
  try {
    await API.post(`/admissions/${currentDoctorAdmission.id}/notes`, { note, vitals: vitals || null });
    Utils.showToast('Note added', 'success');
    document.getElementById('new-note-text').value = '';
    document.getElementById('new-note-vitals').value = '';
    loadAdmissionNotesForDoctor(currentDoctorAdmission.id);
  } catch (error) {
    console.error('Failed to add note:', error);
    Utils.showToast(error.message || 'Failed to add note', 'error');
  }
}

async function updateAdmissionCondition(flag) {
  if (!currentDoctorAdmission) return;
  try {
    await API.put(`/admissions/${currentDoctorAdmission.id}/condition`, { condition_flag: flag });
    Utils.showToast(`Marked as ${flag}`, 'success');
    viewAdmissionDetail(currentDoctorAdmission.id);
    loadMyAdmissions();
  } catch (error) {
    console.error('Failed to update condition:', error);
    Utils.showToast(error.message || 'Failed to update condition', 'error');
  }
}

async function submitDoctorDischarge() {
  if (!currentDoctorAdmission) return;
  const summary = document.getElementById('discharge-summary-input')?.value?.trim() || '';
  if (!summary) {
    Utils.showToast('Please enter a discharge summary', 'error');
    return;
  }
  try {
    await API.put(`/admissions/${currentDoctorAdmission.id}/discharge`, { discharge_summary: summary });
    Utils.showToast('Patient discharged and bed freed', 'success');
    closeAdmissionDetailModal();
    loadMyAdmissions();
  } catch (error) {
    console.error('Failed to discharge patient:', error);
    Utils.showToast(error.message || 'Failed to discharge patient', 'error');
  }
}



async function viewLabReport(orderId) {
  try {
    const res = await API.get(`/laboratory/orders/${orderId}/report`);
    const data = res?.data || res;
    const html = data.html || data;
    if (!html) throw new Error('No report available');
    const w = window.open('', '_blank');
    if (!w) {
      Utils.showToast('Allow pop-ups to view the report', 'error');
      return;
    }
    w.document.open();
    w.document.write(html);
    w.document.close();
  } catch (e) {
    Utils.showToast(e.message || String(e), 'error');
  }
}



async function downloadLabReport(orderId) {
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
    Utils.showToast(e.message || String(e), 'error');
  }
}


async function loadAdmissionCourses(admissionId) {
  const el = document.getElementById('admission-courses-list');
  if (!el) return;
  try {
    const res = await API.get(`/nursing/admissions/${admissionId}/courses`);
    const courses = Array.isArray(res) ? res : (res?.data || []);
    if (!courses.length) {
      el.innerHTML = '<p style="color:var(--text-light); font-size:13px;">No multi-day courses yet.</p>';
      return;
    }
    el.innerHTML = courses.map(c => `
      <div style="background:var(--bg-alt); border-radius:8px; padding:10px; margin-bottom:8px; font-size:13px;">
        <strong>${Utils.escapeHtml(c.title)}</strong>
        <span class="badge">${Utils.escapeHtml(c.status)}</span>
        <div style="color:var(--text-light);">${c.start_date} · ${c.duration_days} day(s) · Today: ${c.today_given || 0} given / ${c.today_pending || 0} pending</div>
        <ul style="margin:6px 0 0 16px;">
          ${(c.items || []).map(i => `<li><strong>${Utils.escapeHtml(i.medicine_name)}</strong> ${Utils.escapeHtml(i.dosage)} · ${Utils.escapeHtml(i.frequency)} · ${Utils.escapeHtml((i.route||'tablet'))}${i.drip_rate ? ' · drip ' + Utils.escapeHtml(i.drip_rate) : ''}</li>`).join('')}
        </ul>
      </div>
    `).join('');
  } catch (e) {
    el.innerHTML = '<p style="color:var(--text-light); font-size:13px;">Could not load courses.</p>';
  }
}


function wireCourseMedicineLibrary() {
  document.querySelectorAll('#course-items-builder .course-item-row').forEach(row => {
    const medInput = row.querySelector('[data-field="medicine_name"]');
    const medDrop = row.querySelector('[data-role="med-dropdown"]');
    const doseInput = row.querySelector('[data-field="dosage"]');
    const doseDrop = row.querySelector('[data-role="dose-dropdown"]');
    if (medInput && medDrop && !medInput.dataset.libraryWired) {
      attachAutocompleteEl(medInput, medDrop, window.MEDICINE_LIBRARY || []);
      medInput.dataset.libraryWired = '1';
    }
    if (doseInput && doseDrop && !doseInput.dataset.libraryWired) {
      attachAutocompleteEl(doseInput, doseDrop, window.DOSAGE_OPTIONS || []);
      doseInput.dataset.libraryWired = '1';
    }
  });
}


function onCourseRouteChange(selectEl) {
  const row = selectEl.closest('.course-item-row');
  if (!row) return;
  const dripWrap = row.querySelector('[data-role="drip-wrap"]');
  if (!dripWrap) return;
  const isDrip = selectEl.value === 'drip';
  dripWrap.style.display = isDrip ? 'block' : 'none';
  if (!isDrip) {
    const input = dripWrap.querySelector('[data-field="drip_rate"]');
    if (input) input.value = '';
  }
}

function addCourseItemRow() {
  const box = document.getElementById('course-items-builder');
  if (!box) return;
  const row = document.createElement('div');
  row.className = 'course-item-row';
  row.style.cssText = 'display:grid; grid-template-columns:2fr 1fr 1.2fr 1.2fr 1fr; gap:8px; margin-bottom:8px; align-items:end;';
  // Same medicine library as the prescription form (window.MEDICINE_LIBRARY)
  row.innerHTML = `
    <div class="form-group" style="margin:0; position:relative;">
      <label class="form-label">Medicine name *</label>
      <input class="form-input" data-field="medicine_name" placeholder="Search medicine library..." autocomplete="off">
      <div class="autocomplete-dropdown" data-role="med-dropdown" style="display:none;"></div>
    </div>
    <div class="form-group" style="margin:0; position:relative;">
      <label class="form-label">Dosage *</label>
      <input class="form-input" data-field="dosage" placeholder="e.g. 500mg / 5ml" autocomplete="off">
      <div class="autocomplete-dropdown" data-role="dose-dropdown" style="display:none;"></div>
    </div>
    <div class="form-group" style="margin:0;">
      <label class="form-label">Frequency</label>
      <select class="form-select" data-field="frequency">
        <option value="OD">Once daily (OD)</option>
        <option value="BD">Twice daily (BD)</option>
        <option value="TID">Thrice daily (TID)</option>
        <option value="QID">Four times (QID)</option>
        <option value="STAT">STAT (once)</option>
      </select>
    </div>
    <div class="form-group" style="margin:0;">
      <label class="form-label">Type / Form</label>
      <select class="form-select" data-field="route" onchange="onCourseRouteChange(this)">
        <option value="tablet">Tablet</option>
        <option value="capsule">Capsule</option>
        <option value="syrup">Syrup</option>
        <option value="injection">Injection</option>
        <option value="drip">Drip (IV)</option>
        <option value="other">Other</option>
      </select>
    </div>
    <div class="form-group" data-role="drip-wrap" style="margin:0; display:none;">
      <label class="form-label">Drip rate (optional)</label>
      <input class="form-input" data-field="drip_rate" placeholder="optional">
    </div>
  `;
  box.appendChild(row);

  const medInput = row.querySelector('[data-field="medicine_name"]');
  const medDrop = row.querySelector('[data-role="med-dropdown"]');
  const doseInput = row.querySelector('[data-field="dosage"]');
  const doseDrop = row.querySelector('[data-role="dose-dropdown"]');
  attachAutocompleteEl(medInput, medDrop, window.MEDICINE_LIBRARY || []);
  attachAutocompleteEl(doseInput, doseDrop, window.DOSAGE_OPTIONS || []);
}

async function submitMedicationCourse() {
  if (!currentDoctorAdmission || !['admitted', 'pending'].includes(currentDoctorAdmission.status)) {
    Utils.showToast('Course can only be set for pending or admitted patients', 'error');
    return;
  }
  const user = Auth.getUser();
  const items = [];
  document.querySelectorAll('#course-items-builder .course-item-row').forEach(row => {
    const get = (f) => row.querySelector(`[data-field="${f}"]`)?.value?.trim();
    const name = get('medicine_name');
    const dosage = get('dosage');
    if (name && dosage) {
      const route = get('route') || 'tablet';
      const frequency = get('frequency') || 'OD';
      const freqMap = { OD: 1, QD: 1, STAT: 1, BD: 2, BID: 2, TID: 3, TDS: 3, QID: 4, QDS: 4 };
      const times = freqMap[(frequency || 'OD').toUpperCase()] || 1;
      const drip = route === 'drip' ? (get('drip_rate') || null) : null;
      items.push({
        medicine_name: name,
        dosage,
        route,
        frequency,
        times_per_day: times,
        drip_rate: drip,
      });
    }
  });
  if (!items.length) {
    Utils.showToast('Add at least one medicine line', 'error');
    return;
  }
  const payload = {
    admission_id: currentDoctorAdmission.id,
    ordered_by_doctor_id: user.doctor_id,
    title: document.getElementById('course-title')?.value || 'Ward Medication Course',
    start_date: document.getElementById('course-start')?.value,
    duration_days: parseInt(document.getElementById('course-days')?.value || '1', 10),
    clinical_notes: document.getElementById('course-notes')?.value || null,
    items,
  };
  if (!payload.start_date) {
    Utils.showToast('Start date required', 'error');
    return;
  }
  try {
    await API.post('/nursing/courses', payload);
    Utils.showToast('Course saved — nurses get doses & pharmacist gets orders', 'success');
    loadAdmissionCourses(currentDoctorAdmission.id);
    // If video-call EMR is open for this patient, refresh so course appears immediately
    if (currentEMRContext === 'call' && currentPatientId) {
      const pid = currentPatientId;
      setTimeout(() => loadCallEMR(pid), 400);
    }
  } catch (e) {
    Utils.showToast(e.message || String(e), 'error');
  }
}


async function completeAppointment(appointmentId) {
  try {
    await API.put(`/appointments/${appointmentId}/status`, { status: 'completed' });
    Utils.showToast('Visit marked completed — ready for billing', 'success');
    if (typeof loadAppointments === 'function') loadAppointments();
    if (typeof loadDashboard === 'function') loadDashboard();
  } catch (e) {
    // some backends use different payload
    try {
      await API.put(`/appointments/${appointmentId}`, { status: 'completed' });
      Utils.showToast('Visit marked completed', 'success');
    } catch (e2) {
      Utils.showToast(e2.message || e.message || String(e), 'error');
    }
  }
}
