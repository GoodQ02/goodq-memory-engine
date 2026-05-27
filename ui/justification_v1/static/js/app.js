/*
This renderer assembles epistemic structure only. It must not be used to gate, rank, filter, or refuse.

Hardening harness (integrity-only; no semantics change):
- Validator + order fingerprint: ./integrity.js (diagnostics only; never enforced)
- Diagnostics overlay toggle: press "D" (read-only; does not change <pre> output)
- Golden test: load ./test_render.js then run `GoodQJustificationTests.run()` in console

Justification Channel v1:
- Renders EpistemicReadEnvelope + NonActionDecision[] in a text-first, truth-preserving format.
- No ingestion/training/agent actions; explicit read-only envelope loading only; no sorting, no filtering.
*/

const SEPARATOR = "────────────────────────────────────────────────────────────";
const GOODQ_UI_VERSION =
  typeof window !== "undefined" && typeof window.GOODQ_UI_VERSION === "string" && window.GOODQ_UI_VERSION.trim()
    ? window.GOODQ_UI_VERSION.trim()
    : "justification-ui-v1.0.3";

const GOODQ_UI_VIEW_TEXT = "text";
const GOODQ_UI_VIEW_PROJECT = "project";

/**
 * @param {unknown} v
 * @returns {string}
 */
function fmtScalar(v) {
  if (v === null || v === undefined) return "null";
  if (typeof v === "boolean") return v ? "true" : "false";
  return String(v);
}

/**
 * @param {unknown} obj
 * @returns {string}
 */
function fmtInlineObject(obj) {
  if (!obj || typeof obj !== "object") return "{}";
  const o = obj;
  const keys = Object.keys(o);
  if (keys.length === 0) return "{}";

  const parts = keys.map((k) => {
    const v = o[k];
    if (v === null || v === undefined) return `"${k}": null`;
    if (typeof v === "number" || typeof v === "boolean") return `"${k}": ${fmtScalar(v)}`;
    return `"${k}": "${fmtScalar(v)}"`;
  });
  return `{ ${parts.join(", ")} }`;
}

/**
 * @param {Record<string, unknown> | null | undefined} confidence
 * @returns {string}
 */
function fmtConfidenceLine(confidence) {
  const c = confidence && typeof confidence === "object" ? confidence : {};
  return [
    `intrinsic=${fmtScalar(c.intrinsic)}`,
    `source=${fmtScalar(c.source)}`,
    `temporal=${fmtScalar(c.temporal)}`,
    `consistency=${fmtScalar(c.consistency)}`,
    `overall=${fmtScalar(c.overall)}`,
  ].join("  ");
}

/**
 * @param {Record<string, unknown> | null | undefined} confidence
 * @returns {string[]}
 */
function fmtHitConfidenceBlock(confidence) {
  const c = confidence && typeof confidence === "object" ? confidence : {};
  const lines = [];
  lines.push(`      temporal=${fmtScalar(c.temporal)}`);
  if (typeof c.temporal_explanation === "string" && c.temporal_explanation) {
    lines.push(`      temporal_explanation=${c.temporal_explanation}`);
  }
  lines.push(
    `      intrinsic=${fmtScalar(c.intrinsic)}  source=${fmtScalar(c.source)}  consistency=${fmtScalar(
      c.consistency
    )}  overall=${fmtScalar(c.overall)}`
  );
  return lines;
}

/**
 * @param {unknown} payload
 * @returns {string[]}
 */
function fmtPayloadLines(payload) {
  if (!payload || typeof payload !== "object") return [];
  const p = payload;
  /** @type {string[]} */
  const lines = [];
  for (const k of Object.keys(p)) {
    lines.push(`      ${k}=${fmtScalar(p[k])}`);
  }
  return lines;
}

/**
 * @param {unknown} targets
 * @returns {string[]}
 */
function fmtTargetsLines(targets) {
  if (!targets || typeof targets !== "object") return [];
  const t = targets;
  const names = Object.keys(t);
  const maxNameLen = names.reduce((acc, n) => Math.max(acc, n.length), 0);

  /** @type {string[]} */
  const lines = [];
  for (const name of names) {
    const detail = t[name] && typeof t[name] === "object" ? t[name] : {};
    const prefix = `${name}:`.padEnd(maxNameLen + 1, " ");
    lines.push(
      `        ${prefix} attempted=${fmtScalar(detail.attempted)}  committed=${fmtScalar(detail.committed)}  ref=${fmtScalar(
        detail.ref
      )}`
    );
  }
  return lines;
}

/**
 * @param {unknown} provenance
 * @returns {string[]}
 */
function fmtProvenanceBlock(provenance) {
  if (!provenance || typeof provenance !== "object") return [];
  const p = provenance;
  /** @type {string[]} */
  const lines = [];

  lines.push(`      provenance_version=${fmtScalar(p.provenance_version)}`);
  lines.push(`      ts_utc=${fmtScalar(p.ts_utc)}`);
  lines.push(`      video_id=${fmtScalar(p.video_id)}  scene_id=${fmtScalar(p.scene_id)}`);
  lines.push(
    `      modality=${fmtScalar(p.modality)}  model=${fmtScalar(p.model)}  component=${fmtScalar(p.component)}`
  );
  lines.push(
    `      attempted=${fmtScalar(p.attempted)}  committed=${fmtScalar(p.committed)}  reason=${fmtScalar(p.reason)}`
  );
  if (p.targets && typeof p.targets === "object" && Object.keys(p.targets).length > 0) {
    lines.push(`      targets:`);
    lines.push(...fmtTargetsLines(p.targets));
  }

  return lines;
}

/**
 * @param {unknown} limits
 * @param {string} indent
 * @returns {string[]}
 */
function fmtLimitsBlock(limits, indent) {
  if (!Array.isArray(limits)) return [`${indent}∅`];
  if (limits.length === 0) return [`${indent}∅`];
  return limits.map((l) => `${indent}- ${String(l)}`);
}

/**
 * @param {unknown} nextSteps
 * @returns {string[]}
 */
function fmtNextStepsBlock(nextSteps) {
  if (!Array.isArray(nextSteps) || nextSteps.length === 0) return ["  ∅"];
  /** @type {string[]} */
  const lines = [];
  for (const ns of nextSteps) {
    if (!ns || typeof ns !== "object") continue;
    lines.push(`  - action=${fmtScalar(ns.action)}`);
    lines.push(`    rationale=${fmtScalar(ns.rationale)}`);
    if (ns.scope && typeof ns.scope === "object" && Object.keys(ns.scope).length > 0) {
      const scopePairs = Object.keys(ns.scope).map((k) => `"${k}": "${fmtScalar(ns.scope[k])}"`);
      lines.push(`    scope={ ${scopePairs.join(", ")} }`);
    }
  }
  return lines.length ? lines : ["  ∅"];
}

/**
 * @param {{ envelope: any, nonActionDecisions: any[] }} input
 * @returns {string}
 */
function renderJustificationText(input) {
  const envelope = input && input.envelope ? input.envelope : {};
  const decisions = Array.isArray(input.nonActionDecisions) ? input.nonActionDecisions : [];

  /** @type {string[]} */
  const out = [];

  out.push("GOODQ — JUSTIFICATION CHANNEL v1 (inspection)");
  out.push(`read_model_version: ${fmtScalar(envelope.read_model_version)}`);
  out.push(
    `retrieval_context: ${envelope.retrieval_context ? String(envelope.retrieval_context) : "— (not provided)"}`
  );
  out.push("");

  // QUERY
  out.push("QUERY");
  out.push(SEPARATOR);
  out.push(String((envelope.question && envelope.question.text) || ""));
  out.push("");

  // EPISTEMIC SUMMARY
  out.push("EPISTEMIC SUMMARY");
  out.push(SEPARATOR);
  out.push(`outcome: ${fmtScalar(envelope.outcome)}`);

  const candidates = Array.isArray(envelope.candidates) ? envelope.candidates : [];
  if (fmtScalar(envelope.outcome) === "answer") {
    out.push("candidates (in order):");
    if (candidates.length === 0) {
      out.push("  ∅");
    } else {
      for (const cand of candidates) {
        out.push(`  - ${fmtScalar(cand.candidate_id)}  state=${fmtScalar(cand.state)}`);
      }
    }
  }
  if (fmtScalar(envelope.outcome) === "dont_know" && envelope.dont_know && typeof envelope.dont_know === "object") {
    out.push(`dont_know.state: ${fmtScalar(envelope.dont_know.state)}`);
    out.push(`dont_know.explanation: ${fmtScalar(envelope.dont_know.explanation)}`);
  }
  out.push("");

  // NON-ACTION DECISIONS (if any)
  if (decisions.length > 0) {
    out.push("NON-ACTION DECISIONS");
    out.push(SEPARATOR);
    for (let i = 0; i < decisions.length; i++) {
      const d = decisions[i] && typeof decisions[i] === "object" ? decisions[i] : {};
      out.push(
        `${i + 1}) domain=${fmtScalar(d.domain)}  required_response=${fmtScalar(d.required_response)}`
      );
      out.push(`   condition=${fmtScalar(d.condition)}`);
      out.push(`   rationale=${fmtInlineObject(d.rationale || {})}`);
      out.push("");
    }
    if (out[out.length - 1] === "") out.pop();
    out.push("");
  }

  // CANDIDATES + EVIDENCE
  if (fmtScalar(envelope.outcome) === "answer" && candidates.length > 0) {
    for (const cand of candidates) {
      out.push(`CANDIDATE ${fmtScalar(cand.candidate_id)}`);
      out.push(SEPARATOR);
      out.push(`state: ${fmtScalar(cand.state)}`);
      out.push("answer_text:");
      out.push(`  ${fmtScalar(cand.answer_text)}`);
      out.push("");
      out.push("confidence:");
      out.push(`  ${fmtConfidenceLine(cand.confidence)}`);
      out.push("");
      out.push("limits:");
      if (Array.isArray(cand.limits) && cand.limits.length > 0) {
        out.push(...cand.limits.map((l) => `  - ${String(l)}`));
      } else {
        out.push("  ∅");
      }
      out.push("");
      out.push("next_steps:");
      if (Array.isArray(cand.next_steps) && cand.next_steps.length > 0) {
        out.push(...fmtNextStepsBlock(cand.next_steps));
      } else {
        out.push("  ∅");
      }
      out.push("");

      out.push("EVIDENCE (input order; timestamps shown, not used for sorting)");
      out.push(SEPARATOR);
      out.push("");

      const evidence = Array.isArray(cand.evidence) ? cand.evidence : [];
      if (evidence.length === 0) {
        out.push("Evidence: ∅ (no EvidenceHit items)");
        out.push("");
      }
      for (let i = 0; i < evidence.length; i++) {
        const ev = evidence[i] && typeof evidence[i] === "object" ? evidence[i] : {};
        out.push(`[${i + 1}] role=${fmtScalar(ev.role)}`);
        out.push(
          `    store=${fmtScalar(ev.store)}  store_ref=${fmtScalar(ev.store_ref)}  embedding_id=${fmtScalar(
            ev.embedding_id
          )}  score=${fmtScalar(ev.score)}`
        );
        out.push("    payload (sanitized):");
        out.push(...fmtPayloadLines(ev.payload));
        out.push("    provenance (pointer):");
        out.push(...fmtProvenanceBlock(ev.provenance));
        out.push("    confidence (hit-level, informational):");
        out.push(...fmtHitConfidenceBlock(ev.confidence));
        if (Array.isArray(ev.limits) && ev.limits.length === 0) {
          out.push("    limits: ∅");
        } else if (Array.isArray(ev.limits) && ev.limits.length > 0) {
          out.push("    limits:");
          out.push(...ev.limits.map((l) => `      - ${String(l)}`));
        } else {
          out.push("    limits: ∅");
        }
        out.push("");
      }
    }
  }

  // DONT-KNOW DETAIL (only if outcome dont_know)
  if (fmtScalar(envelope.outcome) === "dont_know" && envelope.dont_know && typeof envelope.dont_know === "object") {
    const dk = envelope.dont_know;
    out.push("DONT-KNOW DETAIL");
    out.push(SEPARATOR);
    out.push(`state: ${fmtScalar(dk.state)}`);
    out.push("explanation:");
    out.push(`  ${fmtScalar(dk.explanation)}`);
    out.push("");

    out.push("evidence:");
    const dkEvidence = Array.isArray(dk.evidence) ? dk.evidence : [];
    if (dkEvidence.length === 0) {
      out.push("  Evidence: ∅ (no related/supporting evidence provided)");
    } else {
      out.push("");
      for (let i = 0; i < dkEvidence.length; i++) {
        const ev = dkEvidence[i] && typeof dkEvidence[i] === "object" ? dkEvidence[i] : {};
        out.push(`[${i + 1}] role=${fmtScalar(ev.role)}`);
        out.push(
          `    store=${fmtScalar(ev.store)}  store_ref=${fmtScalar(ev.store_ref)}  embedding_id=${fmtScalar(
            ev.embedding_id
          )}  score=${fmtScalar(ev.score)}`
        );
        out.push("    payload (sanitized):");
        out.push(...fmtPayloadLines(ev.payload));
        out.push("    provenance (pointer):");
        out.push(...fmtProvenanceBlock(ev.provenance));
        out.push("    confidence (hit-level, informational):");
        out.push(...fmtHitConfidenceBlock(ev.confidence));
        if (Array.isArray(ev.limits) && ev.limits.length === 0) {
          out.push("    limits: ∅");
        } else if (Array.isArray(ev.limits) && ev.limits.length > 0) {
          out.push("    limits:");
          out.push(...ev.limits.map((l) => `      - ${String(l)}`));
        } else {
          out.push("    limits: ∅");
        }
        out.push("");
      }
      if (out[out.length - 1] === "") out.pop();
    }
    out.push("");

    out.push("limits:");
    if (!Array.isArray(dk.limits) || dk.limits.length === 0) {
      out.push("∅ (no limits provided)");
    } else {
      out.push(...dk.limits.map((l) => `- ${String(l)}`));
    }
    out.push("");

    out.push("next_steps:");
    if (!Array.isArray(dk.next_steps) || dk.next_steps.length === 0) {
      out.push("∅");
    } else {
      for (const ns of dk.next_steps) {
        if (!ns || typeof ns !== "object") continue;
        out.push(`- action=${fmtScalar(ns.action)}`);
        out.push(`  rationale=${fmtScalar(ns.rationale)}`);
        if (ns.scope && typeof ns.scope === "object" && Object.keys(ns.scope).length > 0) {
          const scopePairs = Object.keys(ns.scope).map((k) => `"${k}": "${fmtScalar(ns.scope[k])}"`);
          out.push(`  scope={ ${scopePairs.join(", ")} }`);
        }
      }
    }
    out.push("");
  }

  // WHAT’S MISSING (ALWAYS)
  /** @type {string[]} */
  const aggregatedLimits = [];
  const seen = new Set();

  // candidate.limits in order
  for (const cand of candidates) {
    if (Array.isArray(cand.limits)) {
      for (const l of cand.limits) {
        const s = String(l);
        if (!seen.has(s)) {
          aggregatedLimits.push(s);
          seen.add(s);
        }
      }
    }
    // evidence.limits in order
    const evidence = Array.isArray(cand.evidence) ? cand.evidence : [];
    for (const ev of evidence) {
      if (ev && typeof ev === "object" && Array.isArray(ev.limits)) {
        for (const l of ev.limits) {
          const s = String(l);
          if (!seen.has(s)) {
            aggregatedLimits.push(s);
            seen.add(s);
          }
        }
      }
    }
  }
  if (envelope.dont_know && typeof envelope.dont_know === "object" && Array.isArray(envelope.dont_know.limits)) {
    for (const l of envelope.dont_know.limits) {
      const s = String(l);
      if (!seen.has(s)) {
        aggregatedLimits.push(s);
        seen.add(s);
      }
    }
  }

  out.push("WHAT’S MISSING (AGGREGATED LIMITS)");
  out.push(SEPARATOR);
  if (aggregatedLimits.length === 0) {
    out.push("∅");
  } else {
    for (const l of aggregatedLimits) out.push(`- ${l}`);
  }
  out.push("");

  // NEXT STEPS (ONLY WHEN PRESENT)
  /** @type {string[]} */
  const aggregatedNextSteps = [];
  const seenNext = new Set();
  const pushNext = (action, scope) => {
    const key = `${action}::${scope || ""}`;
    if (seenNext.has(key)) return;
    seenNext.add(key);
    aggregatedNextSteps.push({ action, scope });
  };

  for (const cand of candidates) {
    if (Array.isArray(cand.next_steps)) {
      for (const ns of cand.next_steps) {
        if (!ns || typeof ns !== "object") continue;
        const action = fmtScalar(ns.action);
        let scopeText = "";
        if (ns.scope && typeof ns.scope === "object" && Object.keys(ns.scope).length > 0) {
          const parts = Object.keys(ns.scope).map((k) => `${k}=${fmtScalar(ns.scope[k])}`);
          scopeText = `scope={${parts.join(", ")}}`;
        }
        pushNext(action, scopeText);
      }
    }
  }
  if (envelope.dont_know && typeof envelope.dont_know === "object" && Array.isArray(envelope.dont_know.next_steps)) {
    for (const ns of envelope.dont_know.next_steps) {
      if (!ns || typeof ns !== "object") continue;
      const action = fmtScalar(ns.action);
      let scopeText = "";
      if (ns.scope && typeof ns.scope === "object" && Object.keys(ns.scope).length > 0) {
        const parts = Object.keys(ns.scope).map((k) => `${k}=${fmtScalar(ns.scope[k])}`);
        scopeText = `scope={${parts.join(", ")}}`;
      }
      pushNext(action, scopeText);
    }
  }

  if (aggregatedNextSteps.length > 0) {
    out.push("NEXT STEPS (AGGREGATED)");
    out.push(SEPARATOR);
    for (const ns of aggregatedNextSteps) {
      if (ns.scope) out.push(`- ${ns.action}  ${ns.scope}`);
      else out.push(`- ${ns.action}`);
    }
  }

  return out.join("\n");
}

// ---- EpistemicDiff v1 renderer (comparison mode; text-first; no interpretation) ----

/**
 * @param {any} pointers
 * @returns {string}
 */
function fmtDiffPointersInline(pointers) {
  const p = pointers && typeof pointers === "object" ? pointers : {};
  const keys = ["store", "store_ref", "modality", "model", "component"];
  const parts = [];
  for (const k of keys) {
    if (k in p) parts.push(`${k}=${fmtScalar(p[k])}`);
  }
  return parts.length ? parts.join("  ") : "∅";
}

/**
 * @param {any} side
 * @returns {string[]}
 */
function fmtDiffSideLines(side) {
  const s = side && typeof side === "object" ? side : null;
  if (!s) return ["      ∅"];

  const lines = [];
  if (s.ts_utc) lines.push(`      ts_utc=${fmtScalar(s.ts_utc)}`);
  if (s.role) lines.push(`      role=${fmtScalar(s.role)}`);
  if (s.state) lines.push(`      state=${fmtScalar(s.state)}`);
  if (s.pointers && typeof s.pointers === "object") {
    lines.push(`      pointers: ${fmtDiffPointersInline(s.pointers)}`);
  }
  return lines.length ? lines : ["      ∅"];
}

/**
 * Render EpistemicDiff v1 object (as produced by steps/common/epistemic_diff.py).
 * This is visibility-only: structural change, no judgment.
 *
 * @param {{diff: any, nonActionDecisions: any[], errorCode?: string}} input
 * @returns {string}
 */
function renderEpistemicDiffText(input) {
  const diff = input && input.diff && typeof input.diff === "object" ? input.diff : null;
  const decisions = Array.isArray(input && input.nonActionDecisions) ? input.nonActionDecisions : [];
  const errorCode = input && typeof input.errorCode === "string" ? String(input.errorCode) : "";

  /** @type {string[]} */
  const out = [];

  out.push("GOODQ — JUSTIFICATION CHANNEL v1 (comparison)");
  out.push("EPISTEMIC DIFF v1");
  out.push(SEPARATOR);

  if (!diff) {
    out.push("comparison_outcome: dont_know");
    out.push(`explanation: ${errorCode || "compare_diff_missing"}`);
    out.push("");
  } else {
    out.push(`diff_version: ${fmtScalar(diff.diff_version)}`);
    out.push(`comparison_id: ${fmtScalar(diff.comparison_id)}`);
    out.push(`initiated_ts_utc: ${fmtScalar(diff.initiated_ts_utc)}`);
    out.push("");

    const identity = diff.identity_basis && typeof diff.identity_basis === "object" ? diff.identity_basis : {};
    out.push("IDENTITY BASIS");
    out.push(SEPARATOR);
    out.push(`type: ${fmtScalar(identity.type)}`);
    out.push(`matches: ${fmtScalar(identity.matches)}`);
    if (identity.mismatch_reason) out.push(`mismatch_reason: ${fmtScalar(identity.mismatch_reason)}`);
    out.push(`details: ${fmtInlineObject(identity.details || {})}`);
    out.push("");

    const a = diff.envelope_a && typeof diff.envelope_a === "object" ? diff.envelope_a : {};
    const b = diff.envelope_b && typeof diff.envelope_b === "object" ? diff.envelope_b : {};
    out.push("A / B");
    out.push(SEPARATOR);
    out.push(`A.sourceLabel: ${fmtScalar(a.sourceLabel)}`);
    out.push(`A.loaded_at_utc: ${fmtScalar(a.loaded_at_utc)}`);
    out.push(`B.sourceLabel: ${fmtScalar(b.sourceLabel)}`);
    out.push(`B.loaded_at_utc: ${fmtScalar(b.loaded_at_utc)}`);
    out.push("");

    out.push("SUMMARY");
    out.push(SEPARATOR);
    const outA = fmtScalar(a.outcome);
    const outB = fmtScalar(b.outcome);
    if (outA !== outB) out.push(`outcome: ${outA} → ${outB}`);
    else out.push(`outcome: ${outA}`);

    const ca = a.counts && typeof a.counts === "object" ? a.counts : {};
    const cb = b.counts && typeof b.counts === "object" ? b.counts : {};
    out.push(
      `counts: A(candidates=${fmtScalar(ca.candidates)} evidence=${fmtScalar(ca.evidence_hits)} decisions=${fmtScalar(
        ca.non_action_decisions
      )})  B(candidates=${fmtScalar(cb.candidates)} evidence=${fmtScalar(cb.evidence_hits)} decisions=${fmtScalar(
        cb.non_action_decisions
      )})`
    );
    out.push(`diff_total: ${fmtScalar(diff.diff_total)}`);
    out.push("");

    out.push("CATEGORY SUMMARIES");
    out.push(SEPARATOR);
    const summaries = Array.isArray(diff.category_summaries) ? diff.category_summaries : [];
    if (summaries.length === 0) {
      out.push("  ∅");
    } else {
      for (const cs of summaries) {
        const cat = cs && typeof cs === "object" ? cs : {};
        out.push(
          `- category=${fmtScalar(cat.category)}  presence=${fmtScalar(cat.presence)}  diff_count=${fmtScalar(
            cat.diff_count
          )}`
        );
      }
    }
    out.push("");

    out.push("DIFFS");
    out.push(SEPARATOR);
    const diffs = Array.isArray(diff.diffs) ? diff.diffs : [];
    if (diffs.length === 0) {
      out.push("  ∅");
      out.push("");
    } else {
      for (let i = 0; i < diffs.length; i++) {
        const d = diffs[i] && typeof diffs[i] === "object" ? diffs[i] : {};
        const key = d.key && typeof d.key === "object" ? d.key : {};
        out.push(`[${i + 1}] category=${fmtScalar(d.category)}  diff_code=${fmtScalar(d.diff_code)}`);
        out.push(`    key: type=${fmtScalar(key.type)}  value=${fmtScalar(key.value)}`);

        out.push("    A:");
        out.push(...fmtDiffSideLines(d.a));
        out.push("    B:");
        out.push(...fmtDiffSideLines(d.b));
        out.push("");
      }
      if (out[out.length - 1] === "") out.pop();
      out.push("");
    }

    out.push("ABSENCE");
    out.push(SEPARATOR);
    const absent = summaries.filter((cs) => cs && typeof cs === "object" && cs.presence === "absent_both");
    if (absent.length === 0) {
      out.push("  ∅");
    } else {
      for (const cs of absent) {
        out.push(`- category=${fmtScalar(cs.category)}: ∅`);
      }
    }
    out.push("");
  }

  // NON-ACTION DECISIONS (if any)
  if (decisions.length > 0) {
    out.push("NON-ACTION DECISIONS");
    out.push(SEPARATOR);
    for (let i = 0; i < decisions.length; i++) {
      const d = decisions[i] && typeof decisions[i] === "object" ? decisions[i] : {};
      out.push(`${i + 1}) domain=${fmtScalar(d.domain)}  required_response=${fmtScalar(d.required_response)}`);
      out.push(`   condition=${fmtScalar(d.condition)}`);
      out.push(`   rationale=${fmtInlineObject(d.rationale || {})}`);
      out.push("");
    }
    if (out[out.length - 1] === "") out.pop();
  }

  return out.join("\n");
}

/**
 * @param {any} envelope
 * @param {any[]} decisions
 * @param {string} lastRenderTs
 * @returns {string}
 */
function buildDiagnosticsText(envelope, decisions, lastRenderTs) {
  const candidates = Array.isArray(envelope.candidates) ? envelope.candidates : [];

  // Flatten evidence in the same order the renderer would display it.
  /** @type {any[]} */
  const evidenceHits = [];
  if (String(envelope.outcome) === "answer") {
    for (const cand of candidates) {
      const evidence = Array.isArray(cand.evidence) ? cand.evidence : [];
      for (const ev of evidence) evidenceHits.push(ev);
    }
  } else if (String(envelope.outcome) === "dont_know" && envelope.dont_know && typeof envelope.dont_know === "object") {
    const dkEvidence = Array.isArray(envelope.dont_know.evidence) ? envelope.dont_know.evidence : [];
    for (const ev of dkEvidence) evidenceHits.push(ev);
  }

  // Aggregate limits in the same sources/order as the renderer.
  /** @type {string[]} */
  const aggregatedLimits = [];
  const seenLimit = new Set();
  for (const cand of candidates) {
    if (Array.isArray(cand.limits)) {
      for (const l of cand.limits) {
        const s = String(l);
        if (!seenLimit.has(s)) {
          aggregatedLimits.push(s);
          seenLimit.add(s);
        }
      }
    }
    const evidence = Array.isArray(cand.evidence) ? cand.evidence : [];
    for (const ev of evidence) {
      if (ev && typeof ev === "object" && Array.isArray(ev.limits)) {
        for (const l of ev.limits) {
          const s = String(l);
          if (!seenLimit.has(s)) {
            aggregatedLimits.push(s);
            seenLimit.add(s);
          }
        }
      }
    }
  }
  if (envelope.dont_know && typeof envelope.dont_know === "object" && Array.isArray(envelope.dont_know.limits)) {
    for (const l of envelope.dont_know.limits) {
      const s = String(l);
      if (!seenLimit.has(s)) {
        aggregatedLimits.push(s);
        seenLimit.add(s);
      }
    }
  }

  // Aggregate next steps (deduped) using the same key shape as the renderer.
  /** @type {{action: string, scopeText: string}[]} */
  const aggregatedNextSteps = [];
  const seenNext = new Set();
  const pushNext = (action, scopeText) => {
    const key = `${action}::${scopeText || ""}`;
    if (seenNext.has(key)) return;
    seenNext.add(key);
    aggregatedNextSteps.push({ action, scopeText });
  };
  for (const cand of candidates) {
    if (Array.isArray(cand.next_steps)) {
      for (const ns of cand.next_steps) {
        if (!ns || typeof ns !== "object") continue;
        const action = fmtScalar(ns.action);
        let scopeText = "";
        if (ns.scope && typeof ns.scope === "object" && Object.keys(ns.scope).length > 0) {
          const parts = Object.keys(ns.scope).map((k) => `${k}=${fmtScalar(ns.scope[k])}`);
          scopeText = `scope={${parts.join(", ")}}`;
        }
        pushNext(action, scopeText);
      }
    }
  }
  if (envelope.dont_know && typeof envelope.dont_know === "object" && Array.isArray(envelope.dont_know.next_steps)) {
    for (const ns of envelope.dont_know.next_steps) {
      if (!ns || typeof ns !== "object") continue;
      const action = fmtScalar(ns.action);
      let scopeText = "";
      if (ns.scope && typeof ns.scope === "object" && Object.keys(ns.scope).length > 0) {
        const parts = Object.keys(ns.scope).map((k) => `${k}=${fmtScalar(ns.scope[k])}`);
        scopeText = `scope={${parts.join(", ")}}`;
      }
      pushNext(action, scopeText);
    }
  }

  const integrity = window.GoodQIntegrity || null;
  const warnings = [];
  if (integrity && typeof integrity.validateEnvelope === "function") warnings.push(...integrity.validateEnvelope(envelope));
  if (integrity && typeof integrity.validateNonAction === "function") warnings.push(...integrity.validateNonAction(decisions));

  let fingerprint = "fnv1a32:00000000";
  if (integrity && typeof integrity.computeOrderFingerprint === "function") {
    fingerprint = integrity.computeOrderFingerprint(evidenceHits);
  }

  const lines = [];
  lines.push("DIAGNOSTICS (toggle: D)");
  lines.push(SEPARATOR);
  lines.push(`read_model_version: ${fmtScalar(envelope.read_model_version)}`);
  lines.push(`retrieval_context: ${envelope.retrieval_context ? String(envelope.retrieval_context) : "— (not provided)"}`);
  lines.push(`outcome: ${fmtScalar(envelope.outcome)}`);
  lines.push(
    `counts: candidates=${candidates.length} evidence=${evidenceHits.length} limits=${aggregatedLimits.length} next_steps=${aggregatedNextSteps.length}`
  );
  lines.push(`order_fingerprint: ${fingerprint}`);
  lines.push(`last_render_ts: ${lastRenderTs}`);
  lines.push("warnings:");
  if (warnings.length === 0) {
    lines.push("  ∅");
  } else {
    for (const w of warnings) lines.push(`  - ${String(w)}`);
  }
  return lines.join("\n");
}

/**
 * @param {any} diff
 * @returns {string[]}
 */
function validateEpistemicDiff(diff) {
  /** @type {string[]} */
  const warnings = [];
  if (!diff || typeof diff !== "object") return ["diff_invalid: not an object"];
  if (typeof diff.diff_version !== "number") warnings.push("diff_missing_version");
  if (typeof diff.comparison_id !== "string") warnings.push("diff_missing_comparison_id");
  if (!Array.isArray(diff.category_summaries)) warnings.push("diff_missing_category_summaries");
  if (!Array.isArray(diff.diffs)) warnings.push("diff_missing_diffs");
  return warnings;
}

/**
 * @param {any} diff
 * @param {any[]} decisions
 * @param {string} lastRenderTs
 * @returns {string}
 */
function buildCompareDiagnosticsText(diff, decisions, lastRenderTs) {
  const integrity = window.GoodQIntegrity || null;
  const warnings = [];
  warnings.push(...validateEpistemicDiff(diff));
  if (integrity && typeof integrity.validateNonAction === "function") warnings.push(...integrity.validateNonAction(decisions));

  const a = diff && diff.envelope_a && typeof diff.envelope_a === "object" ? diff.envelope_a : {};
  const b = diff && diff.envelope_b && typeof diff.envelope_b === "object" ? diff.envelope_b : {};
  const fpA = a && a.order_fingerprint ? String(a.order_fingerprint) : "";
  const fpB = b && b.order_fingerprint ? String(b.order_fingerprint) : "";
  const id = diff && diff.identity_basis && typeof diff.identity_basis === "object" ? diff.identity_basis : {};

  const lines = [];
  lines.push("DIAGNOSTICS (toggle: D)");
  lines.push(SEPARATOR);
  lines.push("ui_mode: compare");
  lines.push(`diff_version: ${fmtScalar(diff && diff.diff_version)}`);
  lines.push(`identity_matches: ${fmtScalar(id && id.matches)}`);
  lines.push(`diff_total: ${fmtScalar(diff && diff.diff_total)}`);
  lines.push(`order_fingerprint: a=${fpA}  b=${fpB}`);
  lines.push(`last_render_ts: ${lastRenderTs}`);
  lines.push("warnings:");
  if (warnings.length === 0) {
    lines.push("  ∅");
  } else {
    for (const w of warnings) lines.push(`  - ${String(w)}`);
  }
  return lines.join("\n");
}

/**
 * @returns {{overlay: HTMLDivElement, pre: HTMLPreElement}}
 */
function ensureDiagnosticsOverlay() {
  let overlay = document.getElementById("jc-diagnostics-overlay");
  if (overlay && overlay instanceof HTMLDivElement) {
    const pre = overlay.querySelector("pre");
    if (pre && pre instanceof HTMLPreElement) return { overlay, pre };
  }

  overlay = document.createElement("div");
  overlay.id = "jc-diagnostics-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-label", "Diagnostics overlay");

  // Minimal inline styling (no framework, no theming).
  overlay.style.position = "fixed";
  overlay.style.right = "1rem";
  overlay.style.bottom = "1rem";
  overlay.style.maxWidth = "52rem";
  overlay.style.maxHeight = "70vh";
  overlay.style.overflow = "auto";
  overlay.style.padding = "0.75rem 1rem";
  overlay.style.border = "1px solid #ccc";
  overlay.style.background = "rgba(255, 255, 255, 0.97)";
  overlay.style.display = "none";
  overlay.style.zIndex = "9999";

  const pre = document.createElement("pre");
  pre.id = "jc-diagnostics-text";
  pre.style.margin = "0";

  overlay.appendChild(pre);
  document.body.appendChild(overlay);
  return { overlay, pre };
}

/**
 * @param {HTMLDivElement} overlay
 */
function toggleDiagnosticsOverlay(overlay) {
  overlay.style.display = overlay.style.display === "none" ? "block" : "none";
}

// Hardcoded example input (mockup data); no fetching or API calls.
const EXAMPLE = {
  envelope: {
    read_model_version: 1,
    question: { text: "Is there music playing in scene 0007?" },
    retrieval_context: "human.ui.search",
    outcome: "answer",
    candidates: [
      {
        candidate_id: "a2",
        state: "conflicted",
        answer_text: "Evidence is mixed about whether music is present in scene 0007.",
        confidence: { intrinsic: null, source: null, temporal: null, consistency: null, overall: null },
        limits: ["conflict:audio_support_vs_text_contradict"],
        next_steps: [
          {
            action: "inspect scene audio clip",
            rationale: "Resolve conflict by direct listening/inspection",
            scope: { video_id: "video_001", scene_id: "0007" },
          },
        ],
        evidence: [
          {
            role: "support",
            store: "qdrant",
            store_ref: "goodq_audio",
            embedding_id: "8b1a...",
            score: 0.08,
            payload: { video_id: "video_001", scene_id: "0007", model: "clap" },
            provenance: {
              provenance_version: 1,
              ts_utc: "2025-12-17T04:12:03Z",
              video_id: "video_001",
              scene_id: "0007",
              modality: "audio",
              model: "clap",
              component: "audio_embed_clap",
              attempted: true,
              committed: true,
              reason: "—",
              targets: {
                qdrant: { attempted: true, committed: true, ref: "goodq_audio" },
                faiss: { attempted: true, committed: true, ref: "goodq_audio.index" },
              },
            },
            confidence: {
              temporal: 0.61,
              temporal_explanation: "age_bucket: 30-90d",
              intrinsic: null,
              source: null,
              consistency: null,
              overall: null,
            },
            limits: [],
          },
          {
            role: "contradict",
            store: "qdrant",
            store_ref: "goodq_text",
            embedding_id: "4f22...",
            score: 0.13,
            payload: { video_id: "video_001", scene_id: "0007", model: "all-MiniLM-L6-v2", transcript: "[REDACTED]" },
            provenance: {
              provenance_version: 1,
              ts_utc: "2025-12-20T10:31:55Z",
              video_id: "video_001",
              scene_id: "0007",
              modality: "text",
              model: "all-MiniLM-L6-v2",
              component: "text_embed",
              attempted: true,
              committed: true,
              reason: "—",
              targets: {
                qdrant: { attempted: true, committed: true, ref: "goodq_text" },
              },
            },
            confidence: {
              temporal: 0.92,
              temporal_explanation: "age_bucket: 0-7d",
              intrinsic: null,
              source: null,
              consistency: null,
              overall: null,
            },
            limits: ["payload_redacted:transcript"],
          },
        ],
      },
    ],
  },
  nonActionDecisions: [
    {
      contract_version: 1,
      domain: "act",
      condition: "act_blocked_on_conflict",
      required_response: "defer",
      rationale: { candidate_state: "conflicted" },
    },
  ],
};

window.GoodQJustification = {
  renderJustificationText,
  EXAMPLE,
};

// ---- State discipline harness (no API calls; no actions; no semantics changes) ----

const GOODQ_STATE_HISTORY_MAX = 10;
let GoodQState = null;
/** @type {any[]} */
const GoodQStateHistory = [];

let _overlayRef = null;
let _overlayPreRef = null;
let _keyListenerBound = false;
let _lastInspectorDiagnostics = { order_fingerprint: "", warnings: [] };

/**
 * @param {any} envelope
 * @returns {number}
 */
function countEvidenceHits(envelope) {
  if (!envelope || typeof envelope !== "object") return 0;
  const outcome = String(envelope.outcome || "");
  if (outcome === "answer") {
    const candidates = Array.isArray(envelope.candidates) ? envelope.candidates : [];
    let n = 0;
    for (const cand of candidates) {
      const evidence = cand && typeof cand === "object" && Array.isArray(cand.evidence) ? cand.evidence : [];
      n += evidence.length;
    }
    return n;
  }
  if (outcome === "dont_know" && envelope.dont_know && typeof envelope.dont_know === "object") {
    const dkEvidence = Array.isArray(envelope.dont_know.evidence) ? envelope.dont_know.evidence : [];
    return dkEvidence.length;
  }
  return 0;
}

/**
 * Extract a minimal, safe diagnostics snapshot (no raw payloads, no paths).
 * @param {string} diagnosticsText
 * @returns {{order_fingerprint: string, warnings: string[]}}
 */
function extractInspectorDiagnostics(diagnosticsText) {
  const txt = String(diagnosticsText || "");
  const m = txt.match(/^order_fingerprint:\s*(.+)$/m);
  const order_fingerprint = m ? m[1].trim() : "";

  /** @type {string[]} */
  const warnings = [];
  const seen = new Set();
  let inWarnings = false;
  for (const line of txt.split("\n")) {
    const trimmed = String(line || "").trim();
    if (!inWarnings) {
      if (trimmed === "warnings:") inWarnings = true;
      continue;
    }
    if (!trimmed || trimmed === "∅") continue;
    const wm = trimmed.match(/^-\s*(.+)$/);
    if (!wm) continue;
    const raw = wm[1];
    const code = String(raw).split(":")[0].trim();
    if (!code || seen.has(code)) continue;
    seen.add(code);
    warnings.push(code);
  }
  return { order_fingerprint, warnings };
}

/**
 * Observer-only hook. Never blocks rendering.
 * @param {string} eventType
 * @param {string} source
 * @param {any} state
 * @param {{order_fingerprint: string, warnings: string[]}} diagnostics
 */
function emitInspectorEvent(eventType, source, state, diagnostics) {
  try {
    const inspector = window.GoodQInspector;
    if (!inspector || typeof inspector.observe !== "function") return;
    if (typeof inspector.isEnabled === "function" && !inspector.isEnabled()) return;

    const envelope = state && state.envelope ? state.envelope : {};
    const candidates = Array.isArray(envelope.candidates) ? envelope.candidates : [];
    const nonActionCount = state && Array.isArray(state.nonActionDecisions) ? state.nonActionDecisions.length : 0;
    const diag = diagnostics && typeof diagnostics === "object" ? diagnostics : { order_fingerprint: "", warnings: [] };
    const view = state && typeof state.view === "string" ? state.view : GOODQ_UI_VIEW_TEXT;
    const projection = state && state.projection && typeof state.projection === "object" ? state.projection : {};

    inspector.observe({
      ts_utc: new Date().toISOString(),
      ui_version: GOODQ_UI_VERSION,
      event_type: String(eventType || ""),
      source: String(source || ""),
      last_render_ts_utc: state && typeof state.updatedAt === "string" ? state.updatedAt : "",
      view,
      counts: {
        candidates: candidates.length,
        evidence_hits: countEvidenceHits(envelope),
        non_action_decisions: nonActionCount,
      },
      diagnostics: {
        order_fingerprint: String(diag.order_fingerprint || ""),
        warnings: Array.isArray(diag.warnings) ? diag.warnings : [],
      },
      projection: {
        view,
        mode: state && String(state.mode || "") === "compare" ? "compare" : "single",
        focus_hash: hashTokenForInspector(projection.focus_key),
        window_start_s: toFiniteNumber(projection.window_start_s),
        window_end_s: toFiniteNumber(projection.window_end_s),
        cursor_s: toFiniteNumber(projection.cursor_s),
      },
    });
  } catch {
    // Best-effort only.
  }
}

/**
 * @param {any} obj
 * @param {WeakSet<object>} [seen]
 * @returns {any}
 */
function deepFreeze(obj, seen) {
  if (!obj || typeof obj !== "object") return obj;
  const s = seen || new WeakSet();
  if (s.has(obj)) return obj;
  s.add(obj);
  if (Array.isArray(obj)) {
    for (const item of obj) deepFreeze(item, s);
  } else {
    for (const k of Object.keys(obj)) deepFreeze(obj[k], s);
  }
  try {
    Object.freeze(obj);
  } catch {
    // Best-effort only.
  }
  return obj;
}

/**
 * @param {any} state
 */
function assertStateShape(state) {
  if (!state || typeof state !== "object") throw new Error("GoodQState invalid: not an object");
  if (!("envelope" in state)) throw new Error("GoodQState invalid: missing envelope");
  if (!("nonActionDecisions" in state)) throw new Error("GoodQState invalid: missing nonActionDecisions");
  if (!("sourceLabel" in state)) throw new Error("GoodQState invalid: missing sourceLabel");

  if (!state.envelope || typeof state.envelope !== "object") throw new Error("GoodQState invalid: envelope must be object");
  if (!Array.isArray(state.nonActionDecisions)) throw new Error("GoodQState invalid: nonActionDecisions must be array");
  if (typeof state.sourceLabel !== "string" || !state.sourceLabel.trim()) {
    throw new Error("GoodQState invalid: sourceLabel must be non-empty string");
  }

  if ("mode" in state) {
    const m = String(state.mode || "");
    if (m && m !== "single" && m !== "compare") throw new Error("GoodQState invalid: mode must be single|compare");
    if (m === "compare") {
      if (!state.compare || typeof state.compare !== "object") throw new Error("GoodQState invalid: compare must be object");
      const hasDiff = "diff" in state.compare && state.compare.diff && typeof state.compare.diff === "object";
      const hasErr = "error_code" in state.compare && typeof state.compare.error_code === "string";
      if (!hasDiff && !hasErr) throw new Error("GoodQState invalid: compare requires diff or error_code");
    }
  }

  if ("view" in state) {
    const v = String(state.view || "");
    if (v && v !== GOODQ_UI_VIEW_TEXT && v !== GOODQ_UI_VIEW_PROJECT) {
      throw new Error("GoodQState invalid: view must be text|project");
    }
  }

  if ("projection" in state) {
    const p = state.projection;
    if (p !== null && p !== undefined && typeof p !== "object") {
      throw new Error("GoodQState invalid: projection must be object|null");
    }
  }
}

function ensureOverlayRefs() {
  const { overlay, pre } = ensureDiagnosticsOverlay();
  _overlayRef = overlay;
  _overlayPreRef = pre;
}

// ---- Readability view (visibility-only; canonical text remains unchanged) ----

/**
 * @param {Element} el
 */
function clearChildren(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
}

/**
 * @param {string} line
 * @returns {boolean}
 */
function isSectionHeaderLine(line) {
  if (line === "QUERY") return true;
  if (line === "EPISTEMIC SUMMARY") return true;
  if (line === "EPISTEMIC DIFF v1") return true;
  if (line === "IDENTITY BASIS") return true;
  if (line === "A / B") return true;
  if (line === "SUMMARY") return true;
  if (line === "CATEGORY SUMMARIES") return true;
  if (line === "DIFFS") return true;
  if (line === "ABSENCE") return true;
  if (line === "NON-ACTION DECISIONS") return true;
  if (line.startsWith("CANDIDATE ")) return true;
  if (line.startsWith("EVIDENCE (")) return true;
  if (line === "DONT-KNOW DETAIL") return true;
  if (line === "WHAT’S MISSING (AGGREGATED LIMITS)") return true;
  if (line === "NEXT STEPS (AGGREGATED)") return true;
  return false;
}

/**
 * @param {Element} container
 * @param {string} headerText
 * @returns {{section: HTMLElement, header: HTMLElement, body: HTMLElement}}
 */
function createSection(container, headerText) {
  const section = document.createElement("section");
  section.className = "jc-section";

  const header = document.createElement("div");
  header.className = "jc-section-header";
  header.tabIndex = 0;
  header.textContent = headerText;

  const body = document.createElement("div");
  body.className = "jc-section-body";

  section.appendChild(header);
  section.appendChild(body);
  container.appendChild(section);
  return { section, header, body };
}

/**
 * @param {Element} body
 * @param {string[]} lines
 */
function appendPreBlock(body, lines) {
  if (!lines || lines.length === 0) return;
  const pre = document.createElement("pre");
  pre.className = "jc-block";
  pre.textContent = lines.join("\n");
  body.appendChild(pre);
}

/**
 * @param {Element} body
 * @param {string} summaryLine
 * @param {string[]} bodyLines
 */
function appendEvidenceBlock(body, summaryLine, bodyLines) {
  const details = document.createElement("details");
  details.className = "jc-evidence";
  details.open = false;

  const summary = document.createElement("summary");
  summary.className = "jc-evidence-summary";
  summary.tabIndex = 0;
  summary.textContent = summaryLine;

  const pre = document.createElement("pre");
  pre.className = "jc-evidence-body";
  pre.textContent = bodyLines.join("\n");

  details.appendChild(summary);
  details.appendChild(pre);
  body.appendChild(details);
}

/**
 * Render a structured, navigable view derived from the canonical rendered text.
 * This is visibility-only; it must not alter the canonical output string or order.
 *
 * @param {string} renderedText
 */
function renderStructuredView(renderedText) {
  const container = document.getElementById("jc-view");
  if (!container) return;
  clearChildren(container);

  const lines = String(renderedText || "").split("\n");

  // Header block: first line as a section header, then metadata lines until blank line.
  let idx = 0;
  const titleLine = lines[idx] || "";
  const headerSection = createSection(container, titleLine);
  idx++;

  /** @type {string[]} */
  const headerMeta = [];
  while (idx < lines.length && lines[idx] !== "") {
    headerMeta.push(lines[idx]);
    idx++;
  }
  appendPreBlock(headerSection.body, headerMeta);
  // Consume the blank separator line after header meta.
  if (idx < lines.length && lines[idx] === "") idx++;

  /** @type {{body: HTMLElement} | null} */
  let current = null;
  /** @type {string[]} */
  let buf = [];

  const flush = () => {
    if (!current) return;
    appendPreBlock(current.body, buf);
    buf = [];
  };

  while (idx < lines.length) {
    const line = lines[idx];

    if (isSectionHeaderLine(line)) {
      if (!current) {
        // If no section yet, create an implicit section before the first header.
        current = createSection(container, line);
      } else {
        flush();
        current = createSection(container, line);
      }
      idx++;
      continue;
    }

    // Evidence blocks: convert each evidence hit into a collapsible <details>.
    const m = line.match(/^\[(\d+)\]\s+role=/);
    if (m) {
      if (!current) current = createSection(container, "EVIDENCE");
      flush();

      const summaryLine = line;
      idx++;
      /** @type {string[]} */
      const bodyLines = [];
      while (idx < lines.length) {
        const l2 = lines[idx];
        if (l2 === "") break;
        if (l2.match(/^\[(\d+)\]\s+role=/)) break;
        if (isSectionHeaderLine(l2)) break;
        bodyLines.push(l2);
        idx++;
      }

      appendEvidenceBlock(current.body, summaryLine, bodyLines);

      // Consume a single blank line after the evidence block (spacing only).
      if (idx < lines.length && lines[idx] === "") idx++;
      continue;
    }

    if (!current) {
      current = createSection(container, "OUTPUT");
    }

    buf.push(line);
    idx++;
  }

  flush();
}

/**
 * Projection view renderer (read-only; must not alter canonical <pre> output).
 * Implemented per `docs/architecture/VISUAL_PROJECTION_CONTRACT_v1.md`.
 *
 * @param {any} state
 * @param {string} renderedText canonical text (unchanged)
 */
function renderProjectionView(state, renderedText) {
  const container = document.getElementById("jc-view");
  if (!container) return;
  clearChildren(container);

  const mode = state && String(state.mode || "") === "compare" ? "compare" : "single";
  if (mode === "compare") {
    renderProjectionCompare(container, state);
  } else {
    renderProjectionSingle(container, state);
  }
}

/**
 * @param {Element} container
 * @param {any} state
 */
function renderProjectionSingle(container, state) {
  const env = state && state.envelope && typeof state.envelope === "object" ? state.envelope : {};
  const decisions = state && Array.isArray(state.nonActionDecisions) ? state.nonActionDecisions : [];
  const model = buildProjectionModel(env);
  const viewState = resolveProjectionView(model, state && state.projection);

  const root = document.createElement("div");
  root.className = "jc-proj";
  container.appendChild(root);

  const outcome = safeOneLine(env.outcome || "unknown");
  const retrievalContext = safeOneLine(env.retrieval_context || "");
  const q = env.question && typeof env.question === "object" ? safeOneLine(env.question.text || "") : "";
  const sourceLabel = state && typeof state.sourceLabel === "string" ? safeOneLine(state.sourceLabel) : "";

  const header = document.createElement("pre");
  header.className = "jc-proj-header";
  header.textContent = [
    "SITUATIONAL AWARENESS PROJECTION v1 (read-only)",
    SEPARATOR,
    `source=${sourceLabel || "—"}  retrieval_context=${retrievalContext || "—"}  outcome=${outcome || "—"}`,
    `question=${q || "∅"}`,
    `candidates=${model.rails.length}  evidence_hits=${countEvidenceHits(env)}  non_action_decisions=${decisions.length}`,
  ].join("\n");
  root.appendChild(header);

  const focusRow = document.createElement("div");
  focusRow.className = "jc-proj-focus";
  const focusLabel = document.createElement("span");
  focusLabel.className = "jc-proj-focus-label";
  focusLabel.textContent = "lock-on:";

  const focusSelect = document.createElement("select");
  focusSelect.className = "jc-proj-focus-select";
  const optNone = document.createElement("option");
  optNone.value = "";
  optNone.textContent = "∅";
  focusSelect.appendChild(optNone);
  for (const k of model.focus_keys) {
    const opt = document.createElement("option");
    opt.value = k;
    opt.textContent = k;
    focusSelect.appendChild(opt);
  }
  focusSelect.value = viewState.focus_key || "";
  focusSelect.addEventListener("change", () => {
    const v = safeOneLine(focusSelect.value);
    updateProjectionState({ focus_key: v || null }, "entity_lock_on", "projection_focus");
  });
  focusRow.appendChild(focusLabel);
  focusRow.appendChild(focusSelect);
  const focusNote = document.createElement("span");
  focusNote.className = "jc-proj-focus-note";
  focusNote.textContent = "focus ≠ filter (others remain visible)";
  focusRow.appendChild(focusNote);
  root.appendChild(focusRow);

  const timeSection = document.createElement("div");
  timeSection.className = "jc-proj-time";
  root.appendChild(timeSection);

  if (!model.has_time) {
    const absent = document.createElement("div");
    absent.className = "jc-proj-absent";
    absent.textContent = "TIME AXIS: ∅ (no scene start/end fields in envelope payloads)";
    timeSection.appendChild(absent);

    const anchorWrap = document.createElement("div");
    anchorWrap.className = "jc-proj-rails";
    timeSection.appendChild(anchorWrap);

    const rails = model.rails.length
      ? model.rails
      : [{ label: outcome === "dont_know" ? "dont_know" : "candidate", candidate_id: "", state: outcome, segments: [] }];

    for (const r of rails) {
      const row = document.createElement("div");
      row.className = "jc-proj-row";

      const label = document.createElement("div");
      label.className = "jc-proj-row-label";
      label.textContent = safeOneLine(r.label || "candidate");

      const rail = document.createElement("div");
      rail.className = "jc-proj-rail jc-proj-rail-anchors";

      const segs = Array.isArray(r.segments) ? r.segments : [];
      if (!segs.length) {
        const none = document.createElement("div");
        none.className = "jc-proj-gap";
        none.textContent = "∅";
        rail.appendChild(none);
      } else {
        const stateClass = projectionStateClass(r.state || outcome);
        for (const seg of segs) {
          if (!seg || typeof seg !== "object") continue;
          const el = document.createElement("div");
          el.className = `jc-proj-anchor ${stateClass}`;
          if (seg.roles && seg.roles.support > 0 && seg.roles.contradict > 0) el.className += " has-contradiction";
          if (viewState.focus_key) {
            const isFocused =
              Array.isArray(seg.focus_tokens) && seg.focus_tokens.includes(viewState.focus_key);
            el.className += isFocused ? " focused" : " deemphasized";
          }
          el.title = safeOneLine(`${seg.key}  support=${seg.roles.support}  contradict=${seg.roles.contradict}`);
          el.textContent = safeOneLine(seg.scene_id || "scene");
          rail.appendChild(el);
        }
      }

      row.appendChild(label);
      row.appendChild(rail);
      anchorWrap.appendChild(row);
    }
  } else {
    const railWrap = document.createElement("div");
    railWrap.className = "jc-proj-rails";
    timeSection.appendChild(railWrap);

    const viewStart = typeof viewState.window_start_s === "number" ? viewState.window_start_s : model.time_min_s;
    const viewEnd = typeof viewState.window_end_s === "number" ? viewState.window_end_s : model.time_max_s;
    const span = Math.max(0.0001, viewEnd - viewStart);
    const rails = model.rails.length
      ? model.rails
      : [{ label: outcome === "dont_know" ? "dont_know" : "candidate", candidate_id: "", state: outcome, segments: [] }];

    for (const r of rails) {
      const row = document.createElement("div");
      row.className = "jc-proj-row";

      const label = document.createElement("div");
      label.className = "jc-proj-row-label";
      label.textContent = safeOneLine(r.label || "candidate");

      const rail = document.createElement("div");
      rail.className = "jc-proj-rail";

      const segs = Array.isArray(r.segments) ? r.segments : [];
      const stateClass = projectionStateClass(r.state || outcome);

      // Render segments (time-known only). Preserve source order; no sorting.
      const unknownSegs = [];
      let prevVisibleEnd = null;
      for (const seg of segs) {
        if (!seg || typeof seg !== "object") continue;
        if (!seg.time) {
          unknownSegs.push(seg);
          continue;
        }
        if (typeof seg.time.start_s !== "number" || typeof seg.time.end_s !== "number") continue;

        const segStart = seg.time.start_s;
        const segEnd = seg.time.end_s;
        const visibleStart = Math.max(segStart, viewStart);
        const visibleEnd = Math.min(segEnd, viewEnd);
        if (visibleEnd <= visibleStart) continue;

        if (prevVisibleEnd !== null && visibleStart > prevVisibleEnd) {
          const gap = document.createElement("div");
          gap.className = "jc-proj-gap";
          const gLeft = ((prevVisibleEnd - viewStart) / span) * 100;
          const gWidth = ((visibleStart - prevVisibleEnd) / span) * 100;
          gap.style.left = `${gLeft}%`;
          gap.style.width = `${Math.max(0, gWidth)}%`;
          gap.textContent = "∅";
          rail.appendChild(gap);
        }

        const el = document.createElement("div");
        el.className = `jc-proj-seg ${stateClass}`;
        if (seg.roles && seg.roles.support > 0 && seg.roles.contradict > 0) el.className += " has-contradiction";
        if (viewState.focus_key) {
          const isFocused =
            Array.isArray(seg.focus_tokens) && seg.focus_tokens.includes(viewState.focus_key);
          el.className += isFocused ? " focused" : " deemphasized";
        }
        const left = ((visibleStart - viewStart) / span) * 100;
        const width = ((visibleEnd - visibleStart) / span) * 100;
        el.style.left = `${left}%`;
        el.style.width = `${Math.max(0.25, width)}%`;
        el.title = safeOneLine(`${seg.key}  support=${seg.roles.support}  contradict=${seg.roles.contradict}`);
        el.textContent = safeOneLine(seg.scene_id || "scene");
        rail.appendChild(el);

        prevVisibleEnd = visibleEnd;
      }

      if (typeof viewState.cursor_s === "number") {
        const cursor = document.createElement("div");
        cursor.className = "jc-proj-cursor";
        const cx = ((viewState.cursor_s - viewStart) / span) * 100;
        cursor.style.left = `${clamp(cx, 0, 100)}%`;
        rail.appendChild(cursor);
      }

      rail.addEventListener("click", (e) => {
        if (!e) return;
        const rect = rail.getBoundingClientRect();
        const x = clamp((e.clientX - rect.left) / Math.max(1, rect.width), 0, 1);
        const t = viewStart + x * span;
        updateProjectionState({ cursor_s: t }, "time_scrubbed", "projection_scrub");
      });

      row.appendChild(label);
      row.appendChild(rail);
      railWrap.appendChild(row);

      if (unknownSegs.length) {
        const uRow = document.createElement("div");
        uRow.className = "jc-proj-row jc-proj-row-unknown";

        const uLabel = document.createElement("div");
        uLabel.className = "jc-proj-row-label";
        uLabel.textContent = "∅ time";

        const uRail = document.createElement("div");
        uRail.className = "jc-proj-rail jc-proj-rail-anchors";

        for (const seg of unknownSegs) {
          const el = document.createElement("div");
          el.className = `jc-proj-anchor ${stateClass}`;
          if (seg.roles && seg.roles.support > 0 && seg.roles.contradict > 0) el.className += " has-contradiction";
          if (viewState.focus_key) {
            const isFocused =
              Array.isArray(seg.focus_tokens) && seg.focus_tokens.includes(viewState.focus_key);
            el.className += isFocused ? " focused" : " deemphasized";
          }
          el.title = safeOneLine(`${seg.key}  support=${seg.roles.support}  contradict=${seg.roles.contradict}`);
          el.textContent = safeOneLine(seg.scene_id || "scene");
          uRail.appendChild(el);
        }

        uRow.appendChild(uLabel);
        uRow.appendChild(uRail);
        railWrap.appendChild(uRow);
      }
    }
  }

  const nonAction = document.createElement("pre");
  nonAction.className = "jc-proj-nonaction";
  const naLines = [];
  naLines.push("NON-ACTION (visible constraints)");
  naLines.push(SEPARATOR);
  if (!decisions.length) {
    naLines.push("∅");
  } else {
    for (const d of decisions) {
      const o = d && typeof d === "object" ? d : {};
      naLines.push(
        `- domain=${safeOneLine(o.domain || "—")}  condition=${safeOneLine(o.condition || "—")}  required_response=${safeOneLine(
          o.required_response || "—"
        )}`
      );
    }
  }
  nonAction.textContent = naLines.join("\n");
  root.appendChild(nonAction);
}

/**
 * @param {Element} container
 * @param {any} state
 */
function renderProjectionCompare(container, state) {
  const diff =
    state && state.compare && typeof state.compare === "object" && state.compare.diff && typeof state.compare.diff === "object"
      ? state.compare.diff
      : null;
  const decisions = state && Array.isArray(state.nonActionDecisions) ? state.nonActionDecisions : [];
  const compareError =
    state && state.compare && typeof state.compare === "object" && typeof state.compare.error_code === "string"
      ? safeOneLine(state.compare.error_code)
      : "";

  const root = document.createElement("div");
  root.className = "jc-proj jc-proj-compare";
  container.appendChild(root);

  const header = document.createElement("pre");
  header.className = "jc-proj-header";
  header.textContent = [
    "SITUATIONAL AWARENESS PROJECTION v1 (compare; read-only)",
    SEPARATOR,
    diff && typeof diff.diff_version === "number" ? `diff_version=${diff.diff_version}` : "diff_version=∅",
    diff && diff.identity_basis && typeof diff.identity_basis === "object"
      ? `identity_basis=${safeOneLine(diff.identity_basis.type || "—")}  matches=${fmtScalar(diff.identity_basis.matches)}`
      : "identity_basis=∅",
    diff && diff.envelope_a && typeof diff.envelope_a === "object"
      ? `A=${safeOneLine(diff.envelope_a.sourceLabel || "—")}  loaded_at_utc=${safeOneLine(diff.envelope_a.loaded_at_utc || "∅")}  outcome=${safeOneLine(
          diff.envelope_a.outcome || "—"
        )}`
      : "A=∅",
    diff && diff.envelope_b && typeof diff.envelope_b === "object"
      ? `B=${safeOneLine(diff.envelope_b.sourceLabel || "—")}  loaded_at_utc=${safeOneLine(diff.envelope_b.loaded_at_utc || "∅")}  outcome=${safeOneLine(
          diff.envelope_b.outcome || "—"
        )}`
      : "B=∅",
    diff && typeof diff.diff_total === "number" ? `diff_total=${diff.diff_total}` : "diff_total=∅",
    compareError ? `compare_error_code=${compareError}` : "",
  ]
    .filter((l) => l !== "")
    .join("\n");
  root.appendChild(header);

  const cats = diff && Array.isArray(diff.category_summaries) ? diff.category_summaries : [];
  const catWrap = document.createElement("div");
  catWrap.className = "jc-proj-cats";
  root.appendChild(catWrap);

  if (!cats.length) {
    const absent = document.createElement("div");
    absent.className = "jc-proj-absent";
    absent.textContent = "CATEGORIES: ∅";
    catWrap.appendChild(absent);
  } else {
    for (const c of cats) {
      const o = c && typeof c === "object" ? c : {};
      const row = document.createElement("div");
      row.className = "jc-proj-cat-row";

      const name = document.createElement("div");
      name.className = "jc-proj-cat-name";
      name.textContent = safeOneLine(o.category || "category");

      const presence = safeOneLine(o.presence || "");
      const boxA = document.createElement("div");
      const boxB = document.createElement("div");
      boxA.className = "jc-proj-cat-box";
      boxB.className = "jc-proj-cat-box";

      const aPresent = presence === "present_both" || presence === "present_a_only";
      const bPresent = presence === "present_both" || presence === "present_b_only";
      boxA.textContent = aPresent ? " " : "∅";
      boxB.textContent = bPresent ? " " : "∅";
      if (aPresent) boxA.className += " present";
      if (bPresent) boxB.className += " present";

      const meta = document.createElement("div");
      meta.className = "jc-proj-cat-meta";
      meta.textContent = `presence=${presence || "—"}  diff_count=${fmtScalar(o.diff_count)}  changed=${fmtScalar(o.changed)}`;

      row.appendChild(name);
      row.appendChild(boxA);
      row.appendChild(boxB);
      row.appendChild(meta);
      catWrap.appendChild(row);
    }
  }

  const nonAction = document.createElement("pre");
  nonAction.className = "jc-proj-nonaction";
  const naLines = [];
  naLines.push("NON-ACTION (visible constraints)");
  naLines.push(SEPARATOR);
  if (!decisions.length) {
    naLines.push("∅");
  } else {
    for (const d of decisions) {
      const o = d && typeof d === "object" ? d : {};
      naLines.push(
        `- domain=${safeOneLine(o.domain || "—")}  condition=${safeOneLine(o.condition || "—")}  required_response=${safeOneLine(
          o.required_response || "—"
        )}`
      );
    }
  }
  nonAction.textContent = naLines.join("\n");
  root.appendChild(nonAction);
}

/**
 * @param {unknown} v
 * @returns {string}
 */
function safeOneLine(v) {
  return String(v === null || v === undefined ? "" : v)
    .replace(/\r?\n/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * @param {string} token
 * @returns {boolean}
 */
function isSafeToken(token) {
  const t = safeOneLine(token);
  if (!t) return false;
  if (t.length > 96) return false;
  if (/^[a-zA-Z]+:\/\//.test(t)) return false; // URL-ish
  if (/^[A-Za-z]:[\\/]/.test(t)) return false; // Windows absolute
  if (/^\\\\/.test(t)) return false; // UNC
  if (/^\//.test(t)) return false; // POSIX absolute
  return true;
}

/**
 * @param {unknown} v
 * @returns {number|null}
 */
function toFiniteNumber(v) {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

/**
 * Best-effort: extract {start_s,end_s} from payload fields if present.
 * @param {any} payload
 * @returns {{start_s:number, end_s:number} | null}
 */
function extractSceneTimeRange(payload) {
  const p = payload && typeof payload === "object" ? payload : {};
  const startS = toFiniteNumber(p.scene_start_s) ?? toFiniteNumber(p.start_s) ?? toFiniteNumber(p.scene_start) ?? toFiniteNumber(p.start);
  const endS = toFiniteNumber(p.scene_end_s) ?? toFiniteNumber(p.end_s) ?? toFiniteNumber(p.scene_end) ?? toFiniteNumber(p.end);

  const startMs =
    toFiniteNumber(p.scene_start_ms) ?? toFiniteNumber(p.start_ms) ?? toFiniteNumber(p.scene_start_msec) ?? toFiniteNumber(p.start_msec);
  const endMs = toFiniteNumber(p.scene_end_ms) ?? toFiniteNumber(p.end_ms) ?? toFiniteNumber(p.scene_end_msec) ?? toFiniteNumber(p.end_msec);

  const s = startS !== null ? startS : startMs !== null ? startMs / 1000.0 : null;
  const e = endS !== null ? endS : endMs !== null ? endMs / 1000.0 : null;
  if (s === null || e === null) return null;
  if (!Number.isFinite(s) || !Number.isFinite(e)) return null;
  if (e < s) return null;
  return { start_s: s, end_s: e };
}

/**
 * @param {{start_s:number,end_s:number} | null} a
 * @param {{start_s:number,end_s:number} | null} b
 * @returns {{start_s:number,end_s:number} | null}
 */
function mergeTimeRange(a, b) {
  if (!a) return b || null;
  if (!b) return a || null;
  return { start_s: Math.min(a.start_s, b.start_s), end_s: Math.max(a.end_s, b.end_s) };
}

/**
 * @param {any} hit
 * @returns {{video_id:string, scene_id:string, key:string, anchor_token:string}}
 */
function extractSceneAnchor(hit) {
  const payload = hit && hit.payload && typeof hit.payload === "object" ? hit.payload : {};
  const prov = hit && hit.provenance && typeof hit.provenance === "object" ? hit.provenance : {};
  const video_id = safeOneLine(payload.video_id || prov.video_id || "unknown");
  const scene_id = safeOneLine(payload.scene_id || prov.scene_id || "unknown");
  const key = `${video_id}/${scene_id}`;
  return { video_id, scene_id, key, anchor_token: `scene:${key}` };
}

/**
 * Whitelisted subject-ish keys only; never read transcript/text bodies.
 * @param {any} payload
 * @returns {string[]}
 */
function extractEntityTokens(payload) {
  const p = payload && typeof payload === "object" ? payload : {};
  const keys = [
    "entity_ids",
    "entity_id",
    "person_ids",
    "people",
    "objects",
    "subjects",
    "tags",
    "topic_tags",
  ];

  /** @type {string[]} */
  const out = [];
  for (const k of keys) {
    if (!(k in p)) continue;
    const v = p[k];
    if (Array.isArray(v)) {
      for (const item of v) {
        const t = safeOneLine(item);
        if (isSafeToken(t)) out.push(t);
      }
      continue;
    }
    const t = safeOneLine(v);
    if (isSafeToken(t)) out.push(t);
  }
  return out;
}

/**
 * @param {any} hit
 * @returns {string[]}
 */
function extractFocusTokensForHit(hit) {
  const payload = hit && hit.payload && typeof hit.payload === "object" ? hit.payload : {};
  const { anchor_token } = extractSceneAnchor(hit);
  const tokens = [anchor_token, ...extractEntityTokens(payload)];
  const out = [];
  const seen = new Set();
  for (const t of tokens) {
    const s = safeOneLine(t);
    if (!isSafeToken(s)) continue;
    if (seen.has(s)) continue;
    seen.add(s);
    out.push(s);
  }
  return out;
}

/**
 * Build a deterministic projection model from the envelope (no inference; no sorting).
 * @param {any} envelope
 * @returns {{rails:any[], focus_keys:string[], time_min_s:number|null, time_max_s:number|null, has_time:boolean}}
 */
function buildProjectionModel(envelope) {
  const env = envelope && typeof envelope === "object" ? envelope : {};
  const candidates = Array.isArray(env.candidates) ? env.candidates : [];

  /** @type {any[]} */
  const rails = [];
  /** @type {string[]} */
  const focus_keys = [];
  const focusSeen = new Set();

  let timeMin = Infinity;
  let timeMax = -Infinity;

  const addFocus = (t) => {
    const s = safeOneLine(t);
    if (!isSafeToken(s)) return;
    if (focusSeen.has(s)) return;
    focusSeen.add(s);
    focus_keys.push(s);
  };

  const sourceCandidates = candidates.length ? candidates : [];
  for (const cand of sourceCandidates) {
    const c = cand && typeof cand === "object" ? cand : {};
    const evidence = Array.isArray(c.evidence) ? c.evidence : [];

    const segMap = new Map();
    for (const hit of evidence) {
      const h = hit && typeof hit === "object" ? hit : {};
      const { video_id, scene_id, key, anchor_token } = extractSceneAnchor(h);
      let seg = segMap.get(key);
      if (!seg) {
        seg = {
          key,
          video_id,
          scene_id,
          roles: { support: 0, contradict: 0, related: 0, meta: 0 },
          time: null,
          focus_tokens: [],
        };
        segMap.set(key, seg);
      }

      const role = safeOneLine(h.role || "");
      if (role === "support") seg.roles.support += 1;
      else if (role === "contradict") seg.roles.contradict += 1;
      else if (role === "related") seg.roles.related += 1;
      else seg.roles.meta += 1;

      const tr = extractSceneTimeRange(h.payload);
      seg.time = mergeTimeRange(seg.time, tr);

      // Focus tokens: scene anchor always present; entities optional.
      for (const t of extractFocusTokensForHit(h)) {
        if (!seg.focus_tokens.includes(t)) seg.focus_tokens.push(t);
        addFocus(t);
      }
      addFocus(anchor_token);

      if (seg.time) {
        timeMin = Math.min(timeMin, seg.time.start_s);
        timeMax = Math.max(timeMax, seg.time.end_s);
      }
    }

    const candidate_id = safeOneLine(c.candidate_id || "");
    const state = safeOneLine(c.state || "");
    rails.push({
      label: candidate_id ? `candidate:${candidate_id}` : "candidate",
      candidate_id,
      state,
      segments: Array.from(segMap.values()),
    });
  }

  // If there are no candidates, still provide a focus key from any envelope-level anchors if possible (none by default).
  const has_time = Number.isFinite(timeMin) && Number.isFinite(timeMax) && timeMax >= timeMin;
  return {
    rails,
    focus_keys,
    time_min_s: has_time ? timeMin : null,
    time_max_s: has_time ? timeMax : null,
    has_time,
  };
}

/**
 * Map epistemic state → presence class (no scores; no ranking).
 * @param {unknown} rawState
 * @returns {string}
 */
function projectionStateClass(rawState) {
  const s = safeOneLine(rawState || "").toLowerCase();
  if (s === "supported") return "state-supported";
  if (s === "partially_supported") return "state-partially_supported";
  if (s === "conflicted") return "state-conflicted";
  if (s === "unsupported_but_related") return "state-unsupported_but_related";
  if (s === "unknown" || s === "dont_know") return "state-unknown";
  return "state-unknown";
}

/**
 * @param {string} input
 * @returns {string}
 */
function fnv1a32Hex(input) {
  let hash = 0x811c9dc5;
  const s = String(input || "");
  for (let i = 0; i < s.length; i++) {
    hash ^= s.charCodeAt(i);
    // 32-bit FNV-1a prime: 16777619
    hash = (hash + ((hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24))) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

/**
 * Inspector-safe identifier (never log raw tokens).
 * @param {unknown} token
 * @returns {string}
 */
function hashTokenForInspector(token) {
  const t = safeOneLine(token || "");
  if (!t) return "";
  return `fnv1a32:${fnv1a32Hex(t)}`;
}

/**
 * @param {number} n
 * @param {number} lo
 * @param {number} hi
 * @returns {number}
 */
function clamp(n, lo, hi) {
  if (!Number.isFinite(n)) return lo;
  if (n < lo) return lo;
  if (n > hi) return hi;
  return n;
}

/**
 * @param {{time_min_s:number|null, time_max_s:number|null, has_time:boolean}} model
 * @param {any} projection
 * @returns {{window_start_s:number|null, window_end_s:number|null, cursor_s:number|null, focus_key:string|null}}
 */
function resolveProjectionView(model, projection) {
  const p = projection && typeof projection === "object" ? projection : {};
  const focus_key = typeof p.focus_key === "string" && p.focus_key ? p.focus_key : null;
  if (!model.has_time || model.time_min_s === null || model.time_max_s === null) {
    return { window_start_s: null, window_end_s: null, cursor_s: null, focus_key };
  }

  const tMin = model.time_min_s;
  const tMax = model.time_max_s;
  const wStartRaw = toFiniteNumber(p.window_start_s);
  const wEndRaw = toFiniteNumber(p.window_end_s);
  let window_start_s = wStartRaw !== null ? wStartRaw : tMin;
  let window_end_s = wEndRaw !== null ? wEndRaw : tMax;
  if (window_end_s <= window_start_s) {
    window_start_s = tMin;
    window_end_s = tMax;
  }
  window_start_s = clamp(window_start_s, tMin, tMax);
  window_end_s = clamp(window_end_s, tMin, tMax);
  if (window_end_s <= window_start_s) {
    window_start_s = tMin;
    window_end_s = tMax;
  }

  const cursorRaw = toFiniteNumber(p.cursor_s);
  const cursor_s =
    cursorRaw !== null ? clamp(cursorRaw, window_start_s, window_end_s) : window_start_s;

  return { window_start_s, window_end_s, cursor_s, focus_key };
}

/**
 * Replace projection state immutably (view-only; no data mutation).
 * @param {Record<string, unknown>} patch
 * @param {string} eventType
 * @param {string} source
 */
function updateProjectionState(patch, eventType, source) {
  const current = getState();
  if (!current || typeof current !== "object") return;
  const proj = current.projection && typeof current.projection === "object" ? current.projection : {};
  const next = { ...proj, ...patch };
  const nextState = {
    envelope: current.envelope,
    nonActionDecisions: current.nonActionDecisions,
    sourceLabel: current.sourceLabel,
    mode: current.mode,
    compare: current.compare,
    view: current.view,
    projection: next,
  };
  loadState(nextState);
  emitInspectorEvent(String(eventType || ""), String(source || ""), getState(), _lastInspectorDiagnostics);
}

/**
 * @param {string} selector
 * @param {number} dir
 */
function focusBySelector(selector, dir) {
  const items = Array.from(document.querySelectorAll(selector));
  if (items.length === 0) return;

  const active = document.activeElement;
  let idx = items.indexOf(active);
  if (idx === -1) idx = dir > 0 ? -1 : items.length;

  let next = idx + dir;
  if (next < 0) next = 0;
  if (next >= items.length) next = items.length - 1;

  const el = items[next];
  if (el && typeof el.focus === "function") el.focus();
}

/**
 * Render current state into the <pre> and diagnostics overlay.
 * @param {any} state
 */
function renderState(state) {
  const el = document.getElementById("jc-output");
  if (!el) return;

  const mode = state && String(state.mode || "") === "compare" ? "compare" : "single";
  const view = state && String(state.view || "") === GOODQ_UI_VIEW_PROJECT ? GOODQ_UI_VIEW_PROJECT : GOODQ_UI_VIEW_TEXT;
  const rendered =
    mode === "compare"
      ? renderEpistemicDiffText({
          diff: state.compare && typeof state.compare === "object" ? state.compare.diff : null,
          errorCode:
            state.compare && typeof state.compare === "object" && typeof state.compare.error_code === "string"
              ? state.compare.error_code
              : "",
          nonActionDecisions: state.nonActionDecisions,
        })
      : renderJustificationText({ envelope: state.envelope, nonActionDecisions: state.nonActionDecisions });
  el.textContent = rendered;

  if (view === GOODQ_UI_VIEW_PROJECT) {
    renderProjectionView(state, rendered);
  } else {
    renderStructuredView(rendered);
  }

  ensureOverlayRefs();
  const diagnosticsText =
    mode === "compare"
      ? buildCompareDiagnosticsText(
          state.compare && typeof state.compare === "object" ? state.compare.diff : null,
          state.nonActionDecisions || [],
          state.updatedAt
        )
      : buildDiagnosticsText(state.envelope, state.nonActionDecisions || [], state.updatedAt);
  if (_overlayPreRef) _overlayPreRef.textContent = diagnosticsText;
  _lastInspectorDiagnostics = extractInspectorDiagnostics(diagnosticsText);
  emitInspectorEvent("diagnostics_update", "renderState", state, _lastInspectorDiagnostics);
}

/**
 * Replace state in one operation; no partial updates.
 * @param {any} newState
 * @returns {any} frozen state
 */
function loadState(newState) {
  const isInitial = GoodQState === null;
  const prevView = GoodQState && typeof GoodQState.view === "string" ? GoodQState.view : GOODQ_UI_VIEW_TEXT;
  assertStateShape(newState);
  deepFreeze(newState);

  const mode = String(newState.mode || "") === "compare" ? "compare" : "single";
  const view = String(newState.view || "") === GOODQ_UI_VIEW_PROJECT ? GOODQ_UI_VIEW_PROJECT : GOODQ_UI_VIEW_TEXT;
  const projection =
    newState.projection && typeof newState.projection === "object" ? newState.projection : null;
  const state = {
    envelope: newState.envelope,
    nonActionDecisions: newState.nonActionDecisions,
    sourceLabel: String(newState.sourceLabel),
    updatedAt: new Date().toISOString(),
    mode,
    view,
    projection,
    compare: mode === "compare" && newState.compare && typeof newState.compare === "object" ? newState.compare : null,
  };
  deepFreeze(state);

  GoodQState = state;
  GoodQStateHistory.push(state);
  while (GoodQStateHistory.length > GOODQ_STATE_HISTORY_MAX) GoodQStateHistory.shift();

  window.GoodQState = state;
  renderState(state);
  emitInspectorEvent(isInitial ? "initial_render" : "state_transition", "loadState", state, _lastInspectorDiagnostics);
  if (prevView !== view) {
    emitInspectorEvent(
      view === GOODQ_UI_VIEW_PROJECT ? "projection_entered" : "projection_exited",
      "loadState",
      state,
      _lastInspectorDiagnostics
    );
  }
  return state;
}

/**
 * Convenience transition: replace envelope + decisions together.
 * @param {any} envelope
 * @param {any[]} decisions
 * @param {string} sourceLabel
 * @returns {any}
 */
function replaceEnvelope(envelope, decisions, sourceLabel, view, projection) {
  return loadState({ envelope, nonActionDecisions: decisions, sourceLabel, view, projection });
}

/**
 * Convenience transition: replace compare diff + decisions together (read-only).
 * @param {any|null} diff
 * @param {string} errorCode
 * @param {any[]} decisions
 * @param {string} sourceLabel
 * @returns {any}
 */
function replaceComparison(diff, errorCode, decisions, sourceLabel, view) {
  const compare = diff && typeof diff === "object" ? { diff } : { error_code: String(errorCode || "compare_failed") };
  const envelopeStub = {
    read_model_version: 1,
    retrieval_context: "human.ui.compare",
    outcome: "dont_know",
    question: { text: "" },
    candidates: [],
  };
  return loadState({
    envelope: envelopeStub,
    nonActionDecisions: decisions,
    sourceLabel,
    mode: "compare",
    compare,
    view,
  });
}

/**
 * Emit comparison lifecycle observations (metadata-only; never blocks rendering).
 * @param {string} eventType
 * @param {string} source
 * @param {any|null} diff
 * @param {string} errorCode
 */
function emitInspectorComparisonEvent(eventType, source, diff, errorCode) {
  try {
    const inspector = window.GoodQInspector;
    if (!inspector || typeof inspector.observe !== "function") return;
    if (typeof inspector.isEnabled === "function" && !inspector.isEnabled()) return;

    const d = diff && typeof diff === "object" ? diff : {};
    const a = d.envelope_a && typeof d.envelope_a === "object" ? d.envelope_a : {};
    const b = d.envelope_b && typeof d.envelope_b === "object" ? d.envelope_b : {};
    const id = d.identity_basis && typeof d.identity_basis === "object" ? d.identity_basis : {};
    const codes = Array.isArray(d.diff_codes) ? d.diff_codes.map((c) => String(c)) : [];

    inspector.observe({
      ts_utc: new Date().toISOString(),
      ui_version: GOODQ_UI_VERSION,
      event_type: String(eventType || ""),
      source: String(source || ""),
      last_render_ts_utc: GoodQState && typeof GoodQState.updatedAt === "string" ? GoodQState.updatedAt : "",
      counts: { candidates: 0, evidence_hits: 0, non_action_decisions: 0 },
      diagnostics: {
        order_fingerprint: _lastInspectorDiagnostics && _lastInspectorDiagnostics.order_fingerprint ? _lastInspectorDiagnostics.order_fingerprint : "",
        warnings: _lastInspectorDiagnostics && Array.isArray(_lastInspectorDiagnostics.warnings) ? _lastInspectorDiagnostics.warnings : [],
      },
      comparison: {
        diff_version: Number.isFinite(d.diff_version) ? d.diff_version : 0,
        diff_total: Number.isFinite(d.diff_total) ? d.diff_total : 0,
        diff_codes: codes,
        identity_type: typeof id.type === "string" ? id.type : "",
        identity_matches: typeof id.matches === "boolean" ? id.matches : null,
        order_fingerprint_a: typeof a.order_fingerprint === "string" ? a.order_fingerprint : "",
        order_fingerprint_b: typeof b.order_fingerprint === "string" ? b.order_fingerprint : "",
        error_code: String(errorCode || ""),
      },
    });
  } catch {
    // Best-effort only.
  }
}

function getState() {
  return GoodQState;
}

function getStateHistory() {
  return GoodQStateHistory.slice();
}

function ensureKeyListener() {
  if (_keyListenerBound) return;
  _keyListenerBound = true;

  document.addEventListener("keydown", (e) => {
    const key = e && e.key ? String(e.key) : "";
    if (key === "d" || key === "D") {
      ensureOverlayRefs();
      if (_overlayRef) toggleDiagnosticsOverlay(_overlayRef);
      return;
    }

    const st = getState();
    const isProjectView = st && typeof st.view === "string" && st.view === GOODQ_UI_VIEW_PROJECT;
    if (isProjectView) {
      if (key === "c" || key === "C") {
        e.preventDefault();
        emitInspectorEvent("compare_toggled", "projection_key", st, _lastInspectorDiagnostics);
        try {
          const params = new URLSearchParams(
            String(window.location && window.location.search ? window.location.search : "")
          );
          if (st && String(st.mode || "") === "compare") {
            params.set("mode", GOODQ_UI_VIEW_PROJECT); // alias: single + view=project
            params.delete("view");
          } else {
            params.set("mode", "compare");
            params.set("view", GOODQ_UI_VIEW_PROJECT);
          }
          const next = params.toString();
          setTimeout(() => {
            window.location.search = next ? `?${next}` : "";
          }, 0);
        } catch {
          // Best-effort only.
        }
        return;
      }

      // Time scrub/pan/zoom (view-only; no re-ranking; no filtering).
      const isSingle = st && String(st.mode || "") !== "compare";
      if (isSingle) {
        const model = buildProjectionModel(st.envelope);
        if (model.has_time) {
          const viewState = resolveProjectionView(model, st.projection);
          const tMin = model.time_min_s;
          const tMax = model.time_max_s;
          const wStart = viewState.window_start_s;
          const wEnd = viewState.window_end_s;
          const cursor = viewState.cursor_s;

          if (
            typeof tMin === "number" &&
            typeof tMax === "number" &&
            typeof wStart === "number" &&
            typeof wEnd === "number" &&
            typeof cursor === "number" &&
            wEnd > wStart
          ) {
            const span = wEnd - wStart;

            if (key === "ArrowLeft" || key === "ArrowRight") {
              e.preventDefault();
              const dir = key === "ArrowLeft" ? -1 : 1;
              if (e.shiftKey) {
                const delta = dir * span * 0.1;
                let ns = wStart + delta;
                let ne = wEnd + delta;
                const wSpan = ne - ns;
                if (ns < tMin) {
                  ns = tMin;
                  ne = tMin + wSpan;
                }
                if (ne > tMax) {
                  ne = tMax;
                  ns = tMax - wSpan;
                }
                updateProjectionState({ window_start_s: ns, window_end_s: ne }, "time_scrubbed", "projection_pan");
              } else {
                const delta = dir * span * 0.01;
                const nc = clamp(cursor + delta, wStart, wEnd);
                updateProjectionState({ cursor_s: nc }, "time_scrubbed", "projection_scrub_key");
              }
              return;
            }

            if (key === "+" || key === "=" || key === "-" || key === "_") {
              e.preventDefault();
              const zoomIn = key === "+" || key === "=";
              const factor = zoomIn ? 0.8 : 1.25;
              const nextSpan = Math.max(0.5, span * factor);
              let ns = cursor - nextSpan / 2;
              let ne = cursor + nextSpan / 2;
              const wSpan = ne - ns;
              if (ns < tMin) {
                ns = tMin;
                ne = tMin + wSpan;
              }
              if (ne > tMax) {
                ne = tMax;
                ns = tMax - wSpan;
              }
              ns = clamp(ns, tMin, tMax);
              ne = clamp(ne, tMin, tMax);
              if (ne <= ns) {
                ns = tMin;
                ne = tMax;
              }
              updateProjectionState({ window_start_s: ns, window_end_s: ne, cursor_s: clamp(cursor, ns, ne) }, "time_scrubbed", "projection_zoom");
              return;
            }
          }
        }
      }
    }

    if (key === "]") {
      e.preventDefault();
      focusBySelector(".jc-section-header", +1);
      return;
    }
    if (key === "[") {
      e.preventDefault();
      focusBySelector(".jc-section-header", -1);
      return;
    }
    if (key === "j" || key === "J") {
      e.preventDefault();
      focusBySelector(".jc-evidence-summary", +1);
      return;
    }
    if (key === "k" || key === "K") {
      e.preventDefault();
      focusBySelector(".jc-evidence-summary", -1);
      return;
    }
  });
}

/**
 * Build a structural dont_know envelope for source-load failures (no stack traces; no guesses).
 * @param {string} sourceLabel
 * @param {string} errorCode
 * @returns {any}
 */
function buildSourceFailureEnvelope(sourceLabel, errorCode) {
  const code = String(errorCode || "source_load_failed");
  const src = String(sourceLabel || "unknown-source");
  return {
    read_model_version: 1,
    question: { text: "" },
    retrieval_context: `system.ui.source_load:${src}`,
    outcome: "dont_know",
    candidates: [],
    dont_know: {
      state: "unknown",
      explanation: `source_load_failed:${code}`,
      evidence: [],
      limits: [`source:${src}`, `error:${code}`],
      next_steps: [
        {
          action: "switch to example source",
          rationale: "Restore a known-good envelope for UI verification",
          scope: { source: "example" },
        },
      ],
    },
  };
}

/**
 * Build a minimal NonActionDecision requiring defer on source-load failures.
 * @param {string} errorCode
 * @returns {any[]}
 */
function buildSourceFailureDecisions(errorCode) {
  const code = String(errorCode || "source_load_failed");
  return [
    {
      contract_version: 1,
      domain: "answer",
      condition: "ui_source_load_failed",
      required_response: "defer",
      rationale: { error_code: code },
    },
  ];
}

/**
 * @param {string} sourceLabel
 * @param {string} errorCode
 */
function renderSourceFailure(sourceLabel, errorCode, view) {
  const envelope = buildSourceFailureEnvelope(sourceLabel, errorCode);
  const decisions = buildSourceFailureDecisions(errorCode);
  const v =
    typeof view === "string" && view
      ? view
      : GoodQState && typeof GoodQState.view === "string"
        ? GoodQState.view
        : GOODQ_UI_VIEW_TEXT;
  replaceEnvelope(envelope, decisions, sourceLabel, v);
}

/**
 * Build a minimal NonActionDecision requiring defer on compare-load failures.
 * @param {string} errorCode
 * @returns {any[]}
 */
function buildCompareFailureDecisions(errorCode) {
  const code = String(errorCode || "compare_load_failed");
  return [
    {
      contract_version: 1,
      domain: "answer",
      condition: "ui_compare_load_failed",
      required_response: "defer",
      rationale: { error_code: code },
    },
  ];
}

/**
 * @param {string} sourceLabel
 * @param {string} errorCode
 */
function renderCompareFailure(sourceLabel, errorCode, view) {
  const decisions = buildCompareFailureDecisions(errorCode);
  const v =
    typeof view === "string" && view
      ? view
      : GoodQState && typeof GoodQState.view === "string"
        ? GoodQState.view
        : GOODQ_UI_VIEW_TEXT;
  replaceComparison(null, errorCode, decisions, sourceLabel, v);
}

/**
 * @param {unknown} raw
 * @returns {string}
 */
function normalizeSourceKey(raw) {
  const s = String(raw || "").trim().toLowerCase();
  if (s === "file" || s === "local-json" || s === "local_json") return "file";
  if (s === "api" || s === "api-readonly" || s === "api_readonly") return "api";
  return "example";
}

/**
 * @param {unknown} raw
 * @returns {"single"|"compare"}
 */
function normalizeMode(raw) {
  const s = String(raw || "").trim().toLowerCase();
  return s === "compare" ? "compare" : "single";
}

/**
 * @param {unknown} raw
 * @returns {"text"|"project"}
 */
function normalizeView(raw) {
  const s = String(raw || "").trim().toLowerCase();
  return s === "project" ? "project" : "text";
}

/**
 * @param {unknown} raw
 * @returns {"file"|"example"|"api"}
 */
function normalizeDiffSourceKey(raw) {
  const s = String(raw || "").trim().toLowerCase();
  if (s === "file" || s === "local-json" || s === "local_json") return "file";
  if (s === "api" || s === "api-readonly" || s === "api_readonly") return "api";
  return "example";
}

/**
 * Disallow absolute/suspicious paths; only allow relative-ish URLs for local JSON loading.
 * @param {unknown} raw
 * @returns {string|null}
 */
function sanitizeLocalJsonPath(raw) {
  let s = String(raw || "").trim();
  // Strip quotes if wrapped
  if (s.startsWith('"') && s.endsWith('"')) {
    s = s.slice(1, -1).trim();
  } else if (s.startsWith("'") && s.endsWith("'")) {
    s = s.slice(1, -1).trim();
  }
  if (!s) return null;

  const p = s.replace(/\\/g, "/");
  if (p.includes("://")) return null;
  if (p.startsWith("//")) return null;
  if (/^[A-Za-z]:\//.test(p)) return null;
  if (p.startsWith("\\\\")) return null;
  if (p.split("/").some((seg) => seg === "..")) return null;

  return p;
}

/**
 * @param {any} data
 * @returns {{envelope:any, decisions:any[]}}
 */
function extractEnvelopeBundle(data) {
  if (!data || typeof data !== "object") throw new Error("bundle_invalid");
  if (!("envelope" in data)) throw new Error("bundle_missing_envelope");
  const envelope = data.envelope;
  const decisions =
    (Array.isArray(data.nonActionDecisions) && data.nonActionDecisions) ||
    (Array.isArray(data.non_action_decisions) && data.non_action_decisions) ||
    [];
  if (!envelope || typeof envelope !== "object") throw new Error("bundle_envelope_invalid");
  if (!Array.isArray(decisions)) throw new Error("bundle_decisions_invalid");
  return { envelope, decisions };
}

/**
 * @param {any} data
 * @returns {{diff:any}}
 */
function extractDiffBundle(data) {
  if (!data || typeof data !== "object") throw new Error("diff_invalid");
  const diff = data.diff && typeof data.diff === "object" ? data.diff : data;
  if (!diff || typeof diff !== "object") throw new Error("diff_missing");
  if (typeof diff.diff_version !== "number") throw new Error("diff_missing_version");
  return { diff };
}

async function loadExampleSource(view) {
  replaceEnvelope(EXAMPLE.envelope, EXAMPLE.nonActionDecisions || [], "example", view);
}

/**
 * Load EpistemicReadEnvelope + NonActionDecision[] from a local JSON file URL (explicit).
 * @param {string} rawPath
 */
async function loadLocalJsonSource(rawPath, view) {
  const safePath = sanitizeLocalJsonPath(rawPath);
  if (!safePath) {
    renderSourceFailure("local-json", "file_path_invalid", view);
    return;
  }

  let url = "";
  try {
    url = new URL(safePath, window.location.href).toString();
  } catch {
    renderSourceFailure("local-json", "file_url_invalid", view);
    return;
  }

  try {
    const resp = await fetch(url, { cache: "no-store" });
    if (!resp.ok) {
      renderSourceFailure("local-json", `file_fetch_http_${resp.status}`, view);
      return;
    }
    let data = null;
    try {
      data = await resp.json();
    } catch {
      renderSourceFailure("local-json", "file_json_parse_error", view);
      return;
    }

    let envelope = null;
    let decisions = [];
    try {
      ({ envelope, decisions } = extractEnvelopeBundle(data));
    } catch (e) {
      const msg = e && typeof e === "object" && "message" in e ? String(e.message || "") : "";
      const code = msg && msg.startsWith("bundle_") ? `file_schema_${msg}` : "file_schema_invalid";
      renderSourceFailure("local-json", code, view);
      return;
    }
    replaceEnvelope(envelope, decisions, "local-json", view);
  } catch {
    renderSourceFailure("local-json", "file_fetch_error", view);
  }
}

/**
 * Resolve read-only API endpoint URL. Avoid assumptions when running from file:// origin.
 * @param {string} apiBase
 * @returns {string|null}
 */
function resolveReadonlyApiUrl(apiBase) {
  const base = String(apiBase || "").trim();
  if (base) {
    try {
      return new URL("/api/read/envelope", base).toString();
    } catch {
      return null;
    }
  }
  try {
    if (window.location && window.location.origin && window.location.origin !== "null") {
      return new URL("/api/read/envelope", window.location.origin).toString();
    }
  } catch {
    // ignore
  }
  return null;
}

/**
 * Load EpistemicReadEnvelope + NonActionDecision[] from the read-only API endpoint (explicit).
 * @param {string} apiBase
 */
async function loadApiReadonlySource(apiBase, view) {
  const url = resolveReadonlyApiUrl(apiBase);
  if (!url) {
    renderSourceFailure("api-readonly", "api_url_unavailable", view);
    return;
  }
  try {
    const resp = await fetch(url, { cache: "no-store" });
    if (!resp.ok) {
      renderSourceFailure("api-readonly", `api_fetch_http_${resp.status}`, view);
      return;
    }
    let data = null;
    try {
      data = await resp.json();
    } catch {
      renderSourceFailure("api-readonly", "api_json_parse_error", view);
      return;
    }

    let envelope = null;
    let decisions = [];
    try {
      ({ envelope, decisions } = extractEnvelopeBundle(data));
    } catch (e) {
      const msg = e && typeof e === "object" && "message" in e ? String(e.message || "") : "";
      const code = msg && msg.startsWith("bundle_") ? `api_schema_${msg}` : "api_schema_invalid";
      renderSourceFailure("api-readonly", code, view);
      return;
    }
    replaceEnvelope(envelope, decisions, "api-readonly", view);
  } catch {
    renderSourceFailure("api-readonly", "api_fetch_error", view);
  }
}

/**
 * Build a minimal EpistemicDiff v1 example (no diffs).
 * Note: real diffs should be produced by the frozen engine `steps/common/epistemic_diff.py`.
 * @returns {any}
 */
function buildExampleDiff() {
  const env = EXAMPLE && EXAMPLE.envelope && typeof EXAMPLE.envelope === "object" ? EXAMPLE.envelope : {};
  const candidates = Array.isArray(env.candidates) ? env.candidates : [];
  const evidenceHits = countEvidenceHits(env);

  const emptyByCat = {
    identity_basis: 0,
    outcome: 0,
    candidates: 0,
    non_action_decisions: 0,
    evidence: 0,
    limits_aggregated: 0,
    limits_dont_know: 0,
    next_steps: 0,
  };

  const category_summaries = Object.keys(emptyByCat).map((cat) => ({
    category: cat,
    presence: "present_both",
    changed: false,
    diff_count: 0,
  }));

  const fingerprint = window.GoodQIntegrity && typeof window.GoodQIntegrity.computeOrderFingerprint === "function"
    ? window.GoodQIntegrity.computeOrderFingerprint([])
    : "fnv1a32:00000000";

  return {
    diff_version: 1,
    comparison_id: "ediff1_example",
    initiated_ts_utc: "",
    identity_basis: { type: "question_text_exact", details: {}, matches: true },
    envelope_a: {
      sourceLabel: "example",
      loaded_at_utc: "",
      read_model_version: env.read_model_version,
      retrieval_context: env.retrieval_context,
      outcome: env.outcome,
      counts: { candidates: candidates.length, evidence_hits: evidenceHits, non_action_decisions: 0 },
      order_fingerprint: fingerprint,
      warning_codes: [],
    },
    envelope_b: {
      sourceLabel: "example",
      loaded_at_utc: "",
      read_model_version: env.read_model_version,
      retrieval_context: env.retrieval_context,
      outcome: env.outcome,
      counts: { candidates: candidates.length, evidence_hits: evidenceHits, non_action_decisions: 0 },
      order_fingerprint: fingerprint,
      warning_codes: [],
    },
    category_summaries,
    diffs: [],
    diff_total: 0,
    diff_by_category: emptyByCat,
    diff_codes: [],
  };
}

/**
 * Load EpistemicDiff v1 from a local JSON file URL (explicit; read-only).
 * @param {string} rawPath
 * @returns {Promise<any>}
 */
async function loadLocalJsonDiffSource(rawPath) {
  const safePath = sanitizeLocalJsonPath(rawPath);
  if (!safePath) throw new Error("diff_file_path_invalid");

  let url = "";
  try {
    url = new URL(safePath, window.location.href).toString();
  } catch {
    throw new Error("diff_file_url_invalid");
  }

  const resp = await fetch(url, { cache: "no-store" });
  if (!resp.ok) throw new Error(`diff_file_fetch_http_${resp.status}`);

  let data = null;
  try {
    data = await resp.json();
  } catch {
    throw new Error("diff_file_json_parse_error");
  }

  try {
    const { diff } = extractDiffBundle(data);
    return diff;
  } catch (e) {
    const msg = e && typeof e === "object" && "message" in e ? String(e.message || "") : "";
    const code = msg && msg.startsWith("diff_") ? `diff_file_schema_${msg}` : "diff_file_schema_invalid";
    throw new Error(code);
  }
}

/**
 * Create a tiny source selector UI (read-only wiring; no actions beyond switching inputs).
 * @returns {{select: HTMLSelectElement, path: HTMLInputElement, apiBase: HTMLInputElement, status: HTMLElement} | null}
 */
function ensureSourceControls() {
  const root = document.getElementById("jc-controls");
  if (!root) return null;
  if (root.getAttribute("data-jc-bound") === "1") {
    const select = /** @type {HTMLSelectElement|null} */ (document.getElementById("jc-source-select"));
    const path = /** @type {HTMLInputElement|null} */ (document.getElementById("jc-source-path"));
    const apiBase = /** @type {HTMLInputElement|null} */ (document.getElementById("jc-api-base"));
    const status = /** @type {HTMLElement|null} */ (document.getElementById("jc-source-status"));
    if (select && path && apiBase && status) return { select, path, apiBase, status };
  }

  root.setAttribute("data-jc-bound", "1");
  root.style.margin = "0 0 0.75rem 0";

  const wrap = document.createElement("div");
  wrap.style.display = "flex";
  wrap.style.flexWrap = "wrap";
  wrap.style.gap = "0.5rem 0.75rem";
  wrap.style.alignItems = "center";

  const label = document.createElement("label");
  label.textContent = "source:";
  label.htmlFor = "jc-source-select";

  const select = document.createElement("select");
  select.id = "jc-source-select";
  select.appendChild(new Option("example", "example"));
  select.appendChild(new Option("local JSON", "file"));
  select.appendChild(new Option("read-only API", "api"));

  const path = document.createElement("input");
  path.id = "jc-source-path";
  path.type = "text";
  path.placeholder = "path/to/envelope.json";
  path.size = 36;

  const apiBase = document.createElement("input");
  apiBase.id = "jc-api-base";
  apiBase.type = "text";
  apiBase.placeholder = "api base (optional)";
  apiBase.size = 26;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = "load";

  const status = document.createElement("span");
  status.id = "jc-source-status";
  status.textContent = "source: example";

  function updateVisibility() {
    const v = normalizeSourceKey(select.value);
    path.style.display = v === "file" ? "inline-block" : "none";
    apiBase.style.display = v === "api" ? "inline-block" : "none";
  }

  async function performLoad() {
    const view = GoodQState && typeof GoodQState.view === "string" ? GoodQState.view : GOODQ_UI_VIEW_TEXT;
    const v = normalizeSourceKey(select.value);
    if (v === "example") {
      await loadExampleSource(view);
      status.textContent = "source: example";
      return;
    }
    if (v === "file") {
      await loadLocalJsonSource(path.value, view);
      status.textContent = "source: local-json";
      return;
    }
    if (v === "api") {
      await loadApiReadonlySource(apiBase.value, view);
      status.textContent = "source: api-readonly";
      return;
    }
    await loadExampleSource(view);
    status.textContent = "source: example";
  }

  select.addEventListener("change", () => {
    updateVisibility();
  });
  btn.addEventListener("click", () => {
    performLoad();
  });
  path.addEventListener("keydown", (e) => {
    if (e && e.key === "Enter") performLoad();
  });
  apiBase.addEventListener("keydown", (e) => {
    if (e && e.key === "Enter") performLoad();
  });

  wrap.appendChild(label);
  wrap.appendChild(select);
  wrap.appendChild(path);
  wrap.appendChild(apiBase);
  wrap.appendChild(btn);
  wrap.appendChild(status);
  root.appendChild(wrap);

  updateVisibility();
  return { select, path, apiBase, status };
}

/**
 * @returns {{sourceKey: string, path: string, apiBase: string}}
 */
function readSourceParams() {
  try {
    const params = new URLSearchParams(String(window.location && window.location.search ? window.location.search : ""));
    const rawMode = String(params.get("mode") || "");
    let mode = normalizeMode(rawMode);
    let view = normalizeView(params.get("view"));
    if (rawMode.trim().toLowerCase() === GOODQ_UI_VIEW_PROJECT) {
      mode = "single";
      view = GOODQ_UI_VIEW_PROJECT;
    }
    const sourceKey = normalizeSourceKey(params.get("source"));
    const diffSourceKey = normalizeDiffSourceKey(params.get("diff_source"));
    return {
      mode,
      view,
      sourceKey,
      path: String(params.get("path") || ""),
      apiBase: String(params.get("api_base") || ""),
      diffSourceKey,
      diffPath: String(params.get("diff_path") || ""),
    };
  } catch {
    return {
      mode: "single",
      view: GOODQ_UI_VIEW_TEXT,
      sourceKey: "example",
      path: "",
      apiBase: "",
      diffSourceKey: "example",
      diffPath: "",
    };
  }
}

window.GoodQJustification = {
  renderJustificationText,
  renderEpistemicDiffText,
  EXAMPLE,
  loadState,
  replaceEnvelope,
  replaceComparison,
  getState,
  getStateHistory,
};

async function main() {
  ensureKeyListener();
  const params = readSourceParams();

  if (params.mode === "compare") {
    const controlsRoot = document.getElementById("jc-controls");
    if (controlsRoot) controlsRoot.style.display = "none";

    emitInspectorComparisonEvent("comparison_initiated", "main", null, "");

    if (params.diffSourceKey === "api") {
      renderCompareFailure("compare", "diff_api_not_supported", params.view);
      emitInspectorComparisonEvent("comparison_completed", "main", null, "diff_api_not_supported");
      return;
    }

    if (params.diffSourceKey === "file") {
      if (!params.diffPath) {
        renderCompareFailure("compare", "diff_path_missing", params.view);
        emitInspectorComparisonEvent("comparison_completed", "main", null, "diff_path_missing");
        return;
      }
      try {
        const diff = await loadLocalJsonDiffSource(params.diffPath);
        replaceComparison(diff, "", [], "compare:file", params.view);
        emitInspectorComparisonEvent("comparison_completed", "main", diff, "");
        return;
      } catch (e) {
        const msg = e && typeof e === "object" && "message" in e ? String(e.message || "") : "";
        const code = msg || "diff_file_fetch_error";
        renderCompareFailure("compare", code, params.view);
        emitInspectorComparisonEvent("comparison_completed", "main", null, code);
        return;
      }
    }

    // Default: example diff (no diffs)
    const diff = buildExampleDiff();
    replaceComparison(diff, "", [], "compare:example", params.view);
    emitInspectorComparisonEvent("comparison_completed", "main", diff, "");
    return;
  }

  const controls = ensureSourceControls();
  if (controls) {
    controls.select.value = params.sourceKey;
    if (params.path) controls.path.value = params.path;
    if (params.apiBase) controls.apiBase.value = params.apiBase;
  }

  if (params.sourceKey === "file") {
    await loadLocalJsonSource(params.path, params.view);
    return;
  }
  if (params.sourceKey === "api") {
    await loadApiReadonlySource(params.apiBase, params.view);
    return;
  }
  await loadExampleSource(params.view);
}

async function pollApiStatus() {
  const statusEl = document.getElementById("header-status");
  const fingerprintEl = document.getElementById("header-fingerprint");
  if (!statusEl && !fingerprintEl) return;

  try {
    const resp = await fetch("/api/status", { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    
    if (statusEl) {
      statusEl.textContent = "Status: ONLINE";
      statusEl.className = "header-status online";
    }
    if (fingerprintEl) {
      const epoch = (data.database && data.database.epoch) || "N/A";
      const runId = (data.processing && data.processing.cli_progress && data.processing.cli_progress.run_id) || (data.processing && data.processing.run_id) || "None";
      fingerprintEl.textContent = `Epoch: ${epoch} | Run: ${runId}`;
    }
  } catch (e) {
    if (statusEl) {
      statusEl.textContent = "Status: OFFLINE";
      statusEl.className = "header-status offline";
    }
    if (fingerprintEl) {
      fingerprintEl.textContent = "API unreachable";
    }
  }
}

function startStatusPolling() {
  pollApiStatus();
  setInterval(pollApiStatus, 3000);
}

// Start status polling when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  startStatusPolling();
});

main();
