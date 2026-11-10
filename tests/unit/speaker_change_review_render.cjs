// Exercise the actual review renderer without a live API or corpus.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('ui/stitching_workbench/static/js/stitching.js', 'utf8');
const render = source.slice(source.indexOf('  function renderSpeakerReviews('), source.indexOf('  async function fetchSpeakerReviews('));
function element() {
  return {children: [], textContent: '', appendChild(e) {this.children.push(e);},
    append(...es) {this.children.push(...es);}, replaceChildren() {this.children = []; this.textContent = '';}};
}
const panel = element();
const context = {document: {getElementById: () => panel, createElement: element}};
vm.createContext(context);
vm.runInContext(render, context);
context.renderSpeakerReviews([{scene_id: '<img onerror=bad>', video_id: 'video', review: {
  status: 'ok', rule: 'collapsed_local_return_v1', flags: [{start: 20.431, end: 20.938,
  window_start: 17, window_end: 27, local_slots: [1, 2, 1], final_cluster: 3, left_gap: 0, right_gap: .354}]}}]);
assert.match(panel.children[0].textContent, /20.431–20.938s \(scene-relative\)/);
assert.match(panel.children[0].textContent, /Unreviewed; speaker identity and exact boundaries unconfirmed/);
assert.match(panel.children[0].textContent, /Signatures and admission are unchanged/);
assert.match(panel.children[1].children[1].textContent, /1 → 2 → 1/);
assert.equal(panel.children[0].innerHTML, undefined); // Evidence rendered as text, not HTML.
context.renderSpeakerReviews([]);
assert.match(panel.textContent, /does not establish speaker purity/);
context.renderSpeakerReviews([{scene_id: 'scene', review: {status: 'error', reason: 'unsupported'}}]);
assert.match(panel.children[0].textContent, /unavailable \(unsupported\)/);
console.log('PASS review renderer: flag, provenance, uncertainty, safe text, absent/error evidence');
