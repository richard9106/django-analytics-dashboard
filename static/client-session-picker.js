(() => {
  document.querySelectorAll('[data-client-session-form]').forEach(form => {
    const client = form.querySelector('[name="client"]');
    const sessions = form.querySelector('select[name="appointment"]');
    const status = form.querySelector('[data-session-picker-status]');
    const retry = form.querySelector('[data-session-picker-retry]');
    if (!client || !sessions || !status || !retry) return;
    let controller;
    let loading = false;
    function placeholder(text) {
      const option = document.createElement('option');
      option.value = ''; option.textContent = text;
      sessions.replaceChildren(option);
    }
    async function load(changed = false) {
      controller?.abort();
      const current = new AbortController();
      controller = current;
      const selected = changed ? '' : sessions.value;
      const previousOptions = [...sessions.options].map(option => option.cloneNode(true));
      retry.hidden = true;
      sessions.disabled = true;
      if (!client.value) {
        loading = false; placeholder('Select a client first');
        status.textContent = 'Choose a client to see their sessions.';
        return;
      }
      loading = true; placeholder('Loading sessions…');
      status.textContent = 'Loading this client’s sessions…';
      try {
        const response = await fetch(form.dataset.sessionsUrl.replace('/0/', `/${client.value}/`), {signal: current.signal, headers: {Accept: 'application/json'}});
        if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error();
        const data = await response.json();
        if (current.signal.aborted) return;
        placeholder('No appointment');
        data.appointments.forEach(session => {
          const option = document.createElement('option');
          option.value = String(session.id); option.textContent = session.label;
          sessions.append(option);
        });
        if ([...sessions.options].some(option => option.value === selected)) sessions.value = selected;
        sessions.disabled = false;
        status.textContent = data.appointments.length ? 'Only this client’s sessions are shown. Linking a session is optional.' : 'This client has no available sessions. You can save a note without an appointment.';
      } catch {
        if (current.signal.aborted) return;
        if (!changed) { sessions.replaceChildren(...previousOptions); sessions.value = selected; }
        else placeholder('No appointment');
        sessions.disabled = false;
        status.textContent = 'Could not load sessions. Retry before choosing an appointment.';
        retry.hidden = false;
      } finally { if (!current.signal.aborted) loading = false; }
    }
    client.addEventListener('change', () => load(true));
    retry.addEventListener('click', () => load());
    form.addEventListener('submit', event => {
      if (loading) { event.preventDefault(); status.textContent = 'Please wait while this client’s sessions load.'; }
    });
    load();
  });
})();
