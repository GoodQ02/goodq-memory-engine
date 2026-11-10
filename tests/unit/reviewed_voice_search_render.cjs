const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('ui/retro_console_v1/static/js/retro.js', 'utf8');
const start = source.indexOf('  function appendIdentitySearchEvidence(');
const end = source.indexOf('  // Render Interstellar Timeline Index Grid', start);
function render(types, strength) {
  const children = [];
  const state = {searchActive: true, searchResults: [{scene_id: 's', identity_only: true,
    identity_evidence: [{display_name: '<Kathy>', strength, evidence_types: types}]}]};
  const context = {state, document: {createElement: () => ({})}};
  vm.createContext(context);
  vm.runInContext(source.slice(start, end), context);
  context.appendIdentitySearchEvidence({appendChild: c => children.push(c)}, 's');
  return children.map(c => c.textContent);
}
assert.deepEqual(render(['voice'], 'voice'), ['<Kathy>: reviewed voice', 'Person match only; event relevance unverified']);
assert.equal(render(['appearance', 'voice', 'mention'], 'appearance')[0], '<Kathy>: face-backed appearance; reviewed voice; transcript mention only');
console.log('PASS: actual renderer keeps voice, appearance and mention labels distinct; names remain text.');
