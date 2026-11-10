"""Static contract for the R-08 Identity Workbench client authority seam."""
from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKBENCH_ROOT = REPO_ROOT / "ui" / "identity_workbench"
IDENTITY_JS = (WORKBENCH_ROOT / "static" / "js" / "identity.js").read_text(
    encoding="utf-8"
)
IDENTITY_HTML = (WORKBENCH_ROOT / "index.html").read_text(encoding="utf-8")
STITCHING_JS = (
    REPO_ROOT / "ui" / "stitching_workbench" / "static" / "js" / "stitching.js"
).read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    match = re.search(rf"(?:async\s+)?function\s+{re.escape(name)}\s*\(", IDENTITY_JS)
    assert match is not None, f"Missing JavaScript function: {name}"
    opening = IDENTITY_JS.index("{", match.end())
    depth = 0
    quote: str | None = None
    escaped = False
    index = opening
    while index < len(IDENTITY_JS):
        char = IDENTITY_JS[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in {'"', "'", "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return IDENTITY_JS[match.start() : index + 1]
        index += 1
    raise AssertionError(f"Unclosed JavaScript function: {name}")


def test_curated_relationships_show_statement_without_media_identity_claim():
    import json
    import subprocess

    # The common quote scanner does not parse regex literals in escHtml.
    escape_source = re.search(r"  function escHtml\(str\) \{.*?^  \}", IDENTITY_JS, re.S | re.M)
    assert escape_source is not None
    source = _function_source("rosterRelationshipsHtml") + escape_source.group(0)
    harness = r'''
const assert=require('node:assert/strict');
eval(JSON.parse(require('node:fs').readFileSync(0,'utf8')));
const html=rosterRelationshipsHtml({relationships:[{target_id:'b',type:'parent',review_status:'user_provided',
 evidence:{kind:'operator_statement',source_id:'statement-1',date:'2026-10-21',statement:'<img src=x> is my parent'}}]},
 [{id:'b',display_name:'Bob'}]);
assert.match(html,/parent → Bob/);assert.match(html,/user_provided/);assert.match(html,/statement-1/);
assert.match(html,/&lt;img src=x&gt;/);assert.ok(!html.includes('<img'));
assert.match(html,/does not identify a face or voice/);
assert.match(rosterRelationshipsHtml({},[]),/No directed relationship recorded/);
'''
    result = subprocess.run(["node", "-e", harness], input=json.dumps(source), text=True,
                            capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_label_mutation_preserves_note_and_uses_local_confirmation_token() -> None:
    labeler = _function_source("applyLabel")
    confirmer = _function_source("confirmedIdentityRequest")

    assert "operator_note: operatorNote" in labeler
    assert "confirmation_token: confirmationToken" in confirmer
    assert "let confirmationToken =" in confirmer
    assert "finally" in confirmer
    assert "confirmationToken = null;" in confirmer
    assert "confirmationToken" not in IDENTITY_JS.split("// ── UI Cache", 1)[0]


def test_focus_navigation_is_idempotent_and_has_a_persistent_failure_surface() -> None:
    opener = _function_source("openFocusPanel")

    assert "if (!ui.focusPanel.open)" in opener
    assert "ui.focusPanel.showModal();" in opener
    assert 'id="focus-operation-failure"' in IDENTITY_HTML
    assert 'role="alert"' in IDENTITY_HTML
    assert 'id="operation-status"' in IDENTITY_HTML
    assert 'role="status"' in IDENTITY_HTML


def test_face_rendering_keeps_canonical_order_and_uses_sample_faces_fallback() -> None:
    renderer = _function_source("renderFaceGrid")
    face_urls = _function_source("faceUrls")

    assert "let clusters = [...state.faceClusters];" in renderer
    assert "clusters.sort(" in renderer
    assert "sample_faces" in face_urls
    assert "representative_frames" in face_urls
    assert "return representative.length ? representative : samples;" in face_urls


def test_recluster_posts_eps_body_through_confirmation_gate() -> None:
    recluster = _function_source("rerunFaceClustering")
    confirmer = _function_source("confirmedIdentityRequest")

    assert '"/api/identity/rebuild-face-clusters"' in recluster
    assert "{ eps }" in recluster
    assert "confirmedIdentityRequest(" in recluster
    assert "body: JSON.stringify({ ...payload, confirmation_token: confirmationToken })" in confirmer
    assert "?eps=" not in recluster


def test_roster_face_options_exclude_clusters_owned_by_other_identities() -> None:
    renderer = _function_source("renderRosterDetail")

    assert "faceClusterOwner(" in renderer
    assert "ownerIdx === -1 || ownerIdx === idx" in renderer


def test_multi_face_evidence_is_visibly_marked_as_ambiguous() -> None:
    renderer = _function_source("renderFaceGrid")

    assert "source_face_count" in renderer
    assert "MULTI-FACE SOURCE" in renderer


def test_stitching_empty_state_names_missing_speaker_pattern_prerequisite() -> None:
    assert "No speaker-pattern evidence exists in the active epoch" in STITCHING_JS
    assert "Roster validation does not create speaker patterns" in STITCHING_JS


def test_validation_renderer_displays_structured_actionable_message() -> None:
    renderer = _function_source("renderValidationResult")

    assert 'typeof m === "string" ? m : m.message' in renderer
