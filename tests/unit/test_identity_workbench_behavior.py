"""Behavioral Node/DOM harness for the R-08 Identity Workbench client."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
IDENTITY_JS = REPO_ROOT / "ui" / "identity_workbench" / "static" / "js" / "identity.js"


HARNESS = r"""
const fs = require("fs");

class ClassList {
  add() {}
  remove() {}
  toggle() {}
}

class Element {
  constructor(id = "") {
    this.id = id;
    this.children = [];
    this.classList = new ClassList();
    this.dataset = {};
    this.hidden = false;
    this.innerHTML = "";
    this.open = false;
    this.style = {};
    this.textContent = "";
    this.value = "";
    this.showModalCalls = 0;
  }
  addEventListener() {}
  appendChild(child) { this.children.push(child); return child; }
  insertAdjacentHTML(_position, html) { this.innerHTML += html; }
  close() { this.open = false; }
  remove() {}
  querySelector() { return new Element(); }
  querySelectorAll() { return []; }
  setAttribute() {}
  showModal() { this.showModalCalls += 1; this.open = true; }
}

const elements = new Map();
const element = (id) => {
  if (!elements.has(id)) elements.set(id, new Element(id));
  return elements.get(id);
};
global.document = {
  addEventListener() {},
  createElement() { return new Element(); },
  getElementById: element,
  querySelectorAll() { return []; },
};
global.window = { confirm: () => true };
global.setTimeout = (callback) => { callback(); return 0; };

let source = fs.readFileSync(process.env.IDENTITY_JS, "utf8");
source = source.replace(
  /\s*init\(\);\s*\}\)\(\);\s*$/,
  "\n  globalThis.__workbench = { state, ui, confirmedIdentityRequest, syncSpeakerAssignment, openFocusPanel, checkStatus, init, renderRosterDetail };\n\n})();\n"
);
if (!source.includes("globalThis.__workbench")) throw new Error("Unable to expose Workbench harness hooks.");
eval(source);
const workbench = globalThis.__workbench;

function response(status, payload) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 403 ? "Forbidden" : "Server Error",
    json: async () => payload,
  };
}

async function run() {
  const calls = [];
  global.fetch = async (_url, options) => {
    calls.push(JSON.parse(options.body));
    if (calls.length === 1) {
      return response(403, { result: { confirmation_token: "scope-token" } });
    }
    return response(200, { ok: true });
  };
  const payload = { cluster_id: "fc_001", label: "Alex", operator_note: "evidence" };
  const accepted = await workbench.confirmedIdentityRequest("/api/identity/face-clusters/label", payload, "confirm");
  if (!accepted || calls.length !== 2) throw new Error("Accepted confirmation did not make the exact retry.");
  if ("confirmation_token" in calls[0]) throw new Error("Preparation request unexpectedly included a token.");
  if (calls[1].confirmation_token !== "scope-token" || calls[1].cluster_id !== "fc_001" || calls[1].operator_note !== "evidence") {
    throw new Error("Confirmed retry did not preserve the exact label scope.");
  }

  let cancelCalls = 0;
  global.window.confirm = () => false;
  global.fetch = async (_url, options) => {
    cancelCalls += 1;
    if ("confirmation_token" in JSON.parse(options.body)) throw new Error("Cancelled operation reused a token.");
    return response(403, { result: { confirmation_token: "cancelled-token" } });
  };
  const cancelled = await workbench.confirmedIdentityRequest("/api/identity/face-clusters/label", payload, "confirm");
  if (cancelled !== null || cancelCalls !== 1) throw new Error("Cancelled confirmation made a retry.");

  global.window.confirm = () => true;
  let speakerCalls = 0;
  global.fetch = async () => {
    speakerCalls += 1;
    if (speakerCalls === 1) return response(403, { result: { confirmation_token: "speaker-token" } });
    return response(500, { detail: "speaker write failed" });
  };
  const previous = { cluster_id: "spk_001", confirmed: false, identity_label: null };
  workbench.state.speakerClusters = [{ cluster_id: "spk_001", confirmed: true, identity_label: "Alex" }];
  await workbench.syncSpeakerAssignment(0, previous);
  const restored = workbench.state.speakerClusters[0];
  if (restored.confirmed !== false || restored.identity_label !== null) {
    throw new Error("Speaker failure did not restore the prior UI value.");
  }
  if (workbench.ui.operationStatus.hidden || !workbench.ui.operationStatus.textContent.includes("Speaker confirmation failed")) {
    throw new Error("Speaker failure was not retained in the shared status surface.");
  }

  workbench.state.faceClusters = [{ cluster_id: "fc_001", face_count: 1 }, { cluster_id: "fc_002", face_count: 2 }];
  workbench.ui.focusPanel.open = true;
  workbench.ui.focusPanel.showModalCalls = 0;
  workbench.openFocusPanel(1);
  if (workbench.ui.focusPanel.showModalCalls !== 0) {
    throw new Error("Focus navigation reopened an already-open dialog.");
  }

  // The production focus renderer must expose every saved member, the exact
  // crop and its source box, while keeping labels/notes and unavailable entries.
  const members = Array.from({length: 97}, (_, index) => ({
    target_face_id: `${index}_1`, target_face_index: 1, source_face_count: 2,
    frame_url: '/api/media/video/test/frame/saved.jpg', timestamp: 65.2,
    evidence_status: 'available', image_width: 128, image_height: 100,
    crop_bbox: [70, 10, 110, 90],
  }));
  members[96] = {target_face_id: '96_1', evidence_status: 'unavailable', reason: 'saved_evidence_unavailable'};
  workbench.state.faceClusters = [{cluster_id: 'group', face_count: 97,
    members, members_available: 96, label: 'Saved label', operator_note: 'Saved note'}];
  global.fetch = async () => { throw new Error('Opening saved members must not write or prepare'); };
  workbench.openFocusPanel(0);
  const gallery = workbench.ui.focusGrid.innerHTML;
  if ((gallery.match(/class="face-member"/g) || []).length !== 97 ||
      !gallery.includes('viewBox="70 10 40 80"') ||
      !gallery.includes('viewBox="0 0 128 100"') ||
      !gallery.includes('Detection 2 of 2') || !gallery.includes('0:01:05') ||
      !gallery.includes('data-face-id="96_1"') || !gallery.includes('Saved evidence could not be verified')) {
    throw new Error('Exact targets, source boxes or full membership were lost.');
  }
  if (workbench.ui.focusNameInput.value !== 'Saved label' || workbench.ui.focusOperatorNote.value !== 'Saved note') {
    throw new Error('Member review changed the saved review fields.');
  }

  const readinessCalls = [];
  global.fetch = async (url) => {
    readinessCalls.push(url);
    if (url === "/api/identity/roster") return response(200, {identities: [
      {id: "a", display_name: "Alice", aliases: ["Al"], relationships: [
        {type: "parent", target_id: "b", review_status: "user_provided",
         evidence: {kind: "operator_statement", statement: "Alice is my parent."}}
      ]}, {id: "b", display_name: "Bob"}
    ]});
    return response(200, {
      configured_epoch_id: "default",
      actions: {
        family_facts: {ready: true},
        face_prepare: {ready: true, count: 202},
        face_review: {ready: false, reason: "epoch_mismatch"},
        speaker_review: {ready: false, reason: "artifact_missing"},
        name_review: {ready: false, reason: "artifact_missing"},
        voice_review: {ready: true, count: 19},
      },
      epoch_authority: {
        configured_epoch_id: "default",
        identity_epoch_id: "epoch_other",
        state: "epoch_mismatch",
        ready: false,
        message: "Identity artifacts do not match the configured epoch.",
      },
    });
  };
  await workbench.init();
  if (JSON.stringify(readinessCalls) !== JSON.stringify(["/api/identity/readiness", "/api/identity/roster"])) {
    throw new Error("Unavailable evidence must not be auto-loaded; roster should remain accessible.");
  }
  if (workbench.ui.epochAuthorityStatus.hidden || !workbench.ui.epochAuthorityStatus.textContent.includes("Family facts are editable")) {
    throw new Error("Independent family-fact readiness was not presented.");
  }
  workbench.renderRosterDetail(0);
  const editable = workbench.ui.rosterDetail.innerHTML;
  if (!editable.includes("Alice is my parent.") || !editable.includes("user_provided") || !editable.includes('value="Al"')) {
    throw new Error("Editable family facts lost relationship evidence or aliases.");
  }
  if (workbench.ui.exportRosterBtn.disabled || workbench.ui.addIdentityBtn.disabled ||
      workbench.ui.rerunFacesBtn.disabled || workbench.ui.voiceReviewLink.hidden ||
      !workbench.ui.voiceReviewNote.textContent.includes("19 saved voice patterns") ||
      !element("add-face-cluster-0").disabled || !element("add-spk-cluster-0").disabled ||
      !workbench.ui.loadFacesBtn.disabled) {
    throw new Error("Action-specific controls did not preserve independent availability.");
  }
  global.fetch = async () => { throw new Error("offline"); };
  await workbench.checkStatus();
  if (!workbench.ui.addIdentityBtn.disabled || !workbench.ui.rerunFacesBtn.disabled || !workbench.ui.voiceReviewLink.hidden) {
    throw new Error("Readiness failure did not fail closed.");
  }
}

run().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
"""


def test_identity_workbench_behavioral_confirmation_and_navigation() -> None:
    env = {**os.environ, "IDENTITY_JS": str(IDENTITY_JS)}
    result = subprocess.run(
        ["node", "-e", HARNESS],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_appearance_flow_keeps_review_scope_cancel_and_stale_states() -> None:
    harness = HARNESS.split("async function run() {")[0].replace(
        "init, renderRosterDetail };", "init, renderRosterDetail, loadAppearancePreview, applyAppearances, undoAppearances };"
    ) + r"""
async function run() {
  const plan = {plan_sha256: 'a'.repeat(64), summary: {people:1,groups:1,appearances:1,scenes:1,observations:1,new_edges:2,existing_edges:0},
    held:{shared_aliases:[]}, people:[{id:'p',display_name:'Avery',scene_count:1,observation_count:1}],
    appearances:[{person_id:'p',scene_id:'scene-1',cluster_ids:['fc'],evidence:[{timestamp:5,evidence_status:'unavailable',target_face_id:'1_0'}]}]};
  const receipt = {id:'b'.repeat(32),receipt_sha256:'c'.repeat(64),status:'applied',created_at:'2026-10-26T00:00:00Z',summary:plan.summary};
  const writes = []; let history = [], stale = false;
  global.fetch = async (url, options) => {
    if (url.endsWith('/saved')) return response(200,{people:[],appearances:[],summary:{},epoch_id:'fixture'});
    if (url.endsWith('/history')) return response(200,{receipts:history});
    if (url.endsWith('/preview')) return response(200,plan);
    const payload = JSON.parse(options.body);
    if (!payload.confirmation_token) return response(403,{result:{confirmation_token:'scoped-token'}});
    if (stale) return response(409,{detail:'The saved inputs changed. Preview again.'});
    writes.push({url,payload});
    history = [{...receipt,status:url.endsWith('/undo')?'undone':'applied'}];
    return response(200,history[0]);
  };
  await workbench.loadAppearancePreview();
  if (!element('appearance-review').innerHTML.includes('Preview · not applied')) throw Error('Missing preview state');
  global.window.confirm = () => false;
  await workbench.applyAppearances();
  if (writes.length || element('appearance-review').hidden) throw Error('Cancel changed preview or sent a write');
  global.window.confirm = () => true;
  await workbench.applyAppearances();
  if (writes[0].payload.plan_sha256 !== plan.plan_sha256 || writes[0].payload.confirmation_token !== 'scoped-token') throw Error('Apply lost exact reviewed scope');
  if (!element('appearance-status').textContent.startsWith('Applied.')) throw Error('Missing applied result');
  await workbench.undoAppearances(receipt);
  if (writes[1].payload.receipt_id !== receipt.id || writes[1].payload.receipt_sha256 !== receipt.receipt_sha256) throw Error('Undo lost receipt scope');
  if (!element('appearance-history').innerHTML.includes('Undone')) throw Error('Undo history not displayed');
  await workbench.loadAppearancePreview();
  stale = true;
  await workbench.applyAppearances();
  if (!element('appearance-review').hidden || !element('appearance-status').textContent.includes('saved inputs changed')) throw Error('Stale plan stayed actionable');
  stale = false; plan.summary.new_edges = 0;
  await workbench.loadAppearancePreview();
  if (!element('apply-appearances-btn').disabled || !element('appearance-status').textContent.includes('already saved')) throw Error('Existing connections advertised an Apply');
}
run().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
"""
    result = subprocess.run(["node", "-e", harness], cwd=REPO_ROOT,
                            env={**os.environ, "IDENTITY_JS": str(IDENTITY_JS)},
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr or result.stdout


def test_saved_people_browsing_restores_selection_and_never_previews_or_writes() -> None:
    harness = HARNESS.split("async function run() {")[0].replace(
        "init, renderRosterDetail };", "init, renderRosterDetail, loadSavedPeople, renderSavedPerson };"
    ) + r"""
async function run() {
  const assert = require('node:assert/strict');
  const saved = {epoch_id:'epoch-fixture', summary:{people:2,appearances:3,scenes:3},
    people:[{id:'a',display_name:'Avery',scene_count:2,observation_count:2},{id:'b',display_name:'Blair',scene_count:1,observation_count:1}],
    appearances:[{person_id:'a',scene_id:'s1',video_id:'Home movie',evidence:[]},
      {person_id:'a',scene_id:'missing',video_id:'Home movie',evidence:[]},
      {person_id:'b',scene_id:'s2',video_id:'Home movie',evidence:[]}]};
  const calls=[]; let restored='';
  window.location={search:'?person=b&scene=s2&epoch=epoch-fixture'};
  window.history={replaceState:(_s,_t,url)=>{restored=url;}};
  global.fetch=async(url, options)=>{
    assert.equal(options.method,undefined,'browsing must not POST'); calls.push(url);
    if(url==='/api/identity/appearances/saved') return response(200,saved);
    if(url==='/api/videos/Home%20movie/scenes') return response(200,[
      {scene_id:'s1',start:10,end:20,original_video_available:true},
      {scene_id:'s2',start:30,end:40,original_video_available:true}]);
    throw Error('Unexpected caller '+url);
  };
  await workbench.loadSavedPeople();
  assert.match(element('saved-person-scenes').innerHTML, /Blair/);
  assert.match(restored, /person=b.*scene=s2/);
  assert.match(element('saved-person-scenes').innerHTML, /watch_person=b&amp;watch_scene=s2&amp;watch_video=Home\+movie&amp;watch_epoch=epoch-fixture/);
  await workbench.renderSavedPerson('a');
  assert.match(element('saved-person-scenes').innerHTML, /2 saved scenes/);
  assert.equal((element('saved-person-scenes').innerHTML.match(/>Watch scene</g)||[]).length,1);
  assert.match(element('saved-person-scenes').innerHTML,/Playback unavailable/);
  assert.equal(calls.filter(x=>x.endsWith('/scenes')).length,1,'source metadata is reused within the browse');
  window.location.search='?person=b&epoch=other-epoch';
  await workbench.loadSavedPeople();
  assert.match(element('saved-person-scenes').textContent,/unavailable in this movie/);
  global.fetch=async()=>response(409,{detail:'Graph unavailable'});
  await workbench.loadSavedPeople();
  assert.equal(element('saved-people-browser').hidden,true);
  assert.match(element('saved-people-status').textContent,/Graph unavailable/);
}
run().catch(error=>{console.error(error.stack||error);process.exitCode=1;});
"""
    result = subprocess.run(["node", "-e", harness], cwd=REPO_ROOT,
                            env={**os.environ, "IDENTITY_JS": str(IDENTITY_JS)},
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr or result.stdout
