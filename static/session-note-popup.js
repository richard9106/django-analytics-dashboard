(() => {
  const dialog = document.getElementById('session-note-popup');
  if (!dialog || !dialog.showModal) return;
  const content = dialog.querySelector('[data-note-popup-content]');
  let trigger;
  let loading;
  let saving = false;
  dialog.addEventListener('cancel', event => { if (saving) event.preventDefault(); });
  dialog.addEventListener('click', event => { if (saving && event.target.closest('[data-modal-close]')) { event.preventDefault(); event.stopPropagation(); } }, true);
  dialog.addEventListener('close', () => loading?.abort());
  dialog.addEventListener('close', () => trigger?.focus());
  document.addEventListener('click', async event => {
    const link = event.target.closest('[data-note-popup]');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    trigger = link;
    document.querySelectorAll('dialog[open]').forEach(open => open.close());
    loading?.abort();
    const controller = new AbortController();
    loading = controller;
    content.textContent = 'Loading note form…';
    dialog.showModal();
    try {
      const response = await fetch(link.href, {signal: controller.signal, headers: {'X-Requested-With': 'XMLHttpRequest'}});
      if (!response.ok || response.redirected) throw new Error('Unavailable');
      const html = await response.text();
      if (controller.signal.aborted) return;
      content.innerHTML = html;
      content.querySelector('[name="content"]')?.focus();
    } catch {
      if (controller.signal.aborted) return;
      content.textContent = 'The form could not be loaded. ';
      const fallback = document.createElement('a');
      fallback.href = link.href;
      fallback.textContent = 'Open note form';
      content.append(fallback);
    }
  });
  dialog.addEventListener('submit', async event => {
    const form = event.target.closest('[data-note-popup-form]');
    if (!form) return;
    event.preventDefault();
    const button = form.querySelector('[type="submit"]');
    button.disabled = true;
    saving = true;
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form), headers: {'X-Requested-With': 'XMLHttpRequest'}});
      if (response.status === 422) {
        content.innerHTML = await response.text();
        content.querySelector('.form-error')?.scrollIntoView({block: 'nearest'});
        content.querySelector('[aria-invalid="true"], textarea, select, input:not([type="hidden"])')?.focus();
      } else if (response.ok && !response.redirected && response.headers.get('content-type')?.includes('application/json')) {
        const data = await response.json();
        const target = new URL(data.redirect, location.origin);
        if (target.origin !== location.origin) throw new Error('Invalid redirect');
        location.assign(target.href);
      } else throw new Error('Unavailable');
    } catch {
      let error = form.querySelector('[data-submit-error]');
      if (!error) { error = document.createElement('p'); error.dataset.submitError = ''; error.className = 'form-error'; error.setAttribute('role', 'alert'); form.prepend(error); }
      error.textContent = 'Could not confirm the save. Your text is still here; check your connection before retrying.';
      button.disabled = false;
    } finally { saving = false; }
  });
})();
