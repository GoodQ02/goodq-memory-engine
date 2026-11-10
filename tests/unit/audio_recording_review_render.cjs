const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync('ui/retro_console_v1/static/js/retro.js', 'utf8');
const start = code.indexOf('  function renderRecordingAudio(');
const end = code.indexOf('  // Render Metadata Detail Inspector Panel', start);
function node(tag) { return {tag, children: [], textContent: '', appendChild(c) {this.children.push(c);}, setAttribute(){}}; }
const context = {document: {createElement: node}, appendText(parent, tag, text) {const n=node(tag);n.textContent=text;parent.appendChild(n);}};
vm.createContext(context);vm.runInContext(code.slice(start,end),context);
const evidence = process.argv[2] ? JSON.parse(fs.readFileSync(process.argv[2], 'utf8')) : {
  schema: 'goodq.scene_audio_view.v1', voice_signature_status: 'insufficient_qualified_speech',
  transcription_context:{vocabulary:['Joe','<Kathi>'],basis:'explicit_profile_vocabulary',identity_claim:false},
  utterances: [{id:'u',text:'<unclear>',media_span:{start:18,end:25},speaker:{id:null},
    eligibility:{transcript:{status:'unresolved'},voice_sample:{status:'ineligible'},vocal_delivery:{status:'ineligible'}},
    confidence:{raw:{avg_logprob:-.8}}}],
  reviews:[{utterance_id:'u',url:'/api/videos/v/scenes/s/audio-evidence/'+ 'a'.repeat(64)}],
  sound_events:[{label:'crying',media_span:{start:18,end:19}}],
  overlap:[
    {media_span:{start:19,end:21},status:'observed',detector:'nemotron3'},
    {media_span:{start:16,end:24},status:'unresolved',reason:'aligned_envelope_collision'},
    {media_span:{start:10,end:11},status:'unresolved',reason:'collapsed_local_speaker_change'},
    {media_span:{start:4,end:5},status:'unresolved',reason:'cross_window_speaker_disagreement'},
    {media_span:{start:6,end:7},status:'unresolved',reason:'simultaneous_source_channels'},
    {media_span:{start:1,end:2},status:'unresolved'}],vocal_delivery:[{label:'sad'}]
};
const root=node('div');context.renderRecordingAudio(root,evidence);
const all=[];function walk(n){all.push(n);n.children.forEach(walk);}walk(root);
const texts=all.map(n=>n.textContent).join('\n');
if (evidence.utterances.length) assert.ok(texts.includes('not calibrated'));
assert.ok(texts.includes('unassigned'));
const players=all.filter(n=>n.tag==='audio');
assert.equal(players.length,evidence.reviews.length);
assert.ok(players.every(n=>n.controls===true && n.preload==='none' && n.autoplay===undefined));
if (!process.argv[2]) {
  assert.ok(texts.includes('Possible words, unclear: <unclear>'));
  assert.ok(texts.includes('Voice signature: withheld'));
  assert.ok(texts.includes('not whole-scene sentiment'));
  assert.ok(texts.includes('Name/spelling hints supplied: Joe, <Kathi>'));
  assert.ok(texts.includes('they do not identify a speaker'));
  assert.ok(texts.includes('overlapping voices candidate'));
  assert.ok(texts.includes('16.00–24.00s: speech timing conflict; simultaneous voices unverified'));
  assert.ok(texts.includes('10.00–11.00s: speaker assignment unresolved'));
  assert.ok(texts.includes('4.00–5.00s: speaker assignment unresolved'));
  assert.ok(texts.includes('6.00–7.00s: activity on multiple audio channels'));
  assert.ok(texts.includes('1.00–2.00s: overlap assessment unresolved'));
  assert.equal((texts.match(/overlapping voices candidate/g)||[]).length,1);
}
console.log(JSON.stringify({status:'passed',utterances:evidence.utterances.length,players:players.length,
  escaped_text:true,automatic_playback:false}));
