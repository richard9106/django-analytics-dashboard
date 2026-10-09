(() => {
  const version = 1;
  const key = 'nuviamy.cookieChoices';
  const tourKey = 'nuviamy.dashboardTourComplete';
  const maxAge = 180 * 24 * 60 * 60 * 1000;
  const notice = document.querySelector('[data-cookie-notice]');
  if (!notice) return;
  let choice = null;
  let returnFocus = null;
  try {
    const stored = JSON.parse(localStorage.getItem(key));
    if (stored && stored.version === version && typeof stored.preferences === 'boolean' &&
        Number.isFinite(stored.savedAt) && Date.now() - stored.savedAt >= 0 &&
        Date.now() - stored.savedAt < maxAge) choice = stored;
  } catch (_) { /* Storage can be disabled; the page remains usable. */ }

  function clearTour() {
    try { localStorage.removeItem(tourKey); } catch (_) {}
  }
  if (!choice || !choice.preferences) clearTour();

  function measure() {
    if (!notice.hidden) document.documentElement.style.setProperty("--cookie-notice-space", `${notice.getBoundingClientRect().height + 32}px`);
  }
  window.addEventListener("resize", measure);
  function show() {
    notice.hidden = false;
    document.body.classList.add('cookie-notice-open');
    measure();
  }
  function hide() {
    notice.hidden = true;
    document.body.classList.remove('cookie-notice-open');
    if (returnFocus) returnFocus.focus();
    returnFocus = null;
  }
  function choose(preferences) {
    choice = {version, preferences, savedAt: Date.now()};
    try { localStorage.setItem(key, JSON.stringify(choice)); } catch (_) {}
    if (!preferences) clearTour();
    hide();
    window.dispatchEvent(new CustomEvent('nuviamy:cookie-choice', {detail: {preferences}}));
  }
  window.NuviaMyCookieChoices = {
    preferencesAllowed: () => Boolean(choice && choice.preferences),
    tourCompleted: () => {
      if (!choice || !choice.preferences) return false;
      try { return localStorage.getItem(tourKey) === '1'; } catch (_) { return false; }
    },
    completeTour: () => {
      if (choice && choice.preferences) {
        try { localStorage.setItem(tourKey, '1'); } catch (_) {}
      }
    },
  };
  document.querySelectorAll('[data-cookie-choice]').forEach(button => {
    button.addEventListener('click', () => choose(button.dataset.cookieChoice === 'preferences'));
  });
  document.querySelectorAll('[data-cookie-settings]').forEach(button => {
    button.addEventListener('click', () => {
      returnFocus = button;
      show();
      notice.querySelector('[data-cookie-choice]').focus();
    });
  });
  document.addEventListener('keydown', event => {
    // Escape closes an already saved choice without changing it; first visit needs a choice.
    if (event.key === 'Escape' && choice && !notice.hidden) hide();
  });
  if (!choice) show();
})();
