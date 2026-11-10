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
    actions: {},
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
    voiceReviewNote: document.getElementById("voice-review-note"),
    voiceReviewLink: document.getElementById("voice-review-link"),

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
    const path = `${state.apiBase}${endpoint}`;
    const url = window.GoodQLibrary?.url(path) || path;
    const resp = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    window.GoodQLibrary?.observeResponse?.(resp, endpoint);
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
    if (typeof document.querySelectorAll === "function") {
      document.querySelectorAll(".ribbon-btn[data-ribbon-tab]").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-ribbon-tab") === tabName);
      });
    }
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
      appearances: "SCENE CONNECTIONS",
      matches:  "MATCH REVIEW · NOTHING APPLIED",
    };
    ui.phaseIndicator.textContent = labels[tabName] || "";
    if (tabName === "appearances" && !savedPeopleData && !savedPeopleLoading) loadSavedPeople();
  }

  ui.tabs.forEach(btn => {
    btn.addEventListener("click", () => activateTab(btn.dataset.tab));
  });
  if (typeof document.querySelectorAll === "function") {
    document.querySelectorAll(".ribbon-btn[data-ribbon-tab]").forEach(btn => {
      btn.addEventListener("click", e => {
        const tab = btn.getAttribute("data-ribbon-tab");
        if (!tab) return;
        e.preventDefault();
        if (tab === "matches") document.getElementById("tab-matches")?.click();
        else activateTab(tab);
      });
    });
  }

  // ── System Status ────────────────────────────────────────────────────────
  function actionReady(action) {
    return state.actions[action]?.ready === true;
  }

  function applyReadiness() {
    const controls = {
      face_prepare: [ui.rerunFacesBtn, ui.epsInput],
      face_review: [ui.loadFacesBtn], speaker_review: [ui.loadSpeakersBtn],
      name_review: [ui.loadNamesBtn],
      family_facts: [ui.validateRosterBtn, ui.exportRosterBtn, ui.newIdentityInput, ui.addIdentityBtn],
    };
    Object.entries(controls).forEach(([action, items]) => items.forEach(control => {
      if (control) control.disabled = !actionReady(action);
    }));
    const note = (action) => state.actions[action]?.message || "Readiness unavailable.";
    ui.facesNote.textContent = actionReady("face_review") ? "Face candidates available."
      : actionReady("face_prepare") ? `${state.actions.face_prepare.count} saved face observations. Prepare candidates to review them.`
      : note("face_review");
    ui.speakersNote.textContent = actionReady("speaker_review") ? "Hypothesis candidates available." : note("speaker_review");
    ui.namesNote.textContent = actionReady("name_review") ? "Name mentions available." : note("name_review");
    ui.voiceReviewNote.textContent = actionReady("voice_review")
      ? `${state.actions.voice_review.count} saved voice patterns available. Patterns are anonymous evidence, not confirmed people.`
      : note("voice_review");
    ui.voiceReviewLink.hidden = !actionReady("voice_review");
  }

  async function checkStatus() {
    try {
      const readiness = await apiCall("/api/identity/readiness");
      state.epochAuthority = readiness;
      state.actions = readiness.actions || {};
      applyReadiness();
      ui.status.textContent = `Status: ONLINE · EPOCH ${readiness.configured_epoch_id || "UNSET"}`;
      ui.status.className = "header-status online";
      ui.epochAuthorityStatus.hidden = false;
      ui.epochAuthorityStatus.textContent = actionReady("family_facts")
        ? "Family facts are editable. Face, voice and name evidence have separate availability. Assignments require matching evidence and confirmation."
        : state.actions.family_facts?.message || "Family-fact editing is unavailable.";
      return true;
    } catch (_) {
      state.actions = {};
      applyReadiness();
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
      await checkStatus();
    } catch (e) {
      const message = `Re-clustering failed: ${e.message}`;
      setOperationFailure(message);
      toast(message, "error");
    } finally {
      ui.rerunFacesBtn.textContent = "PREPARE FACE CANDIDATES";
      ui.rerunFacesBtn.disabled = !actionReady("face_prepare");
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
      const allLabeledMsg = (state.faceFilter === "UNLABELED" && total > 0 && labeledCount === total)
        ? `All ${total} face clusters are labeled (${labeledCount} / ${total}). Select ALL or LABELED above to inspect or edit them.`
        : "No clusters found matching filter.";
      ui.facesGrid.innerHTML = `
        <div class="empty-card">
          <span class="pulse-icon">⬡</span>
          <p>${allLabeledMsg}</p>
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

      const members = cluster.members || [];
      const primaryEvidence = members[0] || (cluster.representative_frames || [])[0] || {};
      const multiFaceWarning = (primaryEvidence.source_face_count || 0) > 1
        ? `<span class="multi-face-warning">MULTI-FACE SOURCE · TARGET DETECTION ${Number(primaryEvidence.target_face_index || 0) + 1} OF ${primaryEvidence.source_face_count}</span>`
        : "";
      const heroThumb = targetFaceHtml(primaryEvidence);

      const stripThumbs = members.slice(1, 5).map(member =>
        `<div class="member-preview">${targetFaceHtml(member)}</div>`).join("");

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
        <button class="toolbar-btn review-members" type="button">VIEW ALL ${cluster.face_count || 0} SAVED MEMBERS</button>
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

  function targetFaceHtml(member, source = false) {
    const box = member.crop_bbox;
    const width = member.image_width, height = member.image_height;
    if (member.evidence_status !== "available" || !member.frame_url ||
        !Array.isArray(box) || box.length !== 4 ||
        ![...box, width, height].every(Number.isFinite) ||
        width <= 0 || height <= 0 || box[2] <= box[0] || box[3] <= box[1]) {
      return '<span class="face-unavailable">Exact target unavailable</span>';
    }
    const [x, y, right, bottom] = box;
    const cropWidth = right - x, cropHeight = bottom - y;
    const viewBox = source ? `0 0 ${width} ${height}` : `${x} ${y} ${cropWidth} ${cropHeight}`;
    const description = `${source ? "Source frame with target box" : "Exact target face"} ${member.target_face_id}`;
    return `<svg class="${source ? "member-source" : "target-face"}" viewBox="${viewBox}" role="img" aria-label="${escHtml(description)}">
      <image href="${escHtml(member.frame_url)}" width="${width}" height="${height}" />
      ${source ? `<rect x="${x}" y="${y}" width="${cropWidth}" height="${cropHeight}" fill="none" stroke="#00e5ff" stroke-width="3" vector-effect="non-scaling-stroke" />` : ""}
    </svg>`;
  }

  function memberTime(timestamp) {
    if (!Number.isFinite(timestamp)) return "Time unavailable";
    const seconds = Math.floor(timestamp);
    return `${Math.floor(seconds / 3600)}:${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  }

  function faceMemberHtml(member, index) {
    const detection = Number.isInteger(member.target_face_index)
      ? ` · Detection ${member.target_face_index + 1} of ${member.source_face_count}` : "";
    const unavailable = member.evidence_status !== "available"
      ? `<p class="face-unavailable">${member.reason === "exact_source_unavailable" ? "Exact source was not recorded for this member." : "Saved evidence could not be verified."}</p>` : "";
    return `<article class="face-member" data-face-id="${escHtml(member.target_face_id)}">
      <h3>Member ${index + 1} · ${memberTime(member.timestamp)}</h3>
      <p class="member-reference">${escHtml(member.target_face_id)}${escHtml(detection)}</p>
      <div class="member-target">${targetFaceHtml(member)}</div>
      <p class="member-view-label">EXACT TARGET · SAVED DETECTION</p>
      ${member.evidence_status === "available" ? targetFaceHtml(member, true) + '<p class="member-view-label">SOURCE FRAME · TARGET OUTLINED</p>' : unavailable}
    </article>`;
  }

  function openFocusPanel(idx) {
    if (idx < 0 || idx >= state.faceClusters.length) return;
    currentFocusIdx = idx;
    const cluster = state.faceClusters[idx];

    const members = cluster.members || [];
    if (ui.focusMeta) ui.focusMeta.textContent = `${cluster.cluster_id} · ${members.length} saved members · ${cluster.members_available || 0} available`;

    if (ui.focusGrid) ui.focusGrid.innerHTML = members.length
      ? members.map(faceMemberHtml).join("")
      : '<p>Exact member evidence is unavailable. Historical source frames below are context only.</p>' +
        faceUrls(cluster).map(src => `<img src="${escHtml(src)}" alt="Historical source frame, target unverified" loading="lazy">`).join("");

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

  function rosterRelationshipsHtml(identity, roster) {
    const rows = (identity.relationships || []).filter(r => r && typeof r === "object");
    const body = rows.map(relation => {
      const target = roster.find(person => person.id === relation.target_id);
      const evidence = relation.evidence || {};
      return `<details class="form-section"><summary>${escHtml(relation.type)} → ${escHtml(target?.display_name || relation.target_id)}</summary>
        <p>Recorded review status: ${escHtml(relation.review_status || "not_recorded")}</p>
        <p>Evidence source: ${escHtml(evidence.kind || "not_recorded")} · ${escHtml(evidence.source_id || "not_recorded")}</p>
        <p>${escHtml(evidence.date || "")}</p><blockquote>${escHtml(evidence.statement || "Supporting statement not recorded.")}</blockquote>
        <p>This roster statement does not identify a face or voice in footage.</p></details>`;
    }).join("");
    return `<div class="form-section"><div class="form-section-title">CURATED RELATIONSHIPS — OUTGOING</div>
      ${body || "<p>No directed relationship recorded.</p>"}</div>`;
  }

  function renderRosterDetail(idx) {
    const identity = state.roster[idx];
    if (!identity) {
      ui.rosterDetail.innerHTML = `<div class="roster-no-selection"><span class="pulse-icon">◼</span><p>SELECT AN IDENTITY</p></div>`;
      return;
    }

    if (!actionReady("family_facts")) {
      ui.rosterDetail.innerHTML = `<div class="form-section">
        <div class="form-section-title">${escHtml(identity.display_name)} — READ ONLY</div>
        <p>Role: ${escHtml(identity.role || "not recorded")}</p>
        <p>Aliases: ${escHtml((identity.aliases || []).join(", ") || "none recorded")}</p>
        <p>${escHtml(identity.notes || "")}</p>
        <p>Face assignments: ${(identity.face_cluster_ids || []).length}. Voice assignments: ${(identity.speaker_cluster_ids || []).length}.</p>
        <p>${escHtml(state.actions.family_facts?.message || "Readiness unavailable.")}</p>
        </div>${rosterRelationshipsHtml(identity, state.roster)}`;
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
          ${actionReady("face_review") ? "" : `<p>${escHtml(state.actions.face_review?.message || "Face evidence unavailable.")}</p>`}
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
          ${actionReady("speaker_review") ? "" : `<p>${escHtml(state.actions.speaker_review?.message || "Speaker hypotheses unavailable.")} Saved voice patterns can be reviewed from the Speaker Hypotheses tab.</p>`}
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

    ui.rosterDetail.insertAdjacentHTML("beforeend", rosterRelationshipsHtml(identity, state.roster));

    // Family facts remain editable while each evidence binding stays scoped.
    const bindings = {
      face_review: [`face-select-${idx}`, `add-face-cluster-${idx}`],
      speaker_review: [`spk-select-${idx}`, `add-spk-cluster-${idx}`],
      name_review: [`name-key-input-${idx}`, `add-name-key-${idx}`],
    };
    Object.entries(bindings).forEach(([action, ids]) => ids.forEach(id => {
      document.getElementById(id).disabled = !actionReady(action);
    }));
    ui.rosterDetail.querySelectorAll(".remove-chip-btn").forEach(btn => {
      btn.disabled = !actionReady({face: "face_review", speaker: "speaker_review", name: "name_review"}[btn.dataset.type]);
    });

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

  // ── Shared Theme Toggle ──────────────────────────────────────────────────
  (function initThemeToggle() {
    const btn = document.getElementById("toggle-theme");
    const storage = typeof localStorage !== "undefined" ? localStorage : null;
    if (!btn || !storage || !document.body || !document.body.classList) return;
    const themes = ["night", "day", "auto"];
    let current = "night";
    try { current = storage.getItem("goodq-theme") || "night"; } catch (_) {}
    function apply(mode) {
      current = mode;
      try { storage.setItem("goodq-theme", mode); } catch (_) {}
      const prefersDark = typeof window !== "undefined" && typeof window.matchMedia === "function"
        ? window.matchMedia("(prefers-color-scheme: dark)").matches
        : true;
      const isDay = mode === "day" || (mode === "auto" && !prefersDark);
      document.body.classList.toggle("theme-day", isDay);
      btn.textContent = "Theme: " + mode.toUpperCase();
    }
    apply(current);
    if (typeof btn.addEventListener === "function") {
      btn.addEventListener("click", function () {
        apply(themes[(themes.indexOf(current) + 1) % themes.length]);
      });
    }
  })();

  // ── Bootstrap ─────────────────────────────────────────────────────────────
  let savedPeopleData = null;
  let savedPeopleLoading = false;
  let savedPeopleGeneration = 0;
  let savedPersonId = null;
  const savedTimelineCache = new Map();

  function savedPeopleLocation(personId, sceneId = "") {
    const params = new URLSearchParams({person: personId});
    if (savedPeopleData.epoch_id) params.set("epoch", savedPeopleData.epoch_id);
    if (window.GoodQLibrary?.source) params.set("library_source", window.GoodQLibrary.source);
    if (sceneId) params.set("scene", sceneId);
    window.history?.replaceState(null, "", `/ui/identity_workbench/?${params}`);
  }

  function savedWatchUrl(personId, scene) {
    return `/ui/retro_console_v1/?${new URLSearchParams({
      watch_person: personId, watch_scene: scene.scene_id,
      watch_video: scene.video_id, watch_epoch: scene.epoch_id || savedPeopleData.epoch_id,
      ...(scene.library_source ? {library_source: scene.library_source} : {}),
    })}`;
  }

  async function renderSavedPerson(personId, selectedScene = "") {
    const person = savedPeopleData.people.find(p => p.id === personId);
    if (!person) return;
    const generation = ++savedPeopleGeneration;
    savedPersonId = personId;
    savedPeopleLocation(personId, selectedScene);
    const target = document.getElementById("saved-person-scenes");
    target.setAttribute("aria-busy", "true");
    target.innerHTML = `<h2>${escHtml(person.display_name)}</h2><p>Loading saved scenes…</p>`;
    document.querySelectorAll("[data-saved-person]").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.savedPerson === personId));
    });
    const scenes = savedPeopleData.appearances.filter(a => a.person_id === personId);
    await Promise.all([...new Set(scenes.map(a => a.video_id).filter(Boolean))].map(async videoId => {
      if (!savedTimelineCache.has(videoId)) {
        savedTimelineCache.set(videoId, apiCall(`/api/videos/${encodeURIComponent(videoId)}/scenes`)
          .then(data => Array.isArray(data) ? data : data.scenes || []).catch(() => []));
      }
      const timeline = await savedTimelineCache.get(videoId);
      scenes.filter(s => s.video_id === videoId).forEach(s => {
        const matches = timeline.filter(row => String(row.scene_id ?? row.id) === s.scene_id);
        s.timeline = matches.length === 1 ? matches[0] : null;
      });
    }));
    if (generation !== savedPeopleGeneration) return;
    scenes.sort((a, b) => (a.video_id || "").localeCompare(b.video_id || "") ||
      (a.timeline?.start ?? Infinity) - (b.timeline?.start ?? Infinity));
    target.innerHTML = `<h2>${escHtml(person.display_name)} <span>${scenes.length} saved scenes</span></h2>
      <p class="appearance-help">Your saved face labels connect these moments. Watch opens the original scene in Explorer; you can return here afterward.</p>
      ${scenes.map(scene => {
        const t = scene.timeline;
        const watchable = t?.original_video_available === true && Number.isFinite(t.start) && t.start >= 0 && Number.isFinite(t.end) && t.end >= t.start;
        const first = scene.evidence.find(m => m.evidence_status === "available") || scene.evidence[0];
        return `<article class="saved-scene" data-saved-scene="${escHtml(scene.scene_id)}">
          <div class="saved-scene-heading"><div><h3>${t ? `${memberTime(t.start)} – ${memberTime(t.end)}` : "Scene timing unavailable"}</h3>
            <p>${escHtml(scene.video_id || "Source unavailable")}</p></div>
            ${watchable ? `<a class="toolbar-btn saved-watch" href="${escHtml(savedWatchUrl(personId, scene))}" data-watch-scene="${escHtml(scene.scene_id)}">Watch scene</a>`
              : '<p class="saved-unavailable">Playback unavailable. Reload saved scenes to try again.</p>'}</div>
          <div class="saved-scene-evidence">${first ? targetFaceHtml(first, true) : ""}
            <div><p>Saved appearance · ${scene.evidence.length} ${scene.evidence.length === 1 ? "observation" : "observations"}</p>
              <p class="appearance-help">Face-group evidence; this does not identify a voice or a spoken name.</p>
              <details><summary>View exact faces and evidence</summary><div class="appearance-evidence">${scene.evidence.map(m => `<figure>
                <div class="appearance-face-pair">${targetFaceHtml(m)}${targetFaceHtml(m, true)}</div>
                <figcaption>${memberTime(m.timestamp)} · ${escHtml(m.target_face_id)}</figcaption></figure>`).join("")}</div></details></div>
          </div></article>`;
      }).join("")}`;
    target.setAttribute("aria-busy", "false");
    target.querySelectorAll("[data-watch-scene]").forEach(link => {
      link.addEventListener("click", () => savedPeopleLocation(personId, link.dataset.watchScene));
    });
    if (selectedScene) {
      const selected = [...target.querySelectorAll("[data-saved-scene]")].find(el => el.dataset.savedScene === selectedScene);
      if (selected) { selected.classList.add("saved-scene-selected"); selected.scrollIntoView({block: "nearest"}); }
    }
  }

  async function loadSavedPeople() {
    const generation = ++savedPeopleGeneration;
    savedPeopleLoading = true;
    const status = document.getElementById("saved-people-status");
    const browser = document.getElementById("saved-people-browser");
    status.textContent = "Loading saved connections…";
    browser.hidden = true;
    savedPeopleData = null;
    savedTimelineCache.clear();
    try {
      const data = await apiCall("/api/identity/appearances/saved");
      if (generation !== savedPeopleGeneration) return;
      savedPeopleData = data;
      status.textContent = data.people.length
        ? `${data.summary.people} people · ${data.summary.appearances} saved appearance links across ${data.summary.scenes} scenes. No changes to apply here.`
        : "No saved appearance connections yet. Open Review or change connections below to preview your labeled groups.";
      document.getElementById("saved-people-list").innerHTML = data.people.map(p => `<button data-saved-person="${escHtml(p.id)}" aria-pressed="false">
        <strong>${escHtml(p.display_name)}</strong><span>${p.scene_count} scenes · ${p.observation_count} observations</span></button>`).join("");
      document.querySelectorAll("[data-saved-person]").forEach(button => {
        button.addEventListener("click", () => renderSavedPerson(button.dataset.savedPerson));
      });
      browser.hidden = !data.people.length;
      const restore = new URLSearchParams(window.location?.search || "");
      const requested = restore.get("person") || savedPersonId;
      const sameEpoch = !restore.get("epoch") || restore.get("epoch") === data.epoch_id
        || (data.library_epochs || []).includes(restore.get("epoch"));
      if (requested && (!sameEpoch || !data.people.some(p => p.id === requested))) {
        document.getElementById("saved-person-scenes").textContent = "That saved selection is unavailable in this movie. Choose a person to continue.";
      } else if (data.people.length) {
        await renderSavedPerson(requested || data.people[0].id, restore.get("scene") || "");
      }
    } catch (error) {
      if (generation === savedPeopleGeneration) status.textContent = `Saved connections could not load: ${error.message} Use Reload saved scenes to try again.`;
    } finally { savedPeopleLoading = false; }
  }

  document.getElementById("reload-saved-people").addEventListener("click", loadSavedPeople);

  let appearancePlan = null;
  let appearanceBusy = false;
  const appearanceReview = document.getElementById("appearance-review");
  const appearanceStatus = document.getElementById("appearance-status");
  const appearanceHistory = document.getElementById("appearance-history");
  const previewAppearancesBtn = document.getElementById("preview-appearances-btn");

  function appearanceMessage(message, error = false) {
    appearanceStatus.textContent = message;
    appearanceStatus.dataset.status = error ? "error" : "info";
  }

  function appearanceControls(busy) {
    appearanceBusy = busy;
    previewAppearancesBtn.disabled = busy;
    previewAppearancesBtn.textContent = busy ? "Checking connections…" : "Refresh preview";
    document.querySelectorAll(".appearance-mutation").forEach(button => {
      button.disabled = busy || (button.id === "apply-appearances-btn" && (!appearancePlan || !appearancePlan.summary.new_edges));
    });
  }

  function renderAppearanceHistory(receipts) {
    appearanceHistory.hidden = !receipts.length;
    appearanceHistory.innerHTML = receipts.length ? `<h2>Connection history</h2>${receipts.map(r => `
      <div class="appearance-history-row">
        <div><strong>${r.status === "undone" ? "Undone" : "Applied"}</strong> · ${r.summary.appearances} appearance links
          <span>${escHtml(r.created_at.replace("T", " ").slice(0, 19))} UTC · Receipt ${escHtml(r.id.slice(0, 8))}</span></div>
        ${r.status === "applied" ? `<button class="toolbar-btn secondary appearance-mutation" data-undo-appearance="${escHtml(r.id)}">Undo these connections</button>` : ""}
      </div>`).join("")}` : "";
    appearanceHistory.querySelectorAll("[data-undo-appearance]").forEach(button => {
      const receipt = receipts.find(r => r.id === button.dataset.undoAppearance);
      button.addEventListener("click", () => undoAppearances(receipt));
    });
  }

  function renderAppearanceEvidence(personId) {
    const target = document.getElementById("appearance-scenes");
    const person = appearancePlan.people.find(p => p.id === personId);
    const scenes = appearancePlan.appearances.filter(a => a.person_id === personId)
      .sort((a, b) => Math.min(...a.evidence.map(m => m.timestamp)) - Math.min(...b.evidence.map(m => m.timestamp)));
    target.innerHTML = `<h2>${escHtml(person.display_name)} <span>${scenes.length} scenes</span></h2>
      <p class="appearance-help">Expand a scene to review every saved target face. Group labels are your input; the links retain candidate evidence.</p>
      ${scenes.map((scene, index) => `<details class="appearance-scene" ${index === 0 ? "open" : ""}>
        <summary><span>${memberTime(Math.min(...scene.evidence.map(m => m.timestamp)))}</span>
          <span>Scene ${escHtml(scene.scene_id.slice(0, 12))}</span><span>${scene.evidence.length} ${scene.evidence.length === 1 ? "observation" : "observations"}</span></summary>
        <div class="appearance-evidence">${scene.evidence.map(member => `<figure>
          <div class="appearance-face-pair">${targetFaceHtml(member)}${targetFaceHtml(member, true)}</div>
          <figcaption>${memberTime(member.timestamp)} · Target ${escHtml(member.target_face_id)}<br>
            ${escHtml(scene.cluster_ids.join(", "))}</figcaption></figure>`).join("")}</div>
      </details>`).join("") || "<p>No saved scene evidence.</p>"}`;
    appearanceReview.querySelectorAll("[data-appearance-person]").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.appearancePerson === personId));
    });
  }

  function renderAppearancePreview(plan) {
    const s = plan.summary;
    appearanceReview.hidden = false;
    appearanceReview.innerHTML = `
      <div class="appearance-summary">
        <div><h2>${!s.appearances ? "No appearance connections to apply" : s.new_edges ? "Preview · not applied" : "Connections are up to date"}</h2>
          <p>${s.people} people · ${s.groups} labeled groups · <strong>${s.appearances} appearance links across ${s.scenes} scenes</strong></p>
          <p>${s.observations} saved observations. ${s.existing_edges ? `${s.existing_edges} connections already exist. ` : ""}Your labels and source movie are preserved.</p></div>
        <button class="toolbar-btn appearance-mutation appearance-apply" id="apply-appearances-btn" ${s.new_edges ? "" : "disabled"}>Apply appearance links</button>
      </div>
      <p class="appearance-held">Mentions held for review${plan.held.shared_aliases.length ? `: ${plan.held.shared_aliases.map(a => `<strong>${escHtml(a.term)}</strong> is shared by ${a.people.map(escHtml).join(" / ")}`).join("; ")}` : "."}. This preview does not decide who a spoken name refers to.</p>
      <div class="appearance-layout">
        <nav class="appearance-people" aria-label="People in this preview">${plan.people.map(p => `
          <button data-appearance-person="${escHtml(p.id)}" aria-pressed="false"><strong>${escHtml(p.display_name)}</strong>
            <span>${p.scene_count} scenes · ${p.observation_count} observations</span></button>`).join("")}</nav>
        <section id="appearance-scenes" aria-label="Proposed scene evidence"></section>
      </div>
      <p class="appearance-plan-note">Reviewed plan ${escHtml(plan.plan_sha256.slice(0, 12))}. Changed saved inputs require a fresh preview. Undo is available after Apply.</p>`;
    appearanceReview.querySelectorAll("[data-appearance-person]").forEach(button => {
      button.addEventListener("click", () => renderAppearanceEvidence(button.dataset.appearancePerson));
    });
    document.getElementById("apply-appearances-btn").addEventListener("click", applyAppearances);
    if (plan.people.length) renderAppearanceEvidence(plan.people[0].id);
  }

  async function loadAppearancePreview() {
    if (appearanceBusy) return;
    appearanceControls(true);
    appearancePlan = null;
    appearanceReview.hidden = true;
    appearanceMessage("Reading saved face evidence and scene connections…");
    setOperationStatus("");
    try {
      const history = await apiCall("/api/identity/appearances/history");
      renderAppearanceHistory(history.receipts);
      appearancePlan = await apiCall("/api/identity/appearances/preview");
      renderAppearancePreview(appearancePlan);
      appearanceMessage(!appearancePlan.summary.appearances
        ? "Link labeled face groups to roster entries, save, then preview again."
        : appearancePlan.summary.new_edges ? "Preview ready. Review the people and scenes before choosing Apply."
        : "All previewed appearance connections are already saved. Review the evidence or connection history below.");
    } catch (error) {
      appearanceMessage(`${error.message} Nothing was applied.`, true);
    } finally {
      appearanceControls(false);
      const applyButton = document.getElementById("apply-appearances-btn");
      if (applyButton) applyButton.disabled = !appearancePlan || !appearancePlan.summary.new_edges;
    }
  }

  async function applyAppearances() {
    if (appearanceBusy || !appearancePlan || !appearancePlan.summary.new_edges) return;
    appearanceControls(true);
    let applied = false;
    try {
      const result = await confirmedIdentityRequest("/api/identity/appearances/apply",
        {plan_sha256: appearancePlan.plan_sha256},
        `Apply the reviewed appearance connections for ${appearancePlan.summary.people} people across ${appearancePlan.summary.scenes} scenes? Transcript mentions and voice identities will remain on hold.`);
      if (result) {
        applied = true;
        appearancePlan = null;
        appearanceReview.hidden = true;
        appearanceMessage("Applied. Appearance connections are now saved in memory. You can undo this receipt below.");
        const history = await apiCall("/api/identity/appearances/history");
        renderAppearanceHistory(history.receipts);
        await loadSavedPeople();
      } else appearanceMessage("Apply cancelled. Your preview is still available; no connections changed.");
    } catch (error) {
      appearancePlan = null;
      appearanceReview.hidden = true;
      appearanceMessage(applied ? `Connections were applied, but history could not load. Refresh to inspect the receipt. ${error.message}`
        : `${error.message} Refresh preview and history before retrying.`, true);
      setOperationFailure(appearanceStatus.textContent);
    } finally { appearanceControls(false); }
  }

  async function undoAppearances(receipt) {
    if (appearanceBusy) return;
    appearanceControls(true);
    try {
      const result = await confirmedIdentityRequest("/api/identity/appearances/undo",
        {receipt_id: receipt.id, receipt_sha256: receipt.receipt_sha256},
        "Undo only the connections added by this receipt? Labels and source evidence are preserved. Later dependent changes will stop Undo.");
      if (result) {
        appearancePlan = null;
        appearanceReview.hidden = true;
        appearanceMessage("Undone. This receipt's connections were removed; your saved labels remain. Refresh to preview again.");
        renderAppearanceHistory((await apiCall("/api/identity/appearances/history")).receipts);
        await loadSavedPeople();
      } else appearanceMessage("Undo cancelled. Saved connections remain applied.");
    } catch (error) {
      appearanceMessage(`${error.message} Reload history before retrying.`, true);
      setOperationFailure(appearanceStatus.textContent);
    } finally { appearanceControls(false); }
  }

  previewAppearancesBtn.addEventListener("click", loadAppearancePreview);

  async function init() {
    if (!await checkStatus()) return;
    const reads = [loadRoster()];
    if (actionReady("face_review")) reads.push(loadFaceClusters());
    if (actionReady("speaker_review")) reads.push(loadSpeakerClusters());
    if (actionReady("name_review")) reads.push(loadNameMentions());
    await Promise.allSettled(reads);
    const params = new URLSearchParams(window.location?.search || "");
    const requestedTab = params.get("tab");
    if (params.has("person") || requestedTab === "appearances") activateTab("appearances");
    else if (requestedTab === "matches") document.getElementById("tab-matches")?.click();
    else if (requestedTab && ["faces", "speakers", "names", "roster"].includes(requestedTab)) activateTab(requestedTab);
    else activateTab("faces");
  }

  init();

})();
