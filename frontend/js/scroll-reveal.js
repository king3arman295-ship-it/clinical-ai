/* ============================================================
   LUMINA HEALTH — Scroll Reveal
   Adds the "elements rise + fade into place as you scroll" effect
   used across the public site. Pure vanilla JS, no dependencies,
   no changes to any other file's logic — it only ever adds an
   "is-visible" class to elements marked data-reveal in the HTML.
   Safe to include on every page; does nothing if there are no
   data-reveal elements on the page.
   ============================================================ */
(function () {
  function init() {
    var els = document.querySelectorAll('[data-reveal]');
    if (!els.length) return;

    var reduceMotion = window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reduceMotion || !('IntersectionObserver' in window)) {
      els.forEach(function (el) { el.classList.add('is-visible'); });
      return;
    }

    // Auto-stagger direct children inside any data-reveal-group container
    document.querySelectorAll('[data-reveal-group]').forEach(function (group) {
      var i = 0;
      Array.prototype.forEach.call(group.children, function (child) {
        if (child.hasAttribute('data-reveal')) {
          child.style.transitionDelay = Math.min(i * 90, 450) + 'ms';
          i++;
        }
      });
    });

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });

    els.forEach(function (el) { io.observe(el); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
