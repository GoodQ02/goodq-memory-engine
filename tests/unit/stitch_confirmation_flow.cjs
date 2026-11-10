// Actual workbench request code: authorization handshake, scope, and failure behavior.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('ui/stitching_workbench/static/js/stitching.js', 'utf8');
const requestCode = source.slice(source.indexOf('  async function apiCall('), source.indexOf('  // Fetch status of DB'));
const payload = {source_node_name: 'reviewed-pattern', target_person_name: 'Kathy', confirm: true, operator_note: 'Reviewed A/F'};
function setup(replies, duringFetch = () => {}, endpoint = '/api/system/identity/stitch') {
  const calls = [];
  const context = {state: {apiBase: ''}, fetch: async (url, options) => {
    calls.push({url, body: JSON.parse(options.body)});
    duringFetch(calls.length);
    const [status, body] = replies.shift();
    return {ok: status === 200, status, statusText: 'Denied', json: async () => body};
  }};
  vm.createContext(context);
  vm.runInContext(requestCode, context);
  return {calls, commit: endpoint.endsWith('/revoke') ? body => context.commitConfirmedIdentity(endpoint, body) : context.commitConfirmedStitch};
}
const preparation = [403, {status: 'needs_confirmation', result: {allowed: false, confirmation_token: 'once-only'}}];
(async () => {
 for (const endpoint of ['/api/system/identity/stitch', '/api/system/identity/stitch/revoke']) {
  const payload = endpoint.endsWith('/revoke') ? {mapping_id:'reviewed-mapping',operator_note:'Reviewed isolated revoke'} : {source_node_name: 'reviewed-pattern', target_person_name: 'Kathy', confirm: true, operator_note: 'Reviewed A/F'};
  const changing = {...payload};
  const success = setup([preparation, [200, {success: true}]], count => {
    if (count === 1) changing.target_person_name = 'Changed while awaiting response';
  }, endpoint);
  assert.equal((await success.commit(changing)).success, true);
  assert.deepEqual(success.calls.map(c => c.body), [payload, {...payload, confirmation_token: 'once-only'}]);
  assert(success.calls.every(c => c.url === endpoint));
  for (const reply of [
    [403, {status: 'error', result: {confirmation_token: 'must-not-use'}}],
    [403, {status: 'needs_confirmation', result: {}}],
    [403, {status: 'needs_confirmation', result: {confirmation_token: '  '}}],
    [500, {status: 'needs_confirmation', result: {confirmation_token: 'must-not-use'}}],
    [200, {success: true}],
  ]) {
    const denied = setup([reply], undefined, endpoint);
    await assert.rejects(() => denied.commit(payload));
    assert.equal(denied.calls.length, 1);
  }
  const expired = setup([preparation, [403, {status: 'error', errors: [{code: 'token_expired'}]}]], undefined, endpoint);
  await assert.rejects(() => expired.commit(payload));
  assert.equal(expired.calls.length, 2, 'Never retry a failed confirmation or silently obtain a new token');
 }
  console.log('PASS: stitch and revoke frozen payloads, real envelopes, rejected preparations, no confirmation retry');
})().catch(error => { console.error(error); process.exitCode = 1; });
