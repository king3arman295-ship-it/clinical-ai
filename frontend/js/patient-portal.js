// Patient Portal Functionality
// The active tab (dashboard / appointments / ai-chat / ...) used to live only
// in this variable, so any reload — including the one some mobile browsers
// trigger when the native file/camera picker opens for an <input type="file">
// while the patient is mid-conversation with the AI — always landed back on
// "dashboard" after DOMContentLoaded re-ran, even though the chat transcript
// itself was already being restored (see restoreChatTranscript). Persisting
// the active tab the same way the chat session/transcript is persisted means
// a reload reopens the same tab instead of bouncing to the dashboard.
let currentPage = sessionStorage.getItem('pp_current_page') || 'dashboard';
// The session id used to be a fresh random value on every page load, which
// meant a browser reload mid-conversation (including the one some mobile
// browsers trigger when the native photo/camera picker opens for a file
// input — a known OS-level behavior, not something JS can prevent) silently
// orphaned the AI's conversation state: the backend still had the booking
// progress / pending upload sitting under the old session id, but the page
// could never reach it again with a brand new one. Reusing the same id for
// the tab's lifetime (and restoring the visible transcript below) means a
// reload picks the conversation back up instead of looking "broken".
let chatSessionId = sessionStorage.getItem('pp_chat_session_id') || ('sess_' + Math.random().toString(36).slice(2, 10));
sessionStorage.setItem('pp_chat_session_id', chatSessionId);

// Video call variables
let agoraClient = null;
let localAudioTrack = null;
let localVideoTrack = null;
let micEnabled = true;
let cameraEnabled = true;

// Doctor names lookup, so the UI can show "Dr. Jane Smith" instead of
// "Dr. #4" everywhere an appointment/record only stores a doctor_id.
let doctorsById = {};
let myAllAppointments = [];

async function ensureDoctorsLoaded() {
  if (Object.keys(doctorsById).length > 0) return;
  try {
    const doctors = await API.get('/doctors/');
    doctorsById = Object.fromEntries((doctors || []).map(d => [d.id, d]));
  } catch (error) {
    console.error('Failed to load doctors:', error);
  }
}

function doctorLabel(doctorId) {
  const doctor = doctorsById[doctorId];
  const name = doctor ? doctor.full_name : `#${doctorId}`;
  const clean = String(name).replace(/^Dr\.?\s+/i, '');
  return `Dr. ${Utils.escapeHtml(clean)}`;
}

document.addEventListener('DOMContentLoaded', async function() {
  // Prevent redirect loop - check if we just came from login
  const isRedirecting = sessionStorage.getItem('auth_redirecting');
  
  // Check authentication
  if (!Auth.isAuthenticated() || Auth.getRole() !== 'patient') {
    if (!isRedirecting) {
      sessionStorage.setItem('auth_redirecting', 'true');
      window.location.href = 'login.html?redirect=patient-portal.html';
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
  setupNavigation();
  setupChatInput();
  await ensureDoctorsLoaded();

  // Reopen whichever tab was active before this load (see currentPage above)
  // instead of always jumping to the dashboard.
  showPage(currentPage);

  setupIncomingCallHandling();
});

// Two ways an accepted call notification reaches this tab, both fired from
// the notificationclick handler in firebase-messaging-sw.js:
//   1. No patient-portal tab was open -> the service worker opened a new
//      one at patient-portal.html?autojoin=<id>, read here from the URL.
//   2. A patient-portal tab was already open -> the service worker focused
//      it and posted a message instead of navigating it, read here via
//      the 'message' listener.
function setupIncomingCallHandling() {
  const autojoinId = new URLSearchParams(window.location.search).get('autojoin');
  if (autojoinId) {
    // Clean the URL so a later refresh doesn't rejoin/re-trigger.
    window.history.replaceState({}, '', 'patient-portal.html');
    acceptIncomingCall(autojoinId);
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', (event) => {
      if (event.data?.type === 'ACCEPT_CALL' && event.data.appointmentId) {
        acceptIncomingCall(event.data.appointmentId);
      }
    });
  }
}

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

    document.getElementById('user-role').textContent = 'Patient';
    document.getElementById('user-info').style.display = 'block';
  }
}

// Notifications are never auto-prompted (see firebase.js) — this banner is
// the one explicit, user-initiated way to turn them on if the person didn't
// already grant permission at login.
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
      e.preventDefault();
      const page = link.dataset.page;
      showPage(page);
    });
  });
}

function showPage(pageName) {
  currentPage = pageName;
  sessionStorage.setItem('pp_current_page', pageName);

  // Update sidebar active state
  document.querySelectorAll('.sidebar-link').forEach(link => {
    link.classList.toggle('active', link.dataset.page === pageName);
  });
  
  // Show page
  document.querySelectorAll('.page').forEach(page => {
    page.classList.toggle('active', page.id === `page-${pageName}`);
  });
  
  // Load page content
  switch(pageName) {
    case 'dashboard':
      loadDashboard();
  refreshBillsBadge();
      break;
    case 'appointments':
      loadAppointments();
      break;
    case 'ai-chat':
      // Chat is already loaded
      break;
    case 'video-call':
      // Entered only via acceptIncomingCall() when a call notification is
      // accepted — nothing to load here, the call joins itself.
      break;
    case 'medical-records':
      loadMedicalRecords();
      break;
    case 'bills':
      loadMyBills();
      break;
    case 'care':
      loadCareInfo();
      break;
  }
}

// Dashboard Functions
async function loadDashboard() {
  try {
    const user = Auth.getUser();
    if (!user || !user.patient_id) {
      Utils.showToast('Patient profile not found', 'error');
      return;
    }

    const [appointments, reports, admissions] = await Promise.all([
      API.get('/appointments/my').catch(() => []),
      API.get(`/emr/patients/${user.patient_id}/reports`).catch(() => []),
      API.get('/admissions/me').catch(() => [])
    ]);

    // If currently admitted, surface it at the top of the dashboard —
    // patients should see this without having to go looking for it.
    const banner = document.getElementById('admission-banner');
    const activeAdmission = (admissions || []).find(a => a.status === 'admitted');
    if (activeAdmission && banner) {
      banner.style.display = 'block';
      banner.innerHTML = `
        <div class="card" style="background: var(--bg-alt); border-left: 4px solid var(--primary); margin-bottom: 20px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px;">
          <div>
            <strong>You are currently admitted</strong>
            <div style="color: var(--text-light); font-size: 14px; margin-top: 4px;">
              ${activeAdmission.ward_name ? Utils.escapeHtml(activeAdmission.ward_name) : 'Ward'}${activeAdmission.bed_number ? ` — Bed ${Utils.escapeHtml(activeAdmission.bed_number)}` : ''}
              ${activeAdmission.admitting_doctor_name ? ` · Dr. ${Utils.escapeHtml(activeAdmission.admitting_doctor_name)}` : ''}
            </div>
          </div>
          <a href="#care" class="btn btn-primary btn-sm" onclick="showPage('care')">View Details</a>
        </div>
      `;
    } else if (banner) {
      banner.style.display = 'none';
      banner.innerHTML = '';
    }

    // Update stats
    const videoAppts = appointments.filter(a => a.appointment_type === 'video');
    (document.getElementById('total-appointments') || {}).textContent = appointments.length;
    (document.getElementById('total-records') || {}).textContent = reports.length;
    (document.getElementById('video-consultations') || {}).textContent = videoAppts.length;

    if (window.PortalUI) {
      PortalUI.ensureChartJs(function () {
        const weekly = PortalUI.weeklyCounts(appointments || [], 'appointment_date');
        PortalUI.lineChart('portal-trend-chart', weekly.labels, weekly.data, 'My appointments');
        const statuses = {};
        (appointments || []).forEach(a => { const s=(a.status||'unknown').toLowerCase(); statuses[s]=(statuses[s]||0)+1; });
        const labels = Object.keys(statuses);
        if (labels.length) PortalUI.doughnutChart('portal-status-chart', labels, labels.map(k=>statuses[k]));
      });
    }

    // Show upcoming appointments
    const upcoming = appointments
      .filter(a => a.status !== 'completed' && a.status !== 'cancelled')
      .sort((a, b) => (a.appointment_date + a.appointment_time).localeCompare(b.appointment_date + b.appointment_time))
      .slice(0, 5);

    const upcomingDiv = document.getElementById('upcoming-appointments');
    if (!upcomingDiv) return;
    if (upcoming.length === 0) {
      upcomingDiv.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No upcoming appointments</p>';
    } else {
      upcomingDiv.innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Time</th>
              <th>Doctor</th>
              <th>Type</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${upcoming.map(a => `
              <tr>
                <td>${Utils.formatDate(a.appointment_date)}</td>
                <td>${Utils.formatTime(a.appointment_time)}</td>
                <td>${doctorLabel(a.doctor_id)}</td>
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

// Appointments Functions
async function loadAppointments() {
  try {
    // Load all appointments
    const appointments = await API.get('/appointments/my');
    const sorted = appointments.sort((a, b) => b.id - a.id);
    const allApptsDiv = document.getElementById('all-appointments');
    
    if (sorted.length === 0) {
      allApptsDiv.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No appointments yet</p>';
    } else {
      allApptsDiv.innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Date</th>
              <th>Time</th>
              <th>Doctor</th>
              <th>Type</th>
              <th>Reason</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${sorted.map(a => `
              <tr>
                <td>#${a.id}</td>
                <td>${Utils.formatDate(a.appointment_date)}</td>
                <td>${Utils.formatTime(a.appointment_time)}</td>
                <td>${doctorLabel(a.doctor_id)}</td>
                <td>${a.appointment_type === 'video' ? `${Icons.video} Video` : `${Icons.hospital} Physical`}</td>
                <td>${Utils.escapeHtml(a.reason || '—')}</td>
                <td><span class="badge badge-${getStatusBadge(a.status)}">${a.status}</span></td>
                <td>
                  ${a.status === 'scheduled'
                    ? `<button class="btn btn-ghost btn-sm" style="color: var(--danger, #B4614C);" onclick="cancelAppointment(${a.id})">Cancel</button>`
                    : '—'}
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }
  } catch (error) {
    console.error('Failed to load appointments:', error);
    Utils.showToast('Failed to load appointments', 'error');
  }
}

async function cancelAppointment(appointmentId) {
  if (!confirm('Are you sure you want to cancel this appointment?')) {
    return;
  }

  try {
    // Patient-scoped cancel endpoint: ownership is verified server-side,
    // so a patient can only ever cancel their own appointment.
    await API.put(`/appointments/my/${appointmentId}/cancel`);
    Utils.showToast('Appointment cancelled.', 'success');

    // Refresh whichever views show appointment data
    loadAppointments();
    loadDashboard();
  } catch (error) {
    console.error('Failed to cancel appointment:', error);
    Utils.showToast(error.message || 'Failed to cancel appointment', 'error');
  }
}

// AI Chat Functions
function setupChatInput() {
  const input = document.getElementById('chat-input');
  const fileInput = document.getElementById('chat-file-input');
  
  input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  // This input has no visible trigger by default. It's only ever opened
  // via the "Attach file" button the assistant adds inline in the chat
  // when it's actually asking for a document (see showChatUploadPrompt).
  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    fileInput.value = '';
    if (!file) return;

    const prompt = document.getElementById('chat-upload-prompt');
    if (prompt) prompt.remove();

    addChatMessage('user', `\u{1F4CE} ${file.name}`);

    // Restore viewport scroll that the native file picker may have clobbered
    if (typeof _savedScrollY !== 'undefined') {
      window.scrollTo(0, _savedScrollY);
      _savedScrollY = undefined;
    }

    sendToAI('', file);
  });

  restoreChatTranscript();
}

// --- Chat transcript persistence -------------------------------------
// The visible chat only ever lived in the DOM, so any reload — including
// the one some mobile browsers trigger when a file/camera picker opens —
// wiped it and made the assistant look broken even though the backend's
// conversation state (tied to chatSessionId, now persisted above) was
// still intact. Saving/restoring the transcript here keeps what the
// patient sees in sync with that.
function getStoredChatTranscript() {
  try {
    return JSON.parse(sessionStorage.getItem('pp_chat_transcript') || '[]');
  } catch (e) {
    return [];
  }
}

function saveChatTranscript(entries) {
  sessionStorage.setItem('pp_chat_transcript', JSON.stringify(entries));
}

function appendToStoredTranscript(entry) {
  const entries = getStoredChatTranscript();
  entries.push(entry);
  saveChatTranscript(entries);
}

function showWelcomeBubble() {
  const wrap = document.createElement('div');
  wrap.className = 'chat-message';
  wrap.innerHTML = `
    <div class="chat-avatar">${Icons.bot}</div>
    <div class="chat-bubble">
      <strong>Hello! I'm your Clinic AI Assistant.</strong><br><br>
      I can help you with:<br>
      \u2022 Booking appointments with our doctors<br>
      \u2022 Our medical departments and specializations<br>
      \u2022 Doctor availability and schedules<br><br>
      How can I assist you today?
    </div>
  `;
  document.getElementById('chat-messages').appendChild(wrap);
  scrollChatToBottom();
}

function restoreChatTranscript() {
  const entries = getStoredChatTranscript();
  if (!entries.length) {
    // First visit — show the new welcome with suggestion buttons
    document.getElementById('chat-messages').innerHTML = '';
    showWelcomeBubble();
    appendToStoredTranscript({ type: 'welcome' });
    showSuggestions(["Book Appointment", "View Departments", "See Available Doctors"]);
    return;
  }

  document.getElementById('chat-messages').innerHTML = '';

  entries.forEach((entry) => {
    if (entry.type === 'welcome') {
      showWelcomeBubble();
    } else if (entry.type === 'upload_prompt') {
      showChatUploadPrompt({ persist: false });
    } else if (entry.type === 'suggestions') {
      showSuggestions(entry.labels, { persist: false });
    } else {
      addChatMessage(entry.role, entry.text, { persist: false });
    }
  });

  // After a file-picker reload the layout settles late; keep the chat
  // pinned to the bottom so an upload doesn't read as a page refresh.
  [100, 300, 700].forEach(ms => setTimeout(scrollChatToBottom, ms));
}

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  if (!message) return;

  addChatMessage('user', message);
  input.value = '';
  await sendToAI(message, null);
}

async function sendToAI(message, file) {
  // Show typing indicator
  const typingDiv = document.createElement('div');
  typingDiv.className = 'chat-message';
  typingDiv.innerHTML = `<div class="chat-avatar">${Icons.bot}</div><div class="chat-bubble">Typing...</div>`;
  document.getElementById('chat-messages').appendChild(typingDiv);
  scrollChatToBottom();

  try {
    let response;

    if (file) {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(
        `${API.config}/ai/chat?session_id=${chatSessionId}&message=${encodeURIComponent(message || '')}`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${Auth.getToken()}` },
          body: formData
        }
      );
      response = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(response?.detail || response?.message || 'Upload failed');
      }
    } else {
      response = await API.post(
        `/ai/chat?session_id=${chatSessionId}&message=${encodeURIComponent(message)}`,
        null
      );
    }

    typingDiv.remove();
    addChatMessage('ai', response.response || response.message || 'No response');

    if (response.suggestions && response.suggestions.length > 0) {
      showSuggestions(response.suggestions);
    }

    if (response.awaiting_upload) {
      showChatUploadPrompt();
    }

    scrollChatToBottom();
    setTimeout(scrollChatToBottom, 200);
    setTimeout(scrollChatToBottom, 500);
  } catch (error) {
    typingDiv.remove();
    addChatMessage('ai', 'Sorry, I encountered an error: ' + error.message);
    scrollChatToBottom();
  }
}

function showSuggestions(suggestions, options = {}) {
  const { persist = true } = options;
  const messagesDiv = document.getElementById('chat-messages');
  const wrap = document.createElement('div');
  wrap.className = 'chat-message ai';
  wrap.innerHTML = `<div class="chat-avatar">${Icons.bot}</div><div class="chat-suggestions"></div>`;
  const container = wrap.querySelector('.chat-suggestions');
  suggestions.forEach(function(label) {
    const btn = document.createElement('button');
    btn.className = 'suggestion-btn';
    btn.textContent = label;
    btn.addEventListener('click', function() {
      document.getElementById('chat-input').value = label;
      sendChatMessage();
    });
    container.appendChild(btn);
  });
  messagesDiv.appendChild(wrap);
  if (persist) appendToStoredTranscript({ type: 'suggestions', labels: suggestions });
  scrollChatToBottom();
}

function showChatUploadPrompt(options = {}) {
  const { persist = true } = options;
  if (document.getElementById('chat-upload-prompt')) return;

  const messagesDiv = document.getElementById('chat-messages');
  const wrap = document.createElement('div');
  wrap.className = 'chat-message';
  wrap.id = 'chat-upload-prompt';
  wrap.innerHTML = `
    <div class="chat-avatar">${Icons.bot}</div>
    <div class="chat-bubble">
      <button type="button" class="btn btn-ghost" id="chat-upload-trigger-btn" style="display:inline-flex; align-items:center; gap:6px;">
        ${Icons.paperclip} Attach file
      </button>
    </div>
  `;
  messagesDiv.appendChild(wrap);
  scrollChatToBottom();

  document.getElementById('chat-upload-trigger-btn').addEventListener('click', () => {
    _savedScrollY = window.scrollY;
    document.getElementById('chat-file-input').click();
  });

  if (persist) appendToStoredTranscript({ type: 'upload_prompt' });
}

function addChatMessage(role, text, options = {}) {
  const { persist = true } = options;
  const messagesDiv = document.getElementById('chat-messages');
  const messageDiv = document.createElement('div');
  messageDiv.className = `chat-message ${role}`;
  messageDiv.innerHTML = `
    <div class="chat-avatar">${role === 'user' ? Icons.person : Icons.bot}</div>
    <div class="chat-bubble">${role === 'user' ? Utils.escapeHtml(text) : Utils.formatBotText(text)}</div>
  `;
  messagesDiv.appendChild(messageDiv);
  scrollChatToBottom();

  if (persist) appendToStoredTranscript({ type: 'message', role, text });
}

function scrollChatToBottom() {
  const el = document.getElementById('chat-messages');
  if (!el) return;
  el.scrollTop = el.scrollHeight;
  const last = el.lastElementChild;
  if (last) last.scrollIntoView({ block: 'end' });
  requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
}

// --- Refresh chat -------------------------------------------------------
// Clears the visible conversation, drops the saved transcript, and starts
// a brand new session id so the AI has no memory of the old conversation.
async function refreshChat() {
  const btn = document.getElementById('refresh-chat-btn');
  if (btn) btn.disabled = true;

  // Best-effort: also ask the backend to drop the old session's state.
  // The chat still resets locally even if this fails (e.g. offline).
  try {
    await API.delete(`/ai/conversation/${encodeURIComponent(chatSessionId)}`);
  } catch (e) {
    console.log('Could not clear server-side conversation state:', e);
  }

  sessionStorage.removeItem('pp_chat_transcript');
  chatSessionId = 'sess_' + Math.random().toString(36).slice(2, 10);
  sessionStorage.setItem('pp_chat_session_id', chatSessionId);

  const messagesDiv = document.getElementById('chat-messages');
  messagesDiv.innerHTML = '';
  showWelcomeBubble();
  appendToStoredTranscript({ type: 'welcome' });
  showSuggestions(["Book Appointment", "View Departments", "See Available Doctors"]);

  if (btn) btn.disabled = false;
}

// Video Call Functions
// Patients never pick an appointment from a list — the only way into a
// call is accepting the incoming-call notification the doctor triggers
// when they start it (see firebase.js / firebase-messaging-sw.js), which
// calls acceptIncomingCall(appointmentId) below.

async function acceptIncomingCall(appointmentId) {
  if (!appointmentId) return;
  try {
    const appointments = await API.get('/appointments/my');
    myAllAppointments = appointments;
  } catch (error) {
    console.error('Failed to load appointments before joining call:', error);
  }
  showPage('video-call');
  await joinVideoCall(appointmentId);
}

async function joinVideoCall(appointmentId) {
  if (!appointmentId) {
    Utils.showToast('No appointment to join', 'error');
    return;
  }

  try {
    // Get video call credentials
    const response = await API.post(`/appointments/${appointmentId}/join/patient`);
    const meeting = response.data || response;

    document.getElementById('video-call-container').style.display = 'block';
    document.getElementById('active-appointment-id').textContent = appointmentId;

    // Load the patient's care record so it's visible during the call,
    // filtered to the selected appointment's doctor only.
    const user = Auth.getUser();
    const appt = myAllAppointments.find(a => a.id == appointmentId);
    if (user?.patient_id) {
      loadDoctorEMR(user.patient_id, appt?.doctor_id);
      startCallEMRPolling(user.patient_id, appt?.doctor_id);
    }

    // Initialize Agora
    await startAgoraCall(meeting);
    Utils.showToast('Connected to video call', 'success');
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

  stopCallEMRPolling();

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
  document.getElementById('video-call-container').style.display = 'none';
  document.getElementById('local-video').innerHTML = '';
  document.getElementById('remote-video').innerHTML = '';

  Utils.showToast('Call ended', 'info');
  showPage('dashboard');
}

// Medical Records Functions
async function loadMedicalRecords() {
  loadMyLabResults();
  try {
    const user = Auth.getUser();
    if (!user || !user.patient_id) return;

    const [reports, appointments] = await Promise.all([
      API.get(`/emr/patients/${user.patient_id}/reports`),
      API.get('/appointments/my')
    ]);
    await ensureDoctorsLoaded();
    populateReportDoctorSelect(appointments);
    const listDiv = document.getElementById('medical-records-list');

    if (reports.length === 0) {
      listDiv.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No medical records uploaded yet</p>';
    } else {
      listDiv.innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Uploaded</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${reports.map(r => {
              const isLab = (r.report_name || '').toLowerCase().includes('lab report')
                || r.report_type === 'blood_test'
                || (r.file_path || '').endsWith('.html');
              return `
              <tr>
                <td>${Utils.escapeHtml(r.report_name)}</td>
                <td><span class="badge badge-info">${Utils.escapeHtml(r.report_type || '')}</span></td>
                <td>${Utils.formatDate(r.uploaded_at)}</td>
                <td style="display:flex; gap:6px; flex-wrap:wrap;">
                  <button class="btn btn-primary btn-sm" onclick="viewOrDownloadReport(${r.id}, true)">View</button>
                  <button class="btn btn-ghost btn-sm" onclick="viewOrDownloadReport(${r.id}, false)">${Icons.download || ''} Download</button>
                </td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      `;
    }

    // Setup upload form
    const form = document.getElementById('upload-record-form');
    form.onsubmit = async (e) => {
      e.preventDefault();
      await uploadMedicalRecord();
    };
  } catch (error) {
    console.error('Failed to load medical records:', error);
    Utils.showToast('Failed to load medical records', 'error');
  }
}

// Admission & Pharmacy Functions (patient-facing)
async function loadCareInfo() {
  await Promise.all([
    loadMyAdmission(),
    loadMyTodayDoses(),
    loadMyPharmacyOrders()
  ]);
  startPatientDoseReminderPoll();
}

const ADMISSION_STATUS_BADGE = {
  pending: 'warning',
  admitted: 'info',
  discharged: 'success',
  cancelled: 'danger'
};

async function loadMyAdmission() {
  const container = document.getElementById('admission-info');
  try {
    const admissions = await API.get('/admissions/me');

    if (!admissions || admissions.length === 0) {
      container.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">You have no admission records.</p>';
      return;
    }

    // Most recent first (backend already orders by requested_at desc)
    container.innerHTML = admissions.map(a => `
      <div class="card" style="background: var(--bg-alt); margin-bottom: 12px;">
        <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-bottom: 10px;">
          <span class="badge badge-${ADMISSION_STATUS_BADGE[a.status] || 'info'}" style="text-transform:capitalize;">${a.status}</span>
          <span style="color: var(--text-light); font-size: 13px;">Requested ${Utils.formatDate(a.requested_at)}</span>
        </div>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; font-size: 14px;">
          ${a.ward_name ? `<div><strong>Ward:</strong> ${Utils.escapeHtml(a.ward_name)}</div>` : ''}
          ${a.bed_number ? `<div><strong>Bed:</strong> ${Utils.escapeHtml(a.bed_number)}</div>` : ''}
          ${a.admitting_doctor_name ? `<div><strong>Doctor:</strong> Dr. ${Utils.escapeHtml(a.admitting_doctor_name)}</div>` : ''}
          ${a.admitted_at ? `<div><strong>Admitted:</strong> ${Utils.formatDate(a.admitted_at)}</div>` : ''}
          ${a.discharged_at ? `<div><strong>Discharged:</strong> ${Utils.formatDate(a.discharged_at)}</div>` : ''}
          ${a.condition_flag ? `<div><strong>Condition:</strong> <span style="text-transform:capitalize;">${a.condition_flag}</span></div>` : ''}
        </div>
        ${a.reason ? `<div style="margin-top:10px; font-size:14px;"><strong>Reason:</strong> ${Utils.escapeHtml(a.reason)}</div>` : ''}
        ${a.diagnosis ? `<div style="margin-top:6px; font-size:14px;"><strong>Diagnosis:</strong> ${Utils.escapeHtml(a.diagnosis)}</div>` : ''}
        ${a.discharge_summary ? `<div style="margin-top:6px; font-size:14px;"><strong>Discharge Summary:</strong> ${Utils.escapeHtml(a.discharge_summary)}</div>` : ''}
      </div>
    `).join('');
  } catch (error) {
    console.error('Failed to load admission info:', error);
    container.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">Could not load admission info.</p>';
  }
}

const PHARMACY_ORDER_STATUS_BADGE = {
  pending: 'warning',
  dispensed: 'success',
  out_of_stock: 'danger',
  cancelled: 'danger'
};

async function loadMyPharmacyOrders() {
  const container = document.getElementById('pharmacy-orders-list');
  try {
    const orders = await API.get('/pharmacy/orders/me');

    if (!orders || orders.length === 0) {
      container.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No medicines have been prescribed yet.</p>';
      return;
    }

    const sorted = orders.sort((a, b) => b.id - a.id);
    container.innerHTML = `
      <table class="table">
        <thead>
          <tr>
            <th>Medicine</th>
            <th>Dosage</th>
            <th>Frequency</th>
            <th>Duration</th>
            <th>Prescribed</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${sorted.map(o => `
            <tr>
              <td>${Icons.pill} ${Utils.escapeHtml(o.medicine_name || 'Medicine')}</td>
              <td>${Utils.escapeHtml(o.dosage || '—')}</td>
              <td>${Utils.escapeHtml(o.frequency || '—')}</td>
              <td>${Utils.escapeHtml(o.duration || '—')}</td>
              <td>${Utils.formatDate(o.created_at)}</td>
              <td><span class="badge badge-${PHARMACY_ORDER_STATUS_BADGE[o.status] || 'info'}" style="text-transform:capitalize;">${o.status.replace('_', ' ')}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (error) {
    console.error('Failed to load pharmacy orders:', error);
    container.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">Could not load prescribed medicines.</p>';
  }
}

function populateReportDoctorSelect(appointments) {
  const select = document.getElementById('record-doctor');
  if (!select) return;

  const doctorIds = [...new Set((appointments || []).map(a => a.doctor_id))];
  const doctors = doctorIds.map(id => doctorsById[id]).filter(Boolean);
  if (!doctors.length) {
    select.innerHTML = '<option value="">No doctors available</option>';
    select.disabled = true;
    return;
  }

  select.disabled = false;
  select.innerHTML = '<option value="">Choose the doctor to receive this document...</option>' +
    doctors.map(doctor =>
      `<option value="${doctor.id}">Dr. ${Utils.escapeHtml(doctor.full_name)}${doctor.specialization ? ` — ${Utils.escapeHtml(doctor.specialization)}` : ''}</option>`
    ).join('');
}

// While a call is active, the doctor may save a prescription/note on their
// side at any moment. There's no websocket/push channel for EMR data, so we
// poll quietly in the background and re-render if anything changed — this
// is what makes a prescription the doctor just saved show up on the
// patient's side during the same call, without needing a page reload.
let callEMRPollTimer = null;
let callEMRLastSnapshot = null;

function startCallEMRPolling(patientId, doctorId) {
  stopCallEMRPolling();
  callEMRPollTimer = setInterval(() => {
    loadDoctorEMR(patientId, doctorId, { silent: true });
  }, 6000);
}

function stopCallEMRPolling() {
  if (callEMRPollTimer) {
    clearInterval(callEMRPollTimer);
    callEMRPollTimer = null;
  }
  callEMRLastSnapshot = null;
}

async function loadDoctorEMR(patientId, doctorId, opts = {}) {
  const content = document.getElementById('doctor-emr-content');
  try {
    const timeline = await API.get(`/emr/patients/${patientId}/timeline`);
    let prescriptions = timeline.prescriptions || [];
    let labOrders = timeline.lab_orders || timeline.data?.lab_orders || [];
    let notes = timeline.doctor_notes || [];
    let diagnoses = timeline.diagnoses || [];
    let vitals = timeline.vitals || [];

    // Show only care from the selected appointment's doctor.
    if (doctorId) {
      const apptDoctor = {};
      myAllAppointments.forEach(a => { apptDoctor[a.id] = a.doctor_id; });
      prescriptions = prescriptions.filter(p => p.doctor_id === doctorId);
      notes = notes.filter(n => n.doctor_id === doctorId);
      diagnoses = diagnoses.filter(d => apptDoctor[d.appointment_id] === doctorId);
      vitals = vitals.filter(v => apptDoctor[v.appointment_id] === doctorId);
    }

    if (opts.silent) {
      const snapshot = JSON.stringify({
        p: prescriptions.map(p => p.id),
        n: notes.map(n => n.id),
        d: diagnoses.map(d => d.id),
        v: vitals.map(v => v.id)
      });
      if (callEMRLastSnapshot === null) {
        callEMRLastSnapshot = snapshot;
      } else if (snapshot === callEMRLastSnapshot) {
        return; // nothing new — don't re-render and cause flicker
      } else {
        const isNewPrescription = prescriptions.length > (JSON.parse(callEMRLastSnapshot).p || []).length;
        callEMRLastSnapshot = snapshot;
        if (isNewPrescription) {
          Utils.showToast('Your doctor just added a new prescription', 'success');
        }
      }
    }

    if (!prescriptions.length && !notes.length && !diagnoses.length && !vitals.length) {
      content.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">Your doctor has not added care notes or prescriptions yet.</p>';
      return;
    }

    const prescriptionRows = prescriptions.flatMap(p => {
      const items = p.items || [];
      return items.map(item => `
        <tr>
          <td>${Utils.formatDate(p.created_at)}</td>
          <td><strong>${Utils.escapeHtml(item.medicine_name)}</strong></td>
          <td>${Utils.escapeHtml(item.dosage || '—')}</td>
          <td>${Utils.escapeHtml(item.frequency || '—')}</td>
          <td>${Utils.escapeHtml(item.duration || '—')}</td>
          <td>${Utils.escapeHtml(item.instructions || '—')}</td>
        </tr>
      `);
    });

    content.innerHTML = `
      ${prescriptionRows.length ? `
        <h3 style="font-size: 16px; margin: 0 0 12px;">Prescriptions</h3>
        <div style="overflow-x: auto; margin-bottom: 24px;">
          <table class="table">
            <thead><tr><th>Date</th><th>Medication</th><th>Dosage</th><th>Frequency</th><th>Duration</th><th>Instructions</th></tr></thead>
            <tbody>${prescriptionRows.join('')}</tbody>
          </table>
        </div>` : ''}
      ${notes.length ? `
        <h3 style="font-size: 16px; margin: 0 0 12px;">Doctor Notes</h3>
        <div style="display: grid; gap: 12px; margin-bottom: 24px;">
          ${notes.map(note => `
            <div style="padding: 14px; background: var(--bg-alt); border-radius: 8px;">
              <div style="font-size: 12px; color: var(--text-light); margin-bottom: 6px;">${Utils.formatDate(note.created_at)} · ${doctorLabel(note.doctor_id)}</div>
              <div>${Utils.escapeHtml(note.note)}</div>
            </div>
          `).join('')}
        </div>` : ''}
      ${diagnoses.length ? `
        <h3 style="font-size: 16px; margin: 0 0 12px;">Diagnoses</h3>
        <div style="display: grid; gap: 8px; margin-bottom: 24px;">
          ${diagnoses.map(diagnosis => `<div><strong>${Utils.escapeHtml(diagnosis.diagnosis)}</strong>${diagnosis.severity ? ` <span class="badge badge-info">${Utils.escapeHtml(diagnosis.severity)}</span>` : ''}${diagnosis.notes ? `<div style="color: var(--text-light); margin-top: 4px;">${Utils.escapeHtml(diagnosis.notes)}</div>` : ''}</div>`).join('')}
        </div>` : ''}
      ${vitals.length ? `
        <h3 style="font-size: 16px; margin: 0 0 12px;">Latest Vital Signs</h3>
        <div style="display: grid; gap: 8px;">
          ${vitals.slice(0, 3).map(vital => `<div>${Utils.formatDate(vital.recorded_at)} — Blood pressure: ${Utils.escapeHtml(vital.blood_pressure || '—')}, Pulse: ${Utils.escapeHtml(vital.pulse || '—')}, Temperature: ${Utils.escapeHtml(vital.temperature || '—')}</div>`).join('')}
        </div>` : ''}
    `;
  } catch (error) {
    console.error('Failed to load doctor EMR:', error);
    content.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">Your care record is currently unavailable.</p>';
  }
}

async function uploadMedicalRecord() {
  try {
    const user = Auth.getUser();
    const file = document.getElementById('record-file').files[0];
    
    if (!file) {
      Utils.showToast('Please select a file', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('patient_id', user.patient_id);
    formData.append('report_name', document.getElementById('record-name').value);
    formData.append('report_type', document.getElementById('record-type').value);
    formData.append('doctor_id', document.getElementById('record-doctor').value);
    formData.append('file', file);

    const response = await fetch(API.config + '/emr/reports/upload', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${Auth.getToken()}`
      },
      body: formData
    });

    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw new Error(error?.detail || error?.message || 'Upload failed');
    }

    Utils.showToast('Document uploaded successfully!', 'success');
    document.getElementById('upload-record-form').reset();
    loadMedicalRecords();
  } catch (error) {
    console.error('Failed to upload record:', error);
    Utils.showToast('Failed to upload document', 'error');
  }
}

async function downloadReport(reportId) {
  return viewOrDownloadReport(reportId, true);
}

async function viewOrDownloadReport(reportId, openInline = true) {
  try {
    const response = await fetch(API.config + `/emr/reports/${reportId}/download`, {
      headers: {
        'Authorization': `Bearer ${Auth.getToken()}`
      }
    });

    if (!response.ok) throw new Error('Download failed');

    const contentType = response.headers.get('content-type') || '';
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    if (openInline || contentType.includes('html') || contentType.includes('pdf') || contentType.includes('image')) {
      const w = window.open(url, '_blank');
      if (!w) Utils.showToast('Allow pop-ups to view the report', 'error');
    } else {
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${reportId}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    }
    setTimeout(() => URL.revokeObjectURL(url), 120000);
  } catch (error) {
    console.error('Failed to download report:', error);
    Utils.showToast('Failed to download report', 'error');
  }
}

async function viewLabOrderReport(orderId) {
  try {
    const res = await API.get(`/laboratory/orders/${orderId}/report`);
    const data = res?.data || res;
    const html = data.html || data;
    if (!html) throw new Error('No report available yet');
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


async function loadMyLabResults() {
  const user = Auth.getUser();
  if (!user?.patient_id) return;
  const el = document.getElementById('my-lab-results-list');
  if (!el) return;
  try {
    const res = await API.get(`/laboratory/patients/${user.patient_id}/orders`);
    const orders = Array.isArray(res) ? res : (res?.data || []);
    const completed = orders.filter(o => o.status === 'completed');
    if (!completed.length) {
      el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">No lab results yet</p>';
      return;
    }
    el.innerHTML = `
      <table class="table">
        <thead><tr><th>Order</th><th>Tests</th><th>Date</th><th>Actions</th></tr></thead>
        <tbody>
          ${completed.map(o => {
            const tests = (o.results || []).map(r => r.test_name || r.test_code || ('#' + r.lab_test_id)).join(', ');
            return `<tr>
              <td><strong>#${o.id}</strong></td>
              <td>${Utils.escapeHtml(tests || '—')}</td>
              <td>${o.completed_at ? Utils.formatDate(o.completed_at) : Utils.formatDate(o.created_at)}</td>
              <td style="display:flex; gap:6px;">
                <button class="btn btn-primary btn-sm" onclick="viewLabOrderReport(${o.id})">View Report</button>
              </td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>`;
  } catch (e) {
    console.error(e);
    el.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 20px;">Unable to load lab results</p>';
  }
}


// ===================== MY BILLS =====================
const BILL_CAT_LABELS = {
  consultation: 'Doctor Fees',
  medicine: 'Medicines',
  lab: 'Laboratory Tests',
  bed: 'Bed / Ward Charges',
  nursing: 'Nursing Services',
  other: 'Other',
};

function billMoney(n) {
  const v = Number(n) || 0;
  return 'PKR ' + v.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

async function loadMyBills() {
  const el = document.getElementById('bills-list');
  const detailCard = document.getElementById('bill-detail-card');
  if (detailCard) detailCard.style.display = 'none';
  if (!el) return;
  el.innerHTML = '<div class="loading-spinner">Loading bills...</div>';
  try {
    const res = await API.get('/billing/my/bills');
    const list = Array.isArray(res) ? res : (res?.data || []);
    const unpaid = list.filter(b => b.status === 'issued').length;
    const badge = document.getElementById('bills-badge');
    if (badge) {
      badge.style.display = unpaid ? 'inline-flex' : 'none';
      badge.textContent = unpaid;
    }
    if (!list.length) {
      el.innerHTML = '<p style="color:var(--text-light); text-align:center; padding:28px;">No bills yet. When the billing desk issues a receipt, it will appear here.</p>';
      return;
    }
    el.innerHTML = `<div class="table-wrap"><table class="table">
      <thead><tr>
        <th>Bill #</th><th>Date</th><th>Total</th><th>Status</th><th></th>
      </tr></thead>
      <tbody>
        ${list.map(b => `<tr>
          <td><strong>${Utils.escapeHtml(b.bill_number)}</strong></td>
          <td style="font-size:13px;">${b.issued_at ? new Date(b.issued_at).toLocaleString() : '—'}</td>
          <td><strong>${billMoney(b.total)}</strong></td>
          <td><span class="badge ${b.status === 'paid' ? 'badge-success' : b.status === 'cancelled' ? 'badge-danger' : 'badge-warning'}">${Utils.escapeHtml((b.status || '').toUpperCase())}</span></td>
          <td><button class="btn btn-ghost btn-sm" type="button" onclick="viewMyBill(${b.id})">View Receipt</button></td>
        </tr>`).join('')}
      </tbody></table></div>`;
  } catch (e) {
    console.error(e);
    el.innerHTML = `<p style="color:var(--text-light);">Unable to load bills. ${Utils.escapeHtml(e.message || '')}</p>`;
  }
}

async function viewMyBill(billId) {
  try {
    const res = await API.get(`/billing/my/bills/${billId}`);
    const bill = res?.data || res;
    const card = document.getElementById('bill-detail-card');
    const body = document.getElementById('bill-detail-body');
    const title = document.getElementById('bill-detail-title');
    if (!card || !body) return;
    if (title) title.textContent = bill.bill_number || 'Bill Receipt';
    card.style.display = 'block';

    const items = bill.items || [];
    const groups = {};
    items.forEach(i => {
      const c = i.category || 'other';
      if (!groups[c]) groups[c] = [];
      groups[c].push(i);
    });
    let itemsHtml = '';
    for (const [cat, rows] of Object.entries(groups)) {
      itemsHtml += `<div style="margin:12px 0 4px; font-weight:700; font-size:13px;">${Utils.escapeHtml(BILL_CAT_LABELS[cat] || cat)}</div>`;
      itemsHtml += `<div class="table-wrap"><table class="table"><thead><tr>
        <th>Description</th><th>Details</th><th style="text-align:right;">Amount</th>
      </tr></thead><tbody>`;
      rows.forEach(i => {
        itemsHtml += `<tr>
          <td><strong>${Utils.escapeHtml(i.description)}</strong></td>
          <td style="font-size:12px;color:var(--text-light);">${Utils.escapeHtml(i.details || '')}</td>
          <td style="text-align:right;">${billMoney(i.amount)}</td>
        </tr>`;
      });
      itemsHtml += '</tbody></table></div>';
    }

    const cats = bill.category_totals || {};
    let totals = Object.entries(cats).map(([k,v]) =>
      `<div style="display:flex;justify-content:space-between;padding:4px 0;"><span>${Utils.escapeHtml(BILL_CAT_LABELS[k]||k)}</span><span>${billMoney(v)}</span></div>`
    ).join('');
    totals += `
      <div style="display:flex;justify-content:space-between;padding:4px 0;"><span>Subtotal</span><span>${billMoney(bill.subtotal)}</span></div>
      <div style="display:flex;justify-content:space-between;padding:4px 0;"><span>Discount</span><span>− ${billMoney(bill.discount)}</span></div>
      <div style="display:flex;justify-content:space-between;padding:4px 0;"><span>Tax</span><span>${billMoney(bill.tax)}</span></div>
      <div style="display:flex;justify-content:space-between;padding:10px 0 0; margin-top:6px; border-top:2px solid var(--charcoal); font-size:18px; font-weight:800;">
        <span>Total</span><span>${billMoney(bill.total)}</span>
      </div>`;

    body.innerHTML = `
      <div style="margin-bottom:12px; font-size:14px;">
        <strong>Status:</strong>
        <span class="badge ${bill.status === 'paid' ? 'badge-success' : bill.status === 'cancelled' ? 'badge-danger' : 'badge-warning'}">${Utils.escapeHtml((bill.status||'').toUpperCase())}</span>
        ${bill.payment_method ? ' · ' + Utils.escapeHtml(bill.payment_method) : ''}
        <br>
        <strong>Issued:</strong> ${bill.issued_at ? new Date(bill.issued_at).toLocaleString() : '—'}
        ${bill.notes ? '<br><strong>Notes:</strong> ' + Utils.escapeHtml(bill.notes) : ''}
      </div>
      ${itemsHtml || '<p style="color:var(--text-light);">No line items</p>'}
      <div style="max-width:320px; margin-left:auto; margin-top:16px;">${totals}</div>
    `;
    card.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    Utils.showToast(e.message || String(e), 'error');
  }
}

// Refresh unpaid badge on dashboard load if available
const _origLoadDashboard = typeof loadDashboard === 'function' ? loadDashboard : null;

async function refreshBillsBadge() {
  // exposed for FCM foreground handler in firebase.js
  try {
    const res = await API.get('/billing/my/bills');
    const list = Array.isArray(res) ? res : (res?.data || []);
    const unpaid = list.filter(b => b.status === 'issued').length;
    const badge = document.getElementById('bills-badge');
    if (badge) {
      badge.style.display = unpaid ? 'inline-flex' : 'none';
      badge.textContent = unpaid;
    }
  } catch (e) { /* ignore */ }
}

window.refreshBillsBadge = refreshBillsBadge;
window.loadMyBills = loadMyBills;
window.viewMyBill = viewMyBill;


// ═════════════════════════════════════════════════════════════
// Patient medication dose schedule + reminders
// ═════════════════════════════════════════════════════════════
let patientDosePollTimer = null;
let patientDoseToastShown = {};

async function loadMyTodayDoses() {
  const el = document.getElementById('today-doses-list');
  if (!el) return;
  try {
    let doses = [];
    try {
      const res = await API.get('/nursing/me/doses');
      doses = Array.isArray(res) ? res : (res?.data || []);
    } catch (e) {
      doses = [];
    }

    // Also build schedule from recent OPD prescriptions (frequency × today)
    try {
      const user = Auth.getUser();
      if (user?.patient_id) {
        const timeline = await API.get(`/emr/patients/${user.patient_id}/timeline`).catch(() => null);
        const prescriptions = timeline?.prescriptions || timeline?.data?.prescriptions || [];
        const today = new Date();
        prescriptions.slice(0, 15).forEach(p => {
          (p.items || []).forEach(item => {
            const times = estimateDoseTimes(item.frequency);
            times.forEach(t => {
              doses.push({
                id: `rx-${p.id}-${item.medicine_name}-${t}`,
                scheduled_time: t,
                scheduled_date: today.toISOString().slice(0, 10),
                status: 'pending',
                medicine_name: item.medicine_name,
                dosage: item.dosage,
                frequency: item.frequency,
                source: 'prescription',
              });
            });
          });
        });
      }
    } catch (_) {}

    // Dedupe by medicine+time
    const seen = new Set();
    doses = doses.filter(d => {
      const k = `${d.medicine_name}|${d.scheduled_time}|${d.scheduled_date || ''}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
    doses.sort((a, b) => String(a.scheduled_time || '').localeCompare(String(b.scheduled_time || '')));

    if (!doses.length) {
      el.innerHTML = '<p style="color:var(--text-light); text-align:center; padding:20px;">No doses scheduled for today. When your doctor orders a course or prescription, times will appear here.</p>';
      return;
    }

    el.innerHTML = `<div class="table-responsive"><table class="table">
      <thead><tr><th>Time</th><th>Medicine</th><th>Dosage</th><th>Status</th></tr></thead>
      <tbody>
        ${doses.map(d => {
          const st = (d.status || 'pending').toLowerCase();
          const badge = st === 'given' ? 'success' : st === 'pending' ? 'warning' : st === 'held' ? 'info' : 'danger';
          return `<tr>
            <td><strong>${Utils.escapeHtml(d.scheduled_time || '—')}</strong></td>
            <td>${Utils.escapeHtml(d.medicine_name || '—')}
              ${d.route ? `<span class="badge" style="margin-left:6px;">${Utils.escapeHtml(String(d.route).toUpperCase())}</span>` : ''}
            </td>
            <td>${Utils.escapeHtml(d.dosage || '—')}</td>
            <td><span class="badge badge-${badge}">${Utils.escapeHtml(st)}</span></td>
          </tr>`;
        }).join('')}
      </tbody>
    </table></div>`;

    // Keep for poller
    window.__patientTodayDoses = doses;
  } catch (e) {
    console.error(e);
    el.innerHTML = '<p style="color:var(--text-light); text-align:center; padding:20px;">Unable to load dose schedule</p>';
  }
}

function estimateDoseTimes(frequency) {
  const raw = String(frequency || '1').trim();
  let timesPerDay = 1;
  if (raw.includes('+')) {
    timesPerDay = Math.max(1, raw.split('+').filter(p => p.trim() !== '').length);
  } else if (/^\d+$/.test(raw)) {
    timesPerDay = Math.max(1, parseInt(raw, 10));
  } else {
    const u = raw.toUpperCase();
    if (/QID|QDS|FOUR/.test(u)) timesPerDay = 4;
    else if (/TID|TDS|THRICE|THREE/.test(u)) timesPerDay = 3;
    else if (/BD|BID|TWICE|TWO/.test(u)) timesPerDay = 2;
    else timesPerDay = 1;
  }
  const defaults = {
    1: ['08:00'],
    2: ['08:00', '20:00'],
    3: ['08:00', '14:00', '20:00'],
    4: ['08:00', '12:00', '16:00', '20:00'],
  };
  return defaults[Math.min(4, timesPerDay)] || ['08:00'];
}

function startPatientDoseReminderPoll() {
  if (patientDosePollTimer) clearInterval(patientDosePollTimer);
  patientDosePollTimer = setInterval(checkPatientDoseReminders, 30000);
  checkPatientDoseReminders();
}

function checkPatientDoseReminders() {
  const doses = window.__patientTodayDoses || [];
  if (!doses.length) return;
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, '0');
  const mm = String(now.getMinutes()).padStart(2, '0');
  const nowMin = now.getHours() * 60 + now.getMinutes();

  doses.forEach(d => {
    if ((d.status || 'pending').toLowerCase() !== 'pending') return;
    const t = String(d.scheduled_time || '08:00');
    const parts = t.split(':');
    const dueMin = parseInt(parts[0], 10) * 60 + (parseInt(parts[1] || '0', 10));
    const diff = dueMin - nowMin;
    // within 10 min before or 5 min after
    if (diff <= 10 && diff >= -5) {
      const key = `${d.id || d.medicine_name}|${t}`;
      if (patientDoseToastShown[key]) return;
      patientDoseToastShown[key] = true;
      const med = d.medicine_name || 'Medicine';
      const dosage = d.dosage ? ` (${d.dosage})` : '';
      Utils.showToast(`💊 Time for ${med}${dosage} — scheduled ${t}`, 'info');
      // Browser notification if permitted
      try {
        if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
          new Notification('Medicine reminder', { body: `Time for ${med}${dosage} at ${t}` });
        } else if (typeof Notification !== 'undefined' && Notification.permission !== 'denied') {
          Notification.requestPermission();
        }
      } catch (_) {}
    }
  });
}
