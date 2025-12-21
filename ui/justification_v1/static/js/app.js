/*
This renderer assembles epistemic structure only. It must not be used to gate, rank, filter, or refuse.

Hardening harness (integrity-only; no semantics change):
- Validator + order fingerprint: ./integrity.js (diagnostics only; never enforced)
- Diagnostics overlay toggle: press "D" (read-only; does not change <pre> output)
- Golden test: load ./test_render.js then run `GoodQJustificationTests.run()` in console

Justification Channel v1:
- Renders EpistemicReadEnvelope + NonActionDecision[] in a text-first, truth-preserving format.
- No actions, no API calls, no fetching, no sorting, no filtering.
*/

const SEPARATOR = "────────────────────────────────────────────────────────────";

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

  const rendered = renderJustificationText({ envelope: state.envelope, nonActionDecisions: state.nonActionDecisions });
  el.textContent = rendered;

  renderStructuredView(rendered);

  ensureOverlayRefs();
  if (_overlayPreRef) {
    _overlayPreRef.textContent = buildDiagnosticsText(state.envelope, state.nonActionDecisions || [], state.updatedAt);
  }
}

/**
 * Replace state in one operation; no partial updates.
 * @param {any} newState
 * @returns {any} frozen state
 */
function loadState(newState) {
  assertStateShape(newState);
  deepFreeze(newState);

  const state = {
    envelope: newState.envelope,
    nonActionDecisions: newState.nonActionDecisions,
    sourceLabel: String(newState.sourceLabel),
    updatedAt: new Date().toISOString(),
  };
  deepFreeze(state);

  GoodQState = state;
  GoodQStateHistory.push(state);
  while (GoodQStateHistory.length > GOODQ_STATE_HISTORY_MAX) GoodQStateHistory.shift();

  window.GoodQState = state;
  renderState(state);
  return state;
}

/**
 * Convenience transition: replace envelope + decisions together.
 * @param {any} envelope
 * @param {any[]} decisions
 * @param {string} sourceLabel
 * @returns {any}
 */
function replaceEnvelope(envelope, decisions, sourceLabel) {
  return loadState({ envelope, nonActionDecisions: decisions, sourceLabel });
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

window.GoodQJustification = {
  renderJustificationText,
  EXAMPLE,
  loadState,
  replaceEnvelope,
  getState,
  getStateHistory,
};

function main() {
  ensureKeyListener();
  replaceEnvelope(EXAMPLE.envelope, EXAMPLE.nonActionDecisions || [], "hardcoded-example");
}

main();
