(() => {
  const country = document.getElementById('id_country');
  const state = document.getElementById('id_state');
  const postal = document.getElementById('id_postal_code');
  if (!country || !state || !postal) return;
  function updateLabels() {
    const us = country.value === 'US';
    state.required = us;
    postal.required = us;
    document.querySelector('label[for="id_state"]').textContent = us ? 'State' : 'State, province or region (optional)';
    document.querySelector('label[for="id_postal_code"]').textContent = us ? 'ZIP code' : 'Postal code (optional)';
    document.getElementById('state-help').textContent = us ? 'Enter the state name or its two-letter abbreviation.' : 'Optional where your billing address does not use a region.';
    document.getElementById('postal_code-help').textContent = us ? '' : 'Optional where your billing address does not use a postal code.';
  }
  country.addEventListener('change', updateLabels);
  updateLabels();
})();
