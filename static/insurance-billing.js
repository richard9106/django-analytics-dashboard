(() => {
  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-insurance-suggest]');
    if (!button) return;
    const form = button.closest('form');
    const feedback = form.querySelector('[data-insurance-feedback]');
    const field = (name) => form.elements.namedItem(name);
    const client = field('client')?.value;
    if (!client) { feedback.textContent = 'Choose a client first.'; return; }
    const params = new URLSearchParams({client, state: field('insurance_state')?.value || '', service_code: field('service_code')?.value || ''});
    const originals = ['amount', 'client_responsibility', 'billing_type'].map((name) => field(name)?.value);
    button.disabled = true;
    try {
      const response = await fetch(`${button.dataset.insuranceSuggest}?${params}`, {headers: {'Accept': 'application/json'}});
      if (!response.ok || response.redirected) throw new Error('Insurance suggestion unavailable. Check your access and client selection.');
      const data = await response.json();
      if (field('client')?.value !== client || (field('insurance_state')?.value || '') !== params.get('state') || (field('service_code')?.value || '') !== params.get('service_code') || ['amount', 'client_responsibility', 'billing_type'].some((name, index) => field(name)?.value !== originals[index])) {
        throw new Error('Selection changed while loading. Request the suggestion again.');
      }
      if (data.billing_type !== 'insurance' || !data.payer_enabled) {
        feedback.textContent = 'Link an enabled payer and choose Insurance in the client profile first. Existing amounts were kept.';
        return;
      }
      field('billing_type').value = 'insurance';
      field('insurance_state').value = data.state;
      if (data.amount !== null) field('amount').value = data.amount;
      // Never retain a previous client's share when the new client's share is unknown.
      field('client_responsibility').value = data.client_share === null ? '' : data.client_share;
      feedback.textContent = `${data.payer_name}: ${data.message}${data.amount !== null ? ` Suggested total: $${data.amount}.` : ' Existing amount was kept.'} Confirm the client share before saving.`;
    } catch (error) {
      feedback.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
})();
