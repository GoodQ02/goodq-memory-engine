/* jshint esversion: 11 */
(function () {
  "use strict";

  // ── App State ────────────────────────────────────────────────────────────
  const state = {
    apiBase: "",

    // Phase data (loaded from JSON files on disk via API endpoints)
    faceClusters: [],      // from /api/identity/face-clusters
    speakerClusters: [],   // from /api/identity/speaker-clusters
    nameMentions: {},      // from /api/identity/name-mentions
    roster: [],            // from /api/identity/roster (family_roster.yaml)

    // Derived / working sets
    knownIdentityLabels: new Set(),  // display_names from roster
    activeFaceModal: null,           // cluster being labeled
    activeRosterIdx: -1,             // selected roster entry index
    nameSortDir: -1,                 // -1 = desc, +1 = asc
    faceFilter: "UNLABELED",
    epochAuthority: null,
  };

  // ── UI Cache ─────────────────────────────────────────────────────────────
  const ui = {
    status:       document.getElementById("system-status"),
    phaseIndicator: document.getElementById("phase-indicator"),
    epochAuthorityStatus: document.getElementById("epoch-authority-status"),

    // Tabs
    tabs: document.querySelectorAll(".tab-btn"),
    panels: document.querySelectorAll(".tab-panel"),

    // Badges
    badgeFaces:    document.getElementById("badge-faces"),
    badgeSpeakers: document.getElementById("badge-speakers"),
    badgeNames:    document.getElementById("badge-names"),
    badgeRoster:   document.getElementById("badge-roster"),

    // Header progress
    headerProgressText: document.getElementById("header-progress-text"),
    headerProgressFill: document.getElementById("header-progress-fill"),

    // Focus Panel
    focusPanel: document.getElementById("focus-panel"),
    focusMeta: document.getElementById("focus-meta"),
    focusNameInput: document.getElementById("focus-name-input"),
    focusOperatorNote: document.getElementById("focus-operator-note"),
    focusTypeaheadList: document.getElementById("focus-typeahead-list"),
    focusOperationFailure: document.getElementById("focus-operation-failure"),
    operationStatus: document.getElementById("operation-status"),
    focusGrid: document.getElementById("focus-grid"),
    focusPrev: document.getElementById("focus-prev"),
    focusNext: document.getElementById("focus-next"),
    focusClose: document.getElementById("focus-close"),

    facesFilterBtns: document.querySelectorAll(".filter-btn"),

    // Phase 1 — Faces
    epsInput:      document.getElementById("eps-input"),
    rerunFacesBtn: document.getElementById("rerun-faces-btn"),
    loadFacesBtn:  document.getElementById("load-faces-btn"),
    facesGrid:     document.getElementById("faces-grid"),
    facesNote:     document.getElementById("faces-note"),

    // Phase 2 — Speakers
    loadSpeakersBtn: document.getElementById("load-speakers-btn"),
    speakersList:    document.getElementById("speakers-list"),
    speakersNote:    document.getElementById("speakers-note"),

    // Phase 3 — Names
    nameSearch:      document.getElementById("name-search"),
    loadNamesBtn:    document.getElementById("load-names-btn"),
    namesTable:      document.getElementById("names-table"),
    namesTbody:      document.getElementById("names-tbody"),
    namesEmpty:      document.getElementById("names-empty"),
    namesNote:       document.getElementById("names-note"),
    sortCount:       document.getElementById("sort-count"),

    // Phase 4 — Roster
    loadRosterBtn:    document.getElementById("load-roster-btn"),
    validateRosterBtn:document.getElementById("validate-roster-btn"),
    exportRosterBtn:  document.getElementById("export-roster-btn"),
    rosterCount:      document.getElementById("roster-count"),
    rosterSidebarList:document.getElementById("roster-sidebar-list"),
    newIdentityInput: document.getElementById("new-identity-input"),
    addIdentityBtn:   document.getElementById("add-identity-btn"),
    rosterDetail:     document.getElementById("roster-detail"),


    // Validate Modal
    validateModal:      document.getElementById("validate-modal"),
    validateModalClose: document.getElementById("validate-modal-close"),
    validateModalOk:    document.getElementById("validate-modal-ok"),
    validateResult:     document.getElementById("validate-result"),

    // Toast
    toastContainer: document.getElementById("toast-container"),
  };

  // ── Toast ────────────────────────────────────────────────────────────────
  function toast(message, type = "success", duration = 4000) {
    const el = document.createElement("div");
    el.className = `toast ${type !== "success" ? type : ""}`.trim();
    el.textContent = message;
    ui.toastContainer.appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transition = "opacity 0.25s";
      setTimeout(() => el.remove(), 260);
    }, duration);
  }

  // ── API helper ───────────────────────────────────────────────────────────
  async function apiCall(endpoint, options = {}) {
    const url = `${state.apiBase}${endpoint}`;
    const resp = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    if (!resp.ok) {
      let msg = resp.statusText;
      let payload = null;
      try { payload = await resp.json(); msg = payload.detail || payload.message || msg; } catch (_) {}
      const err = new Error(msg);
      err.status = resp.status;
      err.payload = payload;
      throw err;
    }
    return resp.json();
  }

  function setOperationStatus(message, type = "info") {
    if (!ui.operationStatus) return;
    ui.operationStatus.textContent = message || "";
    ui.operationStatus.dataset.status = type;
    ui.operationStatus.hidden = !message;
  }

  function setOperationFailure(message) {
    if (message) setOperationStatus(message, "error");
    if (!ui.focusOperationFailure) return;
    ui.focusOperationFailure.textContent = message || "";
    ui.focusOperationFailure.hidden = !message;
  }

  async function confirmedIdentityRequest(endpoint, payload, confirmationCopy) {
    let confirmationToken = null;
    try {
      await apiCall(endpoint, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      throw new Error("Confirmation gate did not require a scoped token.");
    } catch (error) {
      confirmationToken = error.payload && error.payload.result && error.payload.result.confirmation_token;
      if (error.status !== 403 || !confirmationToken) throw error;
      if (!window.confirm(confirmationCopy)) {
        setOperationStatus("Operation cancelled; no change was made.");
        return null;
      }
      const result = await apiCall(endpoint, {
        method: "POST",
        body: JSON.stringify({ ...payload, confirmation_token: confirmationToken }),
      });
      setOperationStatus("Confirmed operation completed.", "success");
      return result;
    } finally {
      confirmationToken = null;
    }
  }

  // ── Tab Navigation ───────────────────────────────────────────────────────
  function activateTab(tabName) {
    ui.tabs.forEach(btn => {
      const isActive = btn.dataset.tab === tabName;
      btn.classList.toggle("active", isActive);
      btn.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    ui.panels.forEach(panel => {
      const isActive = panel.id === `panel-${tabName}`;
      panel.classList.toggle("active", isActive);
      panel.hidden = !isActive;
    });
    const labels = {
      faces:    "PHASE 1 — FACE CLUSTERS",
      speakers: "PHASE 2 — SPEAKER HYPOTHESES",
      names:    "PHASE 3 — NAME MENTIONS",
      roster:   "PHASE 4 — FAMILY ROSTER",
    };
    ui.phaseIndicator.textContent = labels[tabName] || "";
  }

  ui.tabs.forEach(btn => {
    btn.addEventListener("click", () => activateTab(btn.dataset.tab));
  });

  // ── System Status ────────────────────────────────────────────────────────
  async function checkStatus() {
    try {
      const status = await apiCall("/api/status");
      const authority = status.epoch_authority || {};
      state.epochAuthority = authority;
      if (!authority.ready) {
        const configured = authority.configured_epoch_id || "UNSET";
        const identity = authority.identity_epoch_id || "UNRESOLVED";
        ui.status.textContent = "Status: BLOCKED · EPOCH MISMATCH";
        ui.status.className = "header-status offline";
        ui.epochAuthorityStatus.hidden = false;
        ui.epochAuthorityStatus.textContent =
          `IDENTITY WORKBENCH BLOCKED — configured epoch ${configured}; identity epoch ${identity}. ${authority.message || ""}`;
        [
          ui.rerunFacesBtn, ui.loadFacesBtn, ui.loadSpeakersBtn, ui.loadNamesBtn,
          ui.loadRosterBtn, ui.validateRosterBtn, ui.exportRosterBtn,
          ui.newIdentityInput, ui.addIdentityBtn,
        ].forEach(control => { if (control) control.disabled = true; });
        return false;
      }
      ui.status.textContent = `Status: ONLINE · EPOCH ${authority.configured_epoch_id}`;
      ui.status.className = "header-status online";
      ui.epochAuthorityStatus.hidden = true;
      return true;
    } catch (_) {
      ui.status.textContent = "Status: OFFLINE";
      ui.status.className = "header-status offline";
      return false;
    }
  }

  // ── Phase 1 — Face Clusters ──────────────────────────────────────────────

  async function loadFaceClusters() {
    try {
      const data = await apiCall("/api/identity/face-clusters");
      state.faceClusters = data.clusters || [];
      ui.facesNote.textContent = `${state.faceClusters.length} clusters loaded.`;
      ui.badgeFaces.textContent = state.faceClusters.length;
      renderFaceGrid();
    } catch (e) {
      toast(`Failed to load face clusters: ${e.message}`, "error");
      ui.facesNote.textContent = `Error: ${e.message}`;
    }
  }

  async function rerunFaceClustering() {
    const eps = parseFloat(ui.epsInput.value);
    if (isNaN(eps) || eps <= 0 || eps >= 1) {
      toast("EPS must be between 0.05 and 0.95", "warn");
      return;
    }
    ui.rerunFacesBtn.textContent = "RE-CLUSTERING…";
    ui.rerunFacesBtn.disabled = true;
    try {
      const data = await confirmedIdentityRequest(
        "/api/identity/rebuild-face-clusters",
        { eps },
        `Re-cluster face evidence using eps=${eps}? This runs the identity process against the active epoch.`
      );
      if (!data) return;
      state.faceClusters = data.clusters || [];
      ui.badgeFaces.textContent = state.faceClusters.length;
      ui.facesNote.textContent = `${state.faceClusters.length} clusters (eps=${eps}).`;
      renderFaceGrid();
      toast(`Re-clustered: ${state.faceClusters.length} clusters with eps=${eps}`);
    } catch (e) {
      const message = `Re-clustering failed: ${e.message}`;
      setOperationFailure(message);
      toast(message, "error");
    } finally {
      ui.rerunFacesBtn.textContent = "RE-CLUSTER ↻";
      ui.rerunFacesBtn.disabled = false;
    }
  }

  function renderFaceGrid() {
    let clusters = [...state.faceClusters];

    // Calculate progress
    const total = clusters.length;
    const labeledCount = clusters.filter(c => c.label && c.label !== "null").length;
    if(ui.headerProgressText) ui.headerProgressText.textContent = `Labeled: ${labeledCount} / ${total}`;
    if(ui.headerProgressFill) ui.headerProgressFill.style.width = total ? `${(labeledCount / total) * 100}%` : '0%';

    // Filter
    if (state.faceFilter === "LABELED") {
      clusters = clusters.filter(c => c.label && c.label !== "null");
    } else if (state.faceFilter === "UNLABELED") {
      clusters = clusters.filter(c => !c.label || c.label === "null");
    }

    // Sort
    clusters.sort((a, b) => {
       const aLabeled = a.label && a.label !== "null";
       const bLabeled = b.label && b.label !== "null";
       if (aLabeled !== bLabeled) return aLabeled ? 1 : -1;
       return (b.face_count || 0) - (a.face_count || 0);
    });

    if (!clusters.length) {
      ui.facesGrid.innerHTML = `
        <div class="empty-card">
          <span class="pulse-icon">⬡</span>
          <p>No clusters found matching filter.</p>
        </div>`;
      return;
    }

    ui.facesGrid.innerHTML = "";
    clusters.forEach((cluster, loopIdx) => {
      // We need original idx for the API call
      const idx = state.faceClusters.indexOf(cluster);
      const labeled = cluster.label && cluster.label !== "null";
      const card = document.createElement("div");
      card.className = `cluster-card${labeled ? " labeled" : ""}`;
      card.dataset.idx = idx;
      // staggered animation
      card.style.animationDelay = `${(loopIdx % 20) * 50}ms`;

      const faces = faceUrls(cluster);
      const primaryEvidence = (cluster.representative_frames || [])[0] || {};
      const multiFaceWarning = (primaryEvidence.source_face_count || 0) > 1
        ? `<span class="multi-face-warning">MULTI-FACE SOURCE · TARGET DETECTION ${Number(primaryEvidence.target_face_index || 0) + 1} OF ${primaryEvidence.source_face_count}</span>`
        : "";
      const heroThumb = faces.length > 0 ? `<img class="hero-thumb" src="${escHtml(faces[0])}" alt="hero" loading="lazy">` : `<span class="hero-thumb-placeholder">👤</span>`;

      const stripThumbs = faces.slice(1).map(src =>
        `<img class="strip-thumb" src="${escHtml(src)}" alt="face" loading="lazy">`
      ).join("");

      card.innerHTML = `
        <div class="cluster-card-header">
          <span class="cluster-id">${escHtml(cluster.cluster_id)}</span>
          <span class="cluster-label-chip ${labeled ? "" : "unlabeled"}">
            ${labeled ? escHtml(cluster.label) : "UNLABELED"}
          </span>
        </div>
        <div class="cluster-hero-wrapper">
           ${heroThumb}
           ${multiFaceWarning}
        </div>
        <div class="cluster-thumbnails-strip">${stripThumbs}</div>
        <div class="cluster-card-footer">
          <span class="cluster-stat">Faces: <strong>${cluster.face_count ?? "—"}</strong></span>
          <div class="typeahead-wrapper inline">
            <input type="text" class="card-name-input" data-idx="${idx}" placeholder="Name..." value="${labeled ? escHtml(cluster.label) : ""}">
            <ul class="typeahead-list" hidden></ul>
          </div>
        </div>`;

      card.addEventListener("click", (e) => {
        if (e.target.closest(".typeahead-wrapper") || e.target.tagName === 'INPUT') return;
        openFocusPanel(idx);
      });
      setupTypeahead(card.querySelector(".card-name-input"), card.querySelector(".typeahead-list"), idx);

      ui.facesGrid.appendChild(card);
    });
  }

  // ── Focus Panel & Typeahead ─────────────────────────────────────────────

  let currentFocusIdx = -1;

  function faceUrls(cluster) {
    const representative = (cluster.representative_frames || [])
      .map(face => typeof face === "string" ? face : face.frame_url)
      .filter(Boolean);
    const samples = (cluster.sample_faces || [])
      .map(face => typeof face === "string" ? face : (face.frame_url || face.url))
      .filter(Boolean);
    return representative.length ? representative : samples;
  }

  function openFocusPanel(idx) {
    if (idx < 0 || idx >= state.faceClusters.length) return;
    currentFocusIdx = idx;
    const cluster = state.faceClusters[idx];

    if (ui.focusMeta) ui.focusMeta.textContent = `Cluster: ${cluster.cluster_id} | Faces: ${cluster.face_count || 0}`;

    const faces = faceUrls(cluster);
    if (ui.focusGrid) ui.focusGrid.innerHTML = faces.map(src => `<img src="${escHtml(src)}" alt="face" loading="lazy">`).join("");

    if (ui.focusNameInput) ui.focusNameInput.value = (cluster.label && cluster.label !== "null") ? cluster.label : "";
    if (ui.focusOperatorNote) ui.focusOperatorNote.value = cluster.operator_note || "";
    setOperationFailure("");
    if (ui.focusPanel) {
      if (!ui.focusPanel.open) ui.focusPanel.showModal();
    }
  }

  function closeFocusPanel() {
    if (ui.focusPanel && ui.focusPanel.open) ui.focusPanel.close();
  }

  if(ui.focusClose) ui.focusClose.addEventListener("click", closeFocusPanel);
  if(ui.focusPrev) ui.focusPrev.addEventListener("click", () => openFocusPanel(currentFocusIdx - 1));
  if(ui.focusNext) ui.focusNext.addEventListener("click", () => openFocusPanel(currentFocusIdx + 1));

  if(ui.focusPanel) ui.focusPanel.addEventListener("cancel", () => closeFocusPanel());

  // Setup typeahead for focus panel
  if (ui.focusNameInput && ui.focusTypeaheadList) {
    setupTypeahead(ui.focusNameInput, ui.focusTypeaheadList, () => currentFocusIdx);
  }

  function getCombinedNames() {
    const names = new Set(state.knownIdentityLabels);
    Object.keys(state.nameMentions).forEach(k => names.add(k));
    return Array.from(names).sort();
  }

  function setupTypeahead(inputEl, listEl, idxOrGetter) {
    let activeIndex = -1;

    inputEl.addEventListener("input", () => {
      const val = inputEl.value.trim().toLowerCase();
      activeIndex = -1;

      if (!val) {
        listEl.hidden = true;
        return;
      }

      const matches = getCombinedNames().filter(n => n.toLowerCase().includes(val));
      if (!matches.length) {
        listEl.hidden = true;
        return;
      }

      listEl.innerHTML = matches.map((m, i) => `<li data-index="${i}">${escHtml(m)}</li>`).join("");
      listEl.hidden = false;
    });

    inputEl.addEventListener("keydown", async (e) => {
      const items = listEl.querySelectorAll("li");
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (items.length > 0) {
          activeIndex = (activeIndex + 1) % items.length;
          updateActive(items);
        }
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (items.length > 0) {
          activeIndex = (activeIndex - 1 + items.length) % items.length;
          updateActive(items);
        }
      } else if (e.key === "Enter") {
        e.preventDefault();
        let selectedValue = inputEl.value.trim();
        if (activeIndex >= 0 && items[activeIndex]) {
          selectedValue = items[activeIndex].textContent;
          inputEl.value = selectedValue;
        }
        listEl.hidden = true;

        if (selectedValue) {
          const actualIdx = typeof idxOrGetter === "function" ? idxOrGetter() : idxOrGetter;
          await applyLabel(actualIdx, selectedValue);
        }
      } else if (e.key === "Escape") {
        listEl.hidden = true;
      }
    });

    listEl.addEventListener("click", async (e) => {
      if (e.target.tagName === "LI") {
        const val = e.target.textContent;
        inputEl.value = val;
        listEl.hidden = true;
        const actualIdx = typeof idxOrGetter === "function" ? idxOrGetter() : idxOrGetter;
        await applyLabel(actualIdx, val);
      }
    });

    document.addEventListener("click", (e) => {
      if (e.target !== inputEl && !listEl.contains(e.target)) {
        listEl.hidden = true;
      }
    });

    function updateActive(items) {
      items.forEach((item, i) => {
        item.classList.toggle("active", i === activeIndex);
        if (i === activeIndex) {
          item.scrollIntoView({ block: "nearest" });
        }
      });
    }
  }

  async function applyLabel(idx, label) {
    if (idx < 0 || idx >= state.faceClusters.length) return;
    const cluster = state.faceClusters[idx];
    const operatorNote = ui.focusPanel && ui.focusPanel.open
      ? ui.focusOperatorNote.value.trim()
      : window.prompt(`Why is "${label}" supported for ${cluster.cluster_id}?`, cluster.operator_note || "");
    if (operatorNote === null) return;

    try {
      const result = await confirmedIdentityRequest(
        "/api/identity/face-clusters/label",
        {
          cluster_id: cluster.cluster_id,
          label,
          operator_note: operatorNote,
        },
        `Apply label "${label}" to ${cluster.cluster_id}? The scoped confirmation is single-use.`
      );
      if (!result) return;
      cluster.label = label;
      cluster.operator_note = operatorNote;
      state.knownIdentityLabels.add(label);
      renderFaceGrid();
      updateRosterIdentityLabels();
      if (ui.focusPanel && ui.focusPanel.open) {
         closeFocusPanel();
      }
      toast(`Cluster ${cluster.cluster_id} labeled → ${label}`);
    } catch (e) {
      const message = `Label request failed: ${e.message}`;
      setOperationFailure(message);
      toast(message, "error");
    }
  }

  // Toolbar buttons — Phase 1
  if (ui.facesFilterBtns) {
    ui.facesFilterBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        ui.facesFilterBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.faceFilter = btn.dataset.filter;
        renderFaceGrid();
      });
    });
  }
  ui.loadFacesBtn.addEventListener("click", loadFaceClusters);
  ui.rerunFacesBtn.addEventListener("click", rerunFaceClustering);

  // ── Phase 2 — Speaker Clusters ───────────────────────────────────────────

  async function loadSpeakerClusters() {
    try {
      const data = await apiCall("/api/identity/speaker-clusters");
      state.speakerClusters = data.clusters || [];
      ui.speakersNote.textContent = `${state.speakerClusters.length} hypothesis clusters.`;
      ui.badgeSpeakers.textContent = state.speakerClusters.length;
      renderSpeakerList();
    } catch (e) {
      toast(`Failed to load speaker clusters: ${e.message}`, "error");
    }
  }

  function renderSpeakerList() {
    if (!state.speakerClusters.length) {
      ui.speakersList.innerHTML = `
        <div class="empty-card">
          <span class="pulse-icon">◈</span>
          <p>No speaker hypothesis data loaded.</p>
        </div>`;
      return;
    }

    ui.speakersList.innerHTML = "";
    state.speakerClusters.forEach((cluster, idx) => {
      const card = document.createElement("div");
      card.className = `speaker-card${cluster.confirmed ? " confirmed" : ""}`;

      const videos = (cluster.video_hashes || []).slice(0, 4)
        .map(v => v.slice(0, 8)).join(", ");

      card.innerHTML = `
        <div class="speaker-card-info">
          <div class="speaker-id">${escHtml(cluster.cluster_id)}</div>
          <div class="speaker-meta-row">
            <span class="speaker-stat">Segments: <strong>${cluster.segment_count ?? "—"}</strong></span>
            <span class="speaker-stat">Voiced: <strong>${fmtTime(cluster.voiced_seconds)}</strong></span>
          </div>
          <div class="speaker-videos">Videos: ${escHtml(videos)}${(cluster.video_hashes || []).length > 4 ? " …" : ""}</div>
          <span class="speaker-method-badge">${escHtml(cluster.method || "co_occurrence_heuristic")}</span>
        </div>
        <div class="speaker-card-actions">
          <label class="confirm-toggle" title="Manual confirmation required before this maps to an identity">
            <input type="checkbox" class="spk-confirm-cb" data-idx="${idx}" ${cluster.confirmed ? "checked" : ""} />
            <span class="confirm-label">CONFIRMED</span>
          </label>
          <input type="text" class="speaker-identity-input" data-idx="${idx}"
            placeholder="Assign identity…"
            value="${escHtml(cluster.identity_label || "")}"
            title="Assign person name after confirming" />
        </div>`;

      card.querySelector(".spk-confirm-cb").addEventListener("change", (e) => {
        const previous = { ...state.speakerClusters[idx] };
        state.speakerClusters[idx].confirmed = e.target.checked;
        card.classList.toggle("confirmed", e.target.checked);
        syncSpeakerAssignment(idx, previous);
      });

      card.querySelector(".speaker-identity-input").addEventListener("change", (e) => {
        const previous = { ...state.speakerClusters[idx] };
        state.speakerClusters[idx].identity_label = e.target.value.trim();
        syncSpeakerAssignment(idx, previous);
      });

      ui.speakersList.appendChild(card);
    });
  }

  async function syncSpeakerAssignment(idx, previous) {
    const cluster = state.speakerClusters[idx];
    try {
      const result = await confirmedIdentityRequest(
        "/api/identity/speaker-clusters/confirm",
        {
          cluster_id: cluster.cluster_id,
          confirmed: cluster.confirmed,
          identity_label: cluster.identity_label || null,
        },
        `Save speaker confirmation for ${cluster.cluster_id}? The scoped confirmation is single-use.`
      );
      if (!result) {
        state.speakerClusters[idx] = previous;
        renderSpeakerList();
        return;
      }
      toast(`Speaker ${cluster.cluster_id} saved.`);
    } catch (e) {
      state.speakerClusters[idx] = previous;
      renderSpeakerList();
      const message = `Speaker confirmation failed: ${e.message}`;
      setOperationFailure(message);
      toast(message, "error");
    }
  }

  ui.loadSpeakersBtn.addEventListener("click", loadSpeakerClusters);

  // ── Phase 3 — Name Mentions ──────────────────────────────────────────────

  async function loadNameMentions() {
    try {
      const data = await apiCall("/api/identity/name-mentions");
      state.nameMentions = data.mentions || {};
      const termCount = Object.keys(state.nameMentions).length;
      ui.namesNote.textContent = `${termCount} terms loaded.`;
      ui.badgeNames.textContent = termCount;
      renderNamesTable();
    } catch (e) {
      toast(`Failed to load name mentions: ${e.message}`, "error");
    }
  }

  function renderNamesTable() {
    const mentions = state.nameMentions;
    const termCount = Object.keys(mentions).length;

    if (!termCount) {
      ui.namesTable.hidden = true;
      ui.namesEmpty.hidden = false;
      return;
    }

    ui.namesEmpty.hidden = true;
    ui.namesTable.hidden = false;

    const filterText = ui.nameSearch.value.toLowerCase().trim();
    let entries = Object.entries(mentions)
      .filter(([term]) => !filterText || term.toLowerCase().includes(filterText))
      .sort(([, a], [, b]) => state.nameSortDir * ((b.count || 0) - (a.count || 0)));

    ui.namesTbody.innerHTML = "";
    entries.forEach(([term, data]) => {
      const tr = document.createElement("tr");
      const isCurated = data.is_curated;
      const videoCount = data.videos ? data.videos.length : 0;
      const sceneCount = data.scenes ? data.scenes.length : 0;

      // Check if this term is already in the roster
      const inRoster = Array.from(state.knownIdentityLabels).some(
        name => name.toLowerCase() === term.toLowerCase()
      );

      tr.innerHTML = `
        <td>${escHtml(term)}</td>
        <td><span class="type-chip ${isCurated ? "curated" : "candidate"}">
          ${isCurated ? "CURATED" : "CANDIDATE"}
        </span></td>
        <td class="num-col">${data.count ?? 0}</td>
        <td class="num-col">${sceneCount}</td>
        <td class="num-col">${videoCount}</td>
        <td>
          <button class="name-roster-btn ${inRoster ? "added" : ""}" data-term="${escHtml(term)}"
            ${inRoster ? 'title="Already in roster"' : 'title="Add as identity to roster"'}>
            ${inRoster ? "IN ROSTER ✓" : "ADD TO ROSTER +"}
          </button>
        </td>`;

      tr.querySelector(".name-roster-btn").addEventListener("click", (e) => {
        if (!inRoster) addNameToRoster(term, e.currentTarget);
      });

      ui.namesTbody.appendChild(tr);
    });
  }

  function addNameToRoster(term, btn) {
    // Add as a new pending identity in the roster
    const exists = state.roster.some(
      id => id.display_name.toLowerCase() === term.toLowerCase()
    );
    if (!exists) {
      state.roster.push({
        id: term.toLowerCase().replace(/\s+/g, "_"),
        display_name: term,
        aliases: [],
        face_cluster_ids: [],
        speaker_cluster_ids: [],
        name_mention_keys: [term],
        role: "",
        notes: "",
        confirmed: false,
      });
      state.knownIdentityLabels.add(term);
      renderRosterSidebar();
      renderNamesTable();
      toast(`"${term}" added to roster — complete their profile in Phase 4`);
    }
    btn.textContent = "IN ROSTER ✓";
    btn.classList.add("added");
  }

  ui.loadNamesBtn.addEventListener("click", loadNameMentions);
  ui.nameSearch.addEventListener("input", renderNamesTable);
  ui.sortCount.addEventListener("click", () => {
    state.nameSortDir *= -1;
    ui.sortCount.textContent = `MENTIONS ${state.nameSortDir < 0 ? "↓" : "↑"}`;
    renderNamesTable();
  });

  // ── Phase 4 — Family Roster ──────────────────────────────────────────────

  async function loadRoster() {
    try {
      const data = await apiCall("/api/identity/roster");
      state.roster = data.identities || [];
      state.knownIdentityLabels = new Set(state.roster.map(id => id.display_name));
      ui.badgeRoster.textContent = state.roster.length;
      renderRosterSidebar();
      toast(`Roster loaded: ${state.roster.length} identities`);
    } catch (e) {
      toast(`Failed to load roster: ${e.message}`, "error");
    }
  }

  function renderRosterSidebar() {
    ui.rosterCount.textContent = state.roster.length;
    if (!state.roster.length) {
      ui.rosterSidebarList.innerHTML = `<div class="empty-state-small">No identities yet.</div>`;
      return;
    }
    ui.rosterSidebarList.innerHTML = "";
    state.roster.forEach((identity, idx) => {
      const item = document.createElement("div");
      item.className = `roster-identity-item${state.activeRosterIdx === idx ? " selected" : ""}`;
      item.innerHTML = `
        <div>
          <div class="roster-identity-name">${escHtml(identity.display_name)}</div>
          <div class="roster-identity-role">${escHtml(identity.role || "—")}</div>
        </div>
        <span class="count-badge" title="Face clusters">${(identity.face_cluster_ids || []).length}F</span>`;
      item.addEventListener("click", () => selectRosterIdentity(idx));
      ui.rosterSidebarList.appendChild(item);
    });
  }

  function selectRosterIdentity(idx) {
    state.activeRosterIdx = idx;
    renderRosterSidebar(); // re-highlight selected item
    renderRosterDetail(idx);
  }

  function renderRosterDetail(idx) {
    const identity = state.roster[idx];
    if (!identity) {
      ui.rosterDetail.innerHTML = `<div class="roster-no-selection"><span class="pulse-icon">◼</span><p>SELECT AN IDENTITY</p></div>`;
      return;
    }

    // Build face cluster chip options
    const faceOptions = state.faceClusters
      .filter(c => {
        const ownerIdx = faceClusterOwner(c.cluster_id);
        return !(identity.face_cluster_ids || []).includes(c.cluster_id)
          && (ownerIdx === -1 || ownerIdx === idx);
      })
      .map(c => `<option value="${escHtml(c.cluster_id)}">${escHtml(c.cluster_id)}${c.label ? " — " + c.label : ""}</option>`)
      .join("");

    // Build speaker cluster chip options
    const speakerOptions = state.speakerClusters
      .filter(c => !(identity.speaker_cluster_ids || []).includes(c.cluster_id))
      .map(c => `<option value="${escHtml(c.cluster_id)}">${escHtml(c.cluster_id)}${c.confirmed ? " ✓" : " (unconfirmed)"}</option>`)
      .join("");

    const faceChips = (identity.face_cluster_ids || []).map(cid =>
      `<span class="cluster-chip"><span>${escHtml(cid)}</span>
        <button class="remove-chip-btn" data-type="face" data-cid="${escHtml(cid)}" aria-label="Remove">×</button>
      </span>`).join("");

    const speakerChips = (identity.speaker_cluster_ids || []).map(cid => {
      const confirmed = state.speakerClusters.find(c => c.cluster_id === cid)?.confirmed;
      return `<span class="cluster-chip voice-chip${confirmed ? "" : ' title="⚠ Not yet confirmed"'}">
        <span>${escHtml(cid)}${confirmed ? "" : " ⚠"}</span>
        <button class="remove-chip-btn" data-type="speaker" data-cid="${escHtml(cid)}" aria-label="Remove">×</button>
      </span>`;
    }).join("");

    const nameChips = (identity.name_mention_keys || []).map(k =>
      `<span class="cluster-chip"><span>${escHtml(k)}</span>
        <button class="remove-chip-btn" data-type="name" data-cid="${escHtml(k)}" aria-label="Remove">×</button>
      </span>`).join("");

    ui.rosterDetail.innerHTML = `
      <div class="identity-form" id="identity-form-${idx}">
        <div class="form-section">
          <div class="form-section-title">IDENTITY — ${escHtml(identity.display_name)}</div>
          <div class="form-field">
            <label class="form-label" for="field-display-name-${idx}">DISPLAY NAME</label>
            <input class="form-input" id="field-display-name-${idx}" type="text"
              value="${escHtml(identity.display_name)}" data-field="display_name" />
          </div>
          <div class="form-field">
            <label class="form-label" for="field-role-${idx}">FAMILY ROLE (optional)</label>
            <input class="form-input" id="field-role-${idx}" type="text"
              value="${escHtml(identity.role || "")}" data-field="role"
              placeholder="e.g. Father, Daughter, Uncle…" />
          </div>
          <div class="form-field">
            <label class="form-label" for="field-aliases-${idx}">ALIASES (comma-separated)</label>
            <input class="form-input" id="field-aliases-${idx}" type="text"
              value="${escHtml((identity.aliases || []).join(", "))}" data-field="aliases"
              placeholder="e.g. Dad, Daddy, Pop…" />
          </div>
          <div class="form-field">
            <label class="form-label" for="field-notes-${idx}">NOTES</label>
            <input class="form-input" id="field-notes-${idx}" type="text"
              value="${escHtml(identity.notes || "")}" data-field="notes" />
          </div>
        </div>

        <div class="form-section">
          <div class="form-section-title">FACE CLUSTERS (candidate — visual evidence)</div>
          <div class="cluster-chips" id="face-chips-${idx}">${faceChips || "<span style='color:var(--text-faint);font-size:11px'>None assigned</span>"}</div>
          <div class="form-field" style="margin-top:8px">
            <label class="form-label">ADD FACE CLUSTER</label>
            <div style="display:flex;gap:6px">
              <select class="cluster-select" id="face-select-${idx}">
                <option value="">-- select --</option>${faceOptions}
              </select>
              <button class="toolbar-btn" id="add-face-cluster-${idx}">ADD</button>
            </div>
          </div>
        </div>

        <div class="form-section">
          <div class="form-section-title">SPEAKER CLUSTERS ⚠ HYPOTHESIS — CONFIRM BEFORE PROMOTING</div>
          <div class="cluster-chips" id="spk-chips-${idx}">${speakerChips || "<span style='color:var(--text-faint);font-size:11px'>None assigned</span>"}</div>
          <div class="form-field" style="margin-top:8px">
            <label class="form-label">ADD SPEAKER CLUSTER</label>
            <div style="display:flex;gap:6px">
              <select class="cluster-select" id="spk-select-${idx}" style="border-color:var(--voice-color);color:var(--voice-color)">
                <option value="">-- select --</option>${speakerOptions}
              </select>
              <button class="toolbar-btn" id="add-spk-cluster-${idx}" style="border-color:var(--voice-color);color:var(--voice-color)">ADD</button>
            </div>
          </div>
        </div>

        <div class="form-section">
          <div class="form-section-title">NAME MENTION KEYS (transcript search terms)</div>
          <div class="cluster-chips" id="name-chips-${idx}">${nameChips || "<span style='color:var(--text-faint);font-size:11px'>None assigned</span>"}</div>
          <div class="form-field" style="margin-top:8px">
            <div style="display:flex;gap:6px">
              <input type="text" class="mini-input wide" id="name-key-input-${idx}" placeholder="Add mention key (e.g. Dad)…" />
              <button class="toolbar-btn" id="add-name-key-${idx}">ADD</button>
            </div>
          </div>
        </div>

        <div class="form-actions">
          <button class="toolbar-btn" id="save-identity-${idx}">SAVE CHANGES ▶</button>
          <button class="toolbar-btn danger" id="delete-identity-${idx}" style="border-color:var(--error-color);color:var(--error-color)">REMOVE IDENTITY</button>
        </div>
      </div>`;

    // Wire form inputs
    document.querySelectorAll(`#identity-form-${idx} .form-input`).forEach(input => {
      input.addEventListener("change", () => {
        const field = input.dataset.field;
        const value = input.value;
        if (field === "aliases") {
          state.roster[idx].aliases = value.split(",").map(s => s.trim()).filter(Boolean);
        } else {
          state.roster[idx][field] = value;
        }
      });
    });

    // Add face cluster
    document.getElementById(`add-face-cluster-${idx}`).addEventListener("click", () => {
      const sel = document.getElementById(`face-select-${idx}`);
      if (sel.value) {
        if (!state.roster[idx].face_cluster_ids) state.roster[idx].face_cluster_ids = [];
        if (!state.roster[idx].face_cluster_ids.includes(sel.value)) {
          state.roster[idx].face_cluster_ids.push(sel.value);
          renderRosterDetail(idx);
        }
      }
    });

    // Add speaker cluster
    document.getElementById(`add-spk-cluster-${idx}`).addEventListener("click", () => {
      const sel = document.getElementById(`spk-select-${idx}`);
      if (sel.value) {
        const cluster = state.speakerClusters.find(c => c.cluster_id === sel.value);
        if (cluster && !cluster.confirmed) {
          toast(`⚠ Speaker cluster ${sel.value} is NOT confirmed. Confirm it in Phase 2 first.`, "warn");
          return;
        }
        if (!state.roster[idx].speaker_cluster_ids) state.roster[idx].speaker_cluster_ids = [];
        if (!state.roster[idx].speaker_cluster_ids.includes(sel.value)) {
          state.roster[idx].speaker_cluster_ids.push(sel.value);
          renderRosterDetail(idx);
        }
      }
    });

    // Add name key
    document.getElementById(`add-name-key-${idx}`).addEventListener("click", () => {
      const input = document.getElementById(`name-key-input-${idx}`);
      const key = input.value.trim();
      if (key) {
        if (!state.roster[idx].name_mention_keys) state.roster[idx].name_mention_keys = [];
        if (!state.roster[idx].name_mention_keys.includes(key)) {
          state.roster[idx].name_mention_keys.push(key);
          renderRosterDetail(idx);
          input.value = "";
        }
      }
    });

    // Remove chips
    ui.rosterDetail.querySelectorAll(".remove-chip-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const type = btn.dataset.type;
        const cid  = btn.dataset.cid;
        if (type === "face") {
          state.roster[idx].face_cluster_ids = (state.roster[idx].face_cluster_ids || []).filter(c => c !== cid);
        } else if (type === "speaker") {
          state.roster[idx].speaker_cluster_ids = (state.roster[idx].speaker_cluster_ids || []).filter(c => c !== cid);
        } else if (type === "name") {
          state.roster[idx].name_mention_keys = (state.roster[idx].name_mention_keys || []).filter(k => k !== cid);
        }
        renderRosterDetail(idx);
      });
    });

    // Save
    document.getElementById(`save-identity-${idx}`).addEventListener("click", () => saveIdentity(idx));

    // Delete
    document.getElementById(`delete-identity-${idx}`).addEventListener("click", () => {
      if (confirm(`Remove "${state.roster[idx].display_name}" from the roster?`)) {
        state.roster.splice(idx, 1);
        state.activeRosterIdx = -1;
        state.knownIdentityLabels = new Set(state.roster.map(id => id.display_name));
        renderRosterSidebar();
        ui.rosterDetail.innerHTML = `<div class="roster-no-selection"><span class="pulse-icon">◼</span><p>IDENTITY REMOVED</p></div>`;
      }
    });
  }

  function faceClusterOwner(clusterId) {
    return state.roster.findIndex(identity =>
      (identity.face_cluster_ids || []).includes(clusterId)
    );
  }

  async function saveIdentity(idx) {
    const identity = state.roster[idx];
    try {
      const result = await confirmedIdentityRequest(
        "/api/identity/roster/save",
        { identity },
        `Save roster identity "${identity.display_name}"? The scoped confirmation is single-use.`
      );
      if (!result) return;
      state.knownIdentityLabels = new Set(state.roster.map(id => id.display_name));
      renderRosterSidebar();
      toast(`Saved: ${identity.display_name}`);
    } catch (e) {
      const message = `Save failed: ${e.message}`;
      setOperationFailure(message);
      toast(message, "error");
    }
  }

  function addIdentity() {
    const name = ui.newIdentityInput.value.trim();
    if (!name) return;
    const id = name.toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
    if (state.roster.some(i => i.display_name.toLowerCase() === name.toLowerCase())) {
      toast(`"${name}" already in roster`, "warn");
      return;
    }
    state.roster.push({
      id,
      display_name: name,
      aliases: [],
      face_cluster_ids: [],
      speaker_cluster_ids: [],
      name_mention_keys: [],
      role: "",
      notes: "",
      confirmed: false,
    });
    state.knownIdentityLabels.add(name);
    ui.badgeRoster.textContent = state.roster.length;
    renderRosterSidebar();
    selectRosterIdentity(state.roster.length - 1);
    ui.newIdentityInput.value = "";
    toast(`"${name}" added to roster`);
  }

  function updateRosterIdentityLabels() {
    // Called when face clusters are labeled — keep datalist current
    state.faceClusters.forEach(c => {
      if (c.label) state.knownIdentityLabels.add(c.label);
    });
  }

  // Roster event wires
  ui.loadRosterBtn.addEventListener("click", loadRoster);
  ui.addIdentityBtn.addEventListener("click", addIdentity);
  ui.newIdentityInput.addEventListener("keydown", e => { if (e.key === "Enter") addIdentity(); });

  // ── Validate Roster ──────────────────────────────────────────────────────
  async function validateRoster() {
    ui.validateRosterBtn.textContent = "VALIDATING…";
    ui.validateRosterBtn.disabled = true;
    try {
      const data = await confirmedIdentityRequest(
        "/api/identity/roster/validate",
        {},
        "Run roster validation against the active identity data? This runs the identity process."
      );
      if (!data) return;
      renderValidationResult(data);
      ui.validateModal.hidden = false;
    } catch (e) {
      const message = `Validation request failed: ${e.message}`;
      setOperationFailure(message);
      toast(message, "error");
    } finally {
      ui.validateRosterBtn.textContent = "VALIDATE ✓";
      ui.validateRosterBtn.disabled = false;
    }
  }

  function renderValidationResult(data) {
    const passed = data.passed || [];
    const warnings = data.warnings || [];
    const errors = data.errors || [];

    let html = "";
    if (errors.length === 0 && warnings.length === 0) {
      html += `<span class="pass">✓ All checks passed — roster ready for Phase 5A dry-run.\n\n</span>`;
    } else if (errors.length > 0) {
      html += `<span class="fail">✗ VALIDATION FAILED — fix errors before promotion.\n\n</span>`;
    } else {
      html += `<span class="warn">⚠ Warnings present — review before promotion.\n\n</span>`;
    }
    passed.forEach(m => { html += `<span class="pass">  ✓ ${escHtml(m)}\n</span>`; });
    warnings.forEach(m => { html += `<span class="warn">  ⚠ ${escHtml(m)}\n</span>`; });
    errors.forEach(m => {
      const message = typeof m === "string" ? m : m.message;
      html += `<span class="fail">  ✗ ${escHtml(message || "Validation failed.")}\n</span>`;
    });

    ui.validateResult.innerHTML = html;
  }

  ui.validateRosterBtn.addEventListener("click", validateRoster);
  ui.validateModalClose.addEventListener("click", () => { ui.validateModal.hidden = true; });
  ui.validateModalOk.addEventListener("click", () => { ui.validateModal.hidden = true; });
  ui.validateModal.addEventListener("click", e => { if (e.target === ui.validateModal) ui.validateModal.hidden = true; });

  // ── Export YAML ───────────────────────────────────────────────────────────
  async function exportRoster() {
    try {
      const data = await confirmedIdentityRequest(
        "/api/identity/roster/export",
        { identities: state.roster },
        `Export ${state.roster.length} roster identities to the active identity data path? The scoped confirmation is single-use.`
      );
      if (!data) return;
      toast(`Roster exported: ${data.count} identities.`);
    } catch (e) {
      const message = `Roster export failed: ${e.message}`;
      setOperationFailure(message);
      toast(message, "error");
    }
  }

  function rosterToYaml(roster) {
    // Minimal YAML serializer (no dependency needed for this structure)
    let out = "identities:\n";
    roster.forEach(id => {
      out += `  - id: ${yamlStr(id.id)}\n`;
      out += `    display_name: ${yamlStr(id.display_name)}\n`;
      out += `    role: ${yamlStr(id.role || "")}\n`;
      out += `    notes: ${yamlStr(id.notes || "")}\n`;
      out += `    aliases: [${(id.aliases || []).map(yamlStr).join(", ")}]\n`;
      out += `    face_cluster_ids: [${(id.face_cluster_ids || []).map(yamlStr).join(", ")}]\n`;
      out += `    speaker_cluster_ids: [${(id.speaker_cluster_ids || []).map(yamlStr).join(", ")}]\n`;
      out += `    name_mention_keys: [${(id.name_mention_keys || []).map(yamlStr).join(", ")}]\n`;
    });
    return out;
  }

  function yamlStr(s) {
    if (!s) return "\"\"";
    if (/[:#\[\]{},\n]/.test(s)) return `"${s.replace(/"/g, '\\"')}"`;
    return s;
  }

  ui.exportRosterBtn.addEventListener("click", exportRoster);

  // ── Utilities ────────────────────────────────────────────────────────────
  function escHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmtTime(seconds) {
    if (!seconds) return "0s";
    if (seconds < 60) return seconds.toFixed(1) + "s";
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m ${s}s`;
  }

  // ── Bootstrap ─────────────────────────────────────────────────────────────
  async function init() {
    if (!await checkStatus()) return;
    // Auto-load all data sources on startup (silently ignore failures)
    await Promise.allSettled([
      loadFaceClusters(),
      loadSpeakerClusters(),
      loadNameMentions(),
      loadRoster(),
    ]);
  }

  init();

})();
