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
    memory: "/api/memory/stats",
    recurrence: "/api/control-recurrence/reports/latest",
    trend: "/api/control-recurrence/reports/trend",
    videos: "/api/system/videos",
    envelope: "/api/read/envelope",
  };

  const diagnosticEndpointNames = new Set(["engines", "gpu", "wsl", "queue"]);
  const optionalEndpointNames = new Set(["envelope"]);
  const endpointTimeoutMs = {
    engines: 25000,
    wsl: 18000,
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
    if (["warn", "warning", "partial_success", "idle", "unknown", "unavailable", "degraded", "skipped", "not_installed", "inactive"].includes(text)) {
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

  function numberValue(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function statusLabel(value) {
    const kind = statusKind(value);
    if (kind === "ok") return { label: "Nominal", kind: "ok" };
    if (kind === "error") return { label: "Fault", kind: "error" };
    if (kind === "warn") return { label: "Caution", kind: "warn" };
    return { label: "Not observed", kind: "unknown" };
  }

  function notObserved(note) {
    return { label: "Not observed", kind: "unknown", note: note || "" };
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
      "#flight-system-map",
      "#flight-first-run",
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

    const boundary = qs("#boundary-panel");
    clear(boundary);
    const boundaryDot = document.createElement("span");
    boundaryDot.className = `status-dot ${local ? "ok" : "warn"}`;
    boundaryDot.setAttribute("aria-hidden", "true");
    boundary.appendChild(boundaryDot);
    appendText(boundary, "span", local ? "Local machine boundary" : "Non-local API base");
  }

  function renderFlightDeck() {
    const systemMap = qs("#flight-system-map");
    const firstRun = qs("#flight-first-run");
    const contract = qs("#flight-runtime-contract");
    if (!systemMap || !firstRun || !contract) return;

    clear(systemMap);
    clear(firstRun);
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
    const sceneCount = numberValue(run.scenes_processed);
    const firstMemoryCreated = run.available === true && sceneCount !== null && sceneCount > 0;
    const latestRunAgo = relativeTime(latestRunTimestamp(run));

    appendFlightRow(systemMap, "Launcher", notObserved("Launcher state is not exposed"), "flight-launcher-status");
    appendFlightRow(
      systemMap,
      "API Service",
      state.errors.status
        ? { label: "Fault", kind: "error", note: "Status endpoint unavailable" }
        : {
            ...statusLabel(status.status),
            note: "Local read API",
            title: state.apiBase,
          },
      "flight-api-status"
    );
    appendFlightRow(systemMap, "Watchdog", notObserved("Process state is not exposed"), "flight-watchdog-status");
    appendFlightRow(
      systemMap,
      "Ingestion Engine",
      state.errors.queue || !state.data.queue
        ? notObserved("Queue endpoint unavailable")
        : {
            label: processingCount && processingCount > 0 ? "Processing" : "Idle",
            kind: "ok",
            note: processingCount !== null ? `${processingCount} active` : "Queue reachable",
          },
      "flight-ingestion-status"
    );
    appendFlightRow(
      systemMap,
      "SQLite",
      status.database && typeof status.database.exists === "boolean"
        ? {
            label: status.database.exists ? "Nominal" : "Caution",
            kind: status.database.exists ? "ok" : "warn",
            note: status.database.exists ? "Local store observed" : "Store not observed",
          }
        : notObserved("Database probe missing"),
      "flight-sqlite-status"
    );
    appendFlightRow(
      systemMap,
      "Qdrant",
      memory.qdrant && typeof memory.qdrant.available === "boolean"
        ? {
            label: memory.qdrant.available ? "Nominal" : "Caution",
            kind: memory.qdrant.available ? "ok" : "warn",
            note: memory.qdrant.available
              ? `${safeString(memory.qdrant.collections, "collections")} collections`
              : "Vector store unreachable",
            title: qdrantEngine.port ? `http://127.0.0.1:${qdrantEngine.port}` : "",
          }
        : notObserved("Memory stats unavailable"),
      "flight-qdrant-status"
    );
    appendFlightRow(
      systemMap,
      "Knowledge Graph",
      graph.status
        ? statusLabel(graph.status)
        : state.errors.runEvidence
          ? notObserved("Evidence endpoint unavailable")
          : notObserved("Graph rollup missing"),
      "flight-kg-status"
    );

    appendFlightRow(
      firstRun,
      "Import Inbox",
      state.errors.queue || !state.data.queue
        ? notObserved("Inbox count unavailable")
        : {
            label: inboxCount && inboxCount > 0 ? `${inboxCount} file${inboxCount === 1 ? "" : "s"}` : "Empty",
            kind: inboxCount && inboxCount > 0 ? "ok" : "warn",
            note: IMPORT_INBOX_LABEL,
          },
      "flight-import-inbox"
    );
    appendFlightRow(firstRun, "Watchdog", notObserved("Process state is not exposed"), "flight-first-run-watchdog");
    appendFlightRow(
      firstRun,
      "Processing Queue",
      state.errors.queue || !state.data.queue
        ? notObserved("Queue count unavailable")
        : {
            label: processingCount !== null ? `${processingCount} active` : "Not observed",
            kind: processingCount !== null ? "ok" : "unknown",
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
        : notObserved("No run preview"),
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
          ? { label: "Not yet created", kind: "warn", note: "No scene count observed" }
          : notObserved("No run preview"),
      "flight-first-memory"
    );

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
    const artifacts = evidence.artifact_presence || {};
    const steps = evidence.step_runs || {};
    const temporal = evidence.temporal_index || {};
    const sentiment = evidence.sentiment || {};
    const graph = evidence.knowledge_graph || {};
    const audioProof = evidence.audio_vector_proof || {};
    const latestEpisode = evidence.latest_episode || run.latest_episode || {};
    const memory = state.data.memory || {};
    const faissAudioCount = numberValue(memory.faiss?.audio_vectors);
    const sceneContextCount = numberValue(temporal.segments_with_scene_context_llm);
    const audioEmotionCount = numberValue(sentiment.segments_with_audio_emotion ?? temporal.segments_with_audio_emotion);
    const sentimentCount = numberValue(sentiment.segments_with_sentiment);
    const clapOkCount = numberValue(audioProof.clap_ok);
    const provenAudioCount = numberValue(audioProof.current_run_qdrant_proven);
    const stepRows = numberValue(steps.row_count);
    const temporalScenes = numberValue(temporal.total_scenes);
    const graphScenes = numberValue(graph.scene_count);
    const runScenes = numberValue(run.scenes_processed);
    const audioProofStatus = String(audioProof.status || "unavailable");
    const audioProofObserved = audioProofStatus === "current_run_audio_vector_proven";
    const audioProofPartial = audioProofStatus === "partial";
    const audioProofKind = audioProofObserved ? "ok" : audioProofPartial ? "warn" : "unknown";
    const audioProofLabel = audioProof.label || (audioProofObserved ? "Proven" : "No Current-Run Evidence");
    const audioProofNote = provenAudioCount !== null && clapOkCount !== null
      ? `${provenAudioCount} / ${clapOkCount} CLAP-ok scenes`
      : audioProof.impact || "Run-matched Qdrant proof not reported";

    const proofRows = [
      {
        label: "Step run ledger",
        state: proofState(artifacts.step_runs_jsonl === true && hasOkStatus(steps.status), "Observed", "Not observed", evidenceNote(stepRows, "rows"), "warn"),
        missingNote: "step_runs.jsonl missing or unreadable",
      },
      {
        label: "Temporal index",
        state: proofState(artifacts.temporal_index_json === true && hasOkStatus(temporal.status), "Observed", "Not observed", evidenceNote(temporalScenes, "scenes"), "warn"),
        missingNote: "temporal_index.json missing or unreadable",
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
        state: proofState(temporal.has_audio === true, "Observed", "Not observed", audioEmotionCount !== null ? `${audioEmotionCount} emotion rows` : "", "unknown"),
        missingNote: "Latest temporal index does not report audio",
      },
      {
        label: "Transcript Audio",
        state: proofState(temporal.has_transcripts === true, "Observed", "Not observed", evidenceNote(sentiment.segments_total, "segments"), "unknown"),
        missingNote: "Latest temporal index does not report transcripts",
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
      supplementalChecks.filter((row) => row.label === "CLAP memory commit" || row.label === "Current-run Qdrant audio proof")
    );
    proofDisplayRows.forEach((row) => {
      appendProofItem(proofList, {
        label: row.label,
        note: row.state.note,
        status: row.state.label,
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
      ["Latest episode", latestEpisode.episode || "Not observed"],
      ["Latest timestamp", latestEpisode.ts_utc ? relativeTime(latestEpisode.ts_utc) : relativeTime(latestRunTimestamp(run))],
      ["Run scenes", runScenes !== null ? runScenes : "Not observed"],
      ["Temporal scenes", temporalScenes !== null ? temporalScenes : "Not observed"],
      ["Step rows", stepRows !== null ? stepRows : "Not observed"],
      ["Phase 6", graph.phase6_complete === true || temporal.phase6_complete === true ? "Complete" : "Not observed"],
      ["Qdrant", graph.qdrant_ok === true || graph.phase6_qdrant_ok === true ? "Observed" : "Not observed"],
      ["Safety boundary", evidence.safety_boundary?.mode || "read_only"],
    ];

    inspectorRows.forEach(([label, value]) => {
      const cell = document.createElement("div");
      cell.className = "proof-inspector-cell";
      appendText(cell, "span", label);
      appendText(cell, "strong", safeString(value, label));
      inspector.appendChild(cell);
    });
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
        "Engine health",
        health.overall ? health.overall.status : "unknown",
        health.overall ? `${health.overall.healthy}/${health.overall.total} healthy` : "No health summary",
        health.overall ? statusKind(health.overall.status) : "warn"
      )
    );
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
    renderMiniList(node, "Top audio emotions", sentiment.top_audio_emotions, "label", "count");
    renderMiniList(node, "Sentiment labels", sentiment.sentiment_labels, "label", "count");
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

    node.appendChild(panelHeader("Engine diagnostics", "Read-only probes; path-bearing descriptions are omitted", overall.status || "unknown"));
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
      appendText(node, "h3", "GPU", "panel-subtitle");
      renderKv(node, state.data.gpu || {}, [
        "available",
        "name",
        "utilization_percent",
        "memory_used_mb",
        "memory_total_mb",
        "memory_percent",
        "temperature_c",
      ]);
    }

    if (state.errors.wsl) {
      appendInlineError(node, `WSL status unavailable: ${state.errors.wsl}`);
    } else {
      appendText(node, "h3", "WSL", "panel-subtitle");
      renderKv(node, state.data.wsl || {}, [
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

  function renderHealth() {
    const node = qs("#health-panel");
    clear(node);
    if (state.errors.health) return showError(node, `Health summary unavailable: ${state.errors.health}`);
    const health = state.data.health || {};
    node.appendChild(panelHeader("Engine health", "Model service readiness", health.overall?.status || "unknown"));
    renderKv(node, health.overall || {}, ["status", "total", "healthy", "unhealthy"]);
    renderKv(node, health.vllm || {}, ["status", "healthy", "total"]);
    renderKv(node, health.ollama || {}, ["status", "healthy", "total"]);
  }

  function retrievalResultKey(result, index) {
    const video = result && result.video_id ? String(result.video_id) : "video";
    const scene = result && result.scene_id !== null && result.scene_id !== undefined ? String(result.scene_id) : "scene";
    return `${video}:${scene}:${index}`;
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
    return `Scene ${safeString(id, "scene_id")}`;
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
    const start = retrievalNumber(context.start);
    const end = retrievalNumber(context.end);
    if (start !== null && end !== null) return `${formatTime(start)}-${formatTime(end)}`;
    const timestamp = retrievalNumber(result ? result.timestamp : null);
    if (timestamp !== null) return `${formatTime(timestamp)}`;
    return "time not returned";
  }

  function videoInventoryIds() {
    const videos = Array.isArray(state.data.videos) ? state.data.videos : [];
    return new Set(videos.map((video) => String(video.video_id || video.id || "")).filter(Boolean));
  }

  function canOpenRetrievalResult(result) {
    if (!result || !valueObserved(result.video_id) || !valueObserved(result.scene_id)) return false;
    return videoInventoryIds().has(String(result.video_id));
  }

  function objectHasAny(data, keys) {
    if (!data || typeof data !== "object") return false;
    return keys.some((key) => valueObserved(data[key]));
  }

  function retrievalContext(result) {
    return result && result.context && typeof result.context === "object" ? result.context : {};
  }

  function retrievalSceneContextLlm(result) {
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

  function retrievalObjectLabels(result) {
    const context = retrievalContext(result);
    const objects = Array.isArray(result && result.objects) && result.objects.length ? result.objects : context.objects;
    return Array.isArray(objects) ? objects.map((item) => safeString(item, "object")).filter(Boolean) : [];
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
    const llmSummary = retrievalLlmSummary(result);
    const llmTags = retrievalLlmTags(result);
    const epistemic = context.scene_context_epistemic && typeof context.scene_context_epistemic === "object" ? context.scene_context_epistemic : {};
    const arbitration = context.scene_context_arbitration && typeof context.scene_context_arbitration === "object" ? context.scene_context_arbitration : {};
    const facts = [
      ["Episode", result && result.video_id],
      ["Time", resultTimeLabel(result)],
      ["Transcript", valueObserved(result && result.transcript) || valueObserved(context.transcript) ? "Observed" : "Not observed"],
      ["Objects", objects.length ? `${objects.slice(0, 4).join(", ")}${objects.length > 4 ? "..." : ""}` : "Not observed"],
      ["Audio emotion", context.audio_emotion || "Not observed"],
      ["Speaker continuity", context.continuity_key || (context.speaker_count ? `${context.speaker_count} speakers` : "Not observed")],
      ["Scene context LLM", llmSummary || (context.scene_context_llm ? "Observed" : "Not observed")],
      ["LLM tags", llmTags.length ? llmTags.join(", ") : "Not observed"],
      ["Epistemic state", epistemic.state || "Not observed"],
      ["Arbitration", arbitration.resolved_by || "Not observed"],
      ["Sentiment", retrievalSentimentLabel(result) || "Not persisted"],
    ];
    if (result && result.provenance && typeof result.provenance === "object") {
      facts.push(["Provenance", result.provenance.hydrated_from || result.provenance.source || "Returned"]);
    }
    return facts;
  }

  function appendRetrievalEvidence(container, result, selectedIndex, signals, percent) {
    const panel = document.createElement("div");
    panel.className = "retrieval-evidence-digest";
    panel.setAttribute("data-testid", "retrieval-evidence-digest");
    appendText(panel, "h4", "Selected Evidence");
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

    const observedSignals = Array.isArray(signals) ? signals.filter((row) => row.observed).length : 0;
    const footer = document.createElement("p");
    footer.className = "retrieval-evidence-footer";
    footer.textContent = `${resultSceneLabel(result, selectedIndex)} | ${observedSignals} signals observed | ${percentLabel(percent)} returned score`;
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
      modality.includes("audio") ||
      provenanceMentions(result, "audio") ||
      objectHasAny(context, ["audio_emotion", "audio_chunks", "clap_meta"]);
    const kgObserved =
      provenanceMentions(result, "kg") ||
      provenanceMentions(result, "graph") ||
      objectHasAny(context, ["entity_links", "kg_links", "knowledge_graph", "relationships"]);
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
        note: audioObserved ? (context.audio_emotion ? `Audio emotion: ${safeString(context.audio_emotion, "audio_emotion")}` : "Audio modality or audio provenance observed") : "No current-run audio proof returned",
        missing: "Audio vector not yet proven",
      },
      {
        label: "KG Relationship",
        observed: kgObserved,
        strength: null,
        note: kgObserved ? "Graph relationship evidence returned" : "No KG relationship returned",
        missing: "KG relationship not exposed",
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
      item.appendChild(makeBadge(row.observed ? "Observed" : "Not proven", row.observed ? "ok" : "unknown"));
    }
    container.appendChild(item);
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
    if (!input || !count || !list || !explanation || !selectedScore || !previewCopy || !loadMore || !openScene || !viewTimeline) {
      return;
    }

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
        renderRetrievalConsole();
      });
      const label = document.createElement("div");
      appendText(label, "strong", resultSceneLabel(result, index));
      appendText(label, "span", `${resultTimeLabel(result)} | ${safeString(result.modality || "unknown", "modality")}`, "retrieval-result-meta");
      appendText(label, "span", resultSummary(result), "retrieval-result-summary");
      row.appendChild(label);
      const percent = scorePercent(result);
      row.appendChild(makeBadge(percentLabel(percent), percent !== null && percent >= 80 ? "ok" : "warn"));
      list.appendChild(row);
    });

    const selected = selectedRetrievalEntry();
    const result = selected ? selected.result : null;
    const percent = scorePercent(result);
    selectedScore.textContent = percentLabel(percent);

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
    if (result && valueObserved(result.video_id) && !canOpenRetrievalResult(result)) {
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
    previewCopy.textContent = `${resultSceneLabel(result, selected.index)} | ${resultTimeLabel(result)} | ${observedSignals} signals observed | ${percentLabel(percent)} returned score${handoffNote}. ${resultSummary(result)}`;
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
    state.selectedVideoId = String(result.video_id);
    state.selectedSceneKey = String(result.scene_id);
    renderVideos();
    showLoading(qs("#timeline-panel"));
    showLoading(qs("#scene-detail-panel"));
    showLoading(qs("#scene-modality-panel"));
    showLoading(qs("#scene-schema-panel"));
    await refreshTimeline();
    state.selectedSceneKey = String(result.scene_id);
    renderVideos();
    renderTimeline();
    renderSceneInspector();
    window.location.hash = targetHash || "scene-inspector";
  }

  function safeVideoTitle(video) {
    return safeString(video.title || video.video_id || "Untitled video", "title");
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
      const button = document.createElement("button");
      button.type = "button";
      button.className = `video-button ${id === state.selectedVideoId ? "selected" : ""}`;
      button.addEventListener("click", async () => {
        state.selectedVideoId = id;
        state.selectedSceneKey = null;
        renderVideos();
        showLoading(qs("#timeline-panel"));
        showLoading(qs("#scene-detail-panel"));
        showLoading(qs("#scene-modality-panel"));
        showLoading(qs("#scene-schema-panel"));
        await refreshTimeline();
        renderTimeline();
        renderSceneInspector();
      });
      const label = document.createElement("span");
      appendText(label, "span", safeVideoTitle(video), "video-title");
      appendText(
        label,
        "span",
        `${safeString(video.total_scenes, "total_scenes")} scenes | ${safeString(video.processed_date, "processed_date")}`,
        "video-meta"
      );
      button.appendChild(label);
      button.appendChild(makeBadge(id === state.selectedVideoId ? "selected" : "open", id === state.selectedVideoId ? "ok" : ""));
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
    row.appendChild(makeBadge(observed ? "Observed" : "Not observed", observed ? "ok" : "unknown"));
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
    const sceneLabel = safeString(segment.scene_id || segment.segment_id || `Scene ${entry.index + 1}`, "scene_id");
    const startEnd = `${formatTime(segment.start)}-${formatTime(segment.end)}`;
    const speakerIds = Array.isArray(segment.speaker_ids) ? segment.speaker_ids : [];
    const visiblePeople = Array.isArray(segment.candidate_visible_people) ? segment.candidate_visible_people : [];
    const alignedMentions = Array.isArray(segment.speaker_aligned_mentions) ? segment.speaker_aligned_mentions : [];
    const memoryTags = stringList(segment.tags);
    const tagDetails = Array.isArray(segment.tag_details) ? segment.tag_details : [];
    const sceneEntities = Array.isArray(segment.scene_present_entities) ? segment.scene_present_entities : [];
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

    const facts = document.createElement("div");
    facts.className = "scene-fact-list";
    [
      ["Scene ID", segment.scene_id || segment.segment_id || "Not observed"],
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
      "Scene entities",
      sceneEntities.map(formatSceneEntity).filter(Boolean).slice(0, 6),
      "No scene-present entities exposed"
    );
    detail.appendChild(evidence);

    modality.appendChild(panelHeader("Modality coverage", "Evidence visible in selected timeline row", "read-only"));
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
    appendSceneSignal(modalityList, "Scene-present entities", sceneEntities.length > 0, `${sceneEntities.length} entity rows`);
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
      "sentiment_label",
      "audio_emotion",
      "audio_emotion_scores",
      "clap_meta",
      "scene_context_llm",
      "scene_context_epistemic",
      "scene_context_arbitration",
    ];
    const schemaList = document.createElement("div");
    schemaList.className = "schema-field-list";
    expectedFields.forEach((key) => {
      const status = fieldStatus(segment, key);
      const row = document.createElement("div");
      row.className = "schema-field-row";
      appendText(row, "span", key, "schema-field-key");
      row.appendChild(makeBadge(status.label, status.kind));
      schemaList.appendChild(row);
    });
    schema.appendChild(schemaList);

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
        renderTimeline();
        renderSceneInspector();
      });
      appendText(row, "div", `${formatTime(segment.start)}-${formatTime(segment.end)}`, "timeline-time");
      const body = document.createElement("div");
      body.className = "timeline-body";
      appendText(body, "strong", safeString(segment.scene_id || segment.index || "scene", "scene_id"));
      appendText(body, "span", segmentSummary(segment));
      row.appendChild(body);
      row.appendChild(makeBadge(selected ? "selected" : safeString(segment.content_state || "state", "content_state"), selected ? "ok" : ""));
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
    renderMemory();
    renderHealth();
    renderVideos();
    renderTimeline();
    renderSceneInspector();
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
