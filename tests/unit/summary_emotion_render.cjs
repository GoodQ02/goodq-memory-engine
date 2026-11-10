const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
class Element {
  constructor() { this.children=[]; this.style={}; this.textContent=''; }
  set innerHTML(value) { this.children=[]; this.textContent=value; }
  appendChild(child) { this.children.push(child); }
}
const elements=new Map();
const context={document:{addEventListener(){},createElement:()=>new Element(),
  getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('ui/summary_console/static/js/summary.js','utf8'),context);
const rows=[{emotion:'disgust',channel:'audio',basis:'stored_label',count_unit:'scenes',count:1},
  {emotion:'disgust',channel:'text',basis:'top_ranked',count_unit:'scenes',count:7}];
context.renderLeaderboards({people:[],places:[],occasions:[],sentiment_distribution:{},top_emotions:rows});
context.renderEmotionEvidence(rows,'profile-emotions-list');
for(const id of ['emotions-list','profile-emotions-list']) {
 assert.deepEqual(elements.get(id).children.map(e=>e.children.map(c=>c.textContent)),[
   ['Audio · stored label: disgust','1 scene'],['Text · top-ranked: disgust','7 scenes']]);
}
context.renderEmotionEvidence([{emotion:'<legacy>',count:8}],'emotions-list');
assert.deepEqual(elements.get('emotions-list').children[0].children.map(c=>c.textContent),
  ['Source unspecified: <legacy>','8 · unit unspecified']);
context.renderEmotionEvidence([],'profile-emotions-list');
assert.equal(elements.get('profile-emotions-list').children.length,0);
assert.match(elements.get('profile-emotions-list').textContent,/No emotion evidence available/);
console.log('PASS: production dashboard/profile renderer separates channels and units; empty and legacy evidence stay truthful.');
