const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor() { this.children = []; this.listeners = {}; }
  append(...items) { this.children.push(...items); }
  replaceChildren() { this.children = []; }
  querySelectorAll() {
    const checkedInputs = item => item.checked ? [item] : (item.children || []).flatMap(checkedInputs);
    return this.children.flatMap(checkedInputs);
  }
  addEventListener(name, callback) { this.listeners[name] = callback; }
}
const client = new Element(); client.value = '1';
const choices = new Element();
const checked = new Element(); checked.value = '11'; checked.checked = true; choices.append(checked);
const status = new Element();
const form = { querySelector: () => client };
const picker = { dataset: { optionsUrl: '/clinical-notes/diagnosis-options/0/' }, closest: name => name === 'form' ? form : null,
  querySelector: name => name === '[data-diagnosis-choices]' ? choices : status };
const pending = new Map(); let calls = 0;
const document = { querySelectorAll: () => [picker], createElement: () => new Element(), createTextNode: text => ({ text }) };
vm.runInNewContext(fs.readFileSync('static/diagnosis-picker.js', 'utf8'), { document, fetch: url => {
  calls++; return new Promise(resolve => pending.set(url, resolve));
}});
const flush = () => new Promise(resolve => setImmediate(resolve));
const respond = (id, diagnoses) => pending.get(`/clinical-notes/diagnosis-options/${id}/`)({ ok: true, headers: { get: () => 'application/json' }, json: async () => ({ diagnoses }) });
(async () => {
  respond(1, [{ id: 11, code: 'OLD', label: 'Linked inactive', active: false }, { id: 12, code: 'ACTIVE', label: 'Current', active: true }, { id: 13, code: 'HIDDEN', label: 'Unlinked inactive', active: false }]);
  await flush();
  assert.equal(choices.children.length, 2);
  assert.deepEqual(choices.querySelectorAll().map(input => String(input.value)), ['11']);
  client.value = '2'; client.listeners.change();
  assert.equal(choices.children.length, 0, 'Changing patient clears previous choices immediately');
  client.value = '3'; client.listeners.change();
  respond(3, [{ id: 31, code: 'THREE', label: 'Patient three', active: true }]); await flush();
  respond(2, [{ id: 21, code: 'TWO', label: 'Patient two', active: true }]); await flush();
  assert.equal(choices.children[0].children[0].value, 31, 'Late response cannot restore the previous patient');
  assert.equal(choices.querySelectorAll().length, 0, 'Previous patient selections are not carried forward');
  client.value = '1'; client.listeners.change(); await flush();
  assert.equal(calls, 3, 'Patient results are reused within the page');
  assert.equal(choices.children.length, 1, 'Unlinked inactive diagnoses stay hidden');
  status.listeners.click();
  respond(1, [{ id: 12, code: 'ACTIVE', label: 'Current', active: true }, { id: 14, code: 'NEW', label: 'Added in patient record', active: true }]); await flush();
  assert.equal(calls, 4, 'Reload retrieves diagnoses changed in the patient record');
  assert.equal(choices.children.length, 2);
  console.log('Diagnosis picker: patient isolation, stale response handling, inactive links and cache passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
