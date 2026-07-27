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
    const url = `${state.apiBase}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    
    if (!response.ok) {
      let message = response.statusText;
      try {
        const errorJson = await response.json();
        message = errorJson.detail || errorJson.message || message;
      } catch (e) {}
      
      const err = new Error(message);
      err.status = response.status;
      throw err;
    }
    
    return await response.json();
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
      
      item.innerHTML = `
        <div class="pattern-title">${p.node_name}</div>
        <div class="pattern-meta-grid">
          <div class="meta-field">Scenes: <strong>${p.occurrence_count}</strong></div>
          <div class="meta-field">Voiced: <strong>${formatVoicedTime(p.voiced_seconds)}</strong></div>
          <div class="meta-field">Segs: <strong>${p.segment_count}</strong></div>
        </div>
        <div class="pattern-excerpt">${p.sample_transcript ? `"${p.sample_transcript}"` : "No transcript excerpt."}</div>
      `;
      
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
    ui.selectedPatternScenes.textContent = pattern.occurrence_count;
    ui.selectedPatternVoiced.textContent = formatVoicedTime(pattern.voiced_seconds);
    ui.selectedPatternSegments.textContent = pattern.segment_count;
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
      closeModal();
      
      const sourceName = state.selectedPattern.node_name;
      const targetName = ui.targetPersonInput.value.trim();
      const operatorNote = ui.operatorNoteInput.value.trim();
      
      try {
        // Show rebuilding spinner overlay
        ui.rebuildOverlay.removeAttribute("hidden");
        ui.status.textContent = "Status: REBUILDING GRAPH...";
        ui.status.className = "header-status ingesting";
        
        const commitRes = await apiCall("/api/system/identity/stitch", {
          method: "POST",
          body: JSON.stringify({
            source_node_name: sourceName,
            target_person_name: targetName,
            confirm: true,
            operator_note: operatorNote,
          }),
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
        ui.rebuildOverlay.setAttribute("hidden", "");
      }
    });
  }

  // Revoke Mapping Operation
  async function executeRevoke(mapping) {
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
    
    try {
      // Show rebuilding spinner overlay
      ui.rebuildOverlay.removeAttribute("hidden");
      ui.status.textContent = "Status: REBUILDING GRAPH...";
      ui.status.className = "header-status ingesting";
      
      const revokeRes = await apiCall("/api/system/identity/stitch/revoke", {
        method: "POST",
        body: JSON.stringify({
          mapping_id: mapping.mapping_id,
          operator_note: operatorNote || "Revoked by operator",
        }),
      });
      
      showToast(revokeRes.message || "Successfully revoked mapping.");
      
      // Reload datasets
      await refreshData();
      
    } catch (err) {
      showToast(`Revocation failed: ${err.message}`, "error");
    } finally {
      ui.rebuildOverlay.setAttribute("hidden", "");
    }
  }

  // Refreshes all lists on modifications
  async function refreshData() {
    await fetchSystemStatus();
    await fetchUnstitched();
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
