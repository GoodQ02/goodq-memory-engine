/*
Justification Channel v1 — Golden Render Test (read-only).

How to run (browser console):
  1) Load ui/justification_v1/index.html
  2) In console:
       var s=document.createElement('script'); s.src='./static/js/test_render.js'; document.head.appendChild(s);
       GoodQJustificationTests.run();
*/

(function () {
  const GOLDEN = [
    "GOODQ — JUSTIFICATION CHANNEL v1 (inspection)",
    "read_model_version: 1",
    "retrieval_context: human.ui.search",
    "",
    "QUERY",
    "────────────────────────────────────────────────────────────",
    "Is there music playing in scene 0007?",
    "",
    "EPISTEMIC SUMMARY",
    "────────────────────────────────────────────────────────────",
    "outcome: answer",
    "candidates (in order):",
    "  - a2  state=conflicted",
    "",
    "NON-ACTION DECISIONS",
    "────────────────────────────────────────────────────────────",
    "1) domain=act  required_response=defer",
    "   condition=act_blocked_on_conflict",
    '   rationale={ "candidate_state": "conflicted" }',
    "",
    "CANDIDATE a2",
    "────────────────────────────────────────────────────────────",
    "state: conflicted",
    "answer_text:",
    "  Evidence is mixed about whether music is present in scene 0007.",
    "",
    "confidence:",
    "  intrinsic=null  source=null  temporal=null  consistency=null  overall=null",
    "",
    "limits:",
    "  - conflict:audio_support_vs_text_contradict",
    "",
    "next_steps:",
    "  - action=inspect scene audio clip",
    "    rationale=Resolve conflict by direct listening/inspection",
    '    scope={ "video_id": "video_001", "scene_id": "0007" }',
    "",
    "EVIDENCE (input order; timestamps shown, not used for sorting)",
    "────────────────────────────────────────────────────────────",
    "",
    "[1] role=support",
    "    store=qdrant  store_ref=goodq_audio  embedding_id=8b1a...  score=0.08",
    "    payload (sanitized):",
    "      video_id=video_001",
    "      scene_id=0007",
    "      model=clap",
    "    provenance (pointer):",
    "      provenance_version=1",
    "      ts_utc=2025-12-17T04:12:03Z",
    "      video_id=video_001  scene_id=0007",
    "      modality=audio  model=clap  component=audio_embed_clap",
    "      attempted=true  committed=true  reason=—",
    "      targets:",
    "        qdrant: attempted=true  committed=true  ref=goodq_audio",
    "        faiss:  attempted=true  committed=true  ref=goodq_audio.index",
    "    confidence (hit-level, informational):",
    "      temporal=0.61",
    "      temporal_explanation=age_bucket: 30-90d",
    "      intrinsic=null  source=null  consistency=null  overall=null",
    "    limits: ∅",
    "",
    "[2] role=contradict",
    "    store=qdrant  store_ref=goodq_text  embedding_id=4f22...  score=0.13",
    "    payload (sanitized):",
    "      video_id=video_001",
    "      scene_id=0007",
    "      model=all-MiniLM-L6-v2",
    "      transcript=[REDACTED]",
    "    provenance (pointer):",
    "      provenance_version=1",
    "      ts_utc=2025-12-20T10:31:55Z",
    "      video_id=video_001  scene_id=0007",
    "      modality=text  model=all-MiniLM-L6-v2  component=text_embed",
    "      attempted=true  committed=true  reason=—",
    "      targets:",
    "        qdrant: attempted=true  committed=true  ref=goodq_text",
    "    confidence (hit-level, informational):",
    "      temporal=0.92",
    "      temporal_explanation=age_bucket: 0-7d",
    "      intrinsic=null  source=null  consistency=null  overall=null",
    "    limits:",
    "      - payload_redacted:transcript",
    "",
    "WHAT’S MISSING (AGGREGATED LIMITS)",
    "────────────────────────────────────────────────────────────",
    "- conflict:audio_support_vs_text_contradict",
    "- payload_redacted:transcript",
    "",
    "NEXT STEPS (AGGREGATED)",
    "────────────────────────────────────────────────────────────",
    "- inspect scene audio clip  scope={video_id=video_001, scene_id=0007}",
  ].join("\n");

  /**
   * @param {boolean} ok
   * @param {string} msg
   */
  function assert(ok, msg) {
    if (!ok) throw new Error(`ASSERT FAIL: ${msg}`);
  }

  function run() {
    if (!window.GoodQJustification || typeof window.GoodQJustification.renderJustificationText !== "function") {
      throw new Error("Missing GoodQJustification.renderJustificationText (load app.js first).");
    }
    const out = window.GoodQJustification.renderJustificationText(window.GoodQJustification.EXAMPLE);

    assert(out.includes("GOODQ — JUSTIFICATION CHANNEL v1 (inspection)"), "missing header");
    assert(out.includes("EPISTEMIC SUMMARY"), "missing EPISTEMIC SUMMARY");
    assert(out.includes("outcome: answer"), "missing outcome");
    assert(out.includes("limits: ∅"), "missing ∅ rendering for limits");
    assert(out === GOLDEN, "output does not match golden snapshot");

    console.log("[PASS] Justification Channel v1 golden render test");
    return { ok: true };
  }

  window.GoodQJustificationTests = { run, GOLDEN };
})();

