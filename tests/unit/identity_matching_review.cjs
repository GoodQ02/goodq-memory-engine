const assert = require('node:assert/strict');
const fs = require('node:fs');
const fixture = JSON.parse(fs.readFileSync(0, 'utf8'));
const all = [];
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.handlers = {}; this.style = {}; this.dataset = {}; this.textContent = ''; this.hidden = false; this._value = ''; all.push(this); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; this._value = ''; }
  setAttribute(key, value) { this[key] = value; }
  addEventListener(event, fn) { (this.handlers[event] ||= []).push(fn); }
  async emit(event) { for (const fn of this.handlers[event] || []) await fn({preventDefault(){}}); }
  click() { this.emit('click'); }
  pause() { this.paused = true; }
  set value(value) { this._value = value; }
  get value() { return this._value || this.children[0]?.value || ''; }
}
const elements = new Map();
const get = id => { if (!elements.has(id)) elements.set(id, new Element(id)); return elements.get(id); };
get('matches-kind').value = 'face';
get('reuse-confirmed-faces').checked = true;
const document = {
  getElementById: get,
  createElement: tag => new Element(tag),
  querySelectorAll: selector => selector === '.tab-btn' ? [get('tab-matches'), get('tab-faces')] : all.filter(e => e.tagName === 'audio'),
};
const Option = function(text, value) { const e = new Element('option'); e.textContent = text; e.value = value; return e; };
const currentUrl = new URL('http://localhost/ui/identity_workbench/?matches=receipt');
const window = {location: {href: currentUrl.href, search: currentUrl.search}};
const storage = new Map();
window.localStorage = {getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value)};
if (fixture.case === 'legacy-completed') storage.set('goodq.face-review.epoch.receipt.undefined', JSON.stringify(['a']));
if (fixture.case === 'corrupt-draft') storage.set('goodq.face-review.v2.epoch.receipt.undefined', '{broken');
let confirmed = false, confirmations = 0;
window.confirm = () => { confirmations++; return confirmed; };
const history = {replaceState(_a, _b, value) { window.location.href = String(value); }};
const media = kind => kind === 'face'
  ? {kind: 'image', url: '/image', bbox: [5, 10, 50, 80], timestamp: 15}
  : {kind: 'audio', url: '/voice', start: 3, end: 8, timestamp: 33};
const report = {
  id: 'receipt', epoch_id: 'epoch', video_id: 'Movie', video_name: 'Movie.mp4', status: 'ready_for_review', errors: [],
  people: [{id: 'p', display_name: '<Person>'}],
  references: [
    {id: 'r-face', display_name: '<Person>', person_id: 'p', media: media('face'), video_name: 'Old movie'},
    {id: 'r-voice', display_name: null, person_id: null, media: media('voice'), video_name: 'Old movie'},
  ],
  summary: {face: {proposed: 1, no_match: 1}, voice: {proposed: 1}},
  records: [
    {id: 'a', modality: 'face', status: 'proposed', media: media('face'), scene_id: 's', scene_start: 10, scene_end: 20,
      margin: .2, candidates: [{reference_id: 'r-face', person_id: 'p', display_name: '<Person>', similarity: .8}]},
    {id: 'b', modality: 'face', status: 'no_match', media: media('face'), scene_id: 's', scene_start: 10, scene_end: 20,
      margin: .1, candidates: [{reference_id: 'r-face', person_id: 'p', display_name: '<Person>', similarity: .2}]},
    {id: 'c', modality: 'voice', status: 'proposed', media: media('voice'), scene_id: 's', scene_start: 10, scene_end: 40,
      margin: .1, candidates: [{reference_id: 'r-voice', person_id: null, display_name: null, similarity: .5}]},
  ],
};
if (['reassign', 'applied-correction'].includes(fixture.case)) report.people.push({id: 'q', display_name: '<Other>'});
const appliedCorrection = {id: 'r1', status: 'applied', receipt_sha256: 'x',
  summary: {observations: 1, scenes: 1, reusable_faces: 1, corrected: 1, decisions: {correct: 0, incorrect: 1, unsure: 0, not_accepted: 0}},
  review: {report_id: 'receipt', accepted_ids: [], decisions: {b: 'incorrect'}, corrections: {b: 'q'}, reuse_confirmed_faces: true}};
let empty = false;
const requests = [];
const writes = [];
const fetch = async (url, options) => {
  requests.push(url);
  if (options) {
    const body = JSON.parse(options.body); writes.push({url, body});
    assert.equal(options.method, 'POST');
    if (url === '/api/identity/matches/preview') {
      if (fixture.case === 'preview-error') return {ok: false, status: 409, json: async () => ({detail: 'Evidence changed; review again.'})};
      return {ok: true, json: async () => ({review: body, plan_sha256: 'plan', review_changed: true,
        summary: {observations: body.accepted_ids.length, people: 1, scenes: 1, new_edges: 1,
          reusable_faces: body.reuse_confirmed_faces ? body.accepted_ids.length : 0,
          decisions: Object.fromEntries(['correct','incorrect','unsure','not_accepted'].map(state=>[state,Object.values(body.decisions).filter(v=>v===state).length]))},
        held: {faces: 2-body.accepted_ids.length}, appearances: [{display_name: '<Person>', scene_start: 10, scene_end: 20,
          evidence: body.accepted_ids.map(evidence_id => ({evidence_id}))}]})};
    }
    assert.equal(url, '/api/identity/appearances/apply');
    assert.equal(body.plan_sha256, 'plan');
    if (!body.confirmation_token) return {ok: false, status: 403, json: async () => ({result: {confirmation_token: 'once'}})};
    assert.equal(body.confirmation_token, 'once');
    return {ok: true, json: async () => ({mutated: true})};
  }
  if (url === '/api/identity/appearances/history') return {ok: true, json: async () => ({receipts: fixture.case === 'applied-correction' ? [appliedCorrection] : []})};
  assert.ok(['/api/identity/matches', '/api/identity/matches/receipt'].includes(url));
  return {ok: true, json: async () => url.endsWith('/receipt') ? report : {reports: empty ? [] : [report]}};
};
const flatten = element => [element.textContent, ...element.children.map(flatten)].join(' ');
const tick = () => new Promise(resolve => setImmediate(resolve));
eval(fixture.source);
(async () => {
  for (let i = 0; i < 5; i++) await tick();
  assert.equal(get('matches-list').children.length, 2);
  if (fixture.case === 'face-labels') {
    assert.match(flatten(get('matches-list').children[0]), /Possible <Person>/);
    assert.match(flatten(get('matches-list').children[1]), /Unidentified face/);
    assert.match(flatten(get('matches-list').children[1]), /Below match threshold/);
    const watch = get('matches-list').children[0].children.find(e => e.tagName === 'a');
    assert.match(watch.href, /watch_match=receipt/); assert.match(watch.href, /watch_evidence=a/);
  } else if (fixture.case === 'voice-clips') {
    get('matches-kind').value = 'voice'; await get('matches-kind').emit('change');
    assert.equal(get('matches-list').children.length, 1);
    assert.match(flatten(get('matches-list')), /Unidentified speaker/);
    const audio = get('matches-list').children[0].children[1].children[0].children[0];
    assert.equal(audio.src, '/voice#t=3,8'); audio.currentTime = 0; await audio.emit('play');
    assert.equal(audio.currentTime, 3); audio.currentTime = 8; await audio.emit('timeupdate');
    assert.equal(audio.paused, true);
  } else if (fixture.case === 'filter-and-empty-reload') {
    get('matches-result').value = 'no_match'; await get('matches-result').emit('change');
    assert.equal(get('matches-list').children.length, 1);
    empty = true; await get('reload-matches').emit('click');
    assert.equal(get('matches-list').children.length, 0);
    assert.match(get('matches-status').textContent, /No completed comparisons/);
  } else if (fixture.case === 'unidentified-faces') {
    get('matches-person').value = 'unknown'; await get('matches-person').emit('change');
    assert.equal(get('matches-list').children.length, 1);
    assert.match(flatten(get('matches-list')), /Below match threshold/);
    assert.doesNotMatch(flatten(get('matches-list')), /Possible <Person>/);
  } else if (fixture.case === 'unidentified-voices') {
    get('matches-kind').value = 'voice'; await get('matches-kind').emit('change');
    get('matches-person').value = 'unknown'; await get('matches-person').emit('change');
    assert.equal(get('matches-list').children.length, 1);
    assert.match(flatten(get('matches-list')), /Unidentified speaker/);
  } else if (fixture.case === 'reference-review') {
    assert.equal(get('matches-references').children.length, 2);
    assert.match(flatten(get('matches-references')), /Unidentified voice 1/);
    assert.match(get('matches-status').textContent, /1 named face examples and 1 voice references/);
  } else if (fixture.case === 'reassign') {
    const card = () => get('matches-list').children[1];
    const button = text => card().children.find(e => e.className === 'match-review-actions').children.find(e => e.textContent === text);
    const picker = () => card().children.find(e => e.className === 'match-correction')?.children[0];
    assert.equal(picker(), undefined, 'Only Incorrect faces offer another person');
    await button('Incorrect').emit('click');
    assert.deepEqual(picker().children.map(o => o.value), ['', 'q'], 'The rejected person is not offered again');
    picker().value = 'q'; await picker().emit('change');
    assert.match(flatten(card()), /Incorrect: this is <Other>, not <Person> · Draft, not applied/);
    assert.match(get('match-review-status').textContent, /0 Correct · 1 Incorrect · 0 Unsure · 1 reassigned/);
    assert.equal(writes.length, 0, 'Choosing a person changes only the local draft');
    await get('reload-matches').emit('click');
    assert.equal(picker().value, 'q', 'The chosen person survives a reload');
    await get('preview-face-matches').emit('click');
    assert.deepEqual(writes[0].body.corrections, {b: 'q'});
    assert.deepEqual(writes[0].body.decisions, {b: 'incorrect'});
    assert.deepEqual(writes[0].body.accepted_ids, []);
    await button('Unsure').emit('click');
    assert.equal(picker(), undefined);
    await get('preview-face-matches').emit('click');
    assert.equal('corrections' in writes[1].body, false, 'Leaving Incorrect withdraws the correction');
  } else if (fixture.case === 'applied-correction') {
    const card = get('matches-list').children[1];
    assert.match(flatten(card), /Incorrect: this is <Other>, not <Person> · Applied/);
    const picker = card.children.find(e => e.className === 'match-correction').children[0];
    assert.equal(picker.disabled, true); assert.equal(picker.value, 'q');
    assert.match(flatten(get('face-match-history')), /1 reassigned to the right person/);
    assert.match(get('match-review-status').textContent, /1 Incorrect · 0 Unsure · 1 reassigned/);
  } else if (fixture.case === 'corrupt-draft') {
    assert.match(get('match-review-status').textContent, /could not be restored/);
    const controls = get('matches-list').children[1].children.find(e => e.className === 'match-review-actions');
    await controls.children.find(e=>e.textContent === 'Correct').emit('click');
    assert.equal([...storage.values()][0], '{broken', 'Unreadable drafts remain recoverable');
    assert.equal(writes.length, 0);
  } else if (fixture.case === 'legacy-completed') {
    assert.match(get('match-review-status').textContent, /1 Correct/);
    assert.equal(get('legacy-face-review').hidden, false);
    await get('complete-legacy-review').emit('click');
    await get('preview-face-matches').emit('click');
    assert.deepEqual(writes[0].body.decisions, {a:'correct',b:'not_accepted'});
    assert.equal(writes[0].body.completed_review, true);
    assert.match(flatten(get('face-match-preview')), /do not need to repeat the batch/);
    await get('reload-matches').emit('click');
    assert.match(get('match-review-status').textContent, /1 earlier review: not accepted/);
    assert.equal(get('legacy-face-review').hidden, true);
    assert.deepEqual(JSON.parse(storage.get('goodq.face-review.epoch.receipt.undefined')), ['a'], 'Original draft remains recoverable');
  } else if (['select-and-hold', 'preview-only', 'apply-cancel', 'apply-confirm', 'preview-error', 'draft-restore', 'stale-draft', 'no-reuse', 'review-only', 'stale-preview'].includes(fixture.case)) {
    const cardButton = text => get('matches-list').children[1].children.find(e => e.className === 'match-review-actions').children.find(e => e.textContent === text);
    assert.equal(get('preview-face-matches').disabled, true);
    await cardButton('Correct').emit('click');
    assert.equal(get('preview-face-matches').disabled, false);
    assert.match(flatten(get('matches-list').children[1]), /Correct: <Person> · Draft, not applied/);
    assert.equal(writes.length, 0, 'Selecting a face changes only the local draft');
    if (fixture.case === 'select-and-hold') {
      await cardButton('Incorrect').emit('click');
      assert.equal(get('preview-face-matches').disabled, false, 'Negative-only reviews can be saved');
      assert.match(get('match-review-status').textContent, /0 Correct · 1 Incorrect · 0 Unsure/);
      await cardButton('Unsure').emit('click');
      assert.match(get('match-review-status').textContent, /0 Correct · 0 Incorrect · 1 Unsure/);
      await get('reload-matches').emit('click');
      assert.equal(JSON.parse([...storage.values()][0]).decisions.b, 'unsure');
    } else if (fixture.case === 'draft-restore') {
      await get('reload-matches').emit('click');
      assert.match(get('match-review-status').textContent, /1 Correct/);
      assert.match(flatten(get('matches-list').children[1]), /Correct: <Person>/);
    } else if (fixture.case === 'stale-draft') {
      const key = [...storage.keys()][0], changed = JSON.stringify({version:2,decisions:{a:'incorrect'}});
      storage.set(key, changed);
      await cardButton('Unsure').emit('click');
      assert.equal(storage.get(key), changed);
      assert.match(get('match-review-status').textContent, /changed in another tab/);
    } else {
      if (fixture.case === 'no-reuse') { get('reuse-confirmed-faces').checked = false; await get('reuse-confirmed-faces').emit('change'); }
      if (fixture.case === 'review-only') await cardButton('Incorrect').emit('click');
      await get('preview-face-matches').emit('click');
      assert.deepEqual(writes[0].body.accepted_ids, fixture.case === 'review-only' ? [] : ['b']);
      if (fixture.case === 'preview-error') {
        assert.match(get('match-review-status').textContent, /Evidence changed/);
        assert.equal(get('face-match-preview').hidden, true);
      } else {
        assert.equal(get('face-match-preview').hidden, false);
        assert.match(flatten(get('face-match-preview')), /All voices and mentions remain held/);
        if (fixture.case === 'no-reuse') assert.equal(writes[0].body.reuse_confirmed_faces, false);
        if (fixture.case === 'review-only') assert.deepEqual(writes[0].body.decisions, {b:'incorrect'});
        if (fixture.case === 'stale-preview') {
          storage.set([...storage.keys()][0], JSON.stringify({version:2,decisions:{a:'unsure'}}));
          await get('face-match-preview').children.find(e=>e.textContent === 'Apply review and confirmed faces').emit('click');
          assert.equal(confirmations, 0);
          assert.equal(writes.filter(r=>r.url.endsWith('/apply')).length, 0);
          assert.match(get('match-review-status').textContent, /changed in another tab/);
        }
        if (fixture.case.startsWith('apply-')) {
          confirmed = fixture.case === 'apply-confirm';
          await get('face-match-preview').children.find(e => e.textContent === 'Apply review and confirmed faces').emit('click');
          assert.equal(confirmations, 1);
          assert.equal(writes.filter(r => r.url.endsWith('/apply')).length, confirmed ? 2 : 1);
          if (!confirmed) assert.match(get('match-review-status').textContent, /cancelled/);
        }
      }
    }
  }
  assert.ok(requests.every(url => !/search|stitch/.test(url)));
  if (!fixture.case.startsWith('apply-')) assert.ok(requests.every(url => !/apply/.test(url)));
  console.log('PASS ' + fixture.case);
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
