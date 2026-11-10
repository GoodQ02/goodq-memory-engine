const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = new Map();
const context = {document: {
  addEventListener() {},
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, {style: {}, textContent: '', innerHTML: ''});
    return elements.get(id);
  }
}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('ui/summary_console/static/js/summary.js', 'utf8'), context);
function render(distribution, coverage) {
  context.renderLeaderboards({people: [], places: [], occasions: [], top_emotions: [],
    sentiment_distribution: distribution, sentiment_coverage: coverage});
  return elements.get('sentiment-coverage').textContent;
}
assert.equal(render({POSITIVE:21, NEGATIVE:4, NEUTRAL:7}, {classified:32,total:33,unavailable:1}),
  'Sentiment available for 32 of 33 scenes; 1 unavailable. Percentages use classified scenes.');
assert.equal(elements.get('sent-neu-val').textContent, '7 (22%)');
assert.equal(elements.get('sent-neu-bar').style.width, '21.875%');
assert.equal(render({}, {classified:0,total:3,unavailable:3}),
  'Sentiment available for 0 of 3 scenes; 3 unavailable. No classified sentiment to display.');
for (const id of ['sent-pos-bar','sent-neu-bar','sent-neg-bar']) assert.equal(elements.get(id).style.width, '0%');
assert.equal(render({}, {classified:0,total:0,unavailable:0}),
  'Sentiment available for 0 of 0 scenes; 0 unavailable. No classified sentiment to display.');
assert.equal(render({NEUTRAL:2}, null), 'Sentiment coverage unavailable.');
assert.equal(elements.get('sent-neu-val').textContent, '2 (100%)');
console.log('PASS: actual Moods renderer preserves neutral counts, classified denominator, unavailable, empty and legacy coverage.');
