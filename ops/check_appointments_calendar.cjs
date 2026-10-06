const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const listeners = [];
const input = value => ({value, listeners:{}, addEventListener(type,fn){this.listeners[type]=fn;}});
const fields = { starts_at: input('2026-10-06T09:00'), ends_at: input('2026-10-06T10:20') };
const dialog = { querySelector: selector => { const match=selector.match(/name="([^"]+)"/); return match ? fields[match[1]] : null; } };
const document = {
  getElementById: id => id === 'appointment-create-modal' ? dialog : null,
  querySelector: () => null,
  querySelectorAll: selector => selector === 'form.appointment-form' ? [dialog] : [],
  addEventListener: (type, callback, capture) => listeners.push({type, callback, capture}),
};
const context = vm.createContext({document, Date, window: {location:{pathname:'/appointments/',search:'?view=agenda'}}, console});
vm.runInContext(fs.readFileSync('static/appointments-calendar.js','utf8'), context);
assert.equal(vm.runInContext('datetimeFor("2026-10-06", "23:30", 80).end', context), '2026-10-07T00:50');
context.column = {getBoundingClientRect:()=>({top:100}), querySelector:()=>({getBoundingClientRect:()=>({height:64})}), dataset:{availabilityConfigured:'1',availabilityRanges:'540-600'}};
assert.equal(vm.runInContext('timeFromPointer({clientY:308},column)', context), '09:00');
assert.equal(vm.runInContext('isAvailable(column,"09:00",50)', context), true);
assert.equal(vm.runInContext('isAvailable(column,"09:00",80)', context), false, 'Rescheduling uses the actual session duration');
const trigger = {dataset:{modalTarget:'appointment-create-modal',appointmentDate:'2026-10-09'}};
const event = {target:{closest: selector => selector === '[data-modal-target]' ? trigger : null},preventDefault(){}};
const preparation = listeners.find(item=>item.type==='click' && item.capture===true);
assert.ok(preparation,'Prepare selected date before the shared modal opener stops event propagation');
dialog.showModal=()=>{};
preparation.callback(event);
assert.equal(fields.starts_at.value,'2026-10-09T09:00');
assert.equal(fields.ends_at.value,'2026-10-09T09:50');
fields.starts_at.value='2026-10-09T09:00'; fields.ends_at.value='2026-10-09T10:20';
fields.starts_at.listeners.focus(); fields.starts_at.value='2026-10-09T11:00'; fields.starts_at.listeners.change();
assert.equal(fields.ends_at.value,'2026-10-09T12:20','Changing start preserves a custom 80-minute duration');
// The same script also runs on the standalone editor, which has no grid config.
assert.ok(listeners.length>0);
console.log('Appointment calendar checks passed: date preparation, measured grid header, duration and midnight rollover.');
const rescheduleForm = {elements:{date:{focus(){}},time:{},next:{}},action:''};
const heading = {textContent:''};
let opened = false;
const rescheduleDialog = {querySelector: selector => selector === '[data-reschedule-form]' ? rescheduleForm : selector === '[data-reschedule-title]' ? heading : null, showModal(){opened=true;}};
const previousLookup = document.getElementById;
document.getElementById = id => id === 'reschedule-modal' ? rescheduleDialog : previousLookup(id);
const sessionDialog = {id:'appointment-modal-7',close(){}};
const rescheduleTrigger = {dataset:{rescheduleUrl:'/appointments/7/reschedule/',rescheduleDate:'2026-10-09',rescheduleTime:'11:00',rescheduleTitle:'Example client'},closest:()=>sessionDialog};
const rescheduleEvent = {target:{closest: selector => selector === 'button[data-reschedule-url]' ? rescheduleTrigger : null}};
listeners.filter(item => item.type==='click' && !item.capture).forEach(item=>item.callback(rescheduleEvent));
assert.equal(opened,true,'Touch/keyboard reschedule button opens its dialog');
assert.equal(rescheduleForm.action,'/appointments/7/reschedule/');
assert.equal(rescheduleForm.elements.date.value,'2026-10-09');
assert.equal(rescheduleForm.elements.next.value,'/appointments/?view=agenda');
console.log('Explicit rescheduling button preserves calendar return context.');
