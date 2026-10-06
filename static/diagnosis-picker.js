(() => {
  const cache = new Map();
  document.querySelectorAll('[data-diagnosis-picker]').forEach((picker) => {
    const form = picker.closest('form');
    const client = form.querySelector('[name="client"]');
    const choices = picker.querySelector('[data-diagnosis-choices]');
    const status = picker.querySelector('[data-diagnosis-status]');
    let generation = 0;
    async function load(changed = false) {
      const current = ++generation;
      const selected = changed ? new Set() : new Set([...choices.querySelectorAll('input:checked')].map(input => input.value));
      if (changed) choices.replaceChildren();
      if (!client.value) { status.textContent = 'Choose a patient first.'; return; }
      status.textContent = 'Loading patient diagnoses…';
      try {
        const url = picker.dataset.optionsUrl.replace('/0/', `/${client.value}/`);
        if (!cache.has(url)) cache.set(url, fetch(url, { headers: { Accept: 'application/json' } }).then(response => {
          if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error();
          return response.json();
        }).catch(error => { cache.delete(url); throw error; }));
        const data = await cache.get(url);
        if (current !== generation) return;
        choices.replaceChildren();
        const rows = data.diagnoses.filter(row => row.active || selected.has(String(row.id)));
        rows.forEach(row => {
          const label = document.createElement('label'); label.className = 'checkbox-option';
          const input = document.createElement('input'); input.type = 'checkbox'; input.name = 'diagnoses'; input.value = row.id; input.checked = selected.has(String(row.id));
          label.append(input, document.createTextNode(` ${row.code} · ${row.label}${row.active ? '' : ' (inactive, already linked)'}`)); choices.append(label);
        });
        status.textContent = rows.length ? 'Select this patient’s diagnoses. Manage diagnoses in their patient record.' : 'No active diagnoses for this patient. You can save a plan without diagnoses or add one in their patient record.';
      } catch (_) {
        if (current === generation) status.textContent = 'Could not load diagnoses. Existing selections are retained; reload the page to try again.';
      }
    }
    client.addEventListener('change', () => load(true));
    picker.querySelector('[data-diagnosis-reload]')?.addEventListener('click', () => {
      cache.delete(picker.dataset.optionsUrl.replace('/0/', `/${client.value}/`));
      load();
    });
    const dialog = picker.closest('dialog');
    if (dialog) document.addEventListener('click', event => {
      if (event.target.closest('[data-modal-target]')?.dataset.modalTarget === dialog.id) load();
    });
    else load();
  });
})();
