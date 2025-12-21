/*
This renderer assembles epistemic structure only. It must not be used to gate, rank, filter, or refuse.

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

function main() {
  const el = document.getElementById("jc-output");
  if (!el) return;
  el.textContent = renderJustificationText(EXAMPLE);
}

main();
