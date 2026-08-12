// Mobile slide-out sidebar controller.
// Purely presentational: toggles a CSS class on the existing sidebar and
// a generated overlay. Does not read or write any application state.
(function () {
  function init() {
    const sidebar = document.querySelector('.portal-sidebar');
    const toggle = document.querySelector('.topbar-toggle');
    const container = document.querySelector('.portal-container');
    if (!sidebar || !toggle || !container) return;

    let overlay = document.querySelector('.sidebar-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'sidebar-overlay';
      container.appendChild(overlay);
    }

    function closeSidebar() {
      sidebar.classList.remove('open');
      overlay.classList.remove('active');
    }
    function openSidebar() {
      sidebar.classList.add('open');
      overlay.classList.add('active');
    }

    toggle.addEventListener('click', function () {
      if (sidebar.classList.contains('open')) closeSidebar();
      else openSidebar();
    });
    overlay.addEventListener('click', closeSidebar);

    // Close the drawer after picking a destination (mobile only).
    sidebar.querySelectorAll('a.sidebar-link').forEach(function (link) {
      link.addEventListener('click', function () {
        if (window.innerWidth <= 900) closeSidebar();
      });
    });

    window.addEventListener('resize', function () {
      if (window.innerWidth > 900) closeSidebar();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
