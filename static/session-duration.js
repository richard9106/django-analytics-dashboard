(() => {
  document.querySelectorAll('form').forEach(form => {
    const kind = form.querySelector('[name="session_kind"]');
    const start = form.querySelector('[name="starts_at"]');
    const end = form.querySelector('[name="ends_at"]');
    if (!kind || !start || !end) return;
    const duration = () => kind.value === 'initial_consultation' ? 15 : 50;
    const currentDuration = () => (new Date(end.value)-new Date(start.value))/60000;
    let manual = !!start.value && !!end.value && currentDuration() !== duration();
    let customDuration = manual ? currentDuration() : null;
    const propose = () => {
      if (!start.value || (manual && !(customDuration > 0))) return;
      const value = new Date(start.value);
      if (Number.isNaN(value.getTime())) return;
      value.setMinutes(value.getMinutes()+(manual ? customDuration : duration()));
      end.value = `${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,'0')}-${String(value.getDate()).padStart(2,'0')}T${String(value.getHours()).padStart(2,'0')}:${String(value.getMinutes()).padStart(2,'0')}`;
    };
    kind.addEventListener('change', propose);
    start.addEventListener('change', propose);
    const keepDuration = () => { manual = true; customDuration = currentDuration(); };
    end.addEventListener('input', keepDuration);
    end.addEventListener('change', keepDuration);
    const dialog = form.closest('dialog');
    if (dialog?.id === 'appointment-create-modal') {
      document.addEventListener('click', event => {
        if (event.target.closest('[data-modal-target="appointment-create-modal"]') || (event.target.closest('.gcal-day-column[data-drop-date]') && !event.target.closest('a, button, input, select, textarea'))) { manual = false; queueMicrotask(propose); }
      });
    }
  });
})();
