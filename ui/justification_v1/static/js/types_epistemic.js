/**
 * EpistemicReadEnvelope (v1) — type mirror (documentation only).
 *
 * Authoritative contract:
 * - docs/architecture/EPISTEMIC_READ_MODEL.md
 *
 * Non-goals:
 * - No validation
 * - No classification
 * - No thresholds
 * - No policy coupling
 */

/**
 * @typedef {Object} Confidence
 * @property {number|null} [intrinsic]
 * @property {number|null} [source]
 * @property {number|null} [temporal]
 * @property {string|null} [temporal_explanation]
 * @property {number|null} [consistency]
 * @property {number|null} [overall]
 */

/**
 * @typedef {Object.<string, {attempted?: boolean, committed?: boolean, ref?: string, reason?: string}>} TargetsByStore
 */

/**
 * @typedef {Object} ProvenancePointer
 * @property {number} [provenance_version]            // current: 1
 * @property {string|null} [ts_utc]
 * @property {string|null} [scene_id]
 * @property {string|null} [video_id]
 * @property {string|null} [modality]
 * @property {string|null} [model]
 * @property {string|null} [component]
 * @property {boolean|null} [attempted]
 * @property {boolean|null} [committed]
 * @property {string|null} [reason]
 * @property {TargetsByStore} [targets]
 * @property {Confidence} [confidence]
 */

/**
 * EvidenceRole: "support" | "contradict" | "related" | "meta"
 * ReadOutcome: "answer" | "dont_know"
 * EpistemicState:
 *   "supported" | "partially_supported" | "conflicted" | "stale" | "unsupported_but_related" | "unknown"
 */

/**
 * @typedef {Object} EvidenceHit
 * @property {"support"|"contradict"|"related"|"meta"} [role]
 * @property {string|null} [store]                    // "qdrant" | "faiss" | "chroma" | ...
 * @property {string|null} [store_ref]                // collection/index name
 * @property {string|null} [embedding_id]
 * @property {number|null} [score]
 * @property {Object.<string, any>} [payload]         // sanitized; never includes raw user query
 * @property {ProvenancePointer|null} [provenance]
 * @property {Confidence} [confidence]
 * @property {string[]} [limits]
 */

/**
 * @typedef {Object} NextStepHint
 * @property {string} [action]
 * @property {string} [rationale]
 * @property {Object.<string, any>} [scope]
 */

/**
 * @typedef {Object} AnswerCandidate
 * @property {string} [candidate_id]
 * @property {"supported"|"partially_supported"|"conflicted"|"stale"|"unsupported_but_related"|"unknown"} [state]
 * @property {string} [answer_text]
 * @property {Confidence} [confidence]
 * @property {EvidenceHit[]} [evidence]
 * @property {string[]} [limits]
 * @property {NextStepHint[]} [next_steps]
 */

/**
 * @typedef {Object} DontKnowOutcome
 * @property {"supported"|"partially_supported"|"conflicted"|"stale"|"unsupported_but_related"|"unknown"} [state]
 * @property {string} [explanation]
 * @property {EvidenceHit[]} [evidence]
 * @property {string[]} [limits]
 * @property {NextStepHint[]} [next_steps]
 */

/**
 * @typedef {Object} EpistemicReadEnvelope
 * @property {number} [read_model_version]            // must be 1 for v1
 * @property {{text?: string, [k: string]: any}} [question]
 * @property {string|null} [retrieval_context]        // sanitized label; no raw user query
 * @property {"answer"|"dont_know"} [outcome]
 * @property {AnswerCandidate[]} [candidates]
 * @property {DontKnowOutcome|null} [dont_know]
 */
