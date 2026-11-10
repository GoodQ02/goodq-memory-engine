const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
class Element {
  constructor() { this.children=[]; this.style={}; this.textContent=''; this.listeners={}; this.classList={add(){},remove(){}}; }
  set innerHTML(v) { this.children=[]; this.html=v; }
  appendChild(v) { this.children.push(v); }
  setAttribute(k,v) { this[k]=v; }
  addEventListener(k,v) { this.listeners[k]=v; }
}
const elements = new Map();
const context = {document:{addEventListener(){},querySelectorAll(){return [];},createElement:()=>new Element(),
  getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('ui/summary_console/static/js/summary.js','utf8'),context);
const cue={entity_id:'transcript_cue:birthday_song',name:'<birthday_song>',occurrence_count:2,scene_count:1,
  source:'retained_transcript_pattern',confidence:null};
context.renderLeaderboards({people:[],places:[],occasions:[cue],sentiment_distribution:{},top_emotions:[]});
const row=elements.get('occasions-list').children[0];
assert.deepEqual(row.children.map(c=>c.textContent),[
  '<birthday_song>','Transcript cue · not a confirmed event','2 cues / 1 scenes']);
assert.equal(row.children[0].html,undefined); // Source content is never interpolated into HTML.
const scene={video_id:'source',scene_id:'scene-id',start:10,end:20,transcript:'retained transcript',
  music_events:[{label:'birthday_song',start:0,end:2,confidence:.7,context:'<Happy birthday>'},'singing']};
context.renderPlaylistGrid([scene]);
let card=elements.get('playlist-grid').children[0];
assert.match(card.children[1].textContent,/0.00–2.00s scene-relative · heuristic score 0.7 · <Happy birthday>/);
assert.match(card.children[2].textContent,/singing · offset unavailable/);
assert.equal(card.children[1].html,undefined);
context.renderPlaylistGrid([{...scene,music_events:undefined}]);
assert.equal(elements.get('playlist-grid').children[0].children.length,1);
context.renderPlaylistGrid([]);
assert.equal(elements.get('playlist-grid').children.length,0);
const profile={...cue,node_type:'transcript_cue',scenes:[scene],top_emotions:[],co_occurrences:[]};
context.fetch=async()=>({ok:true,json:async()=>profile});
(async()=>{
  await context.loadEntityProfile(cue.entity_id);
  assert.match(elements.get('profile-type').textContent,/not a confirmed event/);
  assert.equal(elements.get('profile-occurrences').textContent,1);
  profile.node_type='person';profile.scenes=[];
  await context.loadEntityProfile('person:example');
  assert.equal(elements.get('profile-type').textContent,'person');
  assert.equal(elements.get('playlist-grid').children.length,0);
  console.log('PASS: cue provenance, separate counts, original context/offsets, safe text and selection clearing.');
})().catch(e=>{console.error(e);process.exitCode=1;});
