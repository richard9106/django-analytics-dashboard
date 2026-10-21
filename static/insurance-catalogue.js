(() => {
  document.querySelectorAll('[data-payer-catalogue]').forEach((catalogue) => {
    const search = catalogue.querySelector('[data-payer-search]');
    if (!search) return;
    const rows = Array.from(catalogue.querySelectorAll('[data-payer-row]'));
    const results = catalogue.querySelector('[data-payer-results]');
    const empty = catalogue.querySelector('[data-payer-empty]');
    const normalize = (value) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
    const entries = rows.map((row) => ({row, name: normalize(row.querySelector('[data-payer-name]').textContent)}));
    search.addEventListener('input', () => {
      const query = normalize(search.value);
      let count = 0;
      entries.forEach(({row, name}) => {
        row.hidden = !name.includes(query);
        if (!row.hidden) count += 1;
      });
      results.textContent = query ? `${count} of ${rows.length} payers match` : `${rows.length} payers available`;
      empty.hidden = count !== 0;
    });
  });
})();
