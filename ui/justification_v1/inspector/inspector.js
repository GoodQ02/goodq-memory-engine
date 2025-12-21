/*
GoodQ Inspector v0 (observer-only).
No actions. No suggestions. No network calls.
*/

(function () {
  const INSPECTOR_VERSION = 0;
  const DEFAULT_MAX_ENTRIES = 500;

  /**
   * @returns {boolean}
   */
  function isEnabled() {
    if (typeof window.GOODQ_INSPECTOR_ENABLED === "boolean") return window.GOODQ_INSPECTOR_ENABLED;
    // Optional URL toggle (no network): ?inspector=1
    try {
      const params = new URLSearchParams(String(window.location && window.location.search ? window.location.search : ""));
      return params.get("inspector") === "1";
    } catch {
      return false;
    }
  }

  /**
   * @param {unknown} v
   * @returns {string}
   */
  function safeStr(v) {
    if (v === null || v === undefined) return "";
    return String(v);
  }

  /**
   * Keep only warning codes (e.g. "absolute_path_detected"), no details.
   * @param {unknown} warnings
   * @returns {string[]}
   */
  function toWarningCodes(warnings) {
    if (!Array.isArray(warnings)) return [];
    const out = [];
    const seen = new Set();
    for (const w of warnings) {
      const raw = safeStr(w).trim();
      if (!raw) continue;
      const code = raw.split(":")[0].trim();
      if (!code || seen.has(code)) continue;
      seen.add(code);
      out.push(code);
    }
    return out;
  }

  /**
   * Sanitize incoming observation: pick whitelisted fields only.
   * @param {any} obs
   */
  function sanitizeObservation(obs) {
    const o = obs && typeof obs === "object" ? obs : {};
    const counts = o.counts && typeof o.counts === "object" ? o.counts : {};
    const diag = o.diagnostics && typeof o.diagnostics === "object" ? o.diagnostics : {};
    const cmp = o.comparison && typeof o.comparison === "object" ? o.comparison : {};

    const diffCodesRaw = Array.isArray(cmp.diff_codes) ? cmp.diff_codes : [];
    const diff_codes = diffCodesRaw.map((c) => safeStr(c)).filter((s) => s.trim().length > 0).slice(0, 64);

    return {
      ts_utc: safeStr(o.ts_utc),
      ui_version: safeStr(o.ui_version),
      inspector_version: INSPECTOR_VERSION,
      event_type: safeStr(o.event_type),
      source: safeStr(o.source),
      last_render_ts_utc: safeStr(o.last_render_ts_utc),
      counts: {
        candidates: Number.isFinite(counts.candidates) ? counts.candidates : 0,
        evidence_hits: Number.isFinite(counts.evidence_hits) ? counts.evidence_hits : 0,
        non_action_decisions: Number.isFinite(counts.non_action_decisions) ? counts.non_action_decisions : 0,
      },
      diagnostics: {
        order_fingerprint: safeStr(diag.order_fingerprint),
        warnings: toWarningCodes(diag.warnings),
      },
      comparison: {
        diff_version: Number.isFinite(cmp.diff_version) ? cmp.diff_version : 0,
        diff_total: Number.isFinite(cmp.diff_total) ? cmp.diff_total : 0,
        diff_codes,
        identity_type: safeStr(cmp.identity_type),
        identity_matches: typeof cmp.identity_matches === "boolean" ? cmp.identity_matches : null,
        order_fingerprint_a: safeStr(cmp.order_fingerprint_a),
        order_fingerprint_b: safeStr(cmp.order_fingerprint_b),
        error_code: safeStr(cmp.error_code),
      },
    };
  }

  /**
   * @returns {boolean}
   */
  function canWriteFile() {
    // Best-effort Node-style detection (no dependencies).
    return (
      typeof process !== "undefined" &&
      !!process.versions &&
      !!process.versions.node &&
      typeof require === "function"
    );
  }

  /**
   * @returns {{fs:any, path:any, logPath:string} | null}
   */
  function getFs() {
    if (!canWriteFile()) return null;
    try {
      // eslint-disable-next-line no-undef
      const fs = require("fs");
      // eslint-disable-next-line no-undef
      const path = require("path");
      // eslint-disable-next-line no-undef
      const logPath = path.join(__dirname, "inspector_log.jsonl");
      return { fs, path, logPath };
    } catch {
      return null;
    }
  }

  /**
   * @param {any} fsx
   * @param {string} logPath
   * @param {number} maxEntries
   * @returns {any[]}
   */
  function readExisting(fsx, logPath, maxEntries) {
    try {
      if (!fsx.existsSync(logPath)) return [];
      const txt = fsx.readFileSync(logPath, "utf8") || "";
      const lines = txt.split(/\r?\n/).filter((l) => l.trim().length > 0);
      const tail = lines.slice(Math.max(0, lines.length - maxEntries));
      const out = [];
      for (const ln of tail) {
        try {
          out.push(JSON.parse(ln));
        } catch {
          // Skip corrupt lines (observer-only; no repair).
        }
      }
      return out;
    } catch {
      return [];
    }
  }

  /**
   * @param {any} fsx
   * @param {string} logPath
   * @param {any[]} entries
   */
  function writeBounded(fsx, logPath, entries) {
    try {
      const lines = entries.map((e) => JSON.stringify(e));
      fsx.writeFileSync(logPath, lines.join("\n") + (lines.length ? "\n" : ""), "utf8");
    } catch {
      // Best-effort only.
    }
  }

  const maxEntries =
    typeof window.GOODQ_INSPECTOR_MAX_ENTRIES === "number" && window.GOODQ_INSPECTOR_MAX_ENTRIES > 0
      ? window.GOODQ_INSPECTOR_MAX_ENTRIES
      : DEFAULT_MAX_ENTRIES;

  const fsCtx = getFs();
  const buffer = fsCtx ? readExisting(fsCtx.fs, fsCtx.logPath, maxEntries) : [];

  /**
   * @param {any} observation
   */
  function observe(observation) {
    if (!isEnabled()) return;
    const entry = sanitizeObservation(observation);
    if (!entry.ts_utc) entry.ts_utc = new Date().toISOString();

    buffer.push(entry);
    while (buffer.length > maxEntries) buffer.shift();

    if (fsCtx) writeBounded(fsCtx.fs, fsCtx.logPath, buffer);
  }

  window.GoodQInspector = {
    observe,
    isEnabled,
    getBuffer: () => buffer.slice(),
    maxEntries,
    version: INSPECTOR_VERSION,
  };
})();
