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
  "\n  globalThis.__workbench = { state, ui, confirmedIdentityRequest, syncSpeakerAssignment, openFocusPanel, checkStatus, init };\n\n})();\n"
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

  const readinessCalls = [];
  global.fetch = async (url) => {
    readinessCalls.push(url);
    return response(200, {
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
  if (readinessCalls.length !== 1 || readinessCalls[0] !== "/api/status") {
    throw new Error("Epoch mismatch did not block identity data requests.");
  }
  if (workbench.ui.epochAuthorityStatus.hidden || !workbench.ui.epochAuthorityStatus.textContent.includes("default")) {
    throw new Error("Epoch mismatch was not presented on the visible authority surface.");
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
