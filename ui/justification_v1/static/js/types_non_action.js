/**
 * NonActionDecision (v1) — type mirror (documentation only).
 *
 * Authoritative contract:
 * - docs/architecture/NON_ACTION_CONTRACT.md
 *
 * Non-goals:
 * - No enforcement
 * - No thresholds
 * - No policy coupling
 */

/**
 * NonActionDomain: "answer" | "ingest" | "train" | "act"
 * NonActionRequiredResponse: "refuse" | "defer" | "dont_know" | "silent"
 */

/**
 * @typedef {Object} NonActionDecision
 * @property {number} contract_version
 * @property {"answer"|"ingest"|"train"|"act"} domain
 * @property {string} condition
 * @property {"refuse"|"defer"|"dont_know"|"silent"} required_response
 * @property {Object.<string, any>} rationale          // machine-readable (not prose)
 */
