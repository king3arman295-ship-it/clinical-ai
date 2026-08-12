// Home page functionality
document.addEventListener('DOMContentLoaded', async function() {
  // Mobile menu toggle
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');
  const navLinks = document.getElementById('navLinks');
  
  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', () => {
      navLinks.classList.toggle('active');
    });
  }

  // Floating nav: transparent over the hero image, solid + blurred once scrolled
  const mainNavbar = document.getElementById('mainNavbar');
  if (mainNavbar) {
    const updateNavbarBg = () => {
      mainNavbar.classList.toggle('scrolled', window.scrollY > 40);
    };
    updateNavbarBg();
    window.addEventListener('scroll', updateNavbarBg, { passive: true });
  }
  
  // Load statistics
  loadDashboardStats();
  
  // Load doctors
  loadDoctors();
  
  // Smooth scrolling for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        navLinks.classList.remove('active');
      }
    });
  });
});

// Load dashboard statistics
async function loadDashboardStats() {
  try {
    const doctors = await API.get('/doctors/');
    const doctorCount = document.getElementById('doctorCount');
    
    if (doctorCount && doctors) {
      animateNumber(doctorCount, 0, doctors.length, 1500);
    }
    
    // Load patient count from the public stats endpoint (real, no auth needed)
    try {
      const stats = await API.get('/dashboard/public-stats');
      const patientCount = document.getElementById('patientCount');
      if (patientCount && stats && stats.patients) {
        animateNumber(patientCount, 0, stats.patients, 1500);
      }
    } catch (e) {
      console.error('Failed to load public stats:', e);
    }
  } catch (error) {
    console.error('Failed to load stats:', error);
  }
}

// Animate number counter
function animateNumber(element, start, end, duration) {
  const range = end - start;
  const increment = range / (duration / 16);
  let current = start;
  
  const timer = setInterval(() => {
    current += increment;
    if (current >= end) {
      element.textContent = Math.floor(end);
      clearInterval(timer);
    } else {
      element.textContent = Math.floor(current);
    }
  }, 16);
}

// Load and display doctors
async function loadDoctors() {
  const doctorsGrid = document.getElementById('doctorsGrid');
  if (!doctorsGrid) return;
  
  try {
    const doctors = await API.get('/doctors/');
    
    if (!doctors || doctors.length === 0) {
      doctorsGrid.innerHTML = '<p style="text-align: center; color: var(--text-light);">No doctors available at the moment.</p>';
      return;
    }
    
    // Show 6 doctors: newest profiles first (the curated seeded doctors)
    const displayDoctors = [...doctors].sort((a, b) => (b.id || 0) - (a.id || 0)).slice(0, 6);
    
    doctorsGrid.innerHTML = displayDoctors.map(doctor => `
      <div class="doctor-card">
        <div class="doctor-header">
          <div class="doctor-avatar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M6 21v-2a6 6 0 0 1 12 0v2"/></svg></div>
          <div class="doctor-name">${Utils.escapeHtml(doctor.full_name)}</div>
          <div class="doctor-specialty">${Utils.escapeHtml(doctor.specialization)}</div>
        </div>
        <div class="doctor-body">
          <div class="doctor-info">
            <div class="info-item">
              <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M21.4 10.9a1 1 0 0 0 0-1.8L12.8 5.1a2 2 0 0 0-1.6 0L2.6 9.1a1 1 0 0 0 0 1.8l8.6 3.9a2 2 0 0 0 1.6 0z"/><path d="M22 10v6"/><path d="M6 12.5V17c0 1.7 2.7 3 6 3s6-1.3 6-3v-4.5"/></svg></span>
              <span>${Utils.escapeHtml(doctor.qualification || 'MBBS')}</span>
            </div>
            <div class="info-item">
              <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/></svg></span>
              <span>${doctor.experience_years || 0} years experience</span>
            </div>
            <div class="info-item">
              <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 12h.01M18 12h.01"/></svg></span>
              <span>Rs. ${doctor.consultation_fee || 'N/A'}</span>
            </div>
            ${doctor.phone ? `
              <div class="info-item">
                <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/></svg></span>
                <span>${Utils.escapeHtml(doctor.phone)}</span>
              </div>
            ` : ''}
          </div>
          <div style="margin-top: 12px;">
            <span class="doctor-badge ${doctor.available ? 'badge-available' : 'badge-unavailable'}">
              ${doctor.available ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Available' : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg> Unavailable'}
            </span>
          </div>
        </div>
      </div>
    `).join('');
  } catch (error) {
    console.error('Failed to load doctors:', error);
    doctorsGrid.innerHTML = '<p style="text-align: center; color: var(--text-light);">Failed to load doctors. Please try again later.</p>';
  }
}
