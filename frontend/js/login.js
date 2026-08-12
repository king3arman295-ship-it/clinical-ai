// Login and Registration functionality
function togglePasswordVisibility(inputId, button) {
  const input = document.getElementById(inputId);
  const isHidden = input.type === 'password';
  input.type = isHidden ? 'text' : 'password';
  button.querySelector('.eye-open').style.display = isHidden ? 'none' : '';
  button.querySelector('.eye-closed').style.display = isHidden ? '' : 'none';
  button.setAttribute('aria-label', isHidden ? 'Hide password' : 'Show password');
  input.focus();
}

document.addEventListener('DOMContentLoaded', function() {
  const params = new URLSearchParams(window.location.search);

  // Already logged in and pointed here by a portal link → go to that portal.
  // A plain visit (e.g. the "Book Now" button) must always show the login form.
  if (Auth.isAuthenticated() && params.get('redirect') && !params.has('force')) {
    redirectToPortal();
    return;
  }

  // Explicit logout / force flag only — do NOT clear session on every visit
  // (that broke admin returning from pharmacy and normal navigation).
  if (Auth.isAuthenticated() && params.has('force')) {
    Auth.clear();
  }

  // Setup form handlers
  document.getElementById('login-form').addEventListener('submit', handleLogin);
  document.getElementById('register-form').addEventListener('submit', handleRegister);

  // Enter key submits the visible form (username/password or any signup field)
  function bindEnterToSubmit(form) {
    if (!form) return;
    form.querySelectorAll('input').forEach((input) => {
      input.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter') return;
        // Allow default only for textarea; for inputs submit the form
        e.preventDefault();
        if (typeof form.requestSubmit === 'function') {
          form.requestSubmit();
        } else {
          form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
        }
      });
    });
  }
  bindEnterToSubmit(document.getElementById('login-form'));
  bindEnterToSubmit(document.getElementById('register-form'));

  // "Book a Consultation" links here with ?mode=register → open signup directly
  if (params.get('mode') === 'register') {
    showRegisterForm(); // header updated inside
  }
});

function updateAuthHeader(mode) {
  const title = document.getElementById('auth-title');
  const subtitle = document.getElementById('auth-subtitle');
  if (!title || !subtitle) return;
  if (mode === 'register') {
    title.textContent = 'Create Patient Account';
    subtitle.textContent = 'Register to book appointments and access medical services';
    document.title = 'Create Account - Lumina Health';
  } else {
    title.textContent = 'Welcome Back';
    subtitle.textContent = 'Sign in to access your account';
    document.title = 'Sign In - Lumina Health';
  }
}

function showRegisterForm() {
  document.getElementById('login-form').style.display = 'none';
  document.getElementById('register-form').style.display = 'block';
  const regErr = document.getElementById('register-error');
  if (regErr) regErr.style.display = 'none';
  updateAuthHeader('register');
}

function showLoginForm() {
  document.getElementById('register-form').style.display = 'none';
  document.getElementById('login-form').style.display = 'block';
  const loginErr = document.getElementById('login-error');
  if (loginErr) loginErr.style.display = 'none';
  updateAuthHeader('login');
}


async function handleLogin(e) {
  e.preventDefault();
  
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  const errorDiv = document.getElementById('login-error');
  const submitBtn = e.target.querySelector('button[type="submit"]');

  if (!username || !password) {
    showError(errorDiv, 'Please enter username and password');
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Signing in...';
  errorDiv.style.display = 'none';

  try {
    // Send login request (OAuth2 form format)
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(API.config + '/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: formData
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      const detail = data?.detail;
      let message;
      if (Array.isArray(detail)) {
        // FastAPI validation errors come back as a list of {msg, loc, ...}
        message = detail.map(d => d.msg || d).join(', ');
      } else {
        message = detail || data?.message || `Login failed (${response.status}). Please check your credentials.`;
      }
      throw new Error(message);
    }

    // Save authentication
    const user = {
      id: data.id || null,
      username: data.username || username,
      role: (data.role || 'user').toLowerCase(),
      doctor_id: data.doctor_id || null,
      patient_id: data.patient_id || null
    };

    Auth.save(data.access_token, user);
    
    // Register FCM token for push notifications (await so redirect doesn't cancel it).
    // This is the one place allowed to pop the native permission dialog —
    // it's tied directly to the person clicking "Sign In", not fired
    // automatically on page load (see firebase.js: auto-prompting on every
    // load is what got this site's notifications auto-blocked by Chrome
    // after being ignored a few times). Also passes notify_login=true so
    // the backend fires the one-time "welcome back" push here, and only
    // here — portal pages re-send the token silently on every load.
    if (window.enableNotifications) {
      await window.enableNotifications();
    } else if (window.sendFCMTokenToBackend) {
      await window.sendFCMTokenToBackend(true);
    }

    // Clear any redirect flags before redirecting
    sessionStorage.removeItem('auth_redirecting');
    
    Utils.showToast(`Welcome back, ${user.username}!`, 'success');

    // Redirect to appropriate portal immediately
    redirectToPortal();

  } catch (error) {
    console.error('Login error:', error);
    showError(errorDiv, error.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Sign In';
  }
}

async function handleRegister(e) {
  e.preventDefault();

  const name = document.getElementById('reg-name').value.trim();
  const phone = document.getElementById('reg-phone').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const username = document.getElementById('reg-username').value.trim();
  const password = document.getElementById('reg-password').value;
  const errorDiv = document.getElementById('register-error');
  const submitBtn = e.target.querySelector('button[type="submit"]');

  if (!name || !phone || !email || !username || !password) {
    showError(errorDiv, 'Please fill in all fields');
    return;
  }

  // Basic validation
  if (password.length < 6) {
    showError(errorDiv, 'Password must be at least 6 characters long');
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Creating account...';
  errorDiv.style.display = 'none';

  try {
    const data = {
      name,
      phone,
      email,
      username,
      password
    };

    const response = await fetch(API.config + '/auth/patient-register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });

    const result = await response.json().catch(() => null);

    if (!response.ok) {
      const detail = result?.detail;
      const message = Array.isArray(detail)
        ? detail.map(d => d.msg || d).join(', ')
        : (detail || result?.message || `Registration failed (${response.status}). Please try again.`);
      throw new Error(message);
    }

    Utils.showToast('Account created successfully! Please sign in.', 'success');

    // Auto-fill login form
    document.getElementById('username').value = username;
    document.getElementById('password').value = password;
    
    // Switch to login form
    showLoginForm();

  } catch (error) {
    console.error('Registration error:', error);
    showError(errorDiv, error.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Create Account';
  }
}

function redirectToPortal() {
  const role = Auth.getRole();
  const urlParams = new URLSearchParams(window.location.search);
  const redirect = urlParams.get('redirect');

  // location.replace keeps login.html out of history so Chrome back
  // does not bounce between login ↔ portal with a live token.
  const go = (url) => { window.location.replace(url); };

  if (redirect) {
    go(redirect);
  } else if (role === 'patient') {
    go('patient-portal.html');
  } else if (role === 'doctor') {
    go('doctor-portal.html');
  } else if (role === 'admin' || role === 'receptionist') {
    go('admin-portal.html');
  } else if (role === 'admission_head') {
    go('admission-portal.html');
  } else if (role === 'pharmacist') {
    go('pharmacy-portal.html');
  } else if (role === 'lab_technician') {
    go('laboratory-portal.html');
  } else if (role === 'nurse') {
    go('nurse-portal.html');
  } else if (role === 'billing') {
    go('billing-portal.html');
  } else {
    go('index.html');
  }
}

function showError(element, message) {
  element.innerHTML = '';
  const iconSpan = document.createElement('span');
  iconSpan.innerHTML = Icons.warning;
  iconSpan.style.marginRight = '6px';
  element.appendChild(iconSpan);
  element.appendChild(document.createTextNode(message));
  element.style.display = 'block';
}


// Only when the user lands on login via browser BACK/FORWARD (or BFCache),
// drop the token so clicking Forward cannot reopen a portal without login.
// Normal links to login while working in a portal are unaffected if they
// use redirect=…; logout uses force=1.
window.addEventListener('pageshow', function (event) {
  const params = new URLSearchParams(window.location.search);
  if (params.get('redirect') && Auth.isAuthenticated() && !params.has('force')) {
    return;
  }
  let viaHistory = !!event.persisted;
  try {
    const nav = performance.getEntriesByType && performance.getEntriesByType('navigation')[0];
    if (nav && nav.type === 'back_forward') viaHistory = true;
  } catch (e) {}
  if (viaHistory && Auth.isAuthenticated()) {
    Auth.clear();
  }
});
