(function () {
  "use strict";

  // App State Model
  const state = {
    unstitched: [],
    mappings: [],
    knownPeople: new Set(),
    selectedPattern: null,
    apiBase: "",
  };

  // UI Element Cache
  const ui = {
    status: document.getElementById("system-status"),
    dbIndicator: document.getElementById("db-indicator"),
    
    // Panels
    unstitchedList: document.getElementById("unstitched-list"),
    unstitchedCount: document.getElementById("unstitched-count"),
    patternSearch: document.getElementById("pattern-search"),
    
    mappingsList: document.getElementById("mappings-list"),
    mappingsCount: document.getElementById("mappings-count"),
    mappingSearch: document.getElementById("mapping-search"),
    
    // Stitch Controls Form
    noPatternSelected: document.getElementById("no-pattern-selected"),
    stitchForm: document.getElementById("stitch-form"),
    selectedPatternName: document.getElementById("selected-pattern-name"),
    selectedPatternScenes: document.getElementById("selected-pattern-scenes"),
    selectedPatternVoiced: document.getElementById("selected-pattern-voiced"),
    selectedPatternSegments: document.getElementById("selected-pattern-segments"),
    selectedPatternTranscript: document.getElementById("selected-pattern-transcript"),
    
    // Form Inputs
    inputsForm: document.getElementById("stitch-inputs-form"),
    targetPersonInput: document.getElementById("target-person-input"),
    operatorNoteInput: document.getElementById("operator-note-input"),
    autocompleteDropdown: document.getElementById("autocomplete-suggestions"),
    previewStitchBtn: document.getElementById("preview-stitch-btn"),
    
    // Modal Overlay
    previewModal: document.getElementById("preview-modal"),
    modalCloseBtn: document.getElementById("modal-close-btn"),
    modalCancelBtn: document.getElementById("modal-cancel-btn"),
    modalConfirmBtn: document.getElementById("modal-confirm-btn"),
    modalSourceName: document.getElementById("modal-source-name"),
    modalTargetName: document.getElementById("modal-target-name"),
    modalScenesCount: document.getElementById("modal-scenes-count"),
    modalEpisodesCount: document.getElementById("modal-episodes-count"),
    modalConflictsSection: document.getElementById("modal-conflicts-section"),
    modalConflictsList: document.getElementById("modal-conflicts-list"),
    modalOperatorNote: document.getElementById("modal-operator-note"),
    
    // Overlay rebuild
    rebuildOverlay: document.getElementById("rebuild-overlay"),
    toastContainer: document.getElementById("toast-container"),
  };

  // Formats voiced seconds nicely
  function formatVoicedTime(seconds) {
    if (!seconds) return "0s";
    if (seconds < 60) return seconds.toFixed(1) + "s";
    const minutes = Math.floor(seconds / 60);
    const remaining = Math.round(seconds % 60);
    return `${minutes}m ${remaining}s`;
  }

  // Toast Helper
  function showToast(message, type = "success") {
    const toast = document.createElement("div");
    toast.className = `toast ${type === "error" ? "error" : ""}`;
    toast.textContent = message;
    ui.toastContainer.appendChild(toast);
    
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transition = "opacity 0.25s ease-out";
      setTimeout(() => toast.remove(), 250);
    }, 4000);
  }

  // Set loading states
  function showLoading(element, text = "Loading...") {
    element.innerHTML = `<div class="empty-state">${text}</div>`;
  }

  // API Call Wrapper
  async function apiCall(endpoint, options = {}) {
    const rawUrl = `${state.apiBase}${endpoint}`;
    const url = (typeof GoodQLibrary !== "undefined" && GoodQLibrary && typeof GoodQLibrary.url === "function")
      ? GoodQLibrary.url(rawUrl)
      : rawUrl;
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    
    if (!response.ok) {
      let message = response.statusText;
      let payload = null;
      try {
        payload = await response.json();
        message = payload.detail || payload.message || message;
      } catch (e) {}
      
      const err = new Error(message);
      err.status = response.status;
      err.payload = payload;
      throw err;
    }
    
    return await response.json();
  }

  // Called only after the operator confirms the preview. Keep the exact payload
  // across the real authority's preparation and single-use confirmation calls.
  async function commitConfirmedStitch(payload) {
    return commitConfirmedIdentity("/api/system/identity/stitch", payload);
  }

  async function commitConfirmedIdentity(endpoint, payload) {
    const body = JSON.stringify(payload);
    let token = null;
    try {
      try {
        await apiCall(endpoint, { method: "POST", body });
        throw new Error("Confirmation gate did not require a scoped token.");
      } catch (error) {
        const envelope = error.payload;
        token = envelope?.result?.confirmation_token;
        if (error.status !== 403 || envelope?.status !== "needs_confirmation" ||
            typeof token !== "string" || !token.trim()) throw error;
      }
      return await apiCall(endpoint, {
        method: "POST",
        body: JSON.stringify({ ...JSON.parse(body), confirmation_token: token }),
      });
    } finally {
      token = null;
    }
  }

  // Fetch status of DB and setup environment headers
  async function fetchSystemStatus() {
    try {
      const data = await apiCall("/api/status");
      ui.status.textContent = "Status: ONLINE";
      ui.status.className = "header-status";
      
      // Update database indicator
      const dbPath = data.indexes?.sqlite_db || "knowledge_graph.db";
      ui.dbIndicator.textContent = `Database: ${dbPath}`;
      ui.dbIndicator.title = dbPath;
    } catch (e) {
      ui.status.textContent = "Status: OFFLINE";
      ui.status.className = "header-status offline";
      ui.dbIndicator.textContent = "Database: API Offline";
      showToast(`API server unreachable: ${e.message}`, "error");
    }
  }

  // Fetch unstitched patterns
  async function fetchUnstitched() {
    try {
      const data = await apiCall("/api/system/identity/unstitched");
      state.unstitched = data || [];
      renderUnstitched();
    } catch (e) {
      showToast(`Failed to load unstitched patterns: ${e.message}`, "error");
      ui.unstitchedList.innerHTML = `<div class="empty-state error-text">Load error: ${e.message}</div>`;
    }
  }

  function renderSpeakerReviews(rows) {
    const panel = document.getElementById("speaker-reviews");
    panel.replaceChildren();
    let notices = 0;
    rows.forEach(({scene_id, video_id, review}) => {
      if (review.status !== "ok") {
        const note = document.createElement("p");
        note.textContent = `Scene ${scene_id}: speaker-change review unavailable (${review.reason || review.status}).`;
        panel.appendChild(note);
        notices++;
      }
      (review.flags || []).forEach(flag => {
        const note = document.createElement("p");
        note.textContent = `Video ${video_id || "unknown"}, scene ${scene_id}, ${Number(flag.start).toFixed(3)}–${Number(flag.end).toFixed(3)}s (scene-relative): possible speaker change merged during diarization. Unreviewed; speaker identity and exact boundaries unconfirmed. Signatures and admission are unchanged.`;
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        summary.textContent = "Supporting evidence";
        const evidence = document.createElement("p");
        evidence.textContent = `Window ${flag.window_start}–${flag.window_end}s; local slots ${(flag.local_slots || []).join(" → ")}; final cluster ${flag.final_cluster}; gaps ${Number(flag.left_gap).toFixed(3)}s / ${Number(flag.right_gap).toFixed(3)}s; rule ${review.rule}. Local slots are not people.`;
        details.append(summary, evidence);
        panel.append(note, details);
        notices++;
      });
    });
    if (!notices) panel.textContent = "No review flags recorded. This does not establish speaker purity; historical scenes may lack review evidence.";
  }

  async function fetchSpeakerReviews() {
    try {
      renderSpeakerReviews(await apiCall("/api/system/identity/speaker-reviews"));
    } catch (e) {
      document.getElementById("speaker-reviews").textContent = `Review evidence unavailable: ${e.message}`;
    }
  }

  // Fetch stitched manual mapping ledger
  async function fetchMappings() {
    try {
      const data = await apiCall("/api/system/identity/mappings");
      state.mappings = data?.mappings || [];
      
      // Extract known target person names for autocomplete suggestions
      state.knownPeople.clear();
      state.mappings.forEach(m => {
        if (m.target_person_name && m.status === "active") {
          state.knownPeople.add(m.target_person_name);
        }
      });
      // Add standard defaults if empty
      if (state.knownPeople.size === 0) {
        ["Joe", "Charlie", "Tony"].forEach(name => state.knownPeople.add(name));
      }
      
      renderMappings();
    } catch (e) {
      showToast(`Failed to load manual mappings: ${e.message}`, "error");
      ui.mappingsList.innerHTML = `<div class="empty-state error-text">Load error: ${e.message}</div>`;
    }
  }

  // Render Unstitched Patterns Panel
  function renderUnstitched() {
    const filter = ui.patternSearch.value.toLowerCase().trim();
    const filtered = state.unstitched.filter(p => {
      return p.node_name.toLowerCase().includes(filter) ||
             (p.sample_transcript && p.sample_transcript.toLowerCase().includes(filter));
    });
    
    ui.unstitchedCount.textContent = filtered.length;
    
    if (filtered.length === 0) {
      ui.unstitchedList.innerHTML = `<div class="empty-state">No speaker-pattern evidence exists in the active epoch.<br><span class="muted">Roster validation does not create speaker patterns; this page only maps recurring voice-pattern evidence already present in the knowledge graph.</span></div>`;
      return;
    }
    
    ui.unstitchedList.innerHTML = "";
    filtered.forEach(p => {
      const item = document.createElement("div");
      item.className = "pattern-item";
      if (state.selectedPattern && state.selectedPattern.node_id === p.node_id) {
        item.classList.add("selected");
      }
      
      const match = /^voice_pattern_([0-9a-f]{8})[0-9a-f]*_speaker_(\d+)_([0-9a-f]{6})/i.exec(p.node_name || "");
      const friendlyTitle = match
        ? `Speaker ${match[2]} · Scene #${match[1]}`
        : p.node_name;
      const shortCode = match ? `${match[1]}…${match[3]}` : "";

      item.innerHTML = `
        <div class="pattern-title-row">
          <div class="pattern-title" title="${p.node_name}">${friendlyTitle}</div>
          ${shortCode ? `<span class="pattern-hash-pill" title="${p.node_name}">${shortCode}</span>` : ""}
        </div>
        <div class="pattern-meta-grid">
          <div class="meta-field">Scenes: <strong>${p.scene_count ?? "Unknown"}</strong></div>
          <div class="meta-field">Voiced: <strong>${formatVoicedTime(p.voiced_seconds)}</strong></div>
          <div class="meta-field">Selected turns: <strong>${p.segment_count ?? "Unknown"}</strong></div>
        </div>
        <div class="pattern-excerpt">${p.sample_transcript ? `"${p.sample_transcript}"` : "No transcript excerpt."}</div>
      `;
      
      const splits = p.possible_same_speaker_patterns || [];
      if (splits.length) {
        const splitDetails = document.createElement("details");
        splitDetails.className = "split-warning-details";
        splitDetails.addEventListener("click", event => event.stopPropagation());
        const splitSummary = document.createElement("summary");
        splitSummary.textContent = `⚠️ ${splits.length} possible same-speaker split${splits.length === 1 ? "" : "s"} — review required`;
        const warning = document.createElement("p");
        warning.textContent = `Possible same-speaker split with ${splits.join(", ")}. Review required; tracks remain separate.`;
        splitDetails.append(splitSummary, warning);
        item.appendChild(splitDetails);
      }
      const evidence = (p.signature_evidence || []).filter(e => e.admission_policy);
      if (evidence.length) {
        const details = document.createElement("details");
        details.addEventListener("click", event => event.stopPropagation());
        const summary = document.createElement("summary");
        summary.textContent = "Signature speech selection (speaker purity unconfirmed)";
        details.appendChild(summary);
        evidence.forEach(e => {
          const note = document.createElement("p");
          const spans = rows => rows == null ? "unknown" : rows.map(s => `${Number(s.start).toFixed(3)}–${Number(s.end).toFixed(3)}s`).join(", ") || "none";
          note.textContent = `Scene ${e.scene_id}: selected ${spans(e.selected_segments)}; excluded overlapping turns ${spans(e.excluded_segments)}.`;
          details.appendChild(note);
        });
        item.appendChild(details);
      }
      item.addEventListener("click", () => selectPattern(p));
      ui.unstitchedList.appendChild(item);
    });
  }

  // Render Manual Mappings Ledger Panel
  function renderMappings() {
    const filter = ui.mappingSearch.value.toLowerCase().trim();
    const filtered = state.mappings.filter(m => {
      return m.source_node_name.toLowerCase().includes(filter) ||
             m.target_person_name.toLowerCase().includes(filter) ||
             m.status.toLowerCase().includes(filter);
    });
    
    ui.mappingsCount.textContent = filtered.length;
    
    if (filtered.length === 0) {
      ui.mappingsList.innerHTML = `<div class="empty-state">No mappings record found.</div>`;
      return;
    }
    
    // Render sorted by active first, then mapping_id descending
    filtered.sort((a, b) => {
      if (a.status !== b.status) {
        return a.status === "active" ? -1 : 1;
      }
      return b.mapping_id.localeCompare(a.mapping_id);
    });
    
    ui.mappingsList.innerHTML = "";
    filtered.forEach(m => {
      const item = document.createElement("div");
      item.className = "mapping-item";
      
      const history = m.history || [];
      const lastNote = history.length > 0 ? history[history.length - 1].operator_note : "";
      
      item.innerHTML = `
        <div class="mapping-main-row">
          <div class="mapping-names">
            <div class="mapping-source" title="${m.source_node_name}">${m.source_node_name}</div>
            <div><span class="mapping-arrow">➔</span> <span class="mapping-target">${m.target_person_name}</span></div>
          </div>
          <span class="status-badge ${m.status === "active" ? "active" : "revoked"}">${m.status.toUpperCase()}</span>
        </div>
        ${lastNote ? `<div class="mapping-note">${lastNote}</div>` : ""}
        ${m.status === "active" ? `
          <div class="mapping-actions-row">
            <button class="revoke-btn" data-id="${m.mapping_id}">REVOKE OVERRIDE</button>
          </div>
        ` : ""}
      `;
      
      const btn = item.querySelector(".revoke-btn");
      if (btn) {
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          executeRevoke(m);
        });
      }
      
      ui.mappingsList.appendChild(item);
    });
  }

  // Select an unstitched pattern
  function selectPattern(pattern) {
    state.selectedPattern = pattern;
    
    // Redraw unstitched list highlights
    renderUnstitched();
    
    // Hide placeholder and reveal form
    ui.noPatternSelected.setAttribute("hidden", "");
    ui.stitchForm.removeAttribute("hidden");
    
    // Populate form data
    ui.selectedPatternName.textContent = pattern.node_name;
    ui.selectedPatternScenes.textContent = pattern.scene_count ?? "Unknown";
    ui.selectedPatternVoiced.textContent = formatVoicedTime(pattern.voiced_seconds);
    ui.selectedPatternSegments.textContent = pattern.segment_count ?? "Unknown";
    ui.selectedPatternTranscript.textContent = pattern.sample_transcript ? `"${pattern.sample_transcript}"` : "No transcript excerpt.";
    
    // Reset form inputs
    ui.targetPersonInput.value = "";
    ui.operatorNoteInput.value = "";
    ui.autocompleteDropdown.setAttribute("hidden", "");
  }

  // Autocomplete functionality
  function setupAutocomplete() {
    ui.targetPersonInput.addEventListener("input", () => {
      const query = ui.targetPersonInput.value.trim().toLowerCase();
      if (!query) {
        ui.autocompleteDropdown.setAttribute("hidden", "");
        return;
      }
      
      const matches = Array.from(state.knownPeople).filter(name => 
        name.toLowerCase().includes(query)
      );
      
      if (matches.length === 0) {
        ui.autocompleteDropdown.setAttribute("hidden", "");
        return;
      }
      
      ui.autocompleteDropdown.innerHTML = "";
      matches.forEach(match => {
        const option = document.createElement("div");
        option.className = "autocomplete-option";
        option.textContent = match;
        option.addEventListener("click", () => {
          ui.targetPersonInput.value = match;
          ui.autocompleteDropdown.setAttribute("hidden", "");
        });
        ui.autocompleteDropdown.appendChild(option);
      });
      
      ui.autocompleteDropdown.removeAttribute("hidden");
    });
    
    // Hide autocomplete on click outside
    document.addEventListener("click", (e) => {
      if (!ui.targetPersonInput.contains(e.target) && !ui.autocompleteDropdown.contains(e.target)) {
        ui.autocompleteDropdown.setAttribute("hidden", "");
      }
    });
  }

  // Two-Stage Transaction Form Submission: PREVIEW
  function setupFormHandlers() {
    ui.inputsForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!state.selectedPattern) return;
      
      const targetName = ui.targetPersonInput.value.trim();
      const operatorNote = ui.operatorNoteInput.value.trim();
      
      if (!targetName || !operatorNote) {
        showToast("Both target name and operator audit notes are required.", "error");
        return;
      }
      
      try {
        ui.previewStitchBtn.textContent = "CALCULATING GRAPH IMPACT...";
        ui.previewStitchBtn.disabled = true;
        
        // Stage 1: Call API /preview endpoint
        const previewRes = await apiCall("/api/system/identity/stitch/preview", {
          method: "POST",
          body: JSON.stringify({
            source_node_name: state.selectedPattern.node_name,
            target_person_name: targetName,
          }),
        });
        
        // Show modal and populate fields
        ui.modalSourceName.textContent = state.selectedPattern.node_name;
        ui.modalTargetName.textContent = targetName;
        ui.modalScenesCount.textContent = previewRes.scenes_affected;
        ui.modalEpisodesCount.textContent = previewRes.episodes_affected;
        ui.modalOperatorNote.textContent = operatorNote;
        
        // Handle conflicts display
        if (previewRes.conflicts && previewRes.conflicts.length > 0) {
          ui.modalConflictsSection.removeAttribute("hidden");
          ui.modalConflictsList.innerHTML = "";
          previewRes.conflicts.forEach(c => {
            const entry = document.createElement("div");
            entry.className = "conflict-entry";
            entry.textContent = `Already mapped to ${c.conflicting_person} (edge: ${c.edge_type}, weight: ${c.weight})`;
            ui.modalConflictsList.appendChild(entry);
          });
        } else {
          ui.modalConflictsSection.setAttribute("hidden", "");
        }
        
        // Reveal Preview modal
        ui.previewModal.removeAttribute("hidden");
        
      } catch (err) {
        showToast(`Preview failed: ${err.message}`, "error");
      } finally {
        ui.previewStitchBtn.textContent = "PREVIEW IDENTITY STITCHING ▶";
        ui.previewStitchBtn.disabled = false;
      }
    });
  }

  // Modal Buttons Integration
  function setupModalHandlers() {
    const closeModal = () => {
      ui.previewModal.setAttribute("hidden", "");
    };
    
    ui.modalCloseBtn.addEventListener("click", closeModal);
    ui.modalCancelBtn.addEventListener("click", closeModal);
    
    // Stage 2: CONFIRM COMMIT
    ui.modalConfirmBtn.addEventListener("click", async () => {
      if (ui.modalConfirmBtn.disabled) return;
      ui.modalConfirmBtn.disabled = true;
      closeModal();
      
      const sourceName = state.selectedPattern.node_name;
      const targetName = ui.targetPersonInput.value.trim();
      const operatorNote = ui.operatorNoteInput.value.trim();
      
      try {
        // Show rebuilding spinner overlay
        ui.rebuildOverlay.removeAttribute("hidden");
        ui.status.textContent = "Status: REBUILDING GRAPH...";
        ui.status.className = "header-status ingesting";
        
        const commitRes = await commitConfirmedStitch({
          source_node_name: sourceName,
          target_person_name: targetName,
          confirm: true,
          operator_note: operatorNote,
        });
        
        showToast(commitRes.message || "Successfully stitched identity.");
        
        // Reset selections
        state.selectedPattern = null;
        ui.stitchForm.setAttribute("hidden", "");
        ui.noPatternSelected.removeAttribute("hidden", "");
        
        // Reload all datasets
        await refreshData();
        
      } catch (err) {
        showToast(`Stitching execution failed: ${err.message}`, "error");
      } finally {
        ui.modalConfirmBtn.disabled = false;
        ui.rebuildOverlay.setAttribute("hidden", "");
      }
    });
  }

  // Revoke Mapping Operation
  let revokePending = false;
  async function executeRevoke(mapping) {
    if (revokePending) return;
    const confirmation = confirm(
      `WARNING: Are you sure you want to revoke the manual identity stitching for:\n` +
      `Pattern: ${mapping.source_node_name}\n` +
      `Identity: ${mapping.target_person_name}\n\n` +
      `This will trigger a full read-model graph metrics rebuild.`
    );
    
    if (!confirmation) return;
    
    const operatorNote = prompt(
      "Please enter a justification note for revoking this mapping:",
      "Revoked by operator override"
    );
    
    if (operatorNote === null) return; // cancelled prompt
    revokePending = true;
    
    try {
      // Show rebuilding spinner overlay
      ui.rebuildOverlay.removeAttribute("hidden");
      ui.status.textContent = "Status: REBUILDING GRAPH...";
      ui.status.className = "header-status ingesting";
      
      const revokeRes = await commitConfirmedIdentity("/api/system/identity/stitch/revoke", {
          mapping_id: mapping.mapping_id,
          operator_note: operatorNote || "Revoked by operator",
      });
      
      showToast(revokeRes.message || "Successfully revoked mapping.");
      
      // Reload datasets
      await refreshData();
      
    } catch (err) {
      showToast(`Revocation failed: ${err.message}`, "error");
    } finally {
      revokePending = false;
      ui.rebuildOverlay.setAttribute("hidden", "");
    }
  }

  // Refreshes all lists on modifications
  async function refreshData() {
    await fetchSystemStatus();
    await fetchUnstitched();
    await fetchSpeakerReviews();
    await fetchMappings();
  }

  // Setup Search filter key listeners
  function setupSearchFilters() {
    ui.patternSearch.addEventListener("input", renderUnstitched);
    ui.mappingSearch.addEventListener("input", renderMappings);
  }

  // Main Initializer
  async function init() {
    setupAutocomplete();
    setupFormHandlers();
    setupModalHandlers();
    setupSearchFilters();
    
    showLoading(ui.unstitchedList, "Scanning unstitched nodes...");
    showLoading(ui.mappingsList, "Loading mappings ledger...");
    
    await refreshData();
  }

  // Trigger init on DOM load
  document.addEventListener("DOMContentLoaded", init);
})();
