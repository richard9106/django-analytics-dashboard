const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Option {
  constructor(value = '', text = '') { this.value = value; this.textContent = text; }
  cloneNode() { return new Option(this.value, this.textContent); }
}
class Select {
  constructor() { this.options = []; this.value = ''; this.handlers = {}; }
  replaceChildren(...options) { this.options = options; this.value = options[0]?.value || ''; }
  append(option) { this.options.push(option); }
  addEventListener(name, handler) { this.handlers[name] = handler; }
}
const client = new Select();
const sessions = new Select();
const status = {};
const retry = new Select();
const requests = [];
const form = {dataset: {sessionsUrl: '/clinical-notes/appointment-options/0/'}, handlers: {},
  querySelector(selector) { return {'[name="client"]':client, 'select[name="appointment"]':sessions, '[data-session-picker-status]':status, '[data-session-picker-retry]':retry}[selector]; },
  addEventListener(name, handler) { this.handlers[name] = handler; }};
vm.runInNewContext(fs.readFileSync('static/client-session-picker.js', 'utf8'), {
  document: {querySelectorAll: () => [form], createElement: () => new Option()}, AbortController,
  fetch(url, options) { return new Promise(resolve => requests.push({url, options, resolve})); }
});
function resolve(request, rows, ok = true) {
  request.resolve({ok, headers: {get: () => 'application/json'}, json: async () => ({appointments:rows})});
}
(async () => {
  assert.equal(requests.length, 0);
  assert.equal(sessions.disabled, true);
  client.value = '1';
  const first = client.handlers.change();
  assert.equal(requests[0].url, '/clinical-notes/appointment-options/1/');
  resolve(requests[0], [{id:10, label:'Client one session'}]); await first;
  assert.equal(sessions.options[1].value, '10'); assert.equal(sessions.disabled, false);
  sessions.value = '10';
  client.value = '2'; const second = client.handlers.change();
  assert.equal(sessions.value, '');
  let prevented = false;
  form.handlers.submit({preventDefault: () => { prevented = true; }});
  assert.equal(prevented, true);
  client.value = '3'; const third = client.handlers.change();
  assert.equal(requests[1].options.signal.aborted, true);
  resolve(requests[2], [{id:30,label:'Client three session'}]); await third;
  resolve(requests[1], [{id:20,label:'Stale client two session'}]); await second;
  assert.deepEqual(sessions.options.map(option => option.value), ['', '30']);
  sessions.value = '30'; const failed = retry.handlers.click();
  resolve(requests[3], [], false); await failed;
  assert.deepEqual(sessions.options.map(option => option.value), ['', '30']);
  assert.equal(sessions.value, '30');
  assert.equal(retry.hidden, false);
  client.value = ''; await client.handlers.change();
  assert.equal(sessions.disabled, true); assert.equal(sessions.value, '');
  console.log('Client session picker checks passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
