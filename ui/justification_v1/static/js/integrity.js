/*
Justification Channel v1 — Integrity Harness (read-only).
No API calls. No actions. No enforcement.
*/

(function () {
  /**
   * @param {string} s
   * @returns {boolean}
   */
  function looksLikeAbsolutePath(s) {
    // Windows drive paths: C:\... or C:/...
    if (/[A-Za-z]:[\\/]/.test(s)) return true;
    // UNC paths: \\server\share\...
    if (/^\\\\/.test(s)) return true;
    // Common Unix/WSL absolute roots (best-effort)
    if (/^\/(mnt|home|Users|var|etc|opt|srv)\b/.test(s)) return true;
    return false;
  }

  /**
   * @param {string} path
   * @returns {boolean}
   */
  function isTranscriptLikePath(path) {
    const p = String(path || "").toLowerCase();
    if (!p.includes(".payload.")) return false;
    return (
      p.endsWith(".transcript") ||
      p.endsWith(".frame_text") ||
      p.endsWith(".ocr_text") ||
      p.endsWith(".caption") ||
      p.endsWith(".text")
    );
  }

  /**
   * @param {string} value
   * @returns {boolean}
   */
  function looksRedacted(value) {
    const s = String(value || "").trim();
    if (!s) return false;
    if (s === "[REDACTED]") return true;
    if (s.toLowerCase() === "redacted") return true;
    if (s.includes("[REDACTED]")) return true;
    return false;
  }

  /**
   * @param {string} path
   * @returns {boolean}
   */
  function isHealthValueLikePath(path) {
    const p = String(path || "").toLowerCase();
    if (!p.includes(".payload.")) return false;
    return (
      p.endsWith(".value") ||
      p.endsWith(".measurement") ||
      p.endsWith(".qty") ||
      p.endsWith(".amount") ||
      p.endsWith(".resting_hr") ||
      p.endsWith(".hr") ||
      p.endsWith(".steps") ||
      p.endsWith(".weight") ||
      p.endsWith(".glucose") ||
      p.endsWith(".bp_systolic") ||
      p.endsWith(".bp_diastolic")
    );
  }

  /**
   * Deep walk objects/arrays and call `onLeaf` for primitive leaves.
   *
   * @param {unknown} value
   * @param {string} path
   * @param {(leaf: unknown, leafPath: string) => void} onLeaf
   */
  function walk(value, path, onLeaf) {
    if (value === null || value === undefined) return;
    if (Array.isArray(value)) {
      for (let i = 0; i < value.length; i++) {
        walk(value[i], `${path}[${i}]`, onLeaf);
      }
      return;
    }
    if (typeof value === "object") {
      const obj = /** @type {Record<string, unknown>} */ (value);
      for (const k of Object.keys(obj)) {
        walk(obj[k], `${path}.${k}`, onLeaf);
      }
      return;
    }
    onLeaf(value, path);
  }

  /**
   * @param {unknown} envelope
   * @returns {string[]} warnings
   */
  function validateEnvelope(envelope) {
    /** @type {string[]} */
    const warnings = [];
    if (!envelope || typeof envelope !== "object") {
      warnings.push("envelope_invalid: not an object");
      return warnings;
    }

    const env = /** @type {any} */ (envelope);
    const candidates = Array.isArray(env.candidates) ? env.candidates : [];
    for (let ci = 0; ci < candidates.length; ci++) {
      const cand = candidates[ci] && typeof candidates[ci] === "object" ? candidates[ci] : {};
      const evidence = Array.isArray(cand.evidence) ? cand.evidence : [];
      for (let ei = 0; ei < evidence.length; ei++) {
        const ev = evidence[ei] && typeof evidence[ei] === "object" ? evidence[ei] : {};

        // Required provenance fields when present
        if (ev.provenance && typeof ev.provenance === "object") {
          if (typeof ev.provenance.provenance_version !== "number") {
            warnings.push(`missing_provenance_version: candidates[${ci}].evidence[${ei}].provenance`);
          }
        }

        // Scan payload/provenance leaves for prohibited patterns.
        if (ev.payload && typeof ev.payload === "object") {
          walk(ev.payload, `candidates[${ci}].evidence[${ei}].payload`, (leaf, leafPath) => {
            if (typeof leaf === "string") {
              if (looksLikeAbsolutePath(leaf)) warnings.push(`absolute_path_detected: ${leafPath}`);
              if (isTranscriptLikePath(leafPath) && !looksRedacted(leaf)) {
                if (leaf.length >= 24 && /\s/.test(leaf)) warnings.push(`possible_raw_transcript: ${leafPath}`);
              }
            }
            if ((typeof leaf === "number" || typeof leaf === "string") && isHealthValueLikePath(leafPath)) {
              warnings.push(`possible_raw_health_value: ${leafPath}`);
            }
          });
        }
        if (ev.provenance && typeof ev.provenance === "object") {
          walk(ev.provenance, `candidates[${ci}].evidence[${ei}].provenance`, (leaf, leafPath) => {
            if (typeof leaf === "string" && looksLikeAbsolutePath(leaf)) {
              warnings.push(`absolute_path_detected: ${leafPath}`);
            }
          });
        }
      }
    }

    // dont_know evidence, if present
    if (env.dont_know && typeof env.dont_know === "object") {
      const dk = env.dont_know;
      const dkEvidence = Array.isArray(dk.evidence) ? dk.evidence : [];
      for (let i = 0; i < dkEvidence.length; i++) {
        const ev = dkEvidence[i] && typeof dkEvidence[i] === "object" ? dkEvidence[i] : {};
        if (ev.payload && typeof ev.payload === "object") {
          walk(ev.payload, `dont_know.evidence[${i}].payload`, (leaf, leafPath) => {
            if (typeof leaf === "string") {
              if (looksLikeAbsolutePath(leaf)) warnings.push(`absolute_path_detected: ${leafPath}`);
              if (isTranscriptLikePath(leafPath) && !looksRedacted(leaf)) {
                if (leaf.length >= 24 && /\s/.test(leaf)) warnings.push(`possible_raw_transcript: ${leafPath}`);
              }
            }
            if ((typeof leaf === "number" || typeof leaf === "string") && isHealthValueLikePath(leafPath)) {
              warnings.push(`possible_raw_health_value: ${leafPath}`);
            }
          });
        }
        if (ev.provenance && typeof ev.provenance === "object") {
          if (typeof ev.provenance.provenance_version !== "number") {
            warnings.push(`missing_provenance_version: dont_know.evidence[${i}].provenance`);
          }
        }
      }
    }

    return warnings;
  }

  /**
   * @param {unknown} decisions
   * @returns {string[]} warnings
   */
  function validateNonAction(decisions) {
    /** @type {string[]} */
    const warnings = [];
    if (!Array.isArray(decisions)) return warnings;

    for (let i = 0; i < decisions.length; i++) {
      const d = decisions[i] && typeof decisions[i] === "object" ? decisions[i] : {};
      if (typeof d.contract_version !== "number") warnings.push(`non_action_missing_contract_version: decisions[${i}]`);
      if (typeof d.domain !== "string") warnings.push(`non_action_missing_domain: decisions[${i}]`);
      if (typeof d.condition !== "string") warnings.push(`non_action_missing_condition: decisions[${i}]`);
      if (typeof d.required_response !== "string") warnings.push(`non_action_missing_required_response: decisions[${i}]`);

      if (d.rationale && typeof d.rationale === "object") {
        walk(d.rationale, `decisions[${i}].rationale`, (leaf, leafPath) => {
          if (typeof leaf === "string" && looksLikeAbsolutePath(leaf)) warnings.push(`absolute_path_detected: ${leafPath}`);
        });
      }
    }
    return warnings;
  }

  /**
   * @param {string} s
   * @returns {string} hex
   */
  function fnv1a32Hex(s) {
    let h = 0x811c9dc5;
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      // 32-bit FNV-1a: h *= 16777619 (via shifts to stay in uint32)
      h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
    }
    return ("00000000" + h.toString(16)).slice(-8);
  }

  /**
   * Produces a stable hash of evidence order so we can detect accidental sorting.
   *
   * @param {unknown} hits
   * @returns {string}
   */
  function computeOrderFingerprint(hits) {
    if (!Array.isArray(hits)) return "fnv1a32:00000000";
    const parts = [];
    for (let i = 0; i < hits.length; i++) {
      const h = hits[i] && typeof hits[i] === "object" ? hits[i] : {};
      const payload = h.payload && typeof h.payload === "object" ? h.payload : {};
      parts.push(
        [
          String(i),
          String(h.role || ""),
          String(h.store || ""),
          String(h.store_ref || ""),
          String(h.embedding_id || ""),
          String(payload.video_id || ""),
          String(payload.scene_id || ""),
          String(payload.model || ""),
        ].join("|")
      );
    }
    return `fnv1a32:${fnv1a32Hex(parts.join("\\n"))}`;
  }

  window.GoodQIntegrity = {
    validateEnvelope,
    validateNonAction,
    computeOrderFingerprint,
  };
})();
