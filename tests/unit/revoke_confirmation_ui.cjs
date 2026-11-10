const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('ui/stitching_workbench/static/js/stitching.js', 'utf8');
const code = source.slice(source.indexOf('  let revokePending'), source.indexOf('  // Refreshes all lists'));
const calls = [];
let consent = false, note = null, release;
const context = {
  confirm: () => consent, prompt: () => note,
  ui: {rebuildOverlay:{removeAttribute(){},setAttribute(){}},status:{}},
  showToast: () => {}, refreshData: async () => {},
  commitConfirmedIdentity: (endpoint,body) => {
    calls.push({endpoint,body});
    return new Promise(resolve => {release = resolve;});
  },
};
vm.createContext(context);vm.runInContext(code,context);
(async () => {
 const mapping={mapping_id:'copy-only',source_node_name:'pattern',target_person_name:'Kathy'};
 await context.executeRevoke(mapping);assert.equal(calls.length,0);
 consent=true;
 await context.executeRevoke(mapping);assert.equal(calls.length,0);
 note='Revoke copied mapping only';
 const pending=context.executeRevoke(mapping);
 await context.executeRevoke(mapping);
 assert.equal(calls.length,1,'In-flight revoke cannot submit twice');
 assert.equal(calls[0].endpoint,'/api/system/identity/stitch/revoke');
 assert.equal(calls[0].body.mapping_id,'copy-only');
 assert.equal(calls[0].body.operator_note,note);
 release({success:true});await pending;
 console.log('PASS: actual revoke handler honors cancellation, mapping scope and duplicate-submit guard');
})().catch(error=>{console.error(error);process.exitCode=1;});
