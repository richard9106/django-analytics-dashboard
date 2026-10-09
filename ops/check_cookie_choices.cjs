const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('static/cookie-choices.js', 'utf8');
function page(initial={}, blocked=false) {
  const data = new Map(Object.entries(initial));
  const buttons = ['preferences','essential'].map(value=>({dataset:{cookieChoice:value},addEventListener(_,fn){this.click=fn},focus(){}}));
  const settings={addEventListener(_,fn){this.click=fn},focus(){this.focused=true}};
  const notice={hidden:true,querySelector(){return buttons[0]},getBoundingClientRect(){return {height:260}}};
  const window={dispatchEvent(){},addEventListener(){}};
  const document={documentElement:{style:{setProperty(){}}},querySelector(){return notice},querySelectorAll(selector){return selector==='[data-cookie-choice]'?buttons:[settings]},addEventListener(){},body:{classList:{add(){},remove(){}}}};
  const localStorage={getItem(key){if(blocked)throw Error();return data.get(key)||null},setItem(key,value){if(blocked)throw Error();data.set(key,value)},removeItem(key){if(blocked)throw Error();data.delete(key)}};
  vm.runInNewContext(source,{window,document,localStorage,Date,CustomEvent:function(){}});
  return {data,buttons,settings,notice,api:window.NuviaMyCookieChoices};
}
const key='nuviamy.cookieChoices', tour='nuviamy.dashboardTourComplete';
let p=page({[tour]:'1'});
assert.equal(p.notice.hidden,false);
assert.equal(p.data.has(tour),false);
p.api.completeTour(); assert.equal(p.data.has(tour),false);
p.buttons[0].click(); p.api.completeTour(); assert.equal(p.data.get(tour),'1');
assert.equal(p.notice.hidden,true);
p=page(Object.fromEntries(p.data)); assert.equal(p.notice.hidden,true); assert.equal(p.api.tourCompleted(),true);
p.settings.click(); assert.equal(p.notice.hidden,false);
p.buttons[1].click(); assert.equal(p.data.has(tour),false); assert.equal(p.settings.focused,true);
p.api.completeTour(); assert.equal(p.data.has(tour),false);
p=page(Object.fromEntries(p.data)); assert.equal(p.notice.hidden,true); assert.equal(p.api.preferencesAllowed(),false);
for(const value of ['bad',JSON.stringify({version:0,preferences:true,savedAt:Date.now()}),JSON.stringify({version:1,preferences:true,savedAt:Date.now()-181*86400000})]){
 p=page({[key]:value,[tour]:'1'}); assert.equal(p.notice.hidden,false); assert.equal(p.api.preferencesAllowed(),false); assert.equal(p.data.has(tour),false);
}
p=page({},true); p.buttons[0].click(); p.api.completeTour(); assert.equal(p.notice.hidden,true);
console.log('Cookie choices: optional storage requires consent, rejection removes it, choices persist, expiry and blocked storage work.');
