const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/insurance-billing.js', 'utf8');
function harness(result, pending = false) {
  const values = {client: '1', insurance_state: 'CA', service_code: '90837', amount: '', client_responsibility: '', billing_type: 'self_pay'};
  const fields = Object.fromEntries(Object.entries(values).map(([name, value]) => [name, {value}]));
  const feedback = {textContent: ''};
  const form = {elements: {namedItem: (name) => fields[name]}, querySelector: () => feedback};
  const button = {dataset: {insuranceSuggest: '/rate-suggestion/'}, closest: () => form, disabled: false};
  let handler, resolve;
  const response = {ok: true, redirected: false, json: async () => result};
  const fetch = pending ? () => new Promise((r) => { resolve = () => r(response); }) : async () => response;
  vm.runInNewContext(source, {document: {addEventListener: (_name, fn) => { handler = fn; }}, fetch, URLSearchParams});
  return {fields, feedback, button, click: () => handler({target: {closest: () => button}}), finish: () => resolve()};
}
(async () => {
  const data = {billing_type: 'insurance', payer_enabled: true, payer_name: 'Test payer', state: 'CA', amount: '120.00', client_share: '20.00', message: 'Review allocation.'};
  let h = harness(data);
  await h.click();
  assert.equal(h.fields.amount.value, '120.00');
  assert.equal(h.fields.client_responsibility.value, '20.00');
  assert.equal(h.fields.billing_type.value, 'insurance');
  assert.equal(h.button.disabled, false);
  h = harness({...data, amount: '0.00', client_share: null});
  h.fields.client_responsibility.value = '45';
  await h.click();
  assert.equal(h.fields.amount.value, '0.00');
  assert.equal(h.fields.client_responsibility.value, '');
  h = harness({...data, payer_enabled: false});
  h.fields.amount.value = '88';
  await h.click();
  assert.equal(h.fields.amount.value, '88');
  assert.equal(h.fields.billing_type.value, 'self_pay');
  for (const changed of ['client', 'amount', 'client_responsibility', 'insurance_state', 'service_code']) {
    h = harness(data, true);
    const request = h.click();
    h.fields[changed].value = 'changed';
    h.finish();
    await request;
    assert.match(h.feedback.textContent, /changed while loading/);
    assert.equal(h.fields[changed].value, 'changed');
    assert.equal(h.fields.billing_type.value, 'self_pay');
  }
  h = harness({...data, amount: null});
  h.fields.amount.value = '90';
  await h.click();
  assert.equal(h.fields.amount.value, '90');
  console.log('Insurance suggestions: zero/unknown amounts, disabled payers and stale-response protection passed.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
