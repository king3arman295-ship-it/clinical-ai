// API Configuration - Auto-detect host
const API_CONFIG = (function() {
  const { protocol, hostname } = window.location;
  
  // If running locally (file://) or localhost, use localhost:8000
  if (!hostname || protocol === 'file:' || hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8000';
  }
  
  // Otherwise, use same host as frontend with port 8000
  return `${protocol}//${hostname}:8000`;
})();

console.log('API Base URL:', API_CONFIG);

// Auth token storage
let authToken = localStorage.getItem('hospital_token') || null;
let currentUser = JSON.parse(localStorage.getItem('hospital_user') || 'null');

// Turns a FastAPI error payload into a human-readable string.
// FastAPI returns `detail` as a plain string for most errors, but as a LIST
// of {loc, msg, type} objects for 422 validation errors — passing that list
// straight into `new Error(...)` silently stringifies each object to
// "[object Object]", which is the "[object Object],[object Object]" bug.
function extractErrorMessage(data, status) {
  const detail = data?.detail;

  if (Array.isArray(detail)) {
    const messages = detail.map(item => {
      if (item && typeof item === 'object') {
        const loc = Array.isArray(item.loc) ? item.loc.filter(part => part !== 'body') : [];
        const field = loc.length ? loc.join('.') : null;
        const msg = item.msg || 'Invalid value';
        return field ? `${field}: ${msg}` : msg;
      }
      return String(item);
    });
    return messages.join('; ') || `Request failed (${status})`;
  }

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (typeof data?.message === 'string' && data.message.trim()) {
    return data.message;
  }

  return `Request failed (${status})`;
}

// API Helper Functions
async function apiRequest(method, endpoint, body = null, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers
  };
  
  if (authToken && !options.noAuth) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  
  const config = {
    method,
    headers
  };
  
  if (body && !options.isFormData) {
    config.body = JSON.stringify(body);
  } else if (body && options.isFormData) {
    delete headers['Content-Type'];
    config.body = body;
  }
  
  try {
    const response = await fetch(API_CONFIG + endpoint, config);
    const contentType = response.headers.get('content-type');
    
    let data = null;
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    }
    
    if (!response.ok) {
      throw new Error(extractErrorMessage(data, response.status));
    }
    
    return data;
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
}

function apiGet(endpoint) {
  return apiRequest('GET', endpoint);
}

function apiPost(endpoint, body, options) {
  return apiRequest('POST', endpoint, body, options);
}

function apiPut(endpoint, body) {
  return apiRequest('PUT', endpoint, body);
}

function apiPatch(endpoint, body) {
  return apiRequest('PATCH', endpoint, body);
}

function apiDelete(endpoint) {
  return apiRequest('DELETE', endpoint);
}

// Auth Functions
function saveAuth(token, user) {
  authToken = token;
  currentUser = user;
  localStorage.setItem('hospital_token', token);
  localStorage.setItem('hospital_user', JSON.stringify(user));
  // Marks a live tab session so browser back→login can invalidate cleanly
  sessionStorage.setItem('auth_session_active', '1');
}

function clearAuth() {
  authToken = null;
  currentUser = null;
  localStorage.removeItem('hospital_token');
  localStorage.removeItem('hospital_user');
  sessionStorage.removeItem('auth_redirecting');
  sessionStorage.removeItem('auth_session_active');
}

function isAuthenticated() {
  return !!(authToken && currentUser);
}

function getUserRole() {
  return currentUser?.role?.toLowerCase() || 'guest';
}

// Utility Functions
function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    // Plain "YYYY-MM-DD" values (appointment_date) must NOT be parsed with
    // `new Date(str)` — JS treats that as UTC midnight, and rendering it in
    // any timezone behind UTC (or near midnight) rolls the displayed date
    // back by one day even though nothing is wrong in the database. Parse
    // the y/m/d parts ourselves and build a local-time Date so the
    // displayed day always matches what was actually stored.
    const dateOnlyMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr);
    const date = dateOnlyMatch
      ? new Date(Number(dateOnlyMatch[1]), Number(dateOnlyMatch[2]) - 1, Number(dateOnlyMatch[3]))
      : new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  } catch (e) {
    return dateStr;
  }
}

// Returns today's date as "YYYY-MM-DD" in the browser's LOCAL timezone.
// `new Date().toISOString().split('T')[0]` looks equivalent but isn't:
// toISOString() always converts to UTC first, so for timezones ahead of
// UTC (e.g. Pakistan, UTC+5) it silently returns *yesterday's* date during
// the first few hours after local midnight. Appointment dates are stored
// and compared as local calendar days, so "today" must be computed the
// same way everywhere.
function todayLocalDateStr() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function formatTime(timeStr) {
  if (!timeStr) return '—';
  return String(timeStr).slice(0, 5);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Renders the AI's light markdown (**bold**, • bullets, line breaks) as HTML.
function formatBotText(text) {
  let html = escapeHtml(text);

  // **bold**
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // Group consecutive bullet lines into a <ul>
  html = html.replace(/(^|\n)((?:•[^\n]*\n?)+)/g, (match, lead, block) => {
    const items = block
      .split('\n')
      .map(l => l.replace(/^•\s*/, '').trim())
      .filter(Boolean)
      .map(i => `<li>${i}</li>`)
      .join('');
    return lead + '<ul>' + items + '</ul>';
  });

  return html.replace(/\n/g, '<br>');
}

function showToast(message, type = 'success') {
  // Simple toast notification
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    top: 24px;
    right: 24px;
    background: ${type === 'success' ? '#6C8560' : type === 'error' ? '#B4614C' : '#1C201A'};
    color: white;
    padding: 16px 24px;
    border-radius: 999px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.25);
    z-index: 9999;
    animation: slideIn 0.3s ease;
    max-width: 400px;
  `;
  
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Add CSS for toast animations
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from { transform: translateX(400px); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
  @keyframes slideOut {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(400px); opacity: 0; }
  }
`;
document.head.appendChild(style);

// Export for use in other scripts
window.API = {
  get: apiGet,
  post: apiPost,
  put: apiPut,
  patch: apiPatch,
  delete: apiDelete,
  config: API_CONFIG
};

window.Auth = {
  save: saveAuth,
  clear: clearAuth,
  isAuthenticated,
  getRole: getUserRole,
  getUser: () => currentUser,
  getToken: () => authToken
};

window.Utils = {
  formatDate,
  formatTime,
  todayLocalDateStr,
  escapeHtml,
  formatBotText,
  showToast
};


// ─────────────────────────────────────────────────────────────
// Admin: "Back to Admin Portal" on department pages only
// ─────────────────────────────────────────────────────────────
function injectAdminBackButton() {
  try {
    if (getUserRole() !== 'admin') return;
    const page = (location.pathname.split('/').pop() || '').toLowerCase();
    if (!page || page === 'admin-portal.html' || page === 'login.html' || page === 'index.html') {
      return;
    }
    if (document.getElementById('admin-back-sidebar-link')) return;

    const link = document.createElement('a');
    link.id = 'admin-back-sidebar-link';
    link.href = 'admin-portal.html';
    // Do NOT use only "sidebar-link" without marking external — setupNavigation
    // calls preventDefault on every .sidebar-link and blocks real navigation.
    link.className = 'sidebar-link admin-back-external';
    link.setAttribute('data-external', 'admin');
    link.innerHTML =
      '<span class="sidebar-link-icon" aria-hidden="true">' +
      '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
      'stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></span>' +
      '<span>Back to Admin Portal</span>';

    link.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopImmediatePropagation();
      window.location.href = 'admin-portal.html';
    }, true); // capture so we run before setupNavigation's bubble handler

    const label = document.createElement('div');
    label.className = 'sidebar-group-label';
    label.id = 'admin-back-sidebar-label';
    label.textContent = 'Admin';
    label.style.marginTop = '12px';

    const sidebar = document.querySelector('.portal-sidebar');
    if (!sidebar) return;

    const footer = sidebar.querySelector('[style*="margin-top: auto"], [style*="margin-top:auto"]');
    if (footer) {
      sidebar.insertBefore(label, footer);
      sidebar.insertBefore(link, footer);
    } else {
      const logoutBtn = sidebar.querySelector('button[onclick*="logout"]');
      if (logoutBtn && logoutBtn.parentNode) {
        logoutBtn.parentNode.insertBefore(label, logoutBtn);
        logoutBtn.parentNode.insertBefore(link, logoutBtn);
      } else {
        sidebar.appendChild(label);
        sidebar.appendChild(link);
      }
    }

    if (!document.getElementById('admin-back-sidebar-style')) {
      const style = document.createElement('style');
      style.id = 'admin-back-sidebar-style';
      style.textContent = [
        '#admin-back-sidebar-link {',
        '  margin-top: 4px;',
        '  border: 1px solid rgba(244,242,233,0.25);',
        '  background: rgba(244,242,233,0.08);',
        '}',
        '#admin-back-sidebar-link:hover {',
        '  background: rgba(244,242,233,0.16);',
        '}',
      ].join('\n');
      document.head.appendChild(style);
    }
  } catch (e) {
    console.warn('injectAdminBackButton', e);
  }
}

function setupSessionGuards() {
  function refreshAuthFromStorage() {
    authToken = localStorage.getItem('hospital_token') || null;
    try {
      currentUser = JSON.parse(localStorage.getItem('hospital_user') || 'null');
    } catch (e) {
      currentUser = null;
    }
  }

  window.addEventListener('pageshow', function () {
    refreshAuthFromStorage();
    // If token was cleared (e.g. user hit back to login), leave this portal.
    if (!authToken || !currentUser) {
      const page = (location.pathname.split('/').pop() || '').toLowerCase();
      if (page && page !== 'login.html' && page !== 'index.html' && !page.endsWith('login.html')) {
        window.location.replace('login.html');
      }
    }
  });
}

window.injectAdminBackButton = injectAdminBackButton;
window.setupSessionGuards = setupSessionGuards;
