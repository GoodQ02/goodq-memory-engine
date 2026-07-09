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
  };

  // ── UI Cache ─────────────────────────────────────────────────────────────
  const ui = {
    status:       document.getElementById("system-status"),
    phaseIndicator: document.getElementById("phase-indicator"),

    // Tabs
    tabs: document.querySelectorAll(".tab-btn"),
    panels: document.querySelectorAll(".tab-panel"),

    // Badges
    badgeFaces:    document.getElementById("badge-faces"),
    badgeSpeakers: document.getElementById("badge-speakers"),
    badgeNames:    document.getElementById("badge-names"),
    badgeRoster:   document.getElementById("badge-roster"),

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

    // Label Modal
    labelModal:      document.getElementById("label-modal"),
    labelModalClose: document.getElementById("label-modal-close"),
    labelModalCancel:document.getElementById("label-modal-cancel"),
    labelModalConfirm:document.getElementById("label-modal-confirm"),
    labelInput:      document.getElementById("cluster-label-input"),
    labelNoteInput:  document.getElementById("cluster-note-input"),
    labelModalWarn:  document.getElementById("label-modal-warning"),
    modalThumbnails: document.getElementById("modal-thumbnails"),
    modalClusterMeta:document.getElementById("modal-cluster-meta"),
    knownIdList:     document.getElementById("known-identities-list"),

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
      try { const j = await resp.json(); msg = j.detail || j.message || msg; } catch (_) {}
      const err = new Error(msg);
      err.status = resp.status;
      throw err;
    }
    return resp.json();
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
      await apiCall("/api/status");
      ui.status.textContent = "Status: ONLINE";
      ui.status.className = "header-status online";
    } catch (_) {
      ui.status.textContent = "Status: OFFLINE";
      ui.status.className = "header-status offline";
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
      const data = await apiCall(`/api/identity/rebuild-face-clusters?eps=${eps}`, { method: "POST" });
      state.faceClusters = data.clusters || [];
      ui.badgeFaces.textContent = state.faceClusters.length;
      ui.facesNote.textContent = `${state.faceClusters.length} clusters (eps=${eps}).`;
      renderFaceGrid();
      toast(`Re-clustered: ${state.faceClusters.length} clusters with eps=${eps}`);
    } catch (e) {
      toast(`Re-clustering failed: ${e.message}`, "error");
    } finally {
      ui.rerunFacesBtn.textContent = "RE-CLUSTER ↻";
      ui.rerunFacesBtn.disabled = false;
    }
  }

  function renderFaceGrid() {
    if (!state.faceClusters.length) {
      ui.facesGrid.innerHTML = `
        <div class="empty-card">
          <span class="pulse-icon">⬡</span>
          <p>No clusters found. Try running Phase 1 or adjusting eps.</p>
        </div>`;
      return;
    }

    ui.facesGrid.innerHTML = "";
    state.faceClusters.forEach((cluster, idx) => {
      const labeled = cluster.label && cluster.label !== "null";
      const card = document.createElement("div");
      card.className = `cluster-card${labeled ? " labeled" : ""}`;
      card.dataset.idx = idx;

      // Thumbnail strip — up to 5 face images
      const thumbs = (cluster.sample_faces || []).slice(0, 5).map(src =>
        `<img class="cluster-thumb" src="${escHtml(src)}" alt="face" loading="lazy"
              onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'cluster-thumb-placeholder',textContent:'👤'}))">`
      );
      // Fill placeholders
      while (thumbs.length < 3) {
        thumbs.push(`<span class="cluster-thumb-placeholder">👤</span>`);
      }

      card.innerHTML = `
        <div class="cluster-card-header">
          <span class="cluster-id">${escHtml(cluster.cluster_id)}</span>
          <span class="cluster-label-chip ${labeled ? "" : "unlabeled"}">
            ${labeled ? escHtml(cluster.label) : "UNLABELED"}
          </span>
        </div>
        <div class="cluster-thumbnails-strip">${thumbs.join("")}</div>
        <div class="cluster-card-footer">
          <span class="cluster-stat">Faces: <strong>${cluster.face_count ?? "—"}</strong></span>
          <span class="cluster-stat">Videos: <strong>${(cluster.video_hashes || []).length}</strong></span>
          <button class="cluster-edit-btn" data-idx="${idx}">LABEL ›</button>
        </div>`;

      card.querySelector(".cluster-edit-btn").addEventListener("click", (e) => {
        e.stopPropagation();
        openLabelModal(idx);
      });
      card.addEventListener("click", () => openLabelModal(idx));
      ui.facesGrid.appendChild(card);
    });
  }

  // ── Face Label Modal ─────────────────────────────────────────────────────

  function openLabelModal(idx) {
    const cluster = state.faceClusters[idx];
    if (!cluster) return;
    state.activeFaceModal = idx;

    // Thumbnails
    const thumbs = (cluster.sample_faces || []).slice(0, 10).map(src =>
      `<img src="${escHtml(src)}" alt="face" loading="lazy"
            onerror="this.style.display='none'">`
    ).join("");
    ui.modalThumbnails.innerHTML = thumbs || `<span style="color:var(--text-faint);font-size:11px">No thumbnail images available</span>`;

    // Meta info
    ui.modalClusterMeta.innerHTML = `
      <span>Cluster: <strong style="color:var(--accent)">${escHtml(cluster.cluster_id)}</strong></span>
      <span>Detections: <strong>${cluster.face_count ?? "—"}</strong></span>
      <span>Videos: <strong>${(cluster.video_hashes || []).length}</strong></span>
      <span>Method: <strong>${escHtml(cluster.status || "candidate")}</strong></span>`;

    // Pre-fill existing label
    ui.labelInput.value = cluster.label || "";
    ui.labelNoteInput.value = cluster.operator_note || "";
    ui.labelModalWarn.hidden = true;

    // Datalist of known identities
    ui.knownIdList.innerHTML = Array.from(state.knownIdentityLabels)
      .map(name => `<option value="${escHtml(name)}">`).join("");

    ui.labelModal.hidden = false;
    ui.labelInput.focus();
  }

  function closeLabelModal() {
    ui.labelModal.hidden = true;
    state.activeFaceModal = null;
  }

  async function applyClusterLabel() {
    const idx = state.activeFaceModal;
    if (idx === null || idx === undefined) return;
    const label = ui.labelInput.value.trim();
    const note  = ui.labelNoteInput.value.trim();

    if (!label) {
      ui.labelModalWarn.textContent = "Label is required.";
      ui.labelModalWarn.hidden = false;
      ui.labelInput.focus();
      return;
    }

    const cluster = state.faceClusters[idx];
    try {
      await apiCall("/api/identity/face-clusters/label", {
        method: "POST",
        body: JSON.stringify({
          cluster_id: cluster.cluster_id,
          label,
          operator_note: note,
        }),
      });
      cluster.label = label;
      cluster.operator_note = note;
      state.knownIdentityLabels.add(label);
      renderFaceGrid();
      updateRosterIdentityLabels();
      toast(`Cluster ${cluster.cluster_id} labeled → ${label}`);
      closeLabelModal();
    } catch (e) {
      ui.labelModalWarn.textContent = `Error: ${e.message}`;
      ui.labelModalWarn.hidden = false;
    }
  }

  ui.labelModalClose.addEventListener("click", closeLabelModal);
  ui.labelModalCancel.addEventListener("click", closeLabelModal);
  ui.labelModalConfirm.addEventListener("click", applyClusterLabel);
  ui.labelModal.addEventListener("click", e => { if (e.target === ui.labelModal) closeLabelModal(); });

  // Confirm label on Enter
  ui.labelInput.addEventListener("keydown", e => { if (e.key === "Enter") applyClusterLabel(); });

  // Toolbar buttons — Phase 1
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
        state.speakerClusters[idx].confirmed = e.target.checked;
        card.classList.toggle("confirmed", e.target.checked);
        toast(`Speaker ${cluster.cluster_id}: confirmed = ${e.target.checked}`);
        syncSpeakerAssignment(idx, card);
      });

      card.querySelector(".speaker-identity-input").addEventListener("change", (e) => {
        state.speakerClusters[idx].identity_label = e.target.value.trim();
        syncSpeakerAssignment(idx, card);
      });

      ui.speakersList.appendChild(card);
    });
  }

  async function syncSpeakerAssignment(idx, _card) {
    const cluster = state.speakerClusters[idx];
    try {
      await apiCall("/api/identity/speaker-clusters/confirm", {
        method: "POST",
        body: JSON.stringify({
          cluster_id: cluster.cluster_id,
          confirmed: cluster.confirmed,
          identity_label: cluster.identity_label || null,
        }),
      });
    } catch (e) {
      // Best-effort — UI state is already updated
      console.warn("Speaker sync failed:", e.message);
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
      .filter(c => !(identity.face_cluster_ids || []).includes(c.cluster_id))
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

  async function saveIdentity(idx) {
    const identity = state.roster[idx];
    try {
      await apiCall("/api/identity/roster/save", {
        method: "POST",
        body: JSON.stringify({ identity }),
      });
      state.knownIdentityLabels = new Set(state.roster.map(id => id.display_name));
      renderRosterSidebar();
      toast(`Saved: ${identity.display_name}`);
    } catch (e) {
      toast(`Save failed: ${e.message}`, "error");
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
      const data = await apiCall("/api/identity/roster/validate", { method: "POST" });
      renderValidationResult(data);
      ui.validateModal.hidden = false;
    } catch (e) {
      toast(`Validation request failed: ${e.message}`, "error");
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
    errors.forEach(m => { html += `<span class="fail">  ✗ ${escHtml(m)}\n</span>`; });

    ui.validateResult.innerHTML = html;
  }

  ui.validateRosterBtn.addEventListener("click", validateRoster);
  ui.validateModalClose.addEventListener("click", () => { ui.validateModal.hidden = true; });
  ui.validateModalOk.addEventListener("click", () => { ui.validateModal.hidden = true; });
  ui.validateModal.addEventListener("click", e => { if (e.target === ui.validateModal) ui.validateModal.hidden = true; });

  // ── Export YAML ───────────────────────────────────────────────────────────
  async function exportRoster() {
    try {
      const data = await apiCall("/api/identity/roster/export", {
        method: "POST",
        body: JSON.stringify({ identities: state.roster }),
      });
      toast(`Roster exported: ${data.path || "family_roster.yaml"}`);
    } catch (e) {
      // Fallback — dump YAML-ish JSON the user can paste
      const yaml = rosterToYaml(state.roster);
      const blob = new Blob([yaml], { type: "text/yaml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "family_roster.yaml";
      a.click();
      URL.revokeObjectURL(url);
      toast("Exported as download (API route unavailable)");
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
    await checkStatus();
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
