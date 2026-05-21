(function () {
  "use strict";

  const DEFAULT_API_BASE = "http://127.0.0.1:30000";
  const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1"]);
  const PATH_KEY_RE = /(^|_)(path|dir|file|files|files_read|artifact|artifacts|thumbnail|stdout|stderr|trace|raw|root)(_|$)/i;
  const WINDOWS_ABS_RE = /^[A-Za-z]:[\\/]/;
  const UNC_RE = /^\\\\/;

  const state = {
    apiBase: DEFAULT_API_BASE,
    selectedVideoId: null,
    selectedSceneKey: null,
    retrieval: {
      query: "",
      limit: 10,
      loading: false,
      hasRun: false,
      response: null,
      results: [],
      selectedKey: null,
      error: null,
    },
    mediaPreview: {
      open: false,
      source: null,
    },
    sceneLineage: null,
    loading: false,
    loadingDiagnostics: false,
    data: {},
    errors: {},
    lastRefresh: null,
  };

  const endpoints = {
    status: "/api/status",
    health: "/api/health/summary",
    engines: "/api/engines",
    gpu: "/api/gpu/stats",
    wsl: "/api/wsl2-status",
    queue: "/api/queue",
    run: "/api/runs/latest/preview",
    runEvidence: "/api/runs/latest/evidence",
    audioProvenance: "/api/runs/audio-proof/latest",
    memory: "/api/memory/stats",
    storage: "/api/storage/summary",
    recurrence: "/api/control-recurrence/reports/latest",
    trend: "/api/control-recurrence/reports/trend",
    videos: "/api/system/videos",
    envelope: "/api/read/envelope",
  };

  const STATE_GRAMMAR = Object.freeze({
    READY: { label: "Ready", kind: "ok" },
    RUNNING: { label: "Running", kind: "ok" },
    IDLE: { label: "Idle", kind: "info" },
    PARTIAL: { label: "Partial", kind: "warn" },
    OPTIONAL_OFFLINE: { label: "Optional Offline", kind: "warn" },
    NOT_CONFIGURED: { label: "Not Configured", kind: "unknown" },
    NOT_EXPOSED: { label: "Not Exposed", kind: "unknown" },
    NO_CURRENT_RUN_EVIDENCE: { label: "No Current-Run Evidence", kind: "unknown" },
    HISTORICAL_ONLY: { label: "Historical Only", kind: "historical" },
    MISMATCH: { label: "Mismatch", kind: "error" },
    NEEDS_EXPLANATION: { label: "Needs Explanation", kind: "warn" },
    FAULT: { label: "Fault", kind: "error" },
    UNKNOWN: { label: "Unknown", kind: "unknown" },
  });

  const RUN_SCOPE_GRAMMAR = Object.freeze({
    configured_output_scene_results: {
      label: "Direct CLI Output",
      kind: "ok",
      note: "configured output file; active runtime evidence",
    },
    scene_ingest_results: {
      label: "Standalone Scene Probe",
      kind: "historical",
      note: "direct scene output; wrapper ledger may be absent",
    },
    standalone_scene_results: {
      label: "Standalone Scene Probe",
      kind: "historical",
      note: "direct scene output; wrapper ledger may be absent",
    },
    wrapper_report_root: {
      label: "Wrapper Report Root",
      kind: "ok",
      note: "orchestrated report artifact root",
    },
    structured_run: {
      label: "Structured Run",
      kind: "info",
      note: "latest structured run projection",
    },
  });

  const diagnosticEndpointNames = new Set(["engines", "gpu", "wsl", "queue"]);
  const optionalEndpointNames = new Set(["envelope"]);
  const endpointTimeoutMs = {
    status: 30000,
    health: 30000,
    engines: 25000,
    wsl: 18000,
    run: 30000,
    runEvidence: 30000,
    audioProvenance: 25000,
    memory: 30000,
    retrieval: 30000,
  };
  const IMPORT_INBOX_LABEL = "<GOODQ_DATA_ROOT>\\GoodQ_Data\\import_inbox";

  function qs(selector) {
    return document.querySelector(selector);
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function appendText(parent, tagName, text, className) {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    node.textContent = text;
    parent.appendChild(node);
    return node;
  }

  function defaultApiBase() {
    try {
      const host = window.location.hostname;
      const port = window.location.port;
      if (LOCAL_HOSTS.has(host) && port && port !== "8000") {
        return window.location.origin;
      }
    } catch (_e) {
      return DEFAULT_API_BASE;
    }
    return DEFAULT_API_BASE;
  }

  function normalizeApiBase(value) {
    const raw = String(value || "").trim() || defaultApiBase();
    try {
      const url = new URL(raw);
      return `${url.protocol}//${url.host}`;
    } catch (_e) {
    return defaultApiBase();
    }
  }

  function isLocalApi(value) {
    try {
      const url = new URL(value);
      return LOCAL_HOSTS.has(url.hostname);
    } catch (_e) {
      return false;
    }
  }

  function endpointUrl(path) {
    return `${state.apiBase}${path}`;
  }

  function mediaEndpointUrl(path) {
    if (!valueObserved(path) || typeof path !== "string") return null;
    const trimmed = path.trim();
    if (trimmed.startsWith("/api/")) return endpointUrl(trimmed);
    try {
      const url = new URL(trimmed);
      if (LOCAL_HOSTS.has(url.hostname) && url.pathname.startsWith("/api/")) return trimmed;
    } catch (_e) {
      return null;
    }
    return null;
  }

  function hasPathValue(value) {
    if (typeof value !== "string") return false;
    const trimmed = value.trim();
    return (
      WINDOWS_ABS_RE.test(trimmed) ||
      UNC_RE.test(trimmed) ||
      trimmed.startsWith("file://") ||
      trimmed.startsWith("~/") ||
      trimmed.includes("\\GOODCUBE\\") ||
      trimmed.includes("\\_DATA\\")
    );
  }

  function safeString(value, key) {
    if (value === null || value === undefined) return "null";
    if (PATH_KEY_RE.test(String(key || "")) || hasPathValue(value)) {
      return "[local-only]";
    }
    if (typeof value === "boolean") return value ? "true" : "false";
    if (typeof value === "number") return Number.isFinite(value) ? String(value) : "null";
    if (Array.isArray(value)) {
      return `${value.length} item${value.length === 1 ? "" : "s"}`;
    }
    if (typeof value === "object") {
      const entries = Object.entries(value)
        .filter(([childKey, childValue]) => !PATH_KEY_RE.test(childKey) && !hasPathValue(childValue))
        .slice(0, 4)
        .map(([childKey, childValue]) => `${childKey}=${safeString(childValue, childKey)}`);
      return entries.length ? entries.join(", ") : "{}";
    }
    const text = String(value).replace(/\u0000/g, "").trim();
    if (hasPathValue(text)) return "[local-only]";
    return text.length > 96 ? `${text.slice(0, 93)}...` : text;
  }

  function valueClass(value, key) {
    return safeString(value, key) === "[local-only]" ? "kv-value redacted" : "kv-value";
  }

  function statusKind(value) {
    const text = String(value || "").toLowerCase();
    if (["ok", "active", "available", "healthy", "success", "running", "passed", "ready", "true"].includes(text)) {
      return "ok";
    }
    if (["idle", "historical only"].includes(text)) {
      return text === "idle" ? "info" : "historical";
    }
    if ([
      "warn",
      "warning",
      "partial_success",
      "partial",
      "unknown",
      "unavailable",
      "optional offline",
      "not configured",
      "not exposed",
      "no current-run evidence",
      "degraded",
      "skipped",
      "not_installed",
      "inactive",
    ].includes(text)) {
      return "warn";
    }
    if (["error", "failed", "unhealthy", "false"].includes(text)) {
      return "error";
    }
    return "unknown";
  }

  function makeBadge(text, kind) {
    const badge = document.createElement("span");
    badge.className = `badge ${kind || statusKind(text)}`;
    badge.textContent = text || "unknown";
    return badge;
  }

  function makeStatusDot(kind, label) {
    const dot = document.createElement("span");
    dot.className = `state-dot-mini ${kind || "unknown"}`;
    dot.title = label || "State indicator";
    dot.setAttribute("aria-label", label || "State indicator");
    return dot;
  }

  function appendIndicatorStrip(container, items, className) {
    const strip = document.createElement("div");
    strip.className = `indicator-strip ${className || ""}`.trim();
    items.forEach((item) => {
      const card = document.createElement("div");
      card.className = `indicator-card ${item.kind || "unknown"}`;
      if (item.title) card.title = item.title;
      const dot = document.createElement("span");
      dot.className = `indicator-dot ${item.kind || "unknown"}`;
      dot.setAttribute("aria-hidden", "true");
      card.appendChild(dot);
      const copy = document.createElement("div");
      appendText(copy, "span", item.label, "indicator-label");
      appendText(copy, "strong", item.value, "indicator-value");
      if (item.note) appendText(copy, "small", item.note, "indicator-note");
      card.appendChild(copy);
      strip.appendChild(card);
    });
    container.appendChild(strip);
  }

  function compactIdentifier(value, options) {
    const opts = options || {};
    const fallback = opts.fallback || "Not observed";
    if (!valueObserved(value)) return fallback;
    const text = safeString(value, opts.key || "id");
    const max = opts.max || 18;
    if (text.length <= max || text === "[local-only]") return text;
    const leading = opts.leading || 10;
    const trailing = opts.trailing || 4;
    return `${text.slice(0, leading)}...${text.slice(-trailing)}`;
  }

  function sceneDisplayLabel(value, fallbackIndex) {
    const fallback = Number.isFinite(fallbackIndex) ? `Result ${fallbackIndex + 1}` : "scene";
    return `Scene ${compactIdentifier(value, { fallback, key: "scene_id", max: 18, leading: 10, trailing: 4 })}`;
  }

  function confidenceBand(percent) {
    if (percent === null || percent === undefined) {
      return {
        label: "No score",
        kind: "unknown",
        note: "Search endpoint did not return a confidence score",
      };
    }
    if (percent >= 80) return { label: "Strong match", kind: "ok", note: "High-confidence retrieval result" };
    if (percent >= 50) return { label: "Reviewable match", kind: "info", note: "Useful for human inspection" };
    if (percent >= 15) return { label: "Exploratory match", kind: "warn", note: "Low confidence; inspect evidence before relying on it" };
    return { label: "Low signal", kind: "unknown", note: "Returned by search, but weakly supported" };
  }

  function confidenceLabel(percent) {
    const band = confidenceBand(percent);
    return percent === null || percent === undefined ? band.label : `${band.label} ${percentLabel(percent)}`;
  }

  function makeConfidenceBadge(percent) {
    const band = confidenceBand(percent);
    const badge = document.createElement("span");
    badge.className = `confidence-badge ${band.kind}`;
    badge.textContent = confidenceLabel(percent);
    badge.title = band.note;
    return badge;
  }

  function numberValue(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function grammarState(name, note, title) {
    const base = STATE_GRAMMAR[name] || STATE_GRAMMAR.UNKNOWN;
    return { label: base.label, kind: base.kind, note: note || "", title: title || "" };
  }

  function statusLabel(value) {
    const text = String(value || "").toLowerCase();
    if (["ok", "active", "available", "healthy", "success", "passed", "ready", "true"].includes(text)) {
      return grammarState("READY");
    }
    if (text === "running") return grammarState("RUNNING");
    if (text === "idle") return grammarState("IDLE");
    if (["degraded", "partial", "partial_success", "warn", "warning"].includes(text)) return grammarState("PARTIAL");
    if (["unavailable", "inactive", "not_installed", "skipped"].includes(text)) return grammarState("OPTIONAL_OFFLINE");
    if (["error", "failed", "unhealthy", "false"].includes(text)) return grammarState("FAULT");
    return grammarState("UNKNOWN");
  }

  function notObserved(note) {
    return grammarState("NOT_EXPOSED", note);
  }

  function llmServiceState(service, label, options) {
    const opts = options || {};
    const healthy = numberValue(service?.healthy);
    const total = numberValue(service?.total);
    const rawStatus = String(service?.status || "").toLowerCase();
    const ready = statusKind(rawStatus) === "ok" || (healthy !== null && healthy > 0);
    const countNote = total !== null ? `${healthy || 0}/${total} probes ready` : "probe count not exposed";
    if (ready) {
      return {
        label,
        value: "Ready",
        note: opts.primary ? `primary LLM path; ${countNote}` : `optional service ready; ${countNote}`,
        kind: "ok",
      };
    }
    if (opts.optional) {
      return {
        label,
        value: "Optional Offline",
        note: `${opts.role || "fallback"} offline; core memory and read/search remain usable`,
        kind: "warn",
      };
    }
    return {
      label,
      value: "Needs Explanation",
      note: `${opts.role || "primary service"} not ready; LLM enrichments may be unavailable`,
      kind: "warn",
    };
  }

  function gpuReservationState(gpu) {
    const used = numberValue(gpu?.memory_used_mb ?? gpu?.gpu_memory_used);
    const total = numberValue(gpu?.memory_total_mb ?? gpu?.gpu_memory_total);
    const reportedPercent = numberValue(gpu?.memory_percent);
    const percent = reportedPercent !== null
      ? reportedPercent
      : (used !== null && total ? Math.round((used / total) * 100) : null);
    const utilization = numberValue(gpu?.utilization_percent ?? gpu?.gpu_utilization);
    if (percent === null) {
      return {
        label: "GPU memory",
        value: "Not Exposed",
        note: "memory reservation probe not returned",
        kind: "unknown",
      };
    }
    const reservedIdle = percent >= 80 && (utilization === null || utilization <= 5);
    return {
      label: "GPU memory",
      value: reservedIdle ? "Reserved" : `${percent}% used`,
      note: reservedIdle
        ? "high memory with low utilization; likely model/runtime reservation before a long run"
        : "GPU memory pressure is visible before ingestion",
      kind: reservedIdle ? "warn" : "info",
    };
  }

  function latestStepByName(stepName) {
    const rows = state.data.runEvidence?.step_runs?.recent;
    if (!Array.isArray(rows)) return null;
    return rows.slice().reverse().find((row) => row && row.step === stepName) || null;
  }

  function wslAudioState(wsl) {
    const latestAudioStep = latestStepByName("audio_unified_wsl2");
    if (latestAudioStep && statusKind(latestAudioStep.status) === "ok") {
      return {
        label: "WSL audio",
        value: "Last Run OK",
        note: "latest evidence shows the WSL audio step completed",
        kind: "ok",
      };
    }
    const raw = String(wsl?.audio_processing || "").toLowerCase();
    if (statusKind(raw) === "ok") {
      return {
        label: "WSL audio",
        value: "Ready",
        note: "runtime probe reports audio processing available",
        kind: "ok",
      };
    }
    return {
      label: "WSL audio",
      value: "Optional Offline",
      note: "preflight probe unavailable; inspect latest step rows before treating as a run failure",
      kind: "warn",
    };
  }

  function apiEnvironment() {
    try {
      const url = new URL(state.apiBase);
      const hostPort = `${url.hostname}${url.port ? `:${url.port}` : ""}`;
      if (!LOCAL_HOSTS.has(url.hostname)) {
        return { label: `API: ${hostPort} [Non-local]`, kind: "error" };
      }
      if (url.port === "30000") return { label: `API: ${hostPort} [Live Data]`, kind: "live" };
      if (url.port === "30003") return { label: `API: ${hostPort} [Demo]`, kind: "demo" };
      return { label: `API: ${hostPort} [Local Custom]`, kind: "warn" };
    } catch (_e) {
      return { label: "API: Not observed", kind: "unknown" };
    }
  }

  function runScopeDescriptor(evidenceRun, run) {
    const scope = String((evidenceRun && evidenceRun.scope) || (run && run.scope) || "").trim();
    const runKind = String((evidenceRun && evidenceRun.run_kind) || (run && run.run_kind) || "").trim();
    const descriptor = RUN_SCOPE_GRAMMAR[scope] || RUN_SCOPE_GRAMMAR[runKind] || RUN_SCOPE_GRAMMAR.structured_run;
    if (!scope && !runKind && !(run && run.available)) {
      return {
        label: "No Run Selected",
        kind: "unknown",
        note: "latest run evidence not observed",
        raw: "",
      };
    }
    return {
      label: descriptor.label,
      kind: descriptor.kind,
      note: descriptor.note,
      raw: scope || runKind || "structured_run",
    };
  }

  function appendScopeItem(container, label, value, kind, note, title) {
    const item = document.createElement("div");
    item.className = `scope-item ${kind || "unknown"}`;
    item.setAttribute("data-testid", `scope-item-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`);
    if (title) item.title = title;
    const text = document.createElement("div");
    appendText(text, "span", label, "scope-label");
    appendText(text, "strong", safeString(value, label), "scope-value");
    if (note) appendText(text, "small", note, "scope-note");
    item.appendChild(text);
    item.appendChild(makeStatusDot(kind || "unknown", `${label}: ${safeString(value, label)}`));
    container.appendChild(item);
  }

  function flightChip(name, label, kind) {
    const chip = document.createElement("span");
    chip.className = `flight-chip ${kind || statusKind(label)}`;
    chip.textContent = label;
    chip.setAttribute("aria-label", `${name} status: ${label}`);
    return chip;
  }

  function appendFlightRow(container, name, status, testId) {
    const row = document.createElement("div");
    row.className = "flight-status-row";
    row.setAttribute("data-testid", testId || `flight-row-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`);
    if (status.title) row.title = status.title;

    const label = document.createElement("div");
    label.className = "flight-row-label";
    appendText(label, "span", name);
    if (status.note) appendText(label, "small", status.note);
    row.appendChild(label);
    row.appendChild(flightChip(name, status.label, status.kind));
    container.appendChild(row);
  }

  function appendFirstRunStep(container, index, title, stateInfo, note) {
    const row = document.createElement("div");
    row.className = "first-run-step";
    row.setAttribute("data-testid", `first-run-step-${index}`);
    appendText(row, "span", String(index), "first-run-step-index");

    const label = document.createElement("div");
    appendText(label, "span", title);
    if (note) appendText(label, "small", note);
    row.appendChild(label);
    row.appendChild(flightChip(title, stateInfo.label, stateInfo.kind));
    container.appendChild(row);
  }

  function relativeTime(value) {
    if (!value) return "Not observed";
    const timestamp = Date.parse(String(value));
    if (!Number.isFinite(timestamp)) return "Not observed";
    const diffMs = Date.now() - timestamp;
    if (diffMs < -60000) return "Future";
    const seconds = Math.max(0, Math.floor(diffMs / 1000));
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 48) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  function latestRunTimestamp(run) {
    return run?.latest_episode?.ts_utc || run?.end_time || run?.start_time || null;
  }

  function hasOkStatus(value) {
    return statusKind(value) === "ok";
  }

  function proofState(observed, observedLabel, missingLabel, note, missingKind) {
    return {
      observed: observed === true,
      label: observed === true ? observedLabel || "Observed" : missingLabel || "Not observed",
      kind: observed === true ? "ok" : missingKind || "unknown",
      note: note || "",
    };
  }

  function projectionGapNote(projection) {
    if (!projection || typeof projection !== "object") return "projection summary not exposed";
    const missing = numberValue(projection.missing_projection_count);
    const fields = projection.fields && typeof projection.fields === "object" ? projection.fields : {};
    const fieldNotes = ["visual_caption", "sentiment", "clap_meta"]
      .map((field) => {
        const row = fields[field] || {};
        const count = numberValue(row.missing_from_temporal);
        return count ? `${field}: ${count}` : null;
      })
      .filter(Boolean);
    if (projection.status === "gap_detected") {
      const prefix = missing !== null ? `${missing} missing projections` : "missing projections";
      return fieldNotes.length
        ? `${prefix}; ${fieldNotes.join(", ")} source truth not projected`
        : `${prefix}; source truth not projected`;
    }
    if (projection.status === "ok") return "source truth projected into temporal index";
    return projection.reason || "projection summary not exposed";
  }

  function appendProofItem(container, item) {
    const row = document.createElement("div");
    row.className = "proof-item";
    row.setAttribute("data-testid", item.testId || `proof-item-${item.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`);

    const label = document.createElement("div");
    label.className = "proof-item-label";
    appendText(label, "span", item.label);
    if (item.note) appendText(label, "small", item.note);
    row.appendChild(label);

    const chip = document.createElement("span");
    chip.className = `proof-chip ${item.kind || "unknown"}`;
    chip.textContent = item.status || item.labelStatus || "Not observed";
    chip.setAttribute("aria-label", `${item.label} proof status: ${chip.textContent}`);
    row.appendChild(chip);
    container.appendChild(row);
  }

  function appendAudioInventoryDrilldown(container, audioProvenance) {
    const rows = Array.isArray(audioProvenance?.runs) && audioProvenance.runs.length
      ? audioProvenance.runs
      : audioProvenance?.latest_run
        ? [audioProvenance.latest_run]
        : [];

    const panel = document.createElement("div");
    panel.className = "audio-inventory-drilldown";
    panel.setAttribute("data-testid", "audio-inventory-drilldown");

    const header = document.createElement("div");
    header.className = "audio-inventory-header";
    appendText(header, "strong", "Audio Provenance Inventory");
    appendText(header, "span", "Run-tagged Qdrant audio payloads; historical until matched to the selected run.");
    panel.appendChild(header);

    if (!rows.length) {
      appendText(panel, "p", "No run-tagged Qdrant audio inventory rows returned.", "audio-inventory-empty");
      container.appendChild(panel);
      return;
    }

    rows.slice(0, 6).forEach((row) => {
      const pointCount = numberValue(row.provenance_capable_points ?? row.point_count ?? row.points);
      const sceneCount = numberValue(row.scene_count ?? row.scenes);
      const videoCount = numberValue(row.video_count ?? row.videos);
      const latestTs = row.latest_timestamp || row.latest_ts || row.latest_commit_ts_utc || row.latest_created_at;
      const missingFields = Array.isArray(row.missing_required_fields)
        ? row.missing_required_fields
        : Object.keys(row.missing_required_fields || {});

      const item = document.createElement("div");
      item.className = "audio-inventory-row";

      const identity = document.createElement("div");
      appendText(identity, "span", "Run", "audio-inventory-label");
      const runId = appendText(identity, "strong", compactIdentifier(row.run_id, { key: "run_id", max: 26 }), "compact-id");
      runId.title = safeString(row.run_id || "Not observed", "run_id");
      item.appendChild(identity);

      const counts = document.createElement("div");
      appendText(counts, "span", "Payloads", "audio-inventory-label");
      appendText(
        counts,
        "strong",
        pointCount !== null ? `${pointCount} points` : "Not observed",
        "audio-inventory-value"
      );
      appendText(
        counts,
        "small",
        `${sceneCount !== null ? sceneCount : "?"} scenes | ${videoCount !== null ? videoCount : "?"} videos`,
        "audio-inventory-note"
      );
      item.appendChild(counts);

      const latest = document.createElement("div");
      appendText(latest, "span", "Latest", "audio-inventory-label");
      appendText(latest, "strong", latestTs ? relativeTime(latestTs) : "Not observed", "audio-inventory-value");
      item.appendChild(latest);

      const stateWrap = document.createElement("div");
      appendText(stateWrap, "span", "Scope", "audio-inventory-label");
      stateWrap.appendChild(makeBadge(missingFields.length ? "Needs Explanation" : "Historical Only", missingFields.length ? "warn" : "historical"));
      if (missingFields.length) {
        appendText(stateWrap, "small", `Missing: ${missingFields.slice(0, 3).join(", ")}`, "audio-inventory-note");
      }
      item.appendChild(stateWrap);

      panel.appendChild(item);
    });

    container.appendChild(panel);
  }

  function evidenceNote(value, suffix) {
    const number = numberValue(value);
    return number === null ? "" : `${number} ${suffix}`;
  }

  function showLoading(node) {
    clear(node);
    const template = qs("#loading-template");
    node.appendChild(template.content.cloneNode(true));
  }

  function showError(node, message) {
    clear(node);
    appendInlineError(node, message);
  }

  function appendInlineError(node, message) {
    const wrap = document.createElement("div");
    wrap.className = "error-state";
    appendText(wrap, "span", message || "Read surface unavailable.");
    node.appendChild(wrap);
  }

  async function fetchJson(name, path) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), endpointTimeoutMs[name] || 12000);
    try {
      const response = await fetch(endpointUrl(path), {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      state.errors[name] = null;
      return await response.json();
    } finally {
      window.clearTimeout(timer);
    }
  }

  async function postJson(name, path, payload) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), endpointTimeoutMs[name] || 12000);
    try {
      const response = await fetch(endpointUrl(path), {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload || {}),
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`.trim());
      }
      return await response.json();
    } finally {
      window.clearTimeout(timer);
    }
  }

  async function refreshAll() {
    state.loading = true;
    state.loadingDiagnostics = false;
    state.errors = {};
    renderLoadingShell();

    const entries = Object.entries(endpoints).filter(
      ([name]) => !diagnosticEndpointNames.has(name) && !optionalEndpointNames.has(name)
    );
    const diagnosticEntries = Object.entries(endpoints).filter(([name]) => diagnosticEndpointNames.has(name));
    diagnosticEntries.forEach(([name]) => {
      state.data[name] = null;
      state.errors[name] = null;
    });

    const results = await Promise.allSettled(entries.map(([name, path]) => fetchJson(name, path)));
    entries.forEach(([name], index) => {
      const result = results[index];
      if (result.status === "fulfilled") {
        state.data[name] = result.value;
      } else {
        state.data[name] = null;
        state.errors[name] = result.reason instanceof Error ? result.reason.message : String(result.reason);
      }
    });

    await refreshRecurrenceRecommendation();

    const videos = Array.isArray(state.data.videos) ? state.data.videos : [];
    if (!state.selectedVideoId && videos.length) {
      state.selectedVideoId = videos[0].video_id || videos[0].id || null;
    }
    await refreshTimeline();

    state.loading = false;
    state.lastRefresh = new Date();
    render();

    state.loadingDiagnostics = true;
    renderFlightDeck();
    renderDiagnostics();
    renderMachine();
    const diagnosticResults = await Promise.allSettled(
      diagnosticEntries.map(([name, path]) => fetchJson(name, path))
    );
    diagnosticEntries.forEach(([name], index) => {
      const result = diagnosticResults[index];
      if (result.status === "fulfilled") {
        state.data[name] = result.value;
      } else {
        state.data[name] = null;
        state.errors[name] = result.reason instanceof Error ? result.reason.message : String(result.reason);
      }
    });
    state.loadingDiagnostics = false;
    renderFlightDeck();
    renderDiagnostics();
    renderMachine();
  }

  async function refreshTimeline() {
    if (!state.selectedVideoId) {
      state.data.timeline = null;
      state.selectedSceneKey = null;
      state.errors.timeline = null;
      return;
    }
    try {
      state.data.timeline = await fetchJson(
        "timeline",
        `/api/videos/${encodeURIComponent(state.selectedVideoId)}/timeline/full`
      );
      state.errors.timeline = null;
      setDefaultSelectedScene();
    } catch (error) {
      state.data.timeline = null;
      state.selectedSceneKey = null;
      state.errors.timeline = error instanceof Error ? error.message : String(error);
    }
  }

  async function refreshRecurrenceRecommendation() {
    const report = state.data.recurrence && state.data.recurrence.report ? state.data.recurrence.report : {};
    const reportId = report.report_id;
    state.data.recurrenceRecommendation = null;
    state.errors.recurrenceRecommendation = null;
    if (!reportId) return;
    try {
      state.data.recurrenceRecommendation = await fetchJson(
        "recurrenceRecommendation",
        `/api/control-recurrence/reports/${encodeURIComponent(reportId)}/recommendations`
      );
    } catch (error) {
      state.errors.recurrenceRecommendation = error instanceof Error ? error.message : String(error);
    }
  }

  function panelHeader(title, subtitle, badgeText) {
    const header = document.createElement("div");
    header.className = "panel-header";

    const titleWrap = document.createElement("div");
    appendText(titleWrap, "h3", title);
    if (subtitle) appendText(titleWrap, "p", subtitle, "panel-subtitle");
    header.appendChild(titleWrap);

    if (badgeText) header.appendChild(makeBadge(badgeText));
    return header;
  }

  function renderLoadingShell() {
    [
      "#scope-banner-grid",
      "#flight-system-map",
      "#flight-first-run",
      "#first-run-guide",
      "#flight-runtime-contract",
      "#proof-list",
      "#gaps-list",
      "#proof-inspector-grid",
      "#summary-grid",
      "#run-panel",
      "#recurrence-panel",
      "#recurrence-trend-panel",
      "#surface-panel",
      "#temporal-surface-panel",
      "#diagnostics-panel",
      "#machine-panel",
      "#storage-panel",
      "#memory-panel",
      "#health-panel",
      "#video-panel",
      "#timeline-panel",
      "#scene-detail-panel",
      "#scene-modality-panel",
      "#scene-schema-panel",
      "#evidence-panel",
    ].forEach((selector) => showLoading(qs(selector)));
  }

  function renderConnection() {
    const connected = state.data.status && !state.errors.status;
    const local = isLocalApi(state.apiBase);
    const status = connected ? safeString(state.data.status.status, "status") : "unavailable";
    const kind = connected ? statusKind(status) : "error";

    const connection = qs("#connection-status");
    clear(connection);
    const dot = document.createElement("span");
    dot.className = `status-dot ${kind}`;
    dot.setAttribute("aria-hidden", "true");
    connection.appendChild(dot);
    appendText(connection, "span", connected ? `${status} from ${state.apiBase}` : `No response from ${state.apiBase}`);

    const pill = qs("#api-environment-pill");
    if (pill) {
      const environment = apiEnvironment();
      pill.className = `api-pill ${connected ? environment.kind : "error"}`;
      pill.textContent = connected ? environment.label : `API: ${state.apiBase.replace(/^https?:\/\//, "")} [No Response]`;
    }

    const boundary = qs("#boundary-panel");
    clear(boundary);
    const boundaryDot = document.createElement("span");
    boundaryDot.className = `status-dot ${local ? "ok" : "warn"}`;
    boundaryDot.setAttribute("aria-hidden", "true");
    boundary.appendChild(boundaryDot);
    appendText(boundary, "span", local ? "Local machine boundary" : "Non-local API base");
  }

  function renderScopeBanner() {
    const grid = qs("#scope-banner-grid");
    if (!grid) return;
    clear(grid);

    const connected = state.data.status && !state.errors.status;
    const run = state.data.run || {};
    const evidence = state.data.runEvidence || {};
    const evidenceRun = evidence.run || {};
    const scope = runScopeDescriptor(evidenceRun, run);
    const latestEpisode = evidence.latest_episode || run.latest_episode || {};
    const selected = selectedSegmentEntry();
    const selectedSegment = selected && selected.segment ? selected.segment : {};
    const runId = run.run_id || evidenceRun.run_id || latestEpisode.run_id || "";
    const sceneCount = numberValue(run.scenes_processed ?? latestEpisode.scene_count ?? evidence.temporal_index?.total_scenes);
    const temporalCount = numberValue(evidence.temporal_index?.total_scenes);
    const audioProof = evidence.audio_vector_proof || {};
    const audioProofStatus = String(audioProof.status || "").toLowerCase();
    const audioProofKind = audioProofStatus === "current_run_audio_vector_proven" ? "ok" : audioProofStatus === "partial" ? "warn" : "unknown";
    const audioProofLabel = audioProof.label || (audioProofKind === "ok" ? "Proven" : "No Current-Run Evidence");
    const selectedSceneValue = selected
      ? `${sceneDisplayLabel(selectedSegment.scene_id || selectedSegment.index || selected.key, selected.index)} ${formatTime(selectedSegment.start)}-${formatTime(selectedSegment.end)}`
      : "Not selected";
    const selectedSceneNote = state.sceneLineage
      ? `${state.sceneLineage.source} handoff`
      : "timeline selection";
    const environment = apiEnvironment();
    const apiKind = environment.kind === "live" ? "ok" : environment.kind;

    appendScopeItem(
      grid,
      "API",
      connected ? environment.label.replace(/^API:\s*/, "") : "No Response",
      connected ? apiKind : "error",
      connected ? "local read surface" : state.errors.status || "status endpoint unavailable",
      state.apiBase
    );
    appendScopeItem(
      grid,
      "Latest Run",
      runId ? compactIdentifier(runId, { key: "run_id", max: 24 }) : "Not observed",
      runId ? "ok" : "unknown",
      sceneCount !== null ? `${sceneCount} scene${sceneCount === 1 ? "" : "s"} in selected run scope` : "scene count not exposed",
      runId
    );
    appendScopeItem(
      grid,
      "Run Source",
      scope.label,
      scope.kind,
      scope.note,
      scope.raw
    );
    appendScopeItem(
      grid,
      "Temporal Scope",
      temporalCount !== null ? `${temporalCount} scene${temporalCount === 1 ? "" : "s"}` : "Not observed",
      temporalCount !== null ? "info" : "unknown",
      temporalCount !== null ? "latest temporal projection" : "temporal index not exposed",
      ""
    );
    appendScopeItem(
      grid,
      "Audio Proof",
      audioProofLabel,
      audioProofKind,
      audioProof.impact || "strict run-matched CLAP/Qdrant verdict",
      audioProofStatus
    );
    appendScopeItem(
      grid,
      "Browsing",
      state.selectedVideoId || latestEpisode.episode || "Not observed",
      state.selectedVideoId || latestEpisode.episode ? "info" : "unknown",
      "selected inventory/timeline target",
      state.selectedVideoId || latestEpisode.episode || ""
    );
    appendScopeItem(
      grid,
      "Selected Scene",
      selectedSceneValue,
      selected ? "ok" : "unknown",
      selected ? selectedSceneNote : "select a timeline or retrieval row",
      selectedSegment.scene_id || selectedSceneValue
    );
    appendScopeItem(
      grid,
      "Mode",
      "Read-only",
      "ok",
      "does not mutate memory, ingestion, or config",
      "operator console boundary"
    );
  }

  function renderFlightDeck() {
    const systemMap = qs("#flight-system-map");
    const firstRun = qs("#flight-first-run");
    const firstRunGuide = qs("#first-run-guide");
    const contract = qs("#flight-runtime-contract");
    if (!systemMap || !firstRun || !firstRunGuide || !contract) return;

    clear(systemMap);
    clear(firstRun);
    clear(firstRunGuide);
    clear(contract);

    const status = state.data.status || {};
    const run = state.data.run || {};
    const evidence = state.data.runEvidence || {};
    const graph = evidence.knowledge_graph || {};
    const memory = state.data.memory || {};
    const queue = state.data.queue || {};
    const gpu = state.data.gpu || {};
    const wsl = state.data.wsl || status.wsl || {};
    const engines = state.data.engines || {};
    const engineDetails = engines.engines || engines.details || {};
    const qdrantEngine = engineDetails.qdrant || engines.qdrant || {};
    const audioEngine = engineDetails.audio_diarization || engines.audio_diarization || {};
    const processingCount = numberValue(queue.processing?.count);
    const inboxCount = numberValue(queue.inbox?.count);
    const processedCount = numberValue(queue.processed?.count);
    const stepRows = numberValue(evidence.step_runs?.row_count);
    const sceneCount = numberValue(run.scenes_processed);
    const firstMemoryCreated = run.available === true && sceneCount !== null && sceneCount > 0;
    const latestRunAgo = relativeTime(latestRunTimestamp(run));
    const pipelineStatus = String(status.processing?.status || status.components?.pipeline || "").toLowerCase();
    const pipelineRunning = Boolean(pipelineStatus && !["idle", "inactive", "unknown", "unavailable"].includes(pipelineStatus));
    const processingFolderNote =
      processingCount !== null
        ? `Historical processing artifacts: ${processingCount}`
        : "Queue reachable";

    appendFlightRow(systemMap, "Launcher", grammarState("NOT_EXPOSED", "Launcher state is not exposed"), "flight-launcher-status");
    appendFlightRow(
      systemMap,
      "API Service",
      state.errors.status
        ? grammarState("FAULT", "Status endpoint unavailable")
        : {
            ...statusLabel(status.status),
            note: "Local read API",
            title: state.apiBase,
      },
      "flight-api-status"
    );
    appendFlightRow(systemMap, "Watchdog", grammarState("NOT_EXPOSED", "Process state is not exposed"), "flight-watchdog-status");
    appendFlightRow(
      systemMap,
      "Ingestion Engine",
      state.errors.queue || !state.data.queue
        ? grammarState("NOT_EXPOSED", "Queue endpoint unavailable")
        : {
            ...(pipelineRunning ? grammarState("RUNNING") : grammarState("IDLE")),
            note: pipelineRunning ? safeString(status.processing?.current_video || pipelineStatus, "current_video") : processingFolderNote,
          },
      "flight-ingestion-status"
    );
    appendFlightRow(
      systemMap,
      "SQLite",
      status.database && typeof status.database.exists === "boolean"
        ? {
            label: status.database.exists ? "Ready" : "Needs Explanation",
            kind: status.database.exists ? "ok" : "warn",
            note: status.database.exists ? "Local store observed" : "Store not observed",
          }
        : grammarState("NOT_EXPOSED", "Database probe missing"),
      "flight-sqlite-status"
    );
    appendFlightRow(
      systemMap,
      "Qdrant",
      memory.qdrant && typeof memory.qdrant.available === "boolean"
        ? {
            label: memory.qdrant.available ? "Ready" : "Optional Offline",
            kind: memory.qdrant.available ? "ok" : "warn",
            note: memory.qdrant.available
              ? `${safeString(memory.qdrant.collections, "collections")} collections`
              : "Vector store unreachable",
            title: qdrantEngine.port ? `http://127.0.0.1:${qdrantEngine.port}` : "",
          }
        : grammarState("NOT_EXPOSED", "Memory stats unavailable"),
      "flight-qdrant-status"
    );
    appendFlightRow(
      systemMap,
      "Knowledge Graph",
      graph.status
        ? statusLabel(graph.status)
        : state.errors.runEvidence
          ? grammarState("NOT_EXPOSED", "Evidence endpoint unavailable")
          : grammarState("NOT_EXPOSED", "Graph rollup missing"),
      "flight-kg-status"
    );

    appendFlightRow(
      firstRun,
      "Qdrant Reachable",
      memory.qdrant?.available === true
        ? grammarState("READY", `${safeString(memory.qdrant.collections, "collections")} collections`)
        : grammarState("OPTIONAL_OFFLINE", "Vector store not reachable from this view"),
      "flight-first-run-qdrant"
    );
    appendFlightRow(
      firstRun,
      "Import Inbox",
      state.errors.queue || !state.data.queue
        ? grammarState("NOT_EXPOSED", "Inbox count unavailable")
        : {
            ...(inboxCount && inboxCount > 0 ? grammarState("READY") : grammarState("IDLE")),
            label: inboxCount && inboxCount > 0 ? `${inboxCount} file${inboxCount === 1 ? "" : "s"}` : "Idle",
            note: IMPORT_INBOX_LABEL,
          },
      "flight-import-inbox"
    );
    appendFlightRow(firstRun, "Watchdog", grammarState("NOT_EXPOSED", "Process state is not exposed"), "flight-first-run-watchdog");
    appendFlightRow(
      firstRun,
      "Running Tasks",
      state.errors.queue || !state.data.queue
        ? grammarState("NOT_EXPOSED", "Queue count unavailable")
        : {
            ...(pipelineRunning ? grammarState("RUNNING") : grammarState("IDLE")),
            label: pipelineRunning ? "Running" : "0 running",
            note: pipelineRunning ? processingFolderNote : `Backlog not exposed; ${processingFolderNote}`,
          },
      "flight-processing-queue"
    );
    appendFlightRow(
      firstRun,
      "Latest Run",
      run.available
        ? {
            label: latestRunAgo,
            kind: "ok",
            note: safeString(run.status || "observed", "status"),
          }
        : grammarState("NO_CURRENT_RUN_EVIDENCE", "No run preview"),
      "flight-latest-run"
    );
    appendFlightRow(
      firstRun,
      "First Memory",
      firstMemoryCreated
        ? {
            label: "Created",
            kind: "ok",
            note: `${sceneCount} scenes observed`,
          }
        : run.available
          ? grammarState("NEEDS_EXPLANATION", "No scene count observed")
          : grammarState("NO_CURRENT_RUN_EVIDENCE", "No run preview"),
      "flight-first-memory"
    );

    appendText(firstRunGuide, "div", "Make One Memory", "first-run-guide-title");
    appendFirstRunStep(
      firstRunGuide,
      1,
      "Confirm local API",
      state.errors.status ? grammarState("FAULT") : grammarState("READY"),
      state.apiBase
    );
    appendFirstRunStep(
      firstRunGuide,
      2,
      "Drop one supported file",
      inboxCount && inboxCount > 0 ? grammarState("READY") : grammarState("IDLE"),
      inboxCount && inboxCount > 0 ? "File name redacted; waiting for watchdog pickup" : IMPORT_INBOX_LABEL
    );
    appendFirstRunStep(
      firstRunGuide,
      3,
      "Watch processing",
      pipelineRunning ? grammarState("RUNNING") : grammarState("IDLE"),
      `Running ${pipelineRunning ? 1 : 0}; processed ${processedCount || 0}; ${processingFolderNote}`
    );
    appendFirstRunStep(
      firstRunGuide,
      4,
      "Open first scene memory",
      firstMemoryCreated ? grammarState("READY") : grammarState("NO_CURRENT_RUN_EVIDENCE"),
      firstMemoryCreated ? `${sceneCount} scenes available` : "No current-run scene memory yet"
    );
    if (stepRows !== null) {
      appendFirstRunStep(
        firstRunGuide,
        5,
        "Review proof ledger",
        stepRows > 0 ? grammarState("HISTORICAL_ONLY") : grammarState("NO_CURRENT_RUN_EVIDENCE"),
        `${stepRows} recent step rows`
      );
    }

    const gpuLabel =
      gpu.available === true
        ? `${safeString(gpu.name || "GPU", "name")} (available${gpu.utilization_percent !== undefined ? `, ${safeString(gpu.utilization_percent, "utilization_percent")}% active` : ""})`
        : status.gpu && numberValue(status.gpu.gpu_memory_total) !== null
          ? `GPU telemetry observed (${safeString(status.gpu.gpu_memory_used, "gpu_memory_used")}/${safeString(status.gpu.gpu_memory_total, "gpu_memory_total")} MB)`
          : "Not observed";
    const wslLabel =
      wsl.active === true || wsl.status === "running"
        ? "Running"
        : wsl.available === true
          ? "Available, not active"
          : "Not observed";
    const audioLabel =
      audioEngine.status && statusKind(audioEngine.status) === "ok"
        ? "Offline diarization ready"
        : "Not observed";
    const qdrantLabel =
      memory.qdrant?.available === true || statusKind(qdrantEngine.status) === "ok"
        ? "http://127.0.0.1:6333"
        : "Not observed";

    const contractRows = [
      ["Profile", "Not observed"],
      ["GPU", gpuLabel],
      ["WSL2", wslLabel],
      ["Audio Backend", audioLabel],
      ["Local API", state.apiBase],
      ["Qdrant", qdrantLabel],
    ];
    contractRows.forEach(([label, value], index) => {
      if (index > 0) appendText(contract, "span", " | ", "flight-contract-separator");
      const group = document.createElement("span");
      group.className = "flight-contract-item";
      appendText(group, "strong", `${label}: `);
      appendText(group, "span", safeString(value, label), label === "Local API" || label === "Qdrant" ? "mono-value" : "");
      contract.appendChild(group);
    });
  }

  function renderProofPanel() {
    const proofList = qs("#proof-list");
    const gapsList = qs("#gaps-list");
    const inspector = qs("#proof-inspector-grid");
    const density = qs("#proof-density-value");
    const scoreValue = qs("#proof-score-value");
    const scoreMax = qs("#proof-score-max");
    const docsLink = qs("#proof-api-docs");
    if (!proofList || !gapsList || !inspector || !density || !scoreValue || !scoreMax) return;

    clear(proofList);
    clear(gapsList);
    clear(inspector);
    if (docsLink) docsLink.href = `${state.apiBase}/docs`;

    if (state.errors.runEvidence) {
      appendInlineError(proofList, `Run evidence unavailable: ${state.errors.runEvidence}`);
      appendInlineError(gapsList, "Proof coverage cannot be derived until latest run evidence is reachable.");
      density.textContent = "0%";
      scoreValue.textContent = "0";
      scoreMax.textContent = "/ 0";
      return;
    }

    const run = state.data.run || {};
    const evidence = state.data.runEvidence || {};
    const evidenceRun = evidence.run || {};
    const runScope = evidenceRun.scope || run.scope || "";
    const runKind = evidenceRun.run_kind || run.run_kind || "";
    const standaloneSceneScope = runScope === "scene_ingest_results" || runKind === "standalone_scene_results";
    const artifacts = evidence.artifact_presence || {};
    const steps = evidence.step_runs || {};
    const temporal = evidence.temporal_index || {};
    const sentiment = evidence.sentiment || {};
    const graph = evidence.knowledge_graph || {};
    const projection = evidence.projection_gaps || {};
    const audioProof = evidence.audio_vector_proof || {};
    const audioProvenance = state.data.audioProvenance || {};
    const latestAudioInventoryRun = audioProvenance.latest_run || {};
    const latestEpisode = evidence.latest_episode || run.latest_episode || {};
    const memory = state.data.memory || {};
    const faissAudioCount = numberValue(memory.faiss?.audio_vectors);
    const sceneContextCount = numberValue(temporal.segments_with_scene_context_llm);
    const audioEmotionCount = numberValue(sentiment.segments_with_audio_emotion ?? temporal.segments_with_audio_emotion);
    const sentimentCount = numberValue(sentiment.segments_with_sentiment);
    const transcriptCount = numberValue(sentiment.segments_with_transcript ?? temporal.segments_with_transcript);
    const clapOkCount = numberValue(audioProof.clap_ok);
    const provenAudioCount = numberValue(audioProof.current_run_qdrant_proven);
    const stepRows = numberValue(steps.row_count);
    const temporalScenes = numberValue(temporal.total_scenes);
    const graphScenes = numberValue(graph.scene_count);
    const runScenes = numberValue(run.scenes_processed);
    const projectionMissing = numberValue(projection.missing_projection_count);
    const projectionReady = projection.status === "ok";
    const projectionGapDetected = projection.status === "gap_detected";
    const audioProofStatus = String(audioProof.status || "unavailable");
    const audioProofObserved = audioProofStatus === "current_run_audio_vector_proven";
    const audioProofPartial = audioProofStatus === "partial";
    const audioProofKind = audioProofObserved ? "ok" : audioProofPartial ? "warn" : "unknown";
    const audioProofLabel = audioProof.label || (audioProofObserved ? "Proven" : "No Current-Run Evidence");
    const audioProofNote = provenAudioCount !== null && clapOkCount !== null
      ? `${provenAudioCount} / ${clapOkCount} CLAP-ok scenes`
      : audioProof.impact || "Run-matched Qdrant proof not reported";
    const provenanceCapablePoints = numberValue(audioProvenance.provenance_capable_points);
    const runTaggedAudioRuns = numberValue(audioProvenance.run_tagged_audio_runs);
    const latestInventoryPoints = numberValue(latestAudioInventoryRun.provenance_capable_points);
    const audioInventoryObserved = audioProvenance.status === "ok" && provenanceCapablePoints !== null && provenanceCapablePoints > 0;
    const audioInventoryNote = audioInventoryObserved
      ? `${provenanceCapablePoints} provenance-capable payloads across ${runTaggedAudioRuns || 0} run-tagged runs`
      : audioProvenance.impact || "Separate Qdrant inventory not exposed";
    const sceneResultsFallbackNote = sentiment.source === "scene_ingest_results" ? "Scene results fallback" : "";
    const stepLedgerMissingLabel = standaloneSceneScope ? "Standalone scope" : "Not observed";
    const temporalMissingLabel = standaloneSceneScope ? "Standalone scope" : "Not observed";
    const stepLedgerMissingNote = standaloneSceneScope
      ? "Direct scene probes do not generate wrapper step ledgers."
      : "step_runs.jsonl missing or unreadable";
    const temporalMissingNote = standaloneSceneScope
      ? "Direct scene probes do not generate temporal indexes."
      : "temporal_index.json missing or unreadable";
    const temporalEvidenceNote = temporalScenes !== null
      ? evidenceNote(temporalScenes, "scenes")
      : standaloneSceneScope
        ? "Standalone scene probe"
        : "";

    const proofRows = [
      {
        label: "Step run ledger",
        state: proofState(artifacts.step_runs_jsonl === true && hasOkStatus(steps.status), "Observed", stepLedgerMissingLabel, stepRows !== null ? evidenceNote(stepRows, "rows") : standaloneSceneScope ? "Standalone scene probe" : "", standaloneSceneScope ? "historical" : "warn"),
        missingNote: stepLedgerMissingNote,
      },
      {
        label: "Temporal index",
        state: proofState(artifacts.temporal_index_json === true && hasOkStatus(temporal.status), "Observed", temporalMissingLabel, temporalEvidenceNote, standaloneSceneScope ? "historical" : "warn"),
        missingNote: temporalMissingNote,
      },
      {
        label: "Scene ingest results",
        state: proofState(artifacts.scene_ingest_results_json === true, "Observed", "Not observed", "scene_ingest_results.json", "warn"),
        missingNote: "scene_ingest_results.json missing",
      },
      {
        label: "Scene context LLM",
        state: proofState(sceneContextCount !== null && sceneContextCount > 0, "Observed", "Not observed", evidenceNote(sceneContextCount, "segments"), "warn"),
        missingNote: "No scene_context_llm segments reported",
      },
      {
        label: "Audio emotion signal",
        state: proofState(temporal.has_audio === true || (audioEmotionCount !== null && audioEmotionCount > 0), "Observed", "Not observed", audioEmotionCount !== null ? `${audioEmotionCount} emotion rows ${sceneResultsFallbackNote}`.trim() : "", "unknown"),
        missingNote: standaloneSceneScope ? "Scene results fallback did not report audio emotion" : "Latest temporal index does not report audio",
      },
      {
        label: "Transcript Audio",
        state: proofState(temporal.has_transcripts === true || (transcriptCount !== null && transcriptCount > 0), "Observed", "Not observed", transcriptCount !== null ? `${transcriptCount} transcript scenes ${sceneResultsFallbackNote}`.trim() : evidenceNote(sentiment.segments_total, "segments"), "unknown"),
        missingNote: standaloneSceneScope ? "Scene results fallback did not report transcripts" : "Latest temporal index does not report transcripts",
      },
      {
        label: "Knowledge Graph",
        state: proofState(hasOkStatus(graph.status), "Observed", "Not observed", evidenceNote(graphScenes, "scenes"), "warn"),
        missingNote: "Knowledge graph rollup unavailable",
      },
      {
        label: "Qdrant scene proof",
        state: proofState(graph.qdrant_ok === true || graph.phase6_qdrant_ok === true || latestEpisode.qdrant_ok === true, "Observed", "Not observed", "latest run scene payload", "warn"),
        missingNote: "Qdrant scene proof not reported for latest evidence",
      },
      {
        label: "Phase 6 complete",
        state: proofState(graph.phase6_complete === true || temporal.phase6_complete === true || latestEpisode.phase6_complete === true, "Observed", "Not observed", "fusion status", "warn"),
        missingNote: "Phase 6 completion not proven",
      },
    ];

    const supplementalChecks = [
      {
        label: "Sentiment labels",
        state: proofState(sentimentCount !== null && sentimentCount > 0, "Observed", "Not observed", sentimentCount !== null ? `${sentimentCount} labels` : "", "unknown"),
        missingNote: "Audio emotion may exist while text sentiment labels are absent",
      },
      {
        label: "CLAP memory commit",
        state: proofState(clapOkCount !== null && clapOkCount > 0, "Present", "No data in this run", clapOkCount !== null ? `${clapOkCount} CLAP-ok scenes` : "", "unknown"),
        missingNote: "Scene results do not report CLAP-ok audio commits for this run",
      },
      {
        label: "Projection gap check",
        state: {
          observed: projectionReady,
          label: projectionReady ? "Ready" : projectionGapDetected ? "Needs Explanation" : standaloneSceneScope ? "Standalone scope" : "Not Exposed",
          kind: projectionReady ? "ok" : projectionGapDetected ? "warn" : standaloneSceneScope ? "historical" : "unknown",
          note: standaloneSceneScope && !projectionReady && !projectionGapDetected ? "Direct scene probes do not generate temporal projection comparisons." : projectionGapNote(projection),
        },
        missingNote: projectionGapNote(projection),
      },
      {
        label: "Current-run Qdrant audio proof",
        state: {
          observed: audioProofObserved,
          label: audioProofLabel,
          kind: audioProofKind,
          note: audioProofNote,
        },
        missingNote: audioProof.impact || "FAISS audio count is not current-run Qdrant proof",
      },
      {
        label: "Run-tagged Qdrant audio inventory",
        state: {
          observed: audioInventoryObserved,
          label: audioInventoryObserved ? "Observed" : (audioProvenance.label || "Not Exposed"),
          kind: audioInventoryObserved ? "historical" : "unknown",
          note: audioInventoryNote,
        },
        missingNote: "Separate inventory does not override latest structured-run proof",
      },
      {
        label: "FAISS audio count",
        state: {
          observed: faissAudioCount !== null && faissAudioCount > 0,
          label: faissAudioCount !== null && faissAudioCount > 0 ? "Count present" : "Not observed",
          kind: faissAudioCount !== null && faissAudioCount > 0 ? "warn" : "unknown",
          note: faissAudioCount !== null ? `${faissAudioCount} count-only vectors` : "Count unavailable",
        },
        missingNote: faissAudioCount !== null ? `${faissAudioCount} count-only vectors` : "Count unavailable",
      },
    ];

    const proofDisplayRows = proofRows.concat(
      supplementalChecks.filter((row) => (
        row.label === "CLAP memory commit"
        || row.label === "Projection gap check"
        || row.label === "Current-run Qdrant audio proof"
        || row.label === "Run-tagged Qdrant audio inventory"
      ))
    );
    const coreObserved = proofRows.filter((row) => row.state.observed).length;
    const optionalObserved = supplementalChecks.filter((row) => row.state.observed).length;
    appendIndicatorStrip(
      proofList,
      [
        {
          label: "Core proof",
          value: `${coreObserved}/${proofRows.length}`,
          note: "scene, temporal, graph",
          kind: coreObserved === proofRows.length ? "ok" : "warn",
        },
        {
          label: "Optional enrichment",
          value: `${optionalObserved}/${supplementalChecks.length}`,
          note: "sentiment, CLAP, FAISS",
          kind: optionalObserved === supplementalChecks.length ? "ok" : "warn",
        },
        {
          label: "Audio vector proof",
          value: audioProofObserved
            ? `${provenAudioCount || 0}/${clapOkCount || 0}`
            : `0/${clapOkCount || 0}`,
          note: "Latest structured run",
          kind: audioProofObserved ? "ok" : "unknown",
          title: audioProofNote,
        },
        {
          label: "Audio inventory",
          value: audioInventoryObserved
            ? `${latestInventoryPoints || 0} latest`
            : "Not exposed",
          note: "run-tagged Qdrant",
          kind: audioInventoryObserved ? "historical" : "unknown",
          title: `${audioInventoryNote}; does not override latest structured-run proof`,
        },
        {
          label: "Projection gaps",
          value: projectionMissing !== null ? String(projectionMissing) : "Not exposed",
          note: "source truth vs temporal index",
          kind: projectionReady ? "ok" : projectionGapDetected ? "warn" : "unknown",
          title: projectionGapNote(projection),
        },
      ],
      "proof-rollup-strip"
    );
    proofDisplayRows.forEach((row) => {
      const compactStatus = row.label === "Current-run Qdrant audio proof"
        ? row.state.label
        : row.label === "Run-tagged Qdrant audio inventory"
          ? row.state.label
        : row.state.observed
          ? "On"
          : row.state.kind === "historical"
            ? "Scope"
          : row.state.kind === "warn"
            ? "Review"
            : "Off";
      appendProofItem(proofList, {
        label: row.label,
        note: row.state.note,
        status: compactStatus,
        kind: row.state.kind,
      });
    });

    const coverageStates = proofRows.map((row) => row.state).concat(supplementalChecks.map((row) => row.state));
    const observedCount = coverageStates.filter((stateItem) => stateItem.observed).length;
    const coverage = coverageStates.length ? Math.round((observedCount / coverageStates.length) * 100) : 0;
    density.textContent = `${coverage}%`;
    scoreValue.textContent = String(observedCount);
    scoreMax.textContent = `/ ${coverageStates.length}`;

    const gapRows = proofRows
      .filter((row) => !row.state.observed)
      .map((row) => ({
        label: row.label,
        note: row.missingNote,
        status: row.state.label,
        kind: row.state.kind,
      }));
    supplementalChecks
      .filter((row) => !row.state.observed || row.state.kind === "warn")
      .forEach((row) => {
        gapRows.push({
          label: row.label,
          note: row.missingNote,
          status: row.state.label,
          kind: row.state.kind,
        });
      });

    if (!gapRows.length) {
      appendProofItem(gapsList, {
        label: "No provenance gaps surfaced",
        note: "Current UI-safe read models agree",
        status: "Clear",
        kind: "ok",
      });
    } else {
      gapRows.slice(0, 10).forEach((gap) => appendProofItem(gapsList, gap));
    }

    const inspectorRows = [
      ["Run", run.run_id || evidence.run?.run_id || "Not observed"],
      ["Run scope", standaloneSceneScope ? "Standalone scene probe" : (runScope || runKind || "Structured run")],
      ["Latest episode", latestEpisode.episode || "Not observed"],
      ["Latest timestamp", latestEpisode.ts_utc ? relativeTime(latestEpisode.ts_utc) : relativeTime(latestRunTimestamp(run))],
      ["Run scenes", runScenes !== null ? runScenes : "Not observed"],
      ["Temporal scenes", temporalScenes !== null ? temporalScenes : "Not observed"],
      ["Step rows", stepRows !== null ? stepRows : "Not observed"],
      ["Phase 6", graph.phase6_complete === true || temporal.phase6_complete === true ? "Complete" : "Not observed"],
      ["Qdrant", graph.qdrant_ok === true || graph.phase6_qdrant_ok === true ? "Observed" : "Not observed"],
      ["Latest structured run audio", audioProofLabel],
      ["Audio inventory run", latestAudioInventoryRun.run_id ? compactIdentifier(latestAudioInventoryRun.run_id, { key: "run_id", max: 22 }) : "Not observed"],
      ["Inventory proof points", latestInventoryPoints !== null ? `${latestInventoryPoints} provenance-capable` : "Not observed"],
      ["Safety boundary", evidence.safety_boundary?.mode || "read_only"],
    ];

    inspectorRows.forEach(([label, value]) => {
      const cell = document.createElement("div");
      cell.className = "proof-inspector-cell";
      appendText(cell, "span", label);
      appendText(cell, "strong", safeString(value, label));
      inspector.appendChild(cell);
    });
    appendAudioInventoryDrilldown(inspector, audioProvenance);
  }

  function metric(label, value, note, kind) {
    const item = document.createElement("article");
    item.className = "metric";
    const labelRow = document.createElement("div");
    labelRow.className = "metric-label";
    appendText(labelRow, "span", label);
    labelRow.appendChild(makeBadge(kind || statusKind(value), kind));
    item.appendChild(labelRow);
    appendText(item, "div", safeString(value, label), "metric-value");
    appendText(item, "div", note || "", "metric-note");
    return item;
  }

  function renderSummary() {
    const grid = qs("#summary-grid");
    clear(grid);

    const status = state.data.status || {};
    const health = state.data.health || {};
    const run = state.data.run || {};
    const memory = state.data.memory || {};
    const videos = Array.isArray(state.data.videos) ? state.data.videos : [];

    grid.appendChild(
      metric(
        "API status",
        status.status || "unavailable",
        `Version ${safeString(status.version || "unknown", "version")}`,
        statusKind(status.status)
      )
    );
    grid.appendChild(
      metric(
        "Core runtime",
        status.database?.exists === true && memory.qdrant?.available === true ? "Ready" : "Partial",
        `SQLite ${status.database?.exists === true ? "ready" : "not exposed"}; Qdrant ${memory.qdrant?.available === true ? "ready" : "not observed"}`,
        status.database?.exists === true && memory.qdrant?.available === true ? "ok" : "warn"
      )
    );
    const optionalHealthy = numberValue(health.overall?.healthy);
    const optionalTotal = numberValue(health.overall?.total);
    grid.appendChild(
      metric(
        "Latest run",
        run.status || "unknown",
        run.available ? `${safeString(run.scenes_processed, "scenes_processed")} scenes processed` : "No run preview",
        statusKind(run.status)
      )
    );
    grid.appendChild(
      metric(
        "Optional model services",
        optionalTotal !== null && optionalHealthy === optionalTotal ? "Ready" : "Optional Offline",
        optionalTotal !== null ? `${optionalHealthy || 0}/${optionalTotal} optional services ready` : "Health summary pending",
        optionalTotal !== null && optionalHealthy === optionalTotal ? "ok" : "warn"
      )
    );
    grid.appendChild(
      metric(
        "Video inventory",
        videos.length,
        memory.qdrant ? `${safeString(memory.qdrant.collections, "collections")} Qdrant collections` : "Memory stats pending",
        videos.length ? "ok" : "warn"
      )
    );
  }

  function renderKv(container, data, keys) {
    const list = document.createElement("div");
    list.className = "kv-list";
    keys.forEach((key) => {
      const row = document.createElement("div");
      row.className = "kv-row";
      appendText(row, "div", key, "kv-key");
      appendText(row, "div", safeString(data ? data[key] : null, key), valueClass(data ? data[key] : null, key));
      list.appendChild(row);
    });
    container.appendChild(list);
  }

  function renderMiniList(container, title, rows, labelKey, valueKey) {
    if (!Array.isArray(rows) || !rows.length) return;
    appendText(container, "h3", title, "panel-subtitle");
    const list = document.createElement("div");
    list.className = "mini-list";
    rows.slice(0, 8).forEach((item) => {
      const row = document.createElement("div");
      row.className = "mini-row";
      appendText(row, "span", safeString(item[labelKey] || item.label || item.step || "unknown", labelKey));
      appendText(row, "strong", safeString(item[valueKey] ?? item.count ?? item.status ?? "observed", valueKey));
      list.appendChild(row);
    });
    container.appendChild(list);
  }

  function renderAudioEmotionDistribution(container, sentiment, temporal) {
    const rows = Array.isArray(sentiment.top_audio_emotions) ? sentiment.top_audio_emotions : [];
    const rawScoreRows = Array.isArray(sentiment.top_audio_emotion_score_signals)
      ? sentiment.top_audio_emotion_score_signals
      : [];
    const total = numberValue(sentiment.segments_total ?? temporal.total_scenes);
    const covered = numberValue(sentiment.segments_with_audio_emotion ?? temporal.segments_with_audio_emotion);

    appendText(container, "h3", "Audio Emotion Distribution", "panel-subtitle");
    const panel = document.createElement("div");
    panel.className = "emotion-distribution";
    panel.setAttribute("data-testid", "audio-emotion-distribution");

    appendIndicatorStrip(
      panel,
      [
        {
          label: "Coverage",
          value: covered !== null && total !== null ? `${covered}/${total}` : "Not exposed",
          note: "Audio classifier labels, latest temporal index",
          kind: covered !== null && total !== null && covered === total ? "ok" : "warn",
        },
        {
          label: "Label families",
          value: String(rows.length),
          note: rows.length ? "observed emotion buckets" : "no buckets returned",
          kind: rows.length ? "info" : "unknown",
        },
        {
          label: "Raw score buckets",
          value: String(rawScoreRows.length),
          note: rawScoreRows.length ? "reviewable scores; not promoted labels" : "no raw score buckets returned",
          kind: rawScoreRows.length ? "info" : "unknown",
        },
        {
          label: "Text sentiment",
          value: numberValue(sentiment.segments_with_sentiment) ? "Observed" : "Not present",
          note: "tracked separately from audio emotion",
          kind: numberValue(sentiment.segments_with_sentiment) ? "ok" : "unknown",
        },
      ],
      "emotion-rollup-strip"
    );

    if (!rows.length) {
      appendText(panel, "p", "No promoted audio emotion labels present in this run.", "sentiment-empty-state");
      if (rawScoreRows.length) {
        appendText(
          panel,
          "p",
          "Raw audio emotion score buckets are available for operator review; they are not promoted as current-run labels.",
          "sentiment-empty-state"
        );
        const rawList = document.createElement("div");
        rawList.className = "emotion-bar-list";
        rawScoreRows.slice(0, 8).forEach((row) => {
          const score = numberValue(row.max_score ?? row.average_score) || 0;
          const count = numberValue(row.count) || 0;
          const percent = Math.max(4, Math.min(100, Math.round(score * 100)));
          const item = document.createElement("div");
          item.className = "emotion-bar-row";
          item.setAttribute("aria-label", `${safeString(row.label || "unknown", "label")}: raw score ${formatPercent(score)}`);

          const label = document.createElement("span");
          label.className = "emotion-bar-label";
          label.textContent = safeString(row.label || "unknown", "label");
          item.appendChild(label);

          const track = document.createElement("div");
          track.className = "emotion-bar-track";
          const fill = document.createElement("span");
          fill.className = "emotion-bar-fill";
          fill.style.width = `${percent}%`;
          track.appendChild(fill);
          item.appendChild(track);

          appendText(item, "span", `${formatPercent(score)} raw | ${count} scene${count === 1 ? "" : "s"}`, "emotion-bar-count");
          rawList.appendChild(item);
        });
        panel.appendChild(rawList);
      }
      container.appendChild(panel);
      return;
    }

    const rowSum = rows.reduce((sum, row) => sum + (numberValue(row.count) || 0), 0);
    const denominator = total || rowSum || 1;
    const list = document.createElement("div");
    list.className = "emotion-bar-list";
    rows.slice(0, 8).forEach((row) => {
      const count = numberValue(row.count) || 0;
      const percent = denominator ? Math.max(4, Math.min(100, Math.round((count / denominator) * 100))) : 0;
      const item = document.createElement("div");
      item.className = "emotion-bar-row";
      item.setAttribute("aria-label", `${safeString(row.label || "unknown", "label")}: ${count}/${denominator} scenes`);

      const label = document.createElement("span");
      label.className = "emotion-bar-label";
      label.textContent = safeString(row.label || "unknown", "label");
      item.appendChild(label);

      const track = document.createElement("div");
      track.className = "emotion-bar-track";
      const fill = document.createElement("span");
      fill.className = "emotion-bar-fill";
      fill.style.width = `${percent}%`;
      track.appendChild(fill);
      item.appendChild(track);

      appendText(item, "strong", `${count}/${denominator}`, "emotion-bar-count");
      list.appendChild(item);
    });
    panel.appendChild(list);

    if (!numberValue(sentiment.segments_with_sentiment)) {
      appendText(panel, "p", "Text sentiment labels not present in this run.", "sentiment-empty-state");
    } else {
      renderMiniList(panel, "Sentiment labels", sentiment.sentiment_labels, "label", "count");
    }
    container.appendChild(panel);
  }

  function renderRecentSteps(container, rows) {
    if (!Array.isArray(rows) || !rows.length) return;
    appendText(container, "h3", "Recent step rows", "panel-subtitle");
    const table = document.createElement("table");
    table.className = "table compact-table";
    const head = document.createElement("thead");
    head.innerHTML = "<tr><th>Step</th><th>Status</th><th>Duration</th></tr>";
    table.appendChild(head);
    const body = document.createElement("tbody");
    rows.slice(-6).forEach((item) => {
      const tr = document.createElement("tr");
      appendText(tr, "td", safeString(item.step || "unknown", "step"));
      const statusCell = document.createElement("td");
      statusCell.appendChild(makeBadge(safeString(item.status || "unknown", "status")));
      tr.appendChild(statusCell);
      appendText(tr, "td", `${safeString(item.duration_ms ?? "n/a", "duration_ms")} ms`);
      body.appendChild(tr);
    });
    table.appendChild(body);
    container.appendChild(table);
  }

  function renderSimpleTable(container, columns, rows) {
    if (!Array.isArray(rows) || !rows.length) return;
    const table = document.createElement("table");
    table.className = "table compact-table";
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    columns.forEach((column) => appendText(headRow, "th", column.label));
    head.appendChild(headRow);
    table.appendChild(head);
    const body = document.createElement("tbody");
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      columns.forEach((column) => {
        const td = document.createElement("td");
        if (column.badge) {
          td.appendChild(makeBadge(safeString(row[column.key] || "unknown", column.key)));
        } else {
          td.textContent = safeString(row[column.key], column.key);
        }
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    table.appendChild(body);
    container.appendChild(table);
  }

  function renderTextList(container, title, rows, emptyText) {
    appendText(container, "h3", title, "panel-subtitle");
    const list = document.createElement("div");
    list.className = "mini-list";
    if (Array.isArray(rows) && rows.length) {
      rows.slice(0, 5).forEach((item, index) => {
        const row = document.createElement("div");
        row.className = "mini-row";
        appendText(row, "span", `${index + 1}. ${safeString(item, title)}`);
        list.appendChild(row);
      });
    } else {
      appendText(list, "span", emptyText, "scene-chip-empty");
    }
    container.appendChild(list);
  }

  function renderRecurrenceRecommendation(container, reportId) {
    appendText(container, "h3", "Recommended next inspection", "panel-subtitle");
    const boundary =
      "This panel only reads existing durable recurrence reports. It does not generate reports, trigger ingestion, heal, mutate configs, or activate ControlAgent.";
    if (!reportId) {
      appendText(container, "p", `No recommendation draft available. ${boundary}`, "panel-subtitle");
      return;
    }
    if (state.errors.recurrenceRecommendation) {
      appendInlineError(container, `Recommendation draft unavailable: ${state.errors.recurrenceRecommendation}`);
      appendText(container, "p", boundary, "panel-subtitle");
      return;
    }
    const draft = state.data.recurrenceRecommendation || {};
    if (draft.status !== "ok") {
      appendText(container, "p", `No recommendation draft available. ${boundary}`, "panel-subtitle");
      return;
    }
    renderKv(container, draft, ["recommendation_status", "highest_category", "defer_mutation_reason"]);
    renderTextList(
      container,
      "Top operator priorities",
      draft.top_operator_priorities,
      "No operator priorities were produced."
    );
    renderTextList(
      container,
      "Inspection plan",
      draft.inspection_plan,
      "No inspection steps were produced."
    );
    appendText(container, "p", boundary, "panel-subtitle");
  }

  function renderRun() {
    const node = qs("#run-panel");
    clear(node);
    if (state.errors.run) return showError(node, `Run preview unavailable: ${state.errors.run}`);
    const run = state.data.run || {};
    node.appendChild(panelHeader("Run preview", safeString(run.run_id || "No run id", "run_id"), run.status || "unknown"));
    renderKv(node, run, [
      "available",
      "status",
      "epoch",
      "source_dir",
      "episodes_total",
      "episodes_completed",
      "episodes_failed",
      "episodes_running",
      "scenes_processed",
      "total_duration_seconds",
    ]);

    if (run.latest_episode) {
      appendText(node, "h3", "Latest episode", "panel-subtitle");
      renderKv(node, run.latest_episode, ["episode", "status", "scene_count", "phase6_complete", "qdrant_ok", "ts_utc"]);
    }
  }

  function renderRecurrence() {
    const node = qs("#recurrence-panel");
    clear(node);
    if (state.errors.recurrence) return showError(node, `Recurrence report unavailable: ${state.errors.recurrence}`);
    const report = state.data.recurrence && state.data.recurrence.report ? state.data.recurrence.report : {};
    node.appendChild(
      panelHeader(
        "Control recurrence",
        safeString(report.report_id || "No report id", "report_id"),
        report.recommendation_status || state.data.recurrence?.status || "unknown"
      )
    );
    renderKv(node, report, [
      "report_type",
      "recommendation_status",
      "highest_category",
      "total_signals",
      "blocking_signal_count",
      "phase6_health_summary",
      "qdrant_health_summary",
      "created_or_updated_at",
    ]);
    renderRecurrenceRecommendation(node, report.report_id);
  }

  function renderRecurrenceTrend() {
    const node = qs("#recurrence-trend-panel");
    clear(node);
    if (state.errors.trend) return showError(node, `Recurrence trend unavailable: ${state.errors.trend}`);
    const trend = state.data.trend || {};
    const report = trend.trend_report || {};
    const windowInfo = trend.report_window || {};
    node.appendChild(panelHeader("Recurrence trend", "Read-only report window and top families", report.status || "unknown"));
    renderKv(node, windowInfo, [
      "total_index_entries",
      "json_backed_reports",
      "metadata_only_entries",
      "warning_count",
      "comparable_scope_groups",
      "scope_group_count",
    ]);
    const familyTrends = Array.isArray(trend.family_trends) ? trend.family_trends.slice(0, 5) : [];
    if (familyTrends.length) {
      renderSimpleTable(
        node,
        [
          { key: "error_family", label: "Family" },
          { key: "category", label: "Category", badge: true },
          { key: "latest_count", label: "Latest" },
          { key: "trend_status", label: "Trend", badge: true },
        ],
        familyTrends
      );
    } else {
      appendText(
        node,
        "p",
        "No comparable trend rows yet. This does not mean no recurrence exists. This view needs indexed recurrence JSON reports with comparable scope.",
        "panel-subtitle"
      );
    }
  }

  function renderMemory() {
    const node = qs("#memory-panel");
    clear(node);
    if (state.errors.memory) return showError(node, `Memory stats unavailable: ${state.errors.memory}`);
    const memory = state.data.memory || {};
    node.appendChild(panelHeader("Memory stores", "SQLite, KG, Qdrant, and FAISS projection", "read-only"));
    renderKv(node, memory.qdrant || {}, ["available", "collections"]);
    renderKv(node, memory.faiss || {}, ["text_vectors", "clip_vectors", "audio_vectors"]);
    if (memory.audio_vector_semantics) {
      renderKv(node, memory.audio_vector_semantics, ["faiss.audio_vectors", "current_run_success_contract"]);
    }
  }

  function renderSurfaces() {
    const node = qs("#surface-panel");
    clear(node);
    if (state.errors.runEvidence) return showError(node, `Run evidence unavailable: ${state.errors.runEvidence}`);
    const evidence = state.data.runEvidence || {};
    const stepRuns = evidence.step_runs || {};
    const graph = evidence.knowledge_graph || {};

    node.appendChild(panelHeader("Evidence surfaces", "Sanitized artifact presence and step history", evidence.available ? "read-only" : "offline"));
    renderKv(node, evidence.artifact_presence || {}, ["step_runs_jsonl", "temporal_index_json", "scene_ingest_results_json"]);
    renderKv(node, stepRuns, ["status", "row_count", "recent_count", "failed_count", "warning_count", "latest_ts_utc"]);
    renderMiniList(node, "Top step activity", stepRuns.top_steps, "step", "count");
    renderRecentSteps(node, stepRuns.recent);
    appendText(node, "h3", "Graph and store truth", "panel-subtitle");
    renderKv(node, graph, [
      "status",
      "scene_count",
      "qdrant_ok",
      "faiss_ok",
      "phase6_complete",
      "phase6_qdrant_ok",
      "control_agent_status",
    ]);
  }

  function renderTemporalSurface() {
    const node = qs("#temporal-surface-panel");
    clear(node);
    if (state.errors.runEvidence) return showError(node, `Temporal evidence unavailable: ${state.errors.runEvidence}`);
    const evidence = state.data.runEvidence || {};
    const temporal = evidence.temporal_index || {};
    const sentiment = evidence.sentiment || {};

    node.appendChild(panelHeader("Temporal index", "Scene continuity, modality, and tone rollups", temporal.status || "unknown"));
    renderKv(node, temporal, [
      "status",
      "version",
      "total_scenes",
      "total_duration",
      "content_summary",
      "phase6_complete",
      "phase6_harmonized",
      "has_audio",
      "has_transcripts",
      "segments_with_scene_context_llm",
      "segments_with_audio_emotion",
    ]);
    appendText(node, "h3", "Emotion and sentiment summary", "panel-subtitle");
    renderKv(node, sentiment, ["status", "segments_total", "segments_with_audio_emotion", "segments_with_sentiment", "average_sentiment_score"]);
    renderAudioEmotionDistribution(node, sentiment, temporal);
  }

  function renderDiagnostics() {
    const node = qs("#diagnostics-panel");
    clear(node);
    if (state.loadingDiagnostics && !state.data.engines && !state.errors.engines) return showLoading(node);
    if (state.errors.engines) return showError(node, `Engine diagnostics unavailable: ${state.errors.engines}`);
    const engines = state.data.engines || {};
    const summary = engines.summary || {};
    const overall = summary.overall || engines.overall || {};
    const details = engines.engines || engines.details || {};
    const rows = Object.values(details)
      .filter((item) => item && typeof item === "object")
      .map((item) => ({
        name: item.name || "unknown",
        category: item.category || "engine",
        status: item.status || "unknown",
        gpu: item.gpu === true ? "gpu" : "cpu",
        port: item.port || "",
      }));

    const readyCount = rows.filter((row) => statusKind(row.status) === "ok").length;
    const optionalOffline = Math.max(0, rows.length - readyCount);
    node.appendChild(panelHeader("Runtime diagnostics", "Core runtime separated from optional services; path-bearing descriptions are omitted", optionalOffline ? "Partial" : "Ready"));
    appendIndicatorStrip(
      node,
      [
        {
          label: "Core runtime",
          value: "Ready",
          note: "API, SQLite, and Qdrant are shown in Flight Deck",
          kind: "ok",
        },
        {
          label: "Optional model services",
          value: optionalOffline ? "Offline" : "Ready",
          note: `${readyCount}/${rows.length} probes ready`,
          kind: optionalOffline ? "warn" : "ok",
        },
        {
          label: "Diagnostic rows",
          value: String(rows.length),
          note: "expanded below",
          kind: rows.length ? "info" : "unknown",
        },
      ],
      "diagnostics-rollup-strip"
    );
    renderKv(node, overall, ["status", "total", "healthy", "unhealthy"]);
    renderSimpleTable(
      node,
      [
        { key: "name", label: "Engine" },
        { key: "category", label: "Category" },
        { key: "status", label: "Status", badge: true },
        { key: "gpu", label: "Mode", badge: true },
        { key: "port", label: "Port" },
      ],
      rows
    );
  }

  function renderMachine() {
    const node = qs("#machine-panel");
    clear(node);
    if (
      state.loadingDiagnostics &&
      !state.data.gpu &&
      !state.data.wsl &&
      !state.data.queue &&
      !state.errors.gpu &&
      !state.errors.wsl &&
      !state.errors.queue
    ) {
      return showLoading(node);
    }

    node.appendChild(panelHeader("Machine and queue", "GPU, WSL, and inbox counters", "read-only"));

    if (state.errors.gpu) {
      appendInlineError(node, `GPU stats unavailable: ${state.errors.gpu}`);
    } else {
      const gpu = state.data.gpu || state.data.status?.gpu || {};
      appendText(node, "h3", "GPU", "panel-subtitle");
      appendIndicatorStrip(
        node,
        [
          gpuReservationState(gpu),
          {
            label: "GPU utilization",
            value: numberValue(gpu.utilization_percent ?? gpu.gpu_utilization) !== null
              ? `${numberValue(gpu.utilization_percent ?? gpu.gpu_utilization)}%`
              : "Not Exposed",
            note: "low utilization with high memory can be normal while vLLM holds a model",
            kind: "info",
          },
        ],
        "machine-rollup-strip"
      );
      renderKv(node, gpu, [
        "available",
        "name",
        "utilization_percent",
        "gpu_utilization",
        "memory_used_mb",
        "gpu_memory_used",
        "memory_total_mb",
        "gpu_memory_total",
        "memory_percent",
        "temperature_c",
      ]);
    }

    if (state.errors.wsl) {
      appendInlineError(node, `WSL status unavailable: ${state.errors.wsl}`);
    } else {
      const wsl = state.data.wsl || state.data.status?.wsl || {};
      appendText(node, "h3", "WSL", "panel-subtitle");
      appendIndicatorStrip(
        node,
        [
          wslAudioState(wsl),
          {
            label: "WSL distro",
            value: hasOkStatus(wsl.status) || wsl.active === true ? "Running" : "Not Observed",
            note: "WSL is a compute extension, not memory truth",
            kind: hasOkStatus(wsl.status) || wsl.active === true ? "ok" : "unknown",
          },
        ],
        "machine-rollup-strip"
      );
      renderKv(node, wsl, [
        "available",
        "status",
        "active",
        "vllm_service",
        "audio_processing",
        "faster_whisper",
        "cuda_version",
        "driver_version",
      ]);
    }

    if (state.errors.queue) {
      appendInlineError(node, `Queue unavailable: ${state.errors.queue}`);
    } else {
      const queue = state.data.queue || {};
      appendText(node, "h3", "Queue", "panel-subtitle");
      renderSimpleTable(
        node,
        [
          { key: "name", label: "Lane" },
          { key: "count", label: "Count" },
          { key: "size", label: "Size" },
        ],
        [
          { name: "inbox", count: queue.inbox?.count, size: queue.inbox?.total_size_mb ? `${queue.inbox.total_size_mb} MB` : "" },
          { name: "processing", count: queue.processing?.count, size: "" },
          { name: "processed", count: queue.processed?.count, size: "" },
          { name: "failed", count: queue.failed?.count, size: "" },
        ]
      );
    }
  }

  function renderStorage() {
    const node = qs("#storage-panel");
    if (!node) return;
    clear(node);
    if (state.errors.storage) return showError(node, `Storage summary unavailable: ${state.errors.storage}`);
    const storage = state.data.storage || {};
    const disk = storage.disk || {};
    const roots = Array.isArray(storage.roots) ? storage.roots : [];

    node.appendChild(panelHeader("Storage and growth", "Read-only local capacity and artifact growth", storage.status || "unknown"));
    renderKv(node, storage, ["status", "mode", "raw_paths"]);
    appendText(node, "h3", "Data volume", "panel-subtitle");
    renderKv(node, disk, ["available", "scope", "free_gb", "used_gb", "total_gb", "used_percent"]);

    const rows = roots.map((row) => ({
      label: row.label || row.name,
      status: row.exists ? row.scan_status || "complete" : "not configured",
      size_mb: row.exists ? row.size_mb : "",
      count: row.exists ? row.file_count : "",
    }));
    renderSimpleTable(
      node,
      [
        { key: "label", label: "Surface" },
        { key: "status", label: "State", badge: true },
        { key: "size_mb", label: "MB" },
        { key: "count", label: "Files" },
      ],
      rows
    );

    if (storage.scan_policy) {
      appendText(
        node,
        "p",
        `Bounded scan: ${safeString(storage.scan_policy.max_entries_per_root, "max_entries")} entries/root, ${safeString(storage.scan_policy.max_seconds_per_root, "max_seconds")}s/root.`,
        "panel-subtitle"
      );
    }
  }

  function renderHealth() {
    const node = qs("#health-panel");
    clear(node);
    if (state.errors.health) return showError(node, `Health summary unavailable: ${state.errors.health}`);
    const health = state.data.health || {};
    const healthy = numberValue(health.overall?.healthy);
    const total = numberValue(health.overall?.total);
    const optionalReady = healthy !== null && total !== null && healthy === total;
    node.appendChild(panelHeader("Optional model services", "Read-only LLM service probes; core memory readiness is in Flight Deck", optionalReady ? "Ready" : "Optional Offline"));
    appendIndicatorStrip(
      node,
      [
        {
          label: "Core runtime",
          value: "See Flight Deck",
          note: "memory path is evaluated separately",
          kind: "info",
        },
        {
          label: "Optional model services",
          value: total !== null ? `${healthy || 0}/${total}` : "Not exposed",
          note: optionalReady ? "all optional services ready" : "offline does not block memory reads",
          kind: optionalReady ? "ok" : "warn",
        },
      ],
      "health-rollup-strip"
    );
    appendIndicatorStrip(
      node,
      [
        llmServiceState(health.vllm, "Primary LLM (vLLM)", { primary: true, role: "primary LLM path" }),
        llmServiceState(health.ollama, "Optional fallback (Ollama)", { optional: true, role: "fallback LLM service" }),
      ],
      "llm-service-strip"
    );
    renderSimpleTable(
      node,
      [
        { key: "name", label: "Service" },
        { key: "state", label: "State", badge: true },
        { key: "readiness", label: "Readiness" },
        { key: "note", label: "Meaning" },
      ],
      [
        (() => {
          const serviceState = llmServiceState(health.vllm, "Primary LLM (vLLM)", { primary: true, role: "primary LLM path" });
          return {
            name: "vLLM",
            state: serviceState.value,
            readiness: `${numberValue(health.vllm?.healthy) || 0}/${numberValue(health.vllm?.total) || 0}`,
            note: serviceState.note,
          };
        })(),
        (() => {
          const serviceState = llmServiceState(health.ollama, "Optional fallback (Ollama)", { optional: true, role: "fallback LLM service" });
          return {
            name: "Ollama",
            state: serviceState.value,
            readiness: `${numberValue(health.ollama?.healthy) || 0}/${numberValue(health.ollama?.total) || 0}`,
            note: serviceState.note,
          };
        })(),
      ]
    );
    renderKv(node, health.overall || {}, ["status", "total", "healthy", "unhealthy"]);
  }

  function retrievalResultKey(result, index) {
    const video = retrievalTimelineVideoId(result) || (result && result.video_id ? String(result.video_id) : "video");
    const scene = result && result.scene_id !== null && result.scene_id !== undefined ? String(result.scene_id) : "scene";
    return `${video}:${scene}:${index}`;
  }

  function retrievalTimelineVideoId(result) {
    if (!result || typeof result !== "object") return null;
    return valueObserved(result.timeline_video_id)
      ? String(result.timeline_video_id)
      : (valueObserved(result.video_id) ? String(result.video_id) : null);
  }

  function retrievalVideoLabel(result) {
    if (!result || typeof result !== "object") return "Not observed";
    return result.display_title || result.timeline_video_id || result.video_id || "Not observed";
  }

  function setRetrievalSceneLineage(result, index, stateLabel) {
    if (!result || typeof result !== "object") {
      state.sceneLineage = null;
      return null;
    }
    const lineage = {
      source: "retrieval",
      stateLabel: stateLabel || "retrieval selected",
      query: state.retrieval.query || "",
      sceneId: valueObserved(result.scene_id) ? String(result.scene_id) : "",
      videoId: retrievalTimelineVideoId(result) || "",
      displayTitle: retrievalVideoLabel(result),
      resultLabel: resultSceneLabel(result, index || 0),
      timeLabel: resultTimeLabel(result),
    };
    state.sceneLineage = lineage;
    return lineage;
  }

  function setTimelineSceneLineage(segment, index) {
    state.sceneLineage = {
      source: "timeline",
      stateLabel: "timeline selected",
      query: "",
      sceneId: valueObserved(segment && segment.scene_id) ? String(segment.scene_id) : segmentKey(segment || {}, index || 0),
      videoId: state.selectedVideoId || "",
      displayTitle: state.selectedVideoId || "Selected timeline",
      resultLabel: sceneDisplayLabel(segment && (segment.scene_id || segment.index || segmentKey(segment, index || 0)), index || 0),
      timeLabel: segment ? `${formatTime(segment.start)}-${formatTime(segment.end)}` : "time not returned",
    };
    return state.sceneLineage;
  }

  function lineageMatchesScene(lineage, segment) {
    if (!lineage || !segment) return false;
    const sceneId = valueObserved(segment.scene_id) ? String(segment.scene_id) : "";
    if (!valueObserved(lineage.sceneId) || lineage.sceneId !== sceneId) return false;
    const segmentVideoId = retrievalTimelineVideoId(segment) || state.selectedVideoId || "";
    return !valueObserved(lineage.videoId) || !valueObserved(segmentVideoId) || lineage.videoId === segmentVideoId;
  }

  function lineageSummaryText(lineage, segment) {
    if (!lineage) return "Timeline selected scene";
    if (lineage.source === "retrieval" && lineageMatchesScene(lineage, segment)) {
      return "Scene handoff confirmed | retrieval -> timeline -> inspector -> preview | Same selected scene id";
    }
    if (lineage.source === "retrieval") return "Retrieval handoff pending timeline confirmation";
    return "Timeline selected scene";
  }

  function normalizeSearchResults(response) {
    return response && Array.isArray(response.results) ? response.results : [];
  }

  function setDefaultRetrievalResult() {
    const results = state.retrieval.results || [];
    if (!results.length) {
      state.retrieval.selectedKey = null;
      return;
    }
    const selectedExists = results.some((result, index) => retrievalResultKey(result, index) === state.retrieval.selectedKey);
    if (!selectedExists) state.retrieval.selectedKey = retrievalResultKey(results[0], 0);
  }

  function selectedRetrievalEntry() {
    const results = state.retrieval.results || [];
    if (!results.length) return null;
    setDefaultRetrievalResult();
    const index = results.findIndex((result, rowIndex) => retrievalResultKey(result, rowIndex) === state.retrieval.selectedKey);
    const selectedIndex = index >= 0 ? index : 0;
    return {
      index: selectedIndex,
      key: retrievalResultKey(results[selectedIndex], selectedIndex),
      result: results[selectedIndex],
    };
  }

  function retrievalNumber(value) {
    if (value === null || value === undefined || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function scorePercent(result) {
    const confidence = result && result.confidence && typeof result.confidence === "object" ? retrievalNumber(result.confidence.overall) : null;
    const score = confidence !== null ? confidence : retrievalNumber(result ? result.score : null);
    if (score === null) return null;
    const normalized = score <= 1 ? score * 100 : score;
    return Math.max(0, Math.min(100, Math.round(normalized)));
  }

  function percentLabel(value) {
    return value === null || value === undefined ? "Not observed" : `${value}%`;
  }

  function resultSceneLabel(result, fallbackIndex) {
    const id = result && result.scene_id !== null && result.scene_id !== undefined ? result.scene_id : `Result ${fallbackIndex + 1}`;
    return sceneDisplayLabel(id, fallbackIndex);
  }

  function resultSummary(result) {
    const context = result && result.context && typeof result.context === "object" ? result.context : {};
    const candidates = [
      result && result.transcript,
      context.transcript,
      retrievalLlmSummary(result),
      context.summary,
      context.caption,
      context.content_state,
      result && Array.isArray(result.keywords) && result.keywords.length ? result.keywords.join(", ") : null,
      result && Array.isArray(result.objects) && result.objects.length ? result.objects.join(", ") : null,
    ];
    return safeString(candidates.find(Boolean) || "No transcript or scene context returned.", "summary");
  }

  function resultTimeLabel(result) {
    const context = result && result.context && typeof result.context === "object" ? result.context : {};
    const start = retrievalNumber(context.start ?? (result && result.start));
    const end = retrievalNumber(context.end ?? (result && result.end));
    if (start !== null && end !== null) return `${formatTime(start)}-${formatTime(end)}`;
    const timestamp = retrievalNumber(result ? result.timestamp : null);
    if (timestamp !== null) return `${formatTime(timestamp)}`;
    return "time not returned";
  }

  function canOpenRetrievalResult(result) {
    const videoId = retrievalTimelineVideoId(result);
    return Boolean(result && valueObserved(videoId) && valueObserved(result.scene_id));
  }

  function objectHasAny(data, keys) {
    if (!data || typeof data !== "object") return false;
    return keys.some((key) => valueObserved(data[key]));
  }

  function retrievalContext(result) {
    return result && result.context && typeof result.context === "object" ? result.context : {};
  }

  function retrievalSceneContextLlm(result) {
    if (result && result.scene_context_llm && typeof result.scene_context_llm === "object") return result.scene_context_llm;
    const context = retrievalContext(result);
    return context.scene_context_llm && typeof context.scene_context_llm === "object" ? context.scene_context_llm : null;
  }

  function retrievalLlmSummary(result) {
    const llm = retrievalSceneContextLlm(result);
    if (!llm) return null;
    return (
      llm.narrative_summary ||
      llm.summary ||
      llm.activity_description ||
      (Array.isArray(llm.key_moments) && llm.key_moments.length ? llm.key_moments.join("; ") : null)
    );
  }

  function retrievalLlmTags(result) {
    const llm = retrievalSceneContextLlm(result);
    if (!llm) return [];
    const tags = []
      .concat(Array.isArray(llm.primary_tags) ? llm.primary_tags : [])
      .concat(Array.isArray(llm.contextual_tags) ? llm.contextual_tags : [])
      .concat(Array.isArray(llm.context_tags) ? llm.context_tags : [])
      .concat(Array.isArray(llm.structural_tags) ? llm.structural_tags : []);
    return [...new Set(tags.map((tag) => safeString(tag, "scene_context_tag")).filter(Boolean))];
  }

  function retrievalLlmKeyMoments(result) {
    const llm = retrievalSceneContextLlm(result);
    if (!llm || !Array.isArray(llm.key_moments)) return [];
    return llm.key_moments.map((moment) => safeString(moment, "key_moment")).filter(Boolean);
  }

  function appendRetrievalSceneContextLens(container, result) {
    const lens = document.createElement("section");
    lens.className = "retrieval-context-lens";
    lens.setAttribute("data-testid", "retrieval-context-lens");
    appendText(lens, "h5", "Scene Context Lens");

    const llm = retrievalSceneContextLlm(result);
    if (!llm) {
      appendText(lens, "p", "No scene_context_llm payload returned for this retrieval result.", "retrieval-context-empty");
      container.appendChild(lens);
      return;
    }

    const summary = retrievalLlmSummary(result);
    if (summary) appendText(lens, "p", summary, "retrieval-context-summary");

    const facts = [
      ["Emotional arc", llm.emotional_arc || llm.emotion_arc || llm.affective_summary],
      ["Activity", llm.activity_description],
      ["Source", llm.source],
    ].filter(([, value]) => valueObserved(value));
    if (facts.length) {
      const dl = document.createElement("dl");
      dl.className = "retrieval-context-facts";
      facts.forEach(([label, value]) => {
        const dt = document.createElement("dt");
        dt.textContent = label;
        const dd = document.createElement("dd");
        dd.textContent = safeString(value, label);
        dl.appendChild(dt);
        dl.appendChild(dd);
      });
      lens.appendChild(dl);
    }

    const moments = retrievalLlmKeyMoments(result);
    if (moments.length) {
      appendText(lens, "strong", "Key moments", "retrieval-context-label");
      const ul = document.createElement("ul");
      ul.className = "retrieval-key-moments";
      moments.slice(0, 3).forEach((moment) => appendText(ul, "li", moment));
      lens.appendChild(ul);
    }

    const tags = retrievalLlmTags(result);
    if (tags.length) {
      const strip = document.createElement("div");
      strip.className = "retrieval-tag-strip";
      tags.slice(0, 8).forEach((tag) => appendText(strip, "span", tag));
      lens.appendChild(strip);
    }

    container.appendChild(lens);
  }

  function retrievalObjectLabels(result) {
    const context = retrievalContext(result);
    const objects = Array.isArray(result && result.objects) && result.objects.length ? result.objects : context.objects;
    return Array.isArray(objects) ? objects.map((item) => safeString(item, "object")).filter(Boolean) : [];
  }

  function evidenceList(source, key) {
    return Array.isArray(source && source[key]) ? source[key] : [];
  }

  function entityEvidenceBuckets(source, fallback) {
    const primary = source || {};
    const secondary = fallback || {};
    const fromEither = (key) => {
      const primaryList = evidenceList(primary, key);
      return primaryList.length ? primaryList : evidenceList(secondary, key);
    };
    const scenePresent = fromEither("scene_present_entities");
    const dialogueMentioned = fromEither("dialogue_mentioned_entities");
    const mentionedPeople = fromEither("mentioned_people");
    const candidateVisible = fromEither("candidate_visible_people");
    const visiblePeople = fromEither("visible_people");
    const speakerAligned = fromEither("speaker_aligned_mentions");
    const entities = fromEither("entities");
    return {
      scenePresent,
      entities,
      dialogueMentioned,
      mentionedPeople,
      candidateVisible,
      visiblePeople,
      speakerAligned,
      total:
        scenePresent.length +
        dialogueMentioned.length +
        mentionedPeople.length +
        candidateVisible.length +
        visiblePeople.length +
        speakerAligned.length,
    };
  }

  function sceneEntityEvidenceBuckets(segment) {
    return entityEvidenceBuckets(segment, {});
  }

  function formatEntityLabel(item) {
    if (!item || typeof item !== "object") return null;
    const text = item.text || item.label || item.name || item.identity || item.entity;
    const type = item.type || item.entity_type;
    if (!valueObserved(text)) return null;
    return type ? `${safeString(text, "entity")} (${safeString(type, "entity_type")})` : safeString(text, "entity");
  }

  function entityEvidenceSummaryNote(buckets) {
    if (!buckets || buckets.total <= 0) return "entity evidence not exposed";
    if (buckets.scenePresent.length) return `${buckets.scenePresent.length} scene-present entities`;
    if (buckets.dialogueMentioned.length) return `${buckets.dialogueMentioned.length} dialogue mentions; not scene-present identity`;
    if (buckets.mentionedPeople.length) return `${buckets.mentionedPeople.length} mentioned people; not scene-present identity`;
    if (buckets.candidateVisible.length || buckets.visiblePeople.length) {
      return `${buckets.candidateVisible.length + buckets.visiblePeople.length} candidate visible people`;
    }
    if (buckets.speakerAligned.length) return `${buckets.speakerAligned.length} speaker-aligned mention links`;
    return `${buckets.total} entity evidence rows`;
  }

  function retrievalEntityLabels(result) {
    const context = retrievalContext(result);
    const buckets = entityEvidenceBuckets(result, context);
    const entities = (
      buckets.scenePresent.length
        ? buckets.scenePresent
        : buckets.dialogueMentioned.length
          ? buckets.dialogueMentioned
          : buckets.mentionedPeople.length
            ? buckets.mentionedPeople
            : buckets.candidateVisible.length
              ? buckets.candidateVisible
              : buckets.entities
    );
    if (!Array.isArray(entities)) return [];
    return entities
      .map((item) => {
        return formatEntityLabel(item);
      })
      .filter(Boolean);
  }

  function retrievalKgEvidence(result) {
    const context = retrievalContext(result);
    const evidence = result && result.kg_evidence && typeof result.kg_evidence === "object"
      ? result.kg_evidence
      : context.kg_evidence;
    return evidence && typeof evidence === "object" ? evidence : {};
  }

  function retrievalRelationshipCount(result) {
    const context = retrievalContext(result);
    const relationships = Array.isArray(result && result.kg_relationships) && result.kg_relationships.length
      ? result.kg_relationships
      : context.relationships;
    if (Array.isArray(relationships)) return relationships.length;
    const evidence = retrievalKgEvidence(result);
    const count = retrievalNumber(evidence.relationship_count);
    return count !== null ? count : 0;
  }

  function retrievalSentimentLabel(result) {
    const context = retrievalContext(result);
    const sentiment = result && result.sentiment && typeof result.sentiment === "object" ? result.sentiment : context.sentiment;
    return (
      (result && result.sentiment_label) ||
      context.sentiment_label ||
      (sentiment && sentiment.label) ||
      null
    );
  }

  function retrievalEvidenceFacts(result) {
    const context = retrievalContext(result);
    const objects = retrievalObjectLabels(result);
    const entities = retrievalEntityLabels(result);
    const kgEvidence = retrievalKgEvidence(result);
    const relationshipCount = retrievalRelationshipCount(result);
    const llmSummary = retrievalLlmSummary(result);
    const llmTags = retrievalLlmTags(result);
    const epistemic = context.scene_context_epistemic && typeof context.scene_context_epistemic === "object" ? context.scene_context_epistemic : {};
    const arbitration = context.scene_context_arbitration && typeof context.scene_context_arbitration === "object" ? context.scene_context_arbitration : {};
    const facts = [
      ["Episode", retrievalVideoLabel(result)],
      ["Search id", result && result.timeline_video_id && result.video_id !== result.timeline_video_id ? compactIdentifier(result.video_id, { key: "search_id", max: 22, leading: 12, trailing: 6 }) : null],
      ["Time", resultTimeLabel(result)],
      ["Transcript", valueObserved(result && result.transcript) || valueObserved(context.transcript) ? "Observed" : "Not observed"],
      ["Objects", objects.length ? `${objects.slice(0, 4).join(", ")}${objects.length > 4 ? "..." : ""}` : "Not observed"],
      ["KG entities", entities.length ? `${entities.slice(0, 4).join(", ")}${entities.length > 4 ? "..." : ""}` : "Not observed"],
      ["KG evidence", valueObserved(kgEvidence.relationship_state) ? `${safeString(kgEvidence.relationship_state, "kg_evidence")} | ${relationshipCount} relationships` : "Not observed"],
      ["Audio emotion", (result && result.audio_emotion) || context.audio_emotion || "Not observed"],
      ["Speaker continuity", context.continuity_key || (context.speaker_count ? `${context.speaker_count} speakers` : "Not observed")],
      ["Scene context LLM", llmSummary || (context.scene_context_llm ? "Observed" : "Not observed")],
      ["LLM tags", llmTags.length ? llmTags.join(", ") : "Not observed"],
      ["Epistemic state", epistemic.state || "Not observed"],
      ["Arbitration", arbitration.resolved_by || "Not observed"],
      ["Sentiment", retrievalSentimentLabel(result) || "Not persisted"],
    ];
    if (result && result.provenance && typeof result.provenance === "object") {
      facts.push(["Provenance", result.provenance.enrichment || result.provenance.hydrated_from || result.provenance.source || "Returned"]);
    }
    return facts.filter(([, value]) => value !== null && value !== undefined && value !== "");
  }

  function retrievalFrameEndpoint(result) {
    if (!result) return null;
    const context = retrievalContext(result);
    return (
      result.representative_frame_endpoint ||
      context.representative_frame_endpoint ||
      result.representative_frame ||
      context.representative_frame
    );
  }

  function appendRetrievalVisualProof(container, result) {
    if (!container) return;
    const stale = qs("#retrieval-visual-proof");
    if (stale) stale.remove();
    if (!result) return;

    const frameUrl = mediaEndpointUrl(retrievalFrameEndpoint(result));
    const panel = document.createElement("div");
    panel.id = "retrieval-visual-proof";
    panel.className = "retrieval-visual-proof";
    panel.setAttribute("data-testid", "retrieval-visual-proof");

    const frame = document.createElement("div");
    frame.className = "retrieval-visual-frame";
    if (frameUrl) {
      const image = document.createElement("img");
      image.src = frameUrl;
      image.alt = "Retrieval result keyframe";
      image.loading = "lazy";
      frame.appendChild(image);
    } else {
      appendText(frame, "span", "No redacted keyframe exposed", "retrieval-visual-empty");
    }
    panel.appendChild(frame);

    const copy = document.createElement("div");
    appendText(copy, "strong", "Visual proof");
    appendText(
      copy,
      "span",
      frameUrl ? "Redacted keyframe endpoint linked to this selected result." : "No redacted keyframe endpoint returned for this result."
    );
    panel.appendChild(copy);

    const actions = container.querySelector(".retrieval-preview-actions");
    container.insertBefore(panel, actions || null);
  }

  function appendRetrievalEvidence(container, result, selectedIndex, signals, percent) {
    const panel = document.createElement("div");
    panel.className = "retrieval-evidence-digest";
    panel.setAttribute("data-testid", "retrieval-evidence-digest");
    appendText(panel, "h4", "Selected Evidence");
    const band = confidenceBand(percent);
    const observedSignals = Array.isArray(signals) ? signals.filter((row) => row.observed).length : 0;
    appendIndicatorStrip(
      panel,
      [
        {
          label: "Match band",
          value: band.label,
          note: percentLabel(percent),
          kind: band.kind,
          title: band.note,
        },
        {
          label: "Evidence signals",
          value: `${observedSignals}/${Array.isArray(signals) ? signals.length : 0}`,
          note: "returned by search response",
          kind: observedSignals ? "info" : "unknown",
        },
      ],
      "retrieval-rollup-strip"
    );
    appendText(panel, "p", resultSummary(result), "retrieval-evidence-summary");

    const grid = document.createElement("dl");
    grid.className = "retrieval-evidence-grid";
    retrievalEvidenceFacts(result).forEach(([label, value]) => {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = safeString(value || "Not observed", label);
      grid.appendChild(dt);
      grid.appendChild(dd);
    });
    panel.appendChild(grid);
    appendRetrievalSceneContextLens(panel, result);

    const footer = document.createElement("p");
    footer.className = "retrieval-evidence-footer";
    footer.textContent = `${resultSceneLabel(result, selectedIndex)} | ${observedSignals} signals observed | ${confidenceLabel(percent)}`;
    panel.appendChild(footer);
    container.appendChild(panel);
  }

  function provenanceMentions(result, token) {
    if (!result || !result.provenance || typeof result.provenance !== "object") return false;
    return JSON.stringify(result.provenance).toLowerCase().includes(token);
  }

  function retrievalSignalRows(result) {
    const modality = safeString(result && result.modality ? result.modality : "unknown", "modality").toLowerCase();
    const context = retrievalContext(result);
    const percent = scorePercent(result);
    const objects = retrievalObjectLabels(result);
    const entities = retrievalEntityLabels(result);
    const entityBuckets = entityEvidenceBuckets(result, context);
    const relationshipCount = retrievalRelationshipCount(result);
    const kgEvidence = retrievalKgEvidence(result);
    const audioProof = result && result.audio_vector_proof && typeof result.audio_vector_proof === "object"
      ? result.audio_vector_proof
      : {};
    const currentRunAudioProof = Boolean(
      result && (
        result.current_run_qdrant_audio_proven ||
        result.current_run_audio_vector_proven ||
        result.audio_qdrant_current_run_proven
      )
    ) || audioProof.status === "current_run_audio_vector_proven";
    const textObserved =
      modality.includes("text") ||
      valueObserved(result && result.transcript) ||
      arrayCount(result && result.keywords) > 0 ||
      objectHasAny(context, ["transcript", "full_transcript", "summary"]);
    const visualObserved =
      modality.includes("visual") ||
      valueObserved(result && result.representative_frame) ||
      arrayCount(result && result.objects) > 0 ||
      objectHasAny(context, ["representative_frame", "clip_id", "dino_id", "objects"]);
    const audioObserved =
      currentRunAudioProof ||
      modality.includes("audio") ||
      provenanceMentions(result, "audio") ||
      objectHasAny(context, ["audio_emotion", "audio_chunks", "clap_meta"]);
    const kgObserved =
      provenanceMentions(result, "kg") ||
      provenanceMentions(result, "graph") ||
      objectHasAny(context, [
        "entity_links",
        "kg_links",
        "knowledge_graph",
        "relationships",
        "scene_present_entities",
        "dialogue_mentioned_entities",
        "mentioned_people",
        "candidate_visible_people",
        "speaker_aligned_mentions",
        "kg_evidence",
      ]) ||
      entityBuckets.total > 0 ||
      entities.length > 0 ||
      relationshipCount > 0 ||
      valueObserved(kgEvidence.relationship_state);
    const speakerObserved = objectHasAny(context, ["continuity_key", "dominant_speaker_id", "speaker_count", "speaker_ids"]);

    return [
      {
        label: "Text Match",
        observed: textObserved,
        strength: modality.includes("text") ? percent : null,
        note: textObserved ? "Transcript or text payload returned by search response" : "No transcript or text proof returned",
        missing: "Text proof not returned for this result",
      },
      {
        label: "Visual Similarity",
        observed: visualObserved,
        strength: modality.includes("visual") ? percent : null,
        note: visualObserved ? (objects.length ? `Objects observed: ${objects.slice(0, 3).join(", ")}` : "Visual payload or visual modality observed") : "No visual payload returned",
        missing: "Visual similarity not proven by this response",
      },
      {
        label: "Audio Overlap",
        observed: audioObserved,
        strength: modality.includes("audio") ? percent : null,
        note: currentRunAudioProof
          ? "Current-run Qdrant audio proof returned"
          : audioObserved
            ? (context.audio_emotion ? `Audio emotion: ${safeString(context.audio_emotion, "audio_emotion")}` : "Audio modality or audio provenance observed")
            : "No current-run audio proof returned",
        missing: "Current-run audio proof not returned",
      },
      {
        label: "KG / Entity Evidence",
        observed: kgObserved,
        strength: null,
        note: kgObserved
          ? (relationshipCount > 0
            ? `Relationships observed: ${relationshipCount}`
            : (entities.length
              ? `${entityEvidenceSummaryNote(entityBuckets)}: ${entities.slice(0, 3).join(", ")}; relationship not asserted`
              : entityEvidenceSummaryNote(entityBuckets)))
          : "No KG or entity evidence returned",
        missing: "Entity evidence not exposed",
      },
      {
        label: "Speaker Continuity",
        observed: speakerObserved,
        strength: null,
        note: speakerObserved ? (context.continuity_key ? `Continuity: ${safeString(context.continuity_key, "continuity_key")}` : "Speaker continuity evidence returned") : "No speaker continuity returned",
        missing: "Speaker continuity not exposed",
      },
    ];
  }

  function appendRetrievalEmpty(container, message) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    appendText(empty, "span", message);
    container.appendChild(empty);
  }

  function appendRetrievalSignal(container, row) {
    const item = document.createElement("div");
    item.className = "retrieval-signal-row";
    const label = document.createElement("div");
    appendText(label, "strong", row.label);
    appendText(label, "span", row.note, "retrieval-signal-note");
    item.appendChild(label);

    if (row.strength !== null && row.strength !== undefined) {
      const meter = document.createElement("div");
      meter.className = "retrieval-meter";
      const fill = document.createElement("span");
      fill.style.width = `${Math.max(0, Math.min(100, row.strength))}%`;
      meter.appendChild(fill);
      const value = document.createElement("strong");
      value.className = "retrieval-meter-value";
      value.textContent = percentLabel(row.strength);
      const wrap = document.createElement("div");
      wrap.className = "retrieval-meter-wrap";
      wrap.appendChild(meter);
      wrap.appendChild(value);
      item.appendChild(wrap);
    } else {
      item.appendChild(makeBadge(row.observed ? "On" : "Off", row.observed ? "ok" : "unknown"));
    }
    container.appendChild(item);
  }

  function appendRetrievalLineageStrip(container, result, selectedIndex) {
    const existing = qs("#retrieval-lineage-strip");
    if (existing) existing.remove();
    const strip = document.createElement("div");
    strip.id = "retrieval-lineage-strip";
    strip.className = "retrieval-lineage-strip";
    strip.setAttribute("data-testid", "retrieval-lineage-strip");
    if (!result) {
      appendText(strip, "span", "No selected retrieval handoff.");
      container.appendChild(strip);
      return;
    }

    const canOpen = canOpenRetrievalResult(result);
    [
      ["Handoff target", retrievalVideoLabel(result)],
      ["Scene", resultSceneLabel(result, selectedIndex || 0)],
      ["Status", canOpen ? "Ready for inspector" : "Timeline handoff unresolved"],
    ].forEach(([label, value]) => {
      const item = document.createElement("div");
      appendText(item, "span", label);
      appendText(item, "strong", value);
      strip.appendChild(item);
    });
    container.appendChild(strip);
  }

  function renderRetrievalConsole() {
    const input = qs("#retrieval-query-input");
    const count = qs("#retrieval-results-count");
    const list = qs("#retrieval-results-list");
    const explanation = qs("#retrieval-explanation");
    const selectedScore = qs("#retrieval-selected-score");
    const previewCopy = qs("#retrieval-preview-copy");
    const loadMore = qs("#retrieval-load-more");
    const openScene = qs("#retrieval-open-scene");
    const viewTimeline = qs("#retrieval-view-timeline");
    const previewPanel = qs('[data-testid="retrieval-preview"]');
    if (!input || !count || !list || !explanation || !selectedScore || !previewCopy || !loadMore || !openScene || !viewTimeline) {
      return;
    }
    const staleLineage = qs("#retrieval-lineage-strip");
    if (staleLineage) staleLineage.remove();
    const staleVisualProof = qs("#retrieval-visual-proof");
    if (staleVisualProof) staleVisualProof.remove();

    if (document.activeElement !== input) input.value = state.retrieval.query || "";
    clear(list);
    clear(explanation);
    setDefaultRetrievalResult();

    const results = state.retrieval.results || [];
    const total = state.retrieval.response?.total_results ?? results.length;
    count.textContent = state.retrieval.hasRun ? `(${safeString(total, "total_results")})` : "(idle)";
    loadMore.disabled = state.retrieval.loading || !state.retrieval.query || results.length >= total;

    if (!state.retrieval.hasRun) {
      appendRetrievalEmpty(list, "Enter a natural-language query to search local memory.");
      appendRetrievalEmpty(explanation, "No result selected. Match signals will appear after a query returns.");
      selectedScore.textContent = "Not observed";
      previewCopy.textContent = "Run a query to inspect one memory result.";
      openScene.disabled = true;
      viewTimeline.setAttribute("aria-disabled", "true");
      return;
    }

    if (state.retrieval.loading) {
      showLoading(list);
      showLoading(explanation);
      selectedScore.textContent = "Searching";
      previewCopy.textContent = "Searching local memory read surfaces...";
      openScene.disabled = true;
      viewTimeline.setAttribute("aria-disabled", "true");
      return;
    }

    if (state.retrieval.error) {
      showError(list, `Search unavailable: ${safeString(state.retrieval.error, "status")}`);
      appendRetrievalEmpty(explanation, "The canonical search surface did not return a result to explain.");
      selectedScore.textContent = "Offline";
      previewCopy.textContent = "Search endpoint unavailable. No memory state was changed.";
      openScene.disabled = true;
      viewTimeline.setAttribute("aria-disabled", "true");
      return;
    }

    if (!results.length) {
      appendRetrievalEmpty(list, "No memory results returned for this query.");
      appendRetrievalEmpty(explanation, "No selected result. Try a different local-memory query.");
      selectedScore.textContent = "0 results";
      previewCopy.textContent = "No selected result.";
      openScene.disabled = true;
      viewTimeline.setAttribute("aria-disabled", "true");
      return;
    }

    results.forEach((result, index) => {
      const key = retrievalResultKey(result, index);
      const selected = key === state.retrieval.selectedKey;
      const row = document.createElement("button");
      row.type = "button";
      row.className = `retrieval-result-row ${selected ? "selected" : ""}`;
      row.title = "Why? Select this result to inspect match signals.";
      row.setAttribute("aria-pressed", selected ? "true" : "false");
      row.setAttribute("data-testid", selected ? "selected-retrieval-result" : "retrieval-result");
      row.addEventListener("click", () => {
        state.retrieval.selectedKey = key;
        setRetrievalSceneLineage(result, index, "retrieval selected");
        renderRetrievalConsole();
        openMediaPreview("retrieval");
      });
      const label = document.createElement("div");
      const sceneLabel = appendText(label, "strong", resultSceneLabel(result, index), "compact-id");
      if (result && result.scene_id !== null && result.scene_id !== undefined) {
        sceneLabel.title = safeString(result.scene_id, "scene_id");
      }
      appendText(label, "span", `${resultTimeLabel(result)} | ${safeString(result.modality || "unknown", "modality")}`, "retrieval-result-meta");
      appendText(label, "span", resultSummary(result), "retrieval-result-summary");
      row.appendChild(label);
      const percent = scorePercent(result);
      row.appendChild(makeConfidenceBadge(percent));
      list.appendChild(row);
    });

    const selected = selectedRetrievalEntry();
    const result = selected ? selected.result : null;
    const percent = scorePercent(result);
    selectedScore.textContent = confidenceLabel(percent);

    const signalList = document.createElement("div");
    signalList.className = "retrieval-signal-list";
    const signals = retrievalSignalRows(result);
    appendRetrievalEvidence(explanation, result, selected.index, signals, percent);
    signals.forEach((row) => appendRetrievalSignal(signalList, row));
    explanation.appendChild(signalList);

    const missing = signals.filter((row) => !row.observed).map((row) => row.missing);
    const context = retrievalContext(result);
    if (!valueObserved(result && result.provenance)) missing.push("Detailed provenance envelope not returned");
    if (!retrievalSentimentLabel(result)) missing.push("Sentiment label not persisted for this scene");
    if (!valueObserved(context.scene_context_llm)) missing.push("scene_context_llm not present in configured search epoch");
    if (result && !canOpenRetrievalResult(result)) {
      missing.push("Timeline handoff id not exposed by search response");
    }
    const missingBox = document.createElement("div");
    missingBox.className = "retrieval-missing";
    appendText(missingBox, "h4", "Missing Signals");
    if (!missing.length) {
      appendText(missingBox, "p", "No missing signals surfaced by the current search response.");
    } else {
      const ul = document.createElement("ul");
      missing.slice(0, 6).forEach((item) => appendText(ul, "li", item));
      missingBox.appendChild(ul);
    }
    explanation.appendChild(missingBox);

    const observedSignals = signals.filter((row) => row.observed).length;
    const handoffNote = canOpenRetrievalResult(result) ? "" : " | timeline handoff not resolved";
    previewCopy.textContent = `${resultSceneLabel(result, selected.index)} | ${resultTimeLabel(result)} | ${observedSignals} signals observed | ${confidenceLabel(percent)}${handoffNote}. ${resultSummary(result)}`;
    if (previewPanel) appendRetrievalVisualProof(previewPanel, result);
    if (previewPanel) appendRetrievalLineageStrip(previewPanel, result, selected.index);
    openScene.disabled = !canOpenRetrievalResult(result);
    if (openScene.disabled) {
      viewTimeline.setAttribute("aria-disabled", "true");
      openScene.title = "Search result video id is not present in the timeline inventory.";
    } else {
      viewTimeline.removeAttribute("aria-disabled");
      openScene.title = "";
    }
  }

  async function runRetrievalQuery(options) {
    const input = qs("#retrieval-query-input");
    const query = options && options.useExistingQuery ? state.retrieval.query : String(input?.value || "").trim();
    if (options && options.resetLimit) state.retrieval.limit = 10;
    state.retrieval.hasRun = true;
    state.retrieval.error = null;

    if (!query) {
      state.retrieval.query = "";
      state.retrieval.results = [];
      state.retrieval.response = null;
      state.retrieval.selectedKey = null;
      state.retrieval.error = "Enter a query before searching.";
      renderRetrievalConsole();
      return;
    }

    state.retrieval.query = query;
    state.retrieval.loading = true;
    renderRetrievalConsole();
    try {
      const response = await postJson("retrieval", "/api/search/multimodal", {
        query,
        top_k: state.retrieval.limit,
      });
      state.retrieval.response = response;
      state.retrieval.results = normalizeSearchResults(response);
      state.retrieval.error = null;
      setDefaultRetrievalResult();
    } catch (error) {
      state.retrieval.response = null;
      state.retrieval.results = [];
      state.retrieval.selectedKey = null;
      state.retrieval.error = error instanceof Error ? error.message : String(error);
    } finally {
      state.retrieval.loading = false;
      renderRetrievalConsole();
    }
  }

  async function selectRetrievalResultSurface(targetHash) {
    const entry = selectedRetrievalEntry();
    const result = entry ? entry.result : null;
    if (!canOpenRetrievalResult(result)) return;
    setRetrievalSceneLineage(result, entry.index, "retrieval -> inspector");
    state.selectedVideoId = retrievalTimelineVideoId(result);
    state.selectedSceneKey = String(result.scene_id);
    renderVideos();
    showLoading(qs("#timeline-panel"));
    showLoading(qs("#scene-detail-panel"));
    showLoading(qs("#scene-modality-panel"));
    showLoading(qs("#scene-schema-panel"));
    await refreshTimeline();
    state.selectedSceneKey = String(result.scene_id);
    setRetrievalSceneLineage(result, entry.index, "retrieval -> timeline -> inspector");
    renderVideos();
    renderTimeline();
    renderSceneInspector();
    openMediaPreview("timeline");
    window.location.hash = targetHash || "scene-inspector";
  }

  function safeVideoTitle(video) {
    return safeString(video.title || video.video_id || "Untitled video", "title");
  }

  function thumbnailEnvelopeLabel(video) {
    if (video && video.thumbnail_available && valueObserved(video.thumbnail_endpoint)) {
      const parts = ["Thumbnail: local API ready"];
      if (video.thumbnail_path_redacted) parts.push("raw path redacted");
      return parts.join(" | ");
    }
    if (video && video.thumbnail_available) return "Thumbnail: available | endpoint not exposed";
    return "Thumbnail: not exposed";
  }

  function thumbnailStatusCompact(video) {
    if (video && video.thumbnail_available && valueObserved(video.thumbnail_endpoint)) {
      return {
        label: "Thumb",
        kind: "ok",
        note: video.thumbnail_path_redacted ? "Thumbnail ready; path redacted" : "Thumbnail ready",
      };
    }
    if (video && video.thumbnail_available) {
      return { label: "Thumb", kind: "warn", note: "Thumbnail exists; endpoint not exposed" };
    }
    return { label: "No thumb", kind: "unknown", note: "Thumbnail not exposed" };
  }

  function renderVideos() {
    const node = qs("#video-panel");
    clear(node);
    if (state.errors.videos) return showError(node, `Video inventory unavailable: ${state.errors.videos}`);
    const videos = Array.isArray(state.data.videos) ? state.data.videos : [];
    node.appendChild(panelHeader("Video inventory", `${videos.length} videos`, "read-only"));

    const list = document.createElement("div");
    list.className = "video-list";
    videos.forEach((video) => {
      const id = video.video_id || video.id || "";
      const thumbnailStatus = thumbnailStatusCompact(video);
      const button = document.createElement("button");
      button.type = "button";
      button.className = `video-button ${id === state.selectedVideoId ? "selected" : ""}`;
      button.title = thumbnailEnvelopeLabel(video);
      button.addEventListener("click", async () => {
        state.selectedVideoId = id;
        state.selectedSceneKey = null;
        state.sceneLineage = null;
        if (state.mediaPreview.open) state.mediaPreview.source = "timeline";
        renderVideos();
        showLoading(qs("#timeline-panel"));
        showLoading(qs("#scene-detail-panel"));
        showLoading(qs("#scene-modality-panel"));
        showLoading(qs("#scene-schema-panel"));
        await refreshTimeline();
        renderTimeline();
        renderSceneInspector();
        renderMediaPreview();
      });
      const label = document.createElement("span");
      appendText(label, "span", safeVideoTitle(video), "video-title");
      appendText(
        label,
        "span",
        `${safeString(video.total_scenes, "total_scenes")} scenes | ${safeString(video.processed_date, "processed_date")}`,
        "video-meta"
      );
      appendText(label, "span", thumbnailStatus.note, "video-meta");
      button.appendChild(label);
      button.appendChild(
        makeStatusDot(id === state.selectedVideoId ? "ok" : thumbnailStatus.kind, id === state.selectedVideoId ? "Selected video" : thumbnailStatus.note)
      );
      list.appendChild(button);
    });

    if (!videos.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      appendText(empty, "span", "No video inventory returned.");
      node.appendChild(empty);
    } else {
      node.appendChild(list);
    }
  }

  function timelineSegments(raw) {
    if (!raw || typeof raw !== "object") return [];
    if (Array.isArray(raw.segments)) return raw.segments;
    if (raw.timeline && Array.isArray(raw.timeline.segments)) return raw.timeline.segments;
    if (Array.isArray(raw.scenes)) return raw.scenes;
    return [];
  }

  function formatTime(value) {
    const seconds = Number(value);
    if (!Number.isFinite(seconds)) return "00:00";
    const mm = Math.floor(seconds / 60);
    const ss = Math.floor(seconds % 60);
    return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
  }

  function segmentSummary(segment) {
    const candidates = [
      segment.scene_context_llm && segment.scene_context_llm.narrative_summary,
      segment.scene_context_llm && segment.scene_context_llm.summary,
      segment.transcript,
      segment.visual_caption,
      segment.caption,
      segment.full_transcript,
      segment.content_state,
      segment.scene_id,
    ];
    return safeString(candidates.find(Boolean) || "No summary", "summary");
  }

  function segmentKey(segment, index) {
    const id = segment && (segment.scene_id || segment.segment_id || segment.index);
    if (id !== null && id !== undefined && id !== "") return String(id);
    const start = segment ? segment.start : "start";
    const end = segment ? segment.end : "end";
    return `${start}-${end}-${index}`;
  }

  function setDefaultSelectedScene() {
    const segments = timelineSegments(state.data.timeline);
    if (!segments.length) {
      state.selectedSceneKey = null;
      return;
    }
    const selectedExists = segments.some((segment, index) => segmentKey(segment, index) === state.selectedSceneKey);
    if (!selectedExists) state.selectedSceneKey = segmentKey(segments[0], 0);
  }

  function selectedSegmentEntry() {
    const segments = timelineSegments(state.data.timeline);
    if (!segments.length) return null;
    setDefaultSelectedScene();
    const index = segments.findIndex((segment, rowIndex) => segmentKey(segment, rowIndex) === state.selectedSceneKey);
    const selectedIndex = index >= 0 ? index : 0;
    return {
      index: selectedIndex,
      key: segmentKey(segments[selectedIndex], selectedIndex),
      segment: segments[selectedIndex],
    };
  }

  function openMediaPreview(source) {
    state.mediaPreview.open = true;
    state.mediaPreview.source = source || "timeline";
    renderMediaPreview();
  }

  function closeMediaPreview() {
    state.mediaPreview.open = false;
    renderMediaPreview();
  }

  function previewCount(value) {
    if (Array.isArray(value)) return value.length;
    if (value && typeof value === "object") return Object.keys(value).length;
    return valueObserved(value) ? 1 : 0;
  }

  function previewArray(value) {
    if (Array.isArray(value)) return value;
    if (value && typeof value === "object") return Object.values(value);
    return valueObserved(value) ? [value] : [];
  }

  function mediaPreviewEvidence(raw, context) {
    const objects = retrievalObjectLabels(raw).length
      ? retrievalObjectLabels(raw)
      : stringList(raw && raw.objects, 4);
    const faces = previewCount(raw && (raw.faces || raw.face_ids || raw.candidate_visible_people || context.candidate_visible_people));
    const transcript = valueObserved(raw && raw.transcript) || valueObserved(context.transcript) || valueObserved(raw && raw.full_transcript);
    const audioEmotion = valueObserved(raw && raw.audio_emotion) || valueObserved(context.audio_emotion) || valueObserved(raw && raw.audio_emotion_scores);
    const frame = valueObserved(raw && (raw.representative_frame_endpoint || raw.representative_frame || context.representative_frame_endpoint || context.representative_frame));
    const clapMeta = raw && raw.clap_meta && typeof raw.clap_meta === "object" ? raw.clap_meta : context.clap_meta;
    const currentRunAudioProof =
      raw && (raw.current_run_qdrant_audio_proven || raw.current_run_audio_vector_proven || raw.audio_qdrant_current_run_proven);

    return [
      { label: frame ? "Keyframe present" : "Keyframe not exposed", observed: frame, kind: frame ? "ok" : "unknown" },
      { label: transcript ? "Transcript present" : "Transcript not exposed", observed: transcript, kind: transcript ? "ok" : "unknown" },
      { label: objects.length ? `${objects.length} objects` : "Objects not exposed", observed: objects.length > 0, kind: objects.length ? "ok" : "unknown" },
      { label: faces ? `${faces} face signals` : "Face signals not exposed", observed: faces > 0, kind: faces ? "info" : "unknown" },
      { label: audioEmotion ? "Audio emotion reviewable" : "Audio emotion not exposed", observed: audioEmotion, kind: audioEmotion ? "info" : "unknown" },
      {
        label: currentRunAudioProof
          ? "Current-run audio proof exposed"
          : valueObserved(clapMeta)
            ? "CLAP metadata present"
            : "Current-run audio proof not exposed",
        observed: Boolean(currentRunAudioProof || valueObserved(clapMeta)),
        kind: currentRunAudioProof ? "ok" : valueObserved(clapMeta) ? "info" : "unknown",
      },
    ];
  }

  function previewSceneLike(raw, context) {
    const base = context && typeof context === "object" ? context : {};
    const source = raw && typeof raw === "object" ? raw : {};
    return {
      ...base,
      ...source,
      scene_context_llm: source.scene_context_llm || base.scene_context_llm,
      scene_context_epistemic: source.scene_context_epistemic || base.scene_context_epistemic,
      scene_context_arbitration: source.scene_context_arbitration || base.scene_context_arbitration,
      transcript: source.transcript || base.transcript,
      full_transcript: source.full_transcript || base.full_transcript,
      representative_frame: source.representative_frame || base.representative_frame,
      representative_frame_endpoint: source.representative_frame_endpoint || base.representative_frame_endpoint,
      objects: Array.isArray(source.objects) && source.objects.length ? source.objects : base.objects,
      tags: Array.isArray(source.tags) && source.tags.length ? source.tags : base.tags,
      audio_emotion: source.audio_emotion || base.audio_emotion,
      audio_emotion_scores: source.audio_emotion_scores || base.audio_emotion_scores,
    };
  }

  function previewMeaningPayload(raw, context) {
    const scene = previewSceneLike(raw, context);
    const families = sceneEvidenceSignalFamilies(scene);
    const observed = families.filter((item) => item.observed).length;
    return {
      summary: sceneMeaningSummary(scene),
      source: sceneMeaningSource(scene),
      tags: sceneContextTags(scene),
      moments: sceneKeyMoments(scene),
      families,
      observed,
      gaps: families.filter((item) => !item.observed),
    };
  }

  function mediaPreviewPayload() {
    if (state.mediaPreview.source === "retrieval") {
      const entry = selectedRetrievalEntry();
      if (entry && entry.result) {
        const result = entry.result;
        const context = retrievalContext(result);
        const frameEndpoint =
          result.representative_frame_endpoint ||
          context.representative_frame_endpoint ||
          result.representative_frame ||
          context.representative_frame;
        return {
          source: "Retrieval",
          raw: result,
          context,
          index: entry.index,
          sceneId: result.scene_id || `Result ${entry.index + 1}`,
          label: resultSceneLabel(result, entry.index),
          start: retrievalNumber(context.start ?? result.start),
          end: retrievalNumber(context.end ?? result.end),
          confidence: scorePercent(result),
          summary: resultSummary(result),
          frameUrl: mediaEndpointUrl(frameEndpoint),
          evidence: mediaPreviewEvidence(result, context),
          meaning: previewMeaningPayload(result, context),
        };
      }
    }

    const entry = selectedSegmentEntry();
    if (!entry) return null;
    const segment = entry.segment || {};
    const frameEndpoint = segment.representative_frame_endpoint || segment.representative_frame;
    return {
      source: "Timeline",
      raw: segment,
      context: {},
      index: entry.index,
      sceneId: segment.scene_id || segment.index || entry.key,
      label: sceneDisplayLabel(segment.scene_id || segment.index || entry.key, entry.index),
      start: numberValue(segment.start),
      end: numberValue(segment.end),
      confidence: null,
      summary: segmentSummary(segment),
      frameUrl: mediaEndpointUrl(frameEndpoint),
      evidence: mediaPreviewEvidence(segment, {}),
      meaning: previewMeaningPayload(segment, {}),
    };
  }

  function appendModalityDot(container, label, active, title) {
    const dot = document.createElement("span");
    dot.className = `modality-dot ${active ? "active" : ""}`;
    dot.textContent = label;
    dot.title = title;
    dot.setAttribute("aria-label", `${title}: ${active ? "present" : "not exposed"}`);
    container.appendChild(dot);
  }

  function appendPreviewEvidenceRow(container, row) {
    const item = document.createElement("div");
    item.className = "summary-row";
    appendText(item, "span", row.label);
    item.appendChild(makeStatusDot(row.kind, row.label));
    container.appendChild(item);
  }

  function appendPreviewEvidenceBridge(container, payload) {
    const meaning = payload.meaning || {};
    const sceneLike = previewSceneLike(payload.raw, payload.context);
    const lineage = state.sceneLineage;
    const bridge = document.createElement("section");
    bridge.className = "preview-evidence-bridge";
    bridge.setAttribute("data-testid", "preview-evidence-bridge");
    appendText(bridge, "h3", "Visual proof linked to selected scene evidence summary");
    appendText(
      bridge,
      "p",
      lineageMatchesScene(lineage, sceneLike)
        ? "Scene handoff confirmed | retrieval -> timeline -> inspector -> preview | Same selected scene id"
        : "Preview follows the currently selected scene.",
      "preview-lineage-note"
    );

    const rollup = document.createElement("div");
    rollup.className = "preview-signal-compact";
    [
      ["Meaning source", meaning.source || "Not observed"],
      ["Evidence present", `${meaning.observed || 0}/${Array.isArray(meaning.families) ? meaning.families.length : 0}`],
      ["Evidence gaps", String(Array.isArray(meaning.gaps) ? meaning.gaps.length : 0)],
    ].forEach(([label, value]) => {
      const item = document.createElement("div");
      appendText(item, "span", label);
      appendText(item, "strong", safeString(value, label));
      rollup.appendChild(item);
    });
    bridge.appendChild(rollup);

    const card = document.createElement("div");
    card.className = "preview-meaning-card";
    appendText(card, "p", meaning.summary ? safeString(meaning.summary, "preview_meaning_summary") : "No scene meaning summary exposed for this preview.");
    if (Array.isArray(meaning.moments) && meaning.moments.length) {
      appendText(card, "span", `Key moment: ${meaning.moments[0]}`, "preview-meaning-meta");
    }
    if (Array.isArray(meaning.tags) && meaning.tags.length) {
      const strip = document.createElement("div");
      strip.className = "scene-tag-strip";
      meaning.tags.slice(0, 5).forEach((tag) => appendText(strip, "span", tag));
      card.appendChild(strip);
    }
    bridge.appendChild(card);

    const link = document.createElement("a");
    link.className = "retrieval-button primary";
    link.href = "#scene-inspector";
    link.textContent = "Open Evidence Summary";
    bridge.appendChild(link);
    container.appendChild(bridge);
  }

  function renderMediaPreview() {
    const panel = qs("#media-preview-panel");
    if (!panel) return;
    clear(panel);
    panel.className = `media-preview-panel ${state.mediaPreview.open ? "active" : ""}`;
    panel.setAttribute("aria-hidden", state.mediaPreview.open ? "false" : "true");

    if (!state.mediaPreview.open) {
      const empty = document.createElement("div");
      empty.className = "preview-empty";
      appendText(empty, "strong", "Media Preview");
      appendText(empty, "span", "Select a scene from inventory, timeline, or retrieval to preview.");
      panel.appendChild(empty);
      return;
    }

    const payload = mediaPreviewPayload();
    if (!payload) {
      const empty = document.createElement("div");
      empty.className = "preview-empty";
      appendText(empty, "strong", "No scene selected");
      appendText(empty, "span", "Select a scene from inventory, timeline, or retrieval to preview.");
      const close = document.createElement("button");
      close.type = "button";
      close.className = "preview-close";
      close.textContent = "Close";
      close.addEventListener("click", closeMediaPreview);
      empty.appendChild(close);
      panel.appendChild(empty);
      return;
    }

    const header = document.createElement("div");
    header.className = "preview-header";
    const meta = document.createElement("div");
    appendText(meta, "span", payload.label, "scene-id").title = safeString(payload.sceneId, "scene_id");
    appendText(
      meta,
      "span",
      `${formatTime(payload.start)} - ${formatTime(payload.end)}`,
      "duration"
    );
    header.appendChild(meta);
    if (payload.confidence !== null && payload.confidence !== undefined) {
      header.appendChild(makeConfidenceBadge(payload.confidence));
    } else {
      header.appendChild(makeBadge(payload.source, "info"));
    }
    const close = document.createElement("button");
    close.type = "button";
    close.className = "preview-close";
    close.textContent = "Close";
    close.addEventListener("click", closeMediaPreview);
    header.appendChild(close);
    panel.appendChild(header);

    const frameBox = document.createElement("div");
    frameBox.className = "keyframe-container";
    if (payload.frameUrl) {
      const image = document.createElement("img");
      image.className = "keyframe";
      image.src = payload.frameUrl;
      image.alt = "Scene keyframe";
      image.loading = "lazy";
      frameBox.appendChild(image);
    } else {
      appendText(frameBox, "span", "No redacted keyframe exposed", "keyframe-fallback");
    }
    const overlay = document.createElement("div");
    overlay.className = "crt-overlay";
    overlay.setAttribute("aria-hidden", "true");
    frameBox.appendChild(overlay);
    panel.appendChild(frameBox);
    appendPreviewEvidenceBridge(panel, payload);

    const miniTimeline = document.createElement("div");
    miniTimeline.className = "mini-timeline";
    appendText(miniTimeline, "span", formatTime(payload.start));
    const rail = document.createElement("div");
    rail.className = "mini-timeline-rail";
    const playhead = document.createElement("span");
    playhead.className = "playhead";
    playhead.style.left = "0%";
    rail.appendChild(playhead);
    miniTimeline.appendChild(rail);
    appendText(miniTimeline, "span", formatTime(payload.end));
    panel.appendChild(miniTimeline);

    const raw = payload.raw || {};
    const context = payload.context || {};
    const modality = document.createElement("div");
    modality.className = "modality-strip";
    appendModalityDot(modality, "V", Boolean(payload.frameUrl || valueObserved(raw.objects)), "Video evidence");
    appendModalityDot(modality, "A", Boolean(valueObserved(raw.audio_emotion) || valueObserved(context.audio_emotion) || valueObserved(raw.audio_emotion_scores)), "Audio evidence");
    appendModalityDot(modality, "T", Boolean(valueObserved(raw.transcript) || valueObserved(context.transcript) || valueObserved(raw.full_transcript)), "Text evidence");
    appendModalityDot(modality, "F", Boolean(previewCount(raw.faces || raw.face_ids || raw.candidate_visible_people || context.candidate_visible_people)), "Face evidence");
    appendModalityDot(modality, "O", Boolean(previewArray(raw.objects || context.objects).length), "Object evidence");
    panel.appendChild(modality);

    const transcript = document.createElement("div");
    transcript.className = "transcript";
    appendText(transcript, "p", payload.summary || "No transcript or scene summary exposed.");
    panel.appendChild(transcript);

    const evidence = document.createElement("div");
    evidence.className = "evidence-summary";
    payload.evidence.forEach((row) => appendPreviewEvidenceRow(evidence, row));
    panel.appendChild(evidence);

    const actions = document.createElement("div");
    actions.className = "preview-actions";
    const play = document.createElement("button");
    play.type = "button";
    play.className = "retrieval-button";
    play.textContent = "Clip playback not exposed";
    play.title = "Clip playback not exposed by the read-only API surface.";
    play.disabled = true;
    actions.appendChild(play);

    const inspector = document.createElement("a");
    inspector.className = "retrieval-button primary";
    inspector.href = "#scene-inspector";
    inspector.textContent = "Open Full Inspector";
    actions.appendChild(inspector);

    const exportButton = document.createElement("button");
    exportButton.type = "button";
    exportButton.className = "retrieval-button";
    exportButton.textContent = "Export manifest not exposed";
    exportButton.title = "Export manifest not exposed by the read-only API surface.";
    exportButton.disabled = true;
    actions.appendChild(exportButton);
    panel.appendChild(actions);
  }

  function valueObserved(value) {
    if (value === null || value === undefined) return false;
    if (typeof value === "string") return value.trim().length > 0;
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === "object") return Object.keys(value).length > 0;
    return true;
  }

  function arrayCount(value) {
    return Array.isArray(value) ? value.length : 0;
  }

  function objectCount(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? Object.keys(value).length : 0;
  }

  function stringList(value, limit) {
    if (!Array.isArray(value)) return [];
    const cleaned = value
      .map((item) => String(item || "").trim())
      .filter(Boolean);
    return Number.isFinite(limit) ? cleaned.slice(0, limit) : cleaned;
  }

  function sortedScorePairs(scores) {
    if (!scores || typeof scores !== "object" || Array.isArray(scores)) return [];
    return Object.entries(scores)
      .map(([label, rawScore]) => [label, Number(rawScore)])
      .filter(([label, score]) => label && Number.isFinite(score))
      .sort((a, b) => b[1] - a[1]);
  }

  function formatPercent(score) {
    if (!Number.isFinite(score)) return "score not observed";
    const normalized = score > 1 ? score / 100 : score;
    return `${Math.round(normalized * 100)}%`;
  }

  function audioEmotionLabel(segment) {
    if (valueObserved(segment.audio_emotion)) return safeString(segment.audio_emotion, "audio_emotion");
    const top = sortedScorePairs(segment.audio_emotion_scores)[0];
    if (top) {
      const reviewLabel = top[1] >= 0.5 ? "Review signal" : "Raw score";
      return `${reviewLabel}: ${top[0]} ${formatPercent(top[1])}`;
    }
    return segment.emotion_status || "Not observed";
  }

  function audioEmotionNote(segment) {
    const top = sortedScorePairs(segment.audio_emotion_scores)[0];
    if (valueObserved(segment.audio_emotion)) {
      return `Promoted label; ${top ? `top raw score ${top[0]} ${formatPercent(top[1])}` : "raw scores not exposed"}`;
    }
    if (top) {
      const scope = top[1] >= 0.5 ? "reviewable by operator" : "below promotion threshold";
      return `${top[0]} ${formatPercent(top[1])}; ${scope}`;
    }
    return "No raw audio emotion scores exposed";
  }

  function flattenTimeHints(hints) {
    if (!hints || typeof hints !== "object" || Array.isArray(hints)) return [];
    const values = [];
    Object.entries(hints).forEach(([key, rawValue]) => {
      const items = Array.isArray(rawValue) ? rawValue : valueObserved(rawValue) ? [rawValue] : [];
      items.forEach((item) => {
        const text = String(item || "").trim();
        if (text) values.push(`${key}: ${text}`);
      });
    });
    return values;
  }

  function appendSceneChipGroup(container, label, items, emptyText) {
    const group = document.createElement("div");
    group.className = "scene-chip-group";
    appendText(group, "span", label, "scene-chip-label");
    const chips = document.createElement("div");
    chips.className = "scene-chip-list";
    if (items.length) {
      items.forEach((item) => appendText(chips, "span", item, "scene-memory-chip"));
    } else {
      appendText(chips, "span", emptyText, "scene-chip-empty");
    }
    group.appendChild(chips);
    container.appendChild(group);
  }

  function appendSceneEvidenceRows(container, label, rows, emptyText) {
    const group = document.createElement("div");
    group.className = "scene-evidence-group";
    appendText(group, "span", label, "scene-chip-label");
    const list = document.createElement("div");
    list.className = "scene-evidence-list";
    if (rows.length) {
      rows.forEach((rowText) => appendText(list, "span", rowText, "scene-evidence-row"));
    } else {
      appendText(list, "span", emptyText, "scene-chip-empty");
    }
    group.appendChild(list);
    container.appendChild(group);
  }

  function formatTagDetail(detail) {
    if (!detail || typeof detail !== "object") return null;
    const label = detail.label || detail.tag || detail.name;
    if (!label) return null;
    const sources = stringList(detail.sources).join(", ") || detail.source || "source not exposed";
    const score = Number(detail.score);
    const scoreText = Number.isFinite(score) ? `score ${Math.round(score * 100) / 100}` : "score not exposed";
    return `${label} | ${sources} | ${scoreText}`;
  }

  function formatSceneEntity(entity) {
    if (!entity || typeof entity !== "object") return null;
    const text = entity.text || entity.entity || entity.name || entity.label;
    if (!text) return null;
    const type = entity.type || "entity";
    const source = entity.source ? ` | ${entity.source}` : "";
    return `${text} (${type})${source}`;
  }

  function formatSceneContextRows(context) {
    if (!context || typeof context !== "object" || Array.isArray(context)) return [];
    const rows = [];
    const summary = context.narrative_summary || context.summary;
    if (valueObserved(summary)) rows.push(`summary: ${safeString(summary, "scene_context_summary")}`);
    if (valueObserved(context.activity_description)) {
      rows.push(`activity: ${safeString(context.activity_description, "scene_context_activity")}`);
    }
    if (valueObserved(context.emotional_arc)) {
      rows.push(`arc: ${safeString(context.emotional_arc, "scene_context_arc")}`);
    }
    const tags = []
      .concat(stringList(context.primary_tags))
      .concat(stringList(context.contextual_tags))
      .concat(stringList(context.context_tags))
      .concat(stringList(context.structural_tags));
    if (tags.length) rows.push(`tags: ${[...new Set(tags)].slice(0, 8).join(", ")}`);
    return rows;
  }

  function sceneContextObject(segment) {
    return segment && segment.scene_context_llm && typeof segment.scene_context_llm === "object" && !Array.isArray(segment.scene_context_llm)
      ? segment.scene_context_llm
      : {};
  }

  function sceneContextTags(segment) {
    const context = sceneContextObject(segment);
    const tags = []
      .concat(stringList(segment && segment.tags, 8))
      .concat(Array.isArray(context.context_tags) ? context.context_tags : [])
      .concat(Array.isArray(context.primary_tags) ? context.primary_tags : [])
      .concat(Array.isArray(context.contextual_tags) ? context.contextual_tags : [])
      .concat(Array.isArray(context.structural_tags) ? context.structural_tags : []);
    return [...new Set(tags.map((tag) => safeString(tag, "scene_tag")).filter(Boolean))];
  }

  function sceneKeyMoments(segment) {
    const context = sceneContextObject(segment);
    return Array.isArray(context.key_moments)
      ? context.key_moments.map((moment) => safeString(moment, "key_moment")).filter(Boolean)
      : [];
  }

  function sceneMeaningSource(segment) {
    const context = sceneContextObject(segment);
    const epistemic = segment && segment.scene_context_epistemic && typeof segment.scene_context_epistemic === "object"
      ? segment.scene_context_epistemic
      : {};
    const arbitration = segment && segment.scene_context_arbitration && typeof segment.scene_context_arbitration === "object"
      ? segment.scene_context_arbitration
      : {};
    return context.source || epistemic.dominant_evidence || epistemic.evidence_family || arbitration.resolved_by || "Not observed";
  }

  function sceneMeaningSummary(segment) {
    const context = sceneContextObject(segment);
    return (
      context.narrative_summary ||
      context.summary ||
      context.activity_description ||
      segment.visual_caption ||
      segment.transcript ||
      segment.full_transcript ||
      null
    );
  }

  function sceneEvidenceSignalFamilies(segment) {
    const context = sceneContextObject(segment);
    const epistemic = segment && segment.scene_context_epistemic && typeof segment.scene_context_epistemic === "object"
      ? segment.scene_context_epistemic
      : {};
    const speakerIds = Array.isArray(segment.speaker_ids) ? segment.speaker_ids : [];
    const visiblePeople = Array.isArray(segment.candidate_visible_people) ? segment.candidate_visible_people : [];
    const alignedMentions = Array.isArray(segment.speaker_aligned_mentions) ? segment.speaker_aligned_mentions : [];
    const entityBuckets = sceneEntityEvidenceBuckets(segment);
    const clapMeta = segment.clap_meta && typeof segment.clap_meta === "object" && !Array.isArray(segment.clap_meta)
      ? segment.clap_meta
      : {};
    return [
      {
        label: "Meaning lens",
        observed: valueObserved(sceneMeaningSummary(segment)) || sceneKeyMoments(segment).length > 0,
        note: valueObserved(context.source) ? `source: ${safeString(context.source, "scene_context_source")}` : "scene_context_llm not exposed",
      },
      {
        label: "Transcript",
        observed: valueObserved(segment.transcript || segment.full_transcript),
        note: valueObserved(segment.transcript || segment.full_transcript) ? "scene-level speech text" : "transcript not exposed",
      },
      {
        label: "Visual proof",
        observed:
          valueObserved(segment.representative_frame) ||
          valueObserved(segment.clip_id) ||
          valueObserved(segment.dino_id) ||
          arrayCount(segment.objects) > 0 ||
          valueObserved(segment.visual_caption) ||
          valueObserved(segment.ocr_text),
        note: `${arrayCount(segment.objects)} objects; frame ${valueObserved(segment.representative_frame) ? "present" : "not exposed"}`,
      },
      {
        label: "Audio review",
        observed: valueObserved(segment.audio_emotion) || objectCount(segment.audio_emotion_scores) > 0,
        note: audioEmotionNote(segment),
      },
      {
        label: "Identity",
        observed: speakerIds.length > 0 || valueObserved(segment.dominant_speaker_id) || visiblePeople.length > 0 || alignedMentions.length > 0,
        note: `${speakerIds.length || 0} speaker ids; ${visiblePeople.length || 0} visible people`,
      },
      {
        label: "Entity evidence",
        observed: entityBuckets.total > 0 || valueObserved(epistemic.evidence_family),
        note: entityBuckets.total ? entityEvidenceSummaryNote(entityBuckets) : (epistemic.evidence_family ? `evidence family: ${safeString(epistemic.evidence_family, "evidence_family")}` : "entity evidence not exposed"),
      },
      {
        label: "Temporal hints",
        observed: flattenTimeHints(segment.time_hints).length > 0,
        note: `${flattenTimeHints(segment.time_hints).length} time hints`,
      },
      {
        label: "Sentiment",
        observed: valueObserved(segment.sentiment_label) || valueObserved(segment.sentiment_score),
        note: valueObserved(segment.sentiment_label) ? safeString(segment.sentiment_label, "sentiment_label") : "text sentiment label not persisted",
      },
      {
        label: "CLAP commit",
        observed: valueObserved(clapMeta.status),
        note: valueObserved(clapMeta.status) ? `status ${safeString(clapMeta.status, "clap_status")}; not current-run Qdrant proof` : "CLAP commit metadata not exposed",
      },
    ];
  }

  function appendSceneEvidenceSummary(container, segment) {
    const panel = document.createElement("section");
    panel.className = "scene-evidence-summary-panel";
    panel.setAttribute("data-testid", "scene-evidence-summary");
    appendText(panel, "h3", "Scene Evidence Summary", "scene-evidence-title");

    const families = sceneEvidenceSignalFamilies(segment);
    const observed = families.filter((item) => item.observed).length;
    const source = sceneMeaningSource(segment);
    appendIndicatorStrip(
      panel,
      [
        {
          label: "Meaning source",
          value: safeString(source, "meaning_source"),
          note: "scene_context_llm / epistemic envelope",
          kind: valueObserved(source) && source !== "Not observed" ? "info" : "unknown",
        },
        {
          label: "Evidence present",
          value: `${observed}/${families.length}`,
          note: "high-value signal families",
          kind: observed >= Math.ceil(families.length * 0.5) ? "ok" : "warn",
        },
        {
          label: "Evidence gaps",
          value: String(families.length - observed),
          note: "optional or absent signals",
          kind: families.length - observed ? "warn" : "ok",
        },
      ],
      "scene-summary-rollup"
    );
    appendSceneLineageBridge(panel, segment);

    const meaning = document.createElement("div");
    meaning.className = "scene-meaning-card";
    const summary = sceneMeaningSummary(segment);
    appendText(
      meaning,
      "p",
      summary ? safeString(summary, "scene_meaning_summary") : "No scene meaning summary exposed for this selected scene.",
      summary ? "scene-meaning-summary" : "scene-meaning-empty"
    );
    const context = sceneContextObject(segment);
    if (valueObserved(context.emotional_arc)) {
      appendText(meaning, "span", `Emotional arc: ${safeString(context.emotional_arc, "emotional_arc")}`, "scene-meaning-meta");
    }
    const moments = sceneKeyMoments(segment);
    if (moments.length) {
      const list = document.createElement("ul");
      list.className = "scene-key-moment-list";
      moments.slice(0, 3).forEach((moment) => appendText(list, "li", moment));
      meaning.appendChild(list);
    }
    const tags = sceneContextTags(segment);
    if (tags.length) {
      const strip = document.createElement("div");
      strip.className = "scene-tag-strip";
      tags.slice(0, 8).forEach((tag) => appendText(strip, "span", tag));
      meaning.appendChild(strip);
    }
    panel.appendChild(meaning);

    const grid = document.createElement("div");
    grid.className = "scene-signal-chip-grid";
    families.forEach((item) => {
      const chip = document.createElement("div");
      chip.className = `scene-signal-chip ${item.observed ? "observed" : "missing"}`;
      chip.appendChild(makeStatusDot(item.observed ? "ok" : "unknown", `${item.label}: ${item.observed ? "present" : "not exposed"}`));
      const body = document.createElement("div");
      appendText(body, "strong", item.label);
      appendText(body, "span", item.note, "scene-signal-note");
      chip.appendChild(body);
      grid.appendChild(chip);
    });
    panel.appendChild(grid);

    const gaps = families.filter((item) => !item.observed);
    const gapList = document.createElement("ul");
    gapList.className = "scene-gap-list";
    if (!gaps.length) {
      appendText(gapList, "li", "No optional evidence gaps surfaced for this selected scene.");
    } else {
      gaps.slice(0, 5).forEach((item) => appendText(gapList, "li", `${item.label}: ${item.note}`));
    }
    panel.appendChild(gapList);
    const actions = document.createElement("div");
    actions.className = "scene-evidence-actions";
    const previewButton = document.createElement("button");
    previewButton.type = "button";
    previewButton.className = "retrieval-button primary scene-open-visual-proof";
    previewButton.setAttribute("data-testid", "scene-open-visual-proof");
    previewButton.textContent = "Open Visual Proof";
    previewButton.title = "Open the linked media preview for this selected scene.";
    previewButton.addEventListener("click", () => openMediaPreview("timeline"));
    actions.appendChild(previewButton);
    panel.appendChild(actions);
    container.appendChild(panel);
  }

  function appendSceneLineageBridge(container, segment) {
    const lineage = state.sceneLineage;
    const bridge = document.createElement("div");
    bridge.className = "scene-lineage-bridge";
    bridge.setAttribute("data-testid", "scene-lineage-bridge");
    appendText(bridge, "strong", lineageSummaryText(lineage, segment));

    const row = document.createElement("div");
    [
      ["Source", lineage && lineage.source === "retrieval" ? "Retrieval result" : "Timeline"],
      ["Episode", lineage && lineage.displayTitle ? lineage.displayTitle : (state.selectedVideoId || "Selected video")],
      ["Scene", lineage && lineage.resultLabel ? lineage.resultLabel : sceneDisplayLabel(segment.scene_id || segment.index || "scene", 0)],
      ["Query", lineage && lineage.query ? lineage.query : "not a search handoff"],
    ].forEach(([label, value]) => {
      const item = document.createElement("span");
      item.textContent = `${label}: ${safeString(value, label)}`;
      row.appendChild(item);
    });
    bridge.appendChild(row);
    container.appendChild(bridge);
  }

  function numericDuration(segment) {
    const start = Number(segment.start);
    const end = Number(segment.end);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return "Not observed";
    return `${Math.round((end - start) * 10) / 10}s`;
  }

  function appendSceneFact(container, label, value, kind) {
    const row = document.createElement("div");
    row.className = "scene-fact-row";
    appendText(row, "span", label, "scene-fact-label");
    const valueNode = appendText(row, "strong", safeString(value, label), valueClass(value, label));
    if (kind) valueNode.classList.add(kind);
    container.appendChild(row);
  }

  function appendSceneSignal(container, label, observed, note) {
    const row = document.createElement("div");
    row.className = "scene-signal-row";
    const labelWrap = document.createElement("div");
    appendText(labelWrap, "strong", label);
    appendText(labelWrap, "span", note || "", "scene-signal-note");
    row.appendChild(labelWrap);
    row.appendChild(makeBadge(observed ? "On" : "Off", observed ? "ok" : "unknown"));
    container.appendChild(row);
  }

  function fieldStatus(segment, key) {
    if (!Object.prototype.hasOwnProperty.call(segment, key)) return { label: "missing", kind: "unknown" };
    const value = segment[key];
    if (!valueObserved(value)) return { label: "empty", kind: "warn" };
    if (safeString(value, key) === "[local-only]") return { label: "present redacted", kind: "warn" };
    return { label: "present", kind: "ok" };
  }

  function fieldInventory(segment) {
    const entries = Object.entries(segment || {});
    return {
      scalar: entries.filter(([, value]) => value === null || typeof value !== "object").length,
      arrays: entries.filter(([, value]) => Array.isArray(value)).length,
      objects: entries.filter(([, value]) => value && typeof value === "object" && !Array.isArray(value)).length,
      empty: entries.filter(([, value]) => !valueObserved(value)).length,
      total: entries.length,
    };
  }

  function renderSceneInspector() {
    const detail = qs("#scene-detail-panel");
    const modality = qs("#scene-modality-panel");
    const schema = qs("#scene-schema-panel");
    if (!detail || !modality || !schema) return;

    clear(detail);
    clear(modality);
    clear(schema);

    if (state.errors.timeline) {
      showError(detail, `Scene inspector unavailable: ${state.errors.timeline}`);
      showError(modality, "Timeline read model unavailable.");
      showError(schema, "Timeline schema unavailable.");
      return;
    }

    const entry = selectedSegmentEntry();
    if (!entry) {
      showError(detail, "Select a video with timeline data to inspect one scene.");
      showError(modality, "No selected scene.");
      showError(schema, "No schema projection.");
      return;
    }

    const segment = entry.segment || {};
    const rawSceneId = segment.scene_id || segment.segment_id || `Scene ${entry.index + 1}`;
    const sceneLabel = sceneDisplayLabel(rawSceneId, entry.index);
    const startEnd = `${formatTime(segment.start)}-${formatTime(segment.end)}`;
    const speakerIds = Array.isArray(segment.speaker_ids) ? segment.speaker_ids : [];
    const visiblePeople = Array.isArray(segment.candidate_visible_people) ? segment.candidate_visible_people : [];
    const alignedMentions = Array.isArray(segment.speaker_aligned_mentions) ? segment.speaker_aligned_mentions : [];
    const memoryTags = stringList(segment.tags);
    const tagDetails = Array.isArray(segment.tag_details) ? segment.tag_details : [];
    const sceneEntities = Array.isArray(segment.scene_present_entities) ? segment.scene_present_entities : [];
    const entityBuckets = sceneEntityEvidenceBuckets(segment);
    const sceneContext = segment.scene_context_llm && typeof segment.scene_context_llm === "object" && !Array.isArray(segment.scene_context_llm)
      ? segment.scene_context_llm
      : {};
    const sceneContextRows = formatSceneContextRows(sceneContext);
    const visualCaptionRows = valueObserved(segment.visual_caption)
      ? [safeString(segment.visual_caption, "visual_caption")]
      : [];
    const ocrTextRows = valueObserved(segment.ocr_text)
      ? [safeString(segment.ocr_text, "ocr_text")]
      : [];
    const ocrDateCandidates = stringList(segment.ocr_date_candidates, 8);
    const audioScoreCount = objectCount(segment.audio_emotion_scores);
    const clapMeta = segment.clap_meta && typeof segment.clap_meta === "object" && !Array.isArray(segment.clap_meta)
      ? segment.clap_meta
      : {};
    const clapCommitObserved = valueObserved(clapMeta.status);
    const clapCommitRows = clapCommitObserved
      ? [
          `status=${safeString(clapMeta.status, "clap_status")}`,
          clapMeta.faiss_id !== undefined && clapMeta.faiss_id !== null ? `faiss_id=${safeString(clapMeta.faiss_id, "clap_faiss_id")}` : null,
          clapMeta.model ? `model=${safeString(clapMeta.model, "clap_model")}` : null,
          "commit metadata only; not current-run Qdrant proof",
        ].filter(Boolean)
      : [];
    const disagreementCount = arrayCount(segment.transcript_entity_disagreements);
    const timeHintCount = objectCount(segment.time_hints);
    const timeHintValues = flattenTimeHints(segment.time_hints);
    const inventory = fieldInventory(segment);

    detail.appendChild(panelHeader("Selected scene", `${sceneLabel} | ${startEnd}`, segment.content_state || "read-only"));
    const summary = document.createElement("div");
    summary.className = "scene-summary";
    appendText(summary, "p", segmentSummary(segment));
    detail.appendChild(summary);
    appendSceneEvidenceSummary(detail, segment);

    const facts = document.createElement("div");
    facts.className = "scene-fact-list";
    [
      ["Scene ID", compactIdentifier(rawSceneId, { key: "scene_id", max: 22, leading: 12, trailing: 6 })],
      ["Timeline index", entry.index + 1],
      ["Duration", numericDuration(segment)],
      ["Content state", segment.content_state || "Not observed"],
      ["Continuity key", segment.continuity_key || "Not observed"],
      ["Dominant speaker", segment.dominant_speaker_id || "Not observed"],
      ["Speaker count", segment.speaker_count ?? (speakerIds.length || "Not observed")],
      ["Audio emotion", audioEmotionLabel(segment)],
      ["Sentiment", segment.sentiment_label || "Not observed"],
      [
        "Normalization",
        Object.prototype.hasOwnProperty.call(segment, "normalization_applied")
          ? segment.normalization_applied === true
            ? "applied"
            : "not applied"
          : "Not observed",
      ],
    ].forEach(([label, value]) => appendSceneFact(facts, label, value));
    detail.appendChild(facts);

    const evidence = document.createElement("div");
    evidence.className = "scene-evidence-block";
    appendText(evidence, "h3", "Scene memory evidence", "scene-evidence-title");
    appendSceneChipGroup(evidence, "Memory tags", memoryTags.slice(0, 10), "No memory tags exposed");
    appendSceneEvidenceRows(
      evidence,
      "Tag provenance",
      tagDetails.map(formatTagDetail).filter(Boolean).slice(0, 6),
      "No tag provenance exposed"
    );
    appendSceneChipGroup(evidence, "Time hints", timeHintValues.slice(0, 6), "No time hints exposed");
    appendSceneEvidenceRows(evidence, "Visual caption", visualCaptionRows, "No visual caption exposed");
    appendSceneEvidenceRows(evidence, "OCR text", ocrTextRows, "No OCR text exposed");
    appendSceneChipGroup(evidence, "OCR date candidates", ocrDateCandidates, "No OCR date candidates exposed");
    appendSceneEvidenceRows(
      evidence,
      "CLAP commit status",
      clapCommitRows,
      "No CLAP commit metadata exposed"
    );
    appendSceneEvidenceRows(
      evidence,
      "Scene context summary",
      sceneContextRows,
      "No scene_context_llm exposed"
    );
    appendSceneEvidenceRows(
      evidence,
      "Scene-present entities",
      sceneEntities.map(formatSceneEntity).filter(Boolean).slice(0, 6),
      "No scene-present entities exposed"
    );
    appendSceneEvidenceRows(
      evidence,
      "Dialogue-mentioned entities",
      entityBuckets.dialogueMentioned.map(formatSceneEntity).filter(Boolean).slice(0, 6),
      "No dialogue-mentioned entities exposed"
    );
    appendSceneEvidenceRows(
      evidence,
      "Mentioned people",
      entityBuckets.mentionedPeople.map(formatSceneEntity).filter(Boolean).slice(0, 6),
      "No mentioned people exposed"
    );
    appendSceneEvidenceRows(
      evidence,
      "Candidate visible people",
      entityBuckets.candidateVisible.concat(entityBuckets.visiblePeople).map(formatSceneEntity).filter(Boolean).slice(0, 6),
      "No candidate visible people exposed"
    );
    appendSceneEvidenceRows(
      evidence,
      "Speaker-aligned mentions",
      entityBuckets.speakerAligned.map(formatSceneEntity).filter(Boolean).slice(0, 6),
      "No speaker-aligned mentions exposed"
    );
    detail.appendChild(evidence);

    modality.appendChild(panelHeader("Modality coverage", "Evidence visible in selected timeline row", "read-only"));
    const modalityStates = [
      valueObserved(segment.representative_frame),
      valueObserved(segment.clip_id) || valueObserved(segment.dino_id),
      valueObserved(segment.visual_caption),
      valueObserved(segment.ocr_text),
      arrayCount(segment.objects) > 0,
      valueObserved(segment.transcript || segment.full_transcript),
      arrayCount(segment.audio_chunks) > 0,
      speakerIds.length > 0 || valueObserved(segment.dominant_speaker_id),
      visiblePeople.length > 0,
      alignedMentions.length > 0,
      memoryTags.length > 0,
      tagDetails.length > 0,
      entityBuckets.total > 0,
      valueObserved(segment.sentiment_label) || valueObserved(segment.sentiment_score),
      valueObserved(segment.audio_emotion) || audioScoreCount > 0,
      clapCommitObserved,
      sceneContextRows.length > 0 || valueObserved(segment.scene_context_epistemic) || valueObserved(segment.scene_context_arbitration),
      timeHintCount > 0,
    ];
    const modalityObserved = modalityStates.filter(Boolean).length;
    appendIndicatorStrip(
      modality,
      [
        {
          label: "Scene modalities",
          value: `${modalityObserved}/${modalityStates.length}`,
          note: "present in selected scene",
          kind: modalityObserved >= Math.ceil(modalityStates.length * 0.5) ? "ok" : "warn",
        },
        {
          label: "Optional gaps",
          value: String(modalityStates.length - modalityObserved),
          note: "visible below",
          kind: modalityStates.length - modalityObserved ? "warn" : "ok",
        },
      ],
      "modality-rollup-strip"
    );
    const modalityList = document.createElement("div");
    modalityList.className = "scene-signal-list";
    appendSceneSignal(
      modalityList,
      "Visual frame proof",
      valueObserved(segment.representative_frame),
      valueObserved(segment.representative_frame) ? "Representative frame present; local path redacted" : "No frame pointer exposed"
    );
    appendSceneSignal(
      modalityList,
      "Visual embeddings",
      valueObserved(segment.clip_id) || valueObserved(segment.dino_id),
      `CLIP ${valueObserved(segment.clip_id) ? "observed" : "missing"}; DINO ${valueObserved(segment.dino_id) ? "observed" : "missing"}`
    );
    appendSceneSignal(
      modalityList,
      "Visual caption",
      valueObserved(segment.visual_caption),
      valueObserved(segment.visual_caption) ? safeString(segment.visual_caption, "visual_caption") : "No visual caption exposed"
    );
    appendSceneSignal(
      modalityList,
      "OCR text",
      valueObserved(segment.ocr_text),
      valueObserved(segment.ocr_text) ? safeString(segment.ocr_text, "ocr_text") : "No OCR text exposed"
    );
    appendSceneSignal(modalityList, "Object detections", arrayCount(segment.objects) > 0, `${arrayCount(segment.objects)} objects`);
    appendSceneSignal(modalityList, "Transcript text", valueObserved(segment.transcript || segment.full_transcript), "Scene-level speech text");
    appendSceneSignal(modalityList, "Audio chunks", arrayCount(segment.audio_chunks) > 0, `${arrayCount(segment.audio_chunks)} chunks`);
    appendSceneSignal(modalityList, "Speaker identity", speakerIds.length > 0 || valueObserved(segment.dominant_speaker_id), `${speakerIds.length} speaker ids`);
    appendSceneSignal(modalityList, "Visible people", visiblePeople.length > 0, `${visiblePeople.length} candidates`);
    appendSceneSignal(modalityList, "Aligned mentions", alignedMentions.length > 0, `${alignedMentions.length} mention links`);
    appendSceneSignal(modalityList, "Memory tags", memoryTags.length > 0, `${memoryTags.length} tags exposed`);
    appendSceneSignal(modalityList, "Tag provenance", tagDetails.length > 0, `${tagDetails.length} provenance rows`);
    appendSceneSignal(modalityList, "Entity evidence", entityBuckets.total > 0, entityEvidenceSummaryNote(entityBuckets));
    appendSceneSignal(modalityList, "Scene-present entities", sceneEntities.length > 0, `${sceneEntities.length} entity rows`);
    appendSceneSignal(modalityList, "Dialogue-mentioned entities", entityBuckets.dialogueMentioned.length > 0, `${entityBuckets.dialogueMentioned.length} dialogue rows`);
    appendSceneSignal(modalityList, "Candidate visible people", entityBuckets.candidateVisible.length + entityBuckets.visiblePeople.length > 0, `${entityBuckets.candidateVisible.length + entityBuckets.visiblePeople.length} candidate rows`);
    appendSceneSignal(
      modalityList,
      "Sentiment analysis",
      valueObserved(segment.sentiment_label) || valueObserved(segment.sentiment_score),
      safeString(segment.sentiment_score ?? "score not observed", "sentiment_score")
    );
    appendSceneSignal(
      modalityList,
      "Audio emotion review",
      valueObserved(segment.audio_emotion) || audioScoreCount > 0,
      audioEmotionNote(segment)
    );
    appendSceneSignal(
      modalityList,
      "CLAP commit metadata",
      clapCommitObserved,
      clapCommitObserved
        ? `status ${safeString(clapMeta.status, "clap_status")}; commit metadata only; not current-run Qdrant proof`
        : "No CLAP commit metadata exposed"
    );
    appendSceneSignal(
      modalityList,
      "Scene context LLM",
      sceneContextRows.length > 0 || valueObserved(segment.scene_context_epistemic) || valueObserved(segment.scene_context_arbitration),
      sceneContextRows.length > 0 ? sceneContextRows[0] : "No scene_context_llm evidence exposed"
    );
    appendSceneSignal(modalityList, "Temporal hints", timeHintCount > 0, `${timeHintCount} hint fields`);
    if (disagreementCount > 0) {
      appendSceneSignal(modalityList, "Entity disagreements", true, `${disagreementCount} disagreement rows`);
    }
    modality.appendChild(modalityList);

    schema.appendChild(panelHeader("Schema projection", "Raw timeline row, safe projection only", `${inventory.total} fields`));
    const inventoryGrid = document.createElement("div");
    inventoryGrid.className = "scene-inventory-grid";
    [
      ["Scalar", inventory.scalar],
      ["Arrays", inventory.arrays],
      ["Objects", inventory.objects],
      ["Empty", inventory.empty],
    ].forEach(([label, value]) => {
      const item = document.createElement("div");
      appendText(item, "span", label);
      appendText(item, "strong", safeString(value, label));
      inventoryGrid.appendChild(item);
    });
    schema.appendChild(inventoryGrid);

    const expectedFields = [
      "scene_id",
      "start",
      "end",
      "transcript",
      "representative_frame",
      "visual_caption",
      "ocr_text",
      "ocr_date_candidates",
      "clip_id",
      "dino_id",
      "speaker_ids",
      "objects",
      "keywords",
      "content_state",
      "continuity_key",
      "time_hints",
      "tags",
      "tag_details",
      "scene_present_entities",
      "entities",
      "dialogue_mentioned_entities",
      "mentioned_people",
      "candidate_visible_people",
      "visible_people",
      "speaker_aligned_mentions",
      "sentiment_label",
      "audio_emotion",
      "audio_emotion_scores",
      "clap_meta",
      "scene_context_llm",
      "scene_context_epistemic",
      "scene_context_arbitration",
    ];
    const fieldStates = expectedFields.map((key) => ({ key, status: fieldStatus(segment, key) }));
    const presentFields = fieldStates.filter((item) => item.status.kind === "ok" || item.status.label === "present redacted").length;
    const emptyFields = fieldStates.filter((item) => item.status.label === "empty").length;
    const missingFields = fieldStates.filter((item) => item.status.label === "missing").length;
    appendIndicatorStrip(
      schema,
      [
        {
          label: "Field coverage",
          value: `${presentFields}/${fieldStates.length}`,
          note: "present or redacted",
          kind: presentFields >= Math.ceil(fieldStates.length * 0.5) ? "ok" : "warn",
        },
        {
          label: "Empty",
          value: String(emptyFields),
          note: "keys present without values",
          kind: emptyFields ? "warn" : "ok",
        },
        {
          label: "Missing",
          value: String(missingFields),
          note: "not exposed in row",
          kind: missingFields ? "unknown" : "ok",
        },
      ],
      "field-status-rollup"
    );
    const schemaList = document.createElement("div");
    schemaList.className = "schema-field-list";
    fieldStates.forEach(({ key, status }) => {
      const row = document.createElement("div");
      row.className = "schema-field-row";
      appendText(row, "span", key, "schema-field-key");
      row.appendChild(makeBadge(status.label, status.kind));
      schemaList.appendChild(row);
    });
    const schemaDetails = document.createElement("details");
    schemaDetails.className = "schema-field-details";
    const schemaSummary = document.createElement("summary");
    schemaSummary.textContent = "Field detail rows";
    schemaDetails.appendChild(schemaSummary);
    schemaDetails.appendChild(schemaList);
    schema.appendChild(schemaDetails);

    const boundary = document.createElement("div");
    boundary.className = "scene-boundary-note";
    appendText(boundary, "span", "Read-only inspector. Local paths and raw artifacts remain redacted.");
    schema.appendChild(boundary);
  }

  function renderTimeline() {
    const node = qs("#timeline-panel");
    clear(node);
    if (state.errors.timeline) return showError(node, `Timeline unavailable: ${state.errors.timeline}`);
    const segments = timelineSegments(state.data.timeline);
    setDefaultSelectedScene();
    node.appendChild(
      panelHeader(
        "Selected timeline",
        state.selectedVideoId ? safeString(state.selectedVideoId, "video_id") : "No selected video",
        `${segments.length} scenes`
      )
    );

    if (!segments.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      appendText(empty, "span", "Select a video with timeline data.");
      node.appendChild(empty);
      return;
    }

    const list = document.createElement("div");
    list.className = "timeline-list";
    segments.slice(0, 24).forEach((segment, index) => {
      const key = segmentKey(segment, index);
      const selected = key === state.selectedSceneKey;
      const row = document.createElement("button");
      row.type = "button";
      row.className = `timeline-row ${selected ? "selected" : ""}`;
      row.setAttribute("aria-pressed", selected ? "true" : "false");
      row.setAttribute("data-testid", selected ? "selected-timeline-row" : "timeline-row");
      row.addEventListener("click", () => {
        state.selectedSceneKey = key;
        setTimelineSceneLineage(segment, index);
        renderTimeline();
        renderSceneInspector();
        openMediaPreview("timeline");
      });
      appendText(row, "div", `${formatTime(segment.start)}-${formatTime(segment.end)}`, "timeline-time");
      const body = document.createElement("div");
      body.className = "timeline-body";
      const fullSceneId = segment.scene_id || segment.index || "scene";
      const sceneTitle = appendText(body, "strong", sceneDisplayLabel(fullSceneId, index), "compact-id");
      sceneTitle.title = safeString(fullSceneId, "scene_id");
      appendText(body, "span", segmentSummary(segment));
      row.appendChild(body);
      row.appendChild(
        makeStatusDot(selected ? "ok" : statusKind(segment.content_state || "state"), selected ? "Selected scene" : `Scene state: ${safeString(segment.content_state || "state", "content_state")}`)
      );
      list.appendChild(row);
    });
    node.appendChild(list);
  }

  function renderEvidence() {
    const node = qs("#evidence-panel");
    clear(node);
    const hasEnvelope = valueObserved(state.data.envelope && state.data.envelope.envelope);
    node.appendChild(
      panelHeader("Justification Channel", "Literal envelope renderer", hasEnvelope ? "ready" : "not configured")
    );

    const info = document.createElement("div");
    info.className = "kv-list";
    const rows = [
      ["Envelope endpoint", hasEnvelope ? "/api/read/envelope" : "not configured"],
      ["Source mode", "explicit read-only API"],
      ["Mutation boundary", "no actions, no commands, no ingestion triggers"],
    ];
    rows.forEach(([key, value]) => {
      const row = document.createElement("div");
      row.className = "kv-row";
      appendText(row, "div", key, "kv-key");
      appendText(row, "div", value, "kv-value");
      info.appendChild(row);
    });
    node.appendChild(info);

    const linkRow = document.createElement("div");
    linkRow.className = "link-row";
    const docs = document.createElement("a");
    docs.className = "link-button";
    docs.href = `${state.apiBase}/docs`;
    docs.target = "_blank";
    docs.rel = "noreferrer";
    docs.textContent = "API docs";
    linkRow.appendChild(docs);

    const justification = document.createElement("a");
    justification.className = "link-button";
    justification.href = `../justification_v1/?source=api&api_base=${encodeURIComponent(state.apiBase)}`;
    justification.textContent = "Open Justification Channel";
    linkRow.appendChild(justification);
    node.appendChild(linkRow);
  }

  function render() {
    qs("#api-base").value = state.apiBase;
    renderConnection();
    renderScopeBanner();
    renderFlightDeck();
    renderProofPanel();
    renderRetrievalConsole();
    renderSummary();
    renderRun();
    renderRecurrence();
    renderRecurrenceTrend();
    renderSurfaces();
    renderTemporalSurface();
    renderDiagnostics();
    renderMachine();
    renderStorage();
    renderMemory();
    renderHealth();
    renderVideos();
    renderTimeline();
    renderSceneInspector();
    renderMediaPreview();
    renderEvidence();
  }

  function readInitialApiBase() {
    const params = new URLSearchParams(window.location.search);
    return normalizeApiBase(params.get("api_base") || window.localStorage.getItem("goodq_operator_api_base"));
  }

  function init() {
    state.apiBase = readInitialApiBase();
    qs("#api-base").value = state.apiBase;
    qs("#api-form").addEventListener("submit", (event) => {
      event.preventDefault();
      state.apiBase = normalizeApiBase(qs("#api-base").value);
      window.localStorage.setItem("goodq_operator_api_base", state.apiBase);
      refreshAll();
    });
    qs("#retrieval-form").addEventListener("submit", (event) => {
      event.preventDefault();
      runRetrievalQuery({ resetLimit: true });
    });
    qs("#retrieval-load-more").addEventListener("click", () => {
      state.retrieval.limit += 10;
      runRetrievalQuery({ useExistingQuery: true });
    });
    qs("#retrieval-open-scene").addEventListener("click", () => {
      selectRetrievalResultSurface("scene-inspector");
    });
    qs("#retrieval-view-timeline").addEventListener("click", (event) => {
      if (!selectedRetrievalEntry()) return;
      event.preventDefault();
      selectRetrievalResultSurface("videos");
    });
    refreshAll();
  }

  window.GoodQOperatorConsole = {
    state,
    refreshAll,
    sanitizeValue: safeString,
    isLocalApi,
    render,
  };

  document.addEventListener("DOMContentLoaded", init);
})();
