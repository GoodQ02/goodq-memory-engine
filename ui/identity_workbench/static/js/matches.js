/* Frozen comparisons, local review drafts, visual grouping, inline roster creation, and cross-film face discovery. */
(function () {
  "use strict";
  const el = id => document.getElementById(id);
  const list = el("matches-list"), status = el("matches-status");
  const reportSelect = el("matches-report"), kind = el("matches-kind"), layoutSelect = el("matches-layout");
  const person = el("matches-person"), result = el("matches-result");
  let report = null, request = 0, limit = 30, loaded = false;
  let selected = new Set(), applied = new Set(), receipts = [], preview = null, busy = false, draftSaved = false, notice = null;
  let decisions = new Map(), savedDecisions = new Map(), completedReview = false, legacyDraft = false, draftRevision = null;
  let draftReadFailed = false;
  // Right saved person for faces marked Incorrect. The decision itself stays Incorrect.
  let corrections = new Map(), savedCorrections = new Map();
  let visualGroupsCache = new Map(), scanCache = new Map(), openScanIds = new Set();
  const decisionNames = {correct: "Correct", incorrect: "Incorrect", unsure: "Unsure", not_accepted: "Earlier review: not accepted"};
  const params = new URLSearchParams(window.location.search);
  const labels = {proposed: "Proposed · not applied", ambiguous: "Uncertain · held", no_match: "Below match threshold", no_reference: "No compatible reference"};

  const stamp = seconds => {
    const n = Math.max(0, Math.floor(Number(seconds) || 0));
    return `${Math.floor(n / 3600)}:${String(Math.floor(n / 60) % 60).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}`;
  };

  function node(tag, text, className) {
    const item = document.createElement(tag);
    if (text != null) item.textContent = text;
    if (className) item.className = className;
    return item;
  }

  const quantity = (n, singular, plural = `${singular}s`) => `${n} ${n === 1 ? singular : plural}`;
  const isImeComposing = event => Boolean(event && (event.isComposing || event.keyCode === 229));

  async function read(url) {
    const response = await fetch(window.GoodQLibrary?.url(url) || url);
    if (!response.ok) {
      let detail = `Saved comparison unavailable (${response.status}).`;
      try {
        const body = await response.json();
        if (typeof body?.detail === "string") detail = body.detail;
      } catch (_) {}
      throw new Error(detail);
    }
    return response.json();
  }

  async function post(url, payload) {
    const response = await fetch(window.GoodQLibrary?.url(url) || url, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      const error = new Error(typeof body.detail === "string" ? body.detail : `Request failed (${response.status}). Reload and preview again.`);
      error.status = response.status;
      error.body = body;
      throw error;
    }
    return body;
  }

  const legacyKey = () => `goodq.face-review.${report.epoch_id}.${report.id}.${report.content_sha256}`;
  const draftKey = () => `goodq.face-review.v2.${report.epoch_id}.${report.id}.${report.content_sha256}`;

  function currentDraft() {
    if (!report || draftReadFailed) return false;
    try {
      if (window.localStorage && window.localStorage.getItem(draftKey()) !== draftRevision) {
        reviewStatus("This draft changed in another tab. Reload comparisons to use the latest decisions.", true);
        return false;
      }
    } catch (_) { /* Page-only use is already disclosed. */ }
    return true;
  }

  function syncSelected() {
    selected = new Set([...decisions].filter(([id, value]) => value === "correct" && !applied.has(id)).map(([id]) => id));
  }

  function saveDraft() {
    draftSaved = false;
    if (!currentDraft()) return;
    try {
      if (window.localStorage) {
        const serialized = JSON.stringify({
          version: 2,
          decisions: Object.fromEntries(decisions),
          corrections: Object.fromEntries(corrections),
          completed_review: completedReview,
          legacy_draft: legacyDraft,
          reuse_confirmed_faces: el("reuse-confirmed-faces").checked,
        });
        window.localStorage.setItem(draftKey(), serialized);
        draftRevision = serialized;
        draftSaved = true;
      }
    } catch (_) { /* The visible status discloses a page-only draft. */ }
  }

  function selectionPayload() {
    const payload = {
      report_id: report.id,
      report_sha256: report.content_sha256,
      accepted_ids: [...decisions].filter(([, state]) => state === "correct").map(([id]) => id).sort(),
      decisions: Object.fromEntries([...decisions].sort()),
      completed_review: completedReview,
      reuse_confirmed_faces: el("reuse-confirmed-faces").checked,
    };
    if (corrections.size) payload.corrections = Object.fromEntries([...corrections].sort());
    return payload;
  }

  function reviewStatus(message, error = false) {
    if (message) notice = {message, error};
    const target = el("match-review-status");
    const count = state => [...decisions.values()].filter(value => value === state).length;
    target.textContent = notice?.message || `${count("correct")} Correct · ${count("incorrect")} Incorrect · ${count("unsure")} Unsure${corrections.size ? ` · ${corrections.size} reassigned to the right person` : ""}${count("not_accepted") ? ` · ${count("not_accepted")} earlier review: not accepted` : ""}. ${applied.size} faces already applied. ${draftSaved ? "Draft saved in this browser." : "Draft kept on this page only."}`;
    target.className = notice?.error ? "match-error" : "";
    el("preview-face-matches").disabled = busy || !decisions.size;
    el("clear-face-selections").disabled = busy || !decisions.size;
    el("legacy-face-review").hidden = !legacyDraft || completedReview;
    el("complete-legacy-review").disabled = busy;
    el("reuse-confirmed-faces").disabled = busy || receipts.some(r => r.status === "applied" && r.review.reuse_confirmed_faces);
  }

  function invalidatePreview() {
    preview = null;
    el("face-match-preview").hidden = true;
  }

  const personName = id => report?.people.find(p => p.id === id)?.display_name || "another saved person";

  function formatDecisionNote(record, topName) {
    const isApplied = applied.has(record.id);
    const decision = decisions.get(record.id);
    const chosen = corrections.get(record.id);
    const notes = {
      correct: `Correct: ${topName}`,
      incorrect: chosen ? `Incorrect: this is ${personName(chosen)}, not ${topName}` : `Incorrect: this is not ${topName}`,
      unsure: `Unsure whether this is ${topName}`,
      not_accepted: "Reviewed in the earlier batch, not accepted. Wrong versus uncertain was not recorded.",
    };
    return `${notes[decision] || "Not reviewed yet."}${isApplied ? " · Applied. Undo the saved review to change it." : decision && decision !== "not_accepted" ? " · Draft, not applied." : ""}`;
  }

  function choose(record, decision) {
    if (busy || applied.has(record.id) || !currentDraft()) return;
    notice = null;
    decisions.set(record.id, decision);
    syncSelected();
    if (decision !== "incorrect") corrections.delete(record.id);
    invalidatePreview();
    saveDraft();
    render();
  }

  function assign(record, personId, inPlaceNoteUpdater) {
    if (busy || applied.has(record.id) || decisions.get(record.id) !== "incorrect" || !currentDraft()) return;
    notice = null;
    if (personId) corrections.set(record.id, personId);
    else corrections.delete(record.id);
    invalidatePreview();
    saveDraft();
    // Update card note + global status in-place so the open <select> is never destroyed mid-selection.
    if (typeof inPlaceNoteUpdater === "function") {
      inPlaceNoteUpdater();
      reviewStatus();
    } else {
      render();
    }
  }

  function assignRecordToPerson(record, personId) {
    if (!record || applied.has(record.id)) return false;
    const topId = record.candidates?.[0]?.person_id;
    if (!topId) return false;
    if (topId === personId) {
      decisions.set(record.id, "correct");
      corrections.delete(record.id);
    } else {
      decisions.set(record.id, "incorrect");
      corrections.set(record.id, personId);
    }
    return true;
  }

  function refreshPersonFilterOptions() {
    if (!report) return;
    const previous = person.value;
    person.replaceChildren(
      new Option("Everyone", ""),
      ...report.people.map(p => new Option(p.display_name, p.id)),
      new Option("Unidentified", "unknown")
    );
    if (previous && (previous === "unknown" || report.people.some(p => p.id === previous))) {
      person.value = previous;
    }
  }

  function normalizeMatchPersonKey(value) {
    return String(value || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  }

  function matchLevenshtein(a, b) {
    if (a === b) return 0;
    if (!a.length) return b.length;
    if (!b.length) return a.length;
    const prev = Array.from({length: b.length + 1}, (_, j) => j);
    for (let i = 1; i <= a.length; i += 1) {
      let prevDiag = prev[0];
      prev[0] = i;
      for (let j = 1; j <= b.length; j += 1) {
        const temp = prev[j];
        prev[j] = Math.min(prev[j] + 1, prev[j - 1] + 1, prevDiag + (a[i - 1] === b[j - 1] ? 0 : 1));
        prevDiag = temp;
      }
    }
    return prev[b.length];
  }

  function findLocalNearDuplicate(rawName) {
    const norm = normalizeMatchPersonKey(rawName);
    if (!norm || norm.length < 3) return null;
    let best = null;
    let bestDist = Infinity;
    for (const p of (report?.people || [])) {
      const cNorm = normalizeMatchPersonKey(p.display_name);
      if (!cNorm || cNorm === norm) continue;
      const minLen = Math.min(norm.length, cNorm.length);
      const maxAllowed = minLen >= 6 ? 2 : 1;
      if (Math.abs(norm.length - cNorm.length) > maxAllowed) continue;
      const dist = matchLevenshtein(norm, cNorm);
      if (dist <= maxAllowed && dist < bestDist) {
        bestDist = dist;
        best = p;
      }
    }
    return best;
  }

  function slugifyPersonId(displayName) {
    const base = String(displayName || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "person";
    const bridgePeople = (typeof window !== "undefined" && window.GoodQIdentityPeople && typeof window.GoodQIdentityPeople.getKnownPeople === "function")
      ? window.GoodQIdentityPeople.getKnownPeople()
      : [];
    const existingIds = new Set([
      ...(report?.people || []).map(p => p.id),
      ...bridgePeople.map(p => p.id),
    ]);
    if (!existingIds.has(base)) return base;
    let suffix = 2;
    while (existingIds.has(`${base}_${suffix}`)) suffix += 1;
    return `${base}_${suffix}`;
  }

  async function createRosterPersonInline(displayName, roleText) {
    const trimmed = String(displayName || "").trim();
    if (!trimmed) throw new Error("Enter a display name for the new person.");
    const existing = (report?.people || []).find(
      p => normalizeMatchPersonKey(p.display_name) === normalizeMatchPersonKey(trimmed)
    );
    if (existing) return existing;

    const bridge = (typeof window !== "undefined" && window.GoodQIdentityPeople) ? window.GoodQIdentityPeople : null;
    let known = bridge && typeof bridge.resolvePerson === "function" ? bridge.resolvePerson(trimmed) : null;
    if (!known) {
      const near = (bridge && typeof bridge.findNearDuplicate === "function" ? bridge.findNearDuplicate(trimmed) : null)
        || findLocalNearDuplicate(trimmed);
      if (near && typeof window !== "undefined" && typeof window.confirm === "function") {
        const useNear = window.confirm(
          `"${trimmed}" looks very close to already-saved person "${near.display_name}".\n\n` +
          `Click OK to use "${near.display_name}" (prevents duplicate entries), or Cancel to create "${trimmed}" as a separate new person.`
        );
        if (useNear) {
          const alreadyListed = (report?.people || []).find(p => p.id === near.id || normalizeMatchPersonKey(p.display_name) === normalizeMatchPersonKey(near.display_name));
          if (alreadyListed) return alreadyListed;
          known = near;
        }
      }
    }

    const canonicalName = known ? known.display_name : trimmed;
    const alreadyInReport = (report?.people || []).find(
      p => (known && p.id === known.id) || normalizeMatchPersonKey(p.display_name) === normalizeMatchPersonKey(canonicalName)
    );
    if (alreadyInReport) return alreadyInReport;

    const newId = (known && known.id && !(report?.people || []).some(p => p.id === known.id))
      ? known.id
      : slugifyPersonId(canonicalName);
    const aliases = known && Array.isArray(known.aliases) ? [...known.aliases] : [];
    const identity = {
      id: newId,
      display_name: canonicalName,
      aliases,
      face_cluster_ids: [],
      speaker_cluster_ids: [],
      name_mention_keys: Array.from(new Set([canonicalName, ...aliases])),
      role: String(roleText || "").trim() || (known && known.role ? known.role : ""),
      notes: "Added inline from Match Review; edit full profile in Family Roster.",
      confirmed: false,
    };
    const saved = await confirmedRequest(
      "/api/identity/roster/save",
      {identity},
      `Add "${canonicalName}" to this movie's Family Roster? You can fill in aliases and relationships later in the Family Roster tab.`
    );
    if (!saved) return null;
    const entry = {id: newId, display_name: canonicalName};
    report.people.push(entry);
    refreshPersonFilterOptions();
    try {
      if (typeof window.dispatchEvent === "function" && typeof CustomEvent === "function") {
        window.dispatchEvent(new CustomEvent("goodq:roster-updated", {detail: {identity}}));
      }
    } catch (_) {}
    return entry;
  }

  function setBusy(value) {
    busy = value;
    [kind, layoutSelect, person, result, reportSelect, el("matches-review"), el("reload-matches"), el("refresh-prior-matches"), el("more-matches")].forEach(control => {
      if (control) control.disabled = value;
    });
    document.querySelectorAll(".match-review-actions button, .match-correction select, .match-preview button, .match-history-row button").forEach(button => {
      button.disabled = value || button.dataset.locked === "true";
    });
    reviewStatus();
  }

  async function confirmedRequest(endpoint, payload, question) {
    try { return await post(endpoint, payload); }
    catch (error) {
      const token = error.body?.result?.confirmation_token;
      if (error.status !== 403 || !token) throw error;
      if (!window.confirm(question)) return null;
      return post(endpoint, {...payload, confirmation_token: token});
    }
  }

  function renderHistory() {
    const historyList = el("face-match-history");
    historyList.replaceChildren();
    receipts.forEach(receipt => {
      const row = node("div", null, "match-history-row");
      row.append(node("span", `${receipt.status === "applied" ? "Applied" : "Undone"}: ${receipt.summary.observations} confirmed faces across ${receipt.summary.scenes} scenes${receipt.summary.corrected ? ` (${receipt.summary.corrected} reassigned to the right person)` : ""}; ${receipt.summary.reusable_faces || 0} reusable examples.${receipt.summary.decisions ? ` Decisions: ${Object.entries(receipt.summary.decisions).map(([state, n]) => `${n} ${decisionNames[state]}`).join(" · ")}.` : ""}`));
      if (receipt.status === "applied") {
        const undo = node("button", "Undo this review", "toolbar-btn");
        undo.addEventListener("click", async () => {
          if (busy) return;
          setBusy(true);
          try {
            const outcome = await confirmedRequest(
              "/api/identity/appearances/undo",
              {receipt_id: receipt.id, receipt_sha256: receipt.receipt_sha256},
              "Undo this receipt's decisions, added scene links and reusable examples? Labels and movies stay intact. Later changes will stop Undo."
            );
            if (outcome) await loadReport(report.id);
            reviewStatus(outcome ? "Links undone. Your labels and movies are unchanged." : "Undo cancelled. Saved links are unchanged.");
          } catch (error) { reviewStatus(error.message, true); }
          finally { setBusy(false); render(); }
        });
        row.append(undo);
      }
      historyList.append(row);
    });
  }

  async function previewSelection() {
    if (busy || !decisions.size || !report || !currentDraft()) return;
    notice = null;
    setBusy(true);
    invalidatePreview();
    try {
      const value = await post("/api/identity/matches/preview", selectionPayload());
      preview = value;
      const panel = el("face-match-preview");
      panel.replaceChildren();
      panel.hidden = false;
      panel.append(
        node("h2", "Preview · nothing new applied"),
        node("p", `${quantity(value.summary.observations, "confirmed face observation")} for ${quantity(value.summary.people, "person", "people")} in ${quantity(value.summary.scenes, "scene")}.`)
      );
      if (value.summary.decisions) panel.append(node("p", Object.entries(value.summary.decisions).map(([state, n]) => `${n} ${decisionNames[state]}`).join(" · ")));
      if (value.summary.corrected) panel.append(node("p", `${quantity(value.summary.corrected, "Incorrect face")} will be linked to the person you chose instead.`));
      panel.append(node("p", `${value.summary.reusable_faces || 0} confirmed faces will be reusable reference examples after Apply. Incorrect rejects only the displayed person; a face you reassigned is linked only to the person you chose. Unsure stays unresolved and never becomes a reference. All voices and mentions remain held.`));
      if (value.summary.decisions?.not_accepted) panel.append(node("p", "Your completed earlier review is preserved: these remaining pairings were mostly incorrect. The old controls did not record which were uncertain, so they remain reviewed, not accepted. You do not need to repeat the batch."));
      const records = new Map(report.records.map(r => [r.id, r]));
      value.appearances.forEach(link => {
        const row = node("div", null, "match-preview-row");
        row.append(node("h3", `${link.display_name} · ${stamp(link.scene_start)} – ${stamp(link.scene_end)}`));
        const evidence = node("div", null, "match-preview-evidence");
        [...link.evidence].sort((a, b) => a.timestamp - b.timestamp).forEach(item => {
          evidence.append(mediaView(records.get(item.evidence_id).media, item.assignment === "human_corrected" ? `Reassigned to ${link.display_name}` : `Selected as ${link.display_name}`));
        });
        row.append(evidence);
        panel.append(row);
      });
      panel.append(node("p", "Apply saves the review decisions, these appearance links and the approved reusable examples. Existing labels and source movies are preserved. Undo remains available."));
      const apply = node("button", "Apply review and confirmed faces", "toolbar-btn match-apply");
      apply.disabled = !value.summary.new_edges && !value.summary.updated_edges && !value.review_changed;
      apply.dataset.locked = String(apply.disabled);
      apply.addEventListener("click", applySelection);
      panel.append(apply);
      const back = node("button", "Keep reviewing", "toolbar-btn");
      back.addEventListener("click", invalidatePreview);
      panel.append(back);
      panel.scrollIntoView?.({block: "start"});
    } catch (error) { reviewStatus(error.message, true); }
    finally { setBusy(false); }
  }

  async function applySelection() {
    if (busy || !preview || !currentDraft()) return;
    const plan = preview;
    setBusy(true);
    try {
      const outcome = await confirmedRequest(
        "/api/identity/appearances/apply",
        {plan_sha256: plan.plan_sha256, match_review: plan.review},
        `Save this review, ${plan.summary.observations} confirmed observations${plan.summary.corrected ? ` (${plan.summary.corrected} reassigned)` : ""} across ${plan.summary.scenes} scenes, and ${plan.summary.reusable_faces || 0} reusable examples? Rejected people, Unsure and earlier not-accepted faces receive no identity links. Voices and mentions remain held.`
      );
      if (!outcome) { reviewStatus("Apply cancelled. Your draft and preview remain available."); return; }
      invalidatePreview();
      await loadReport(report.id);
      reviewStatus("Review and confirmed faces saved. You can undo this receipt above.");
    } catch (error) {
      invalidatePreview();
      reviewStatus(`${error.message} Reload history before trying again.`, true);
    } finally { setBusy(false); render(); }
  }

  function pauseClips() {
    document.querySelectorAll("#panel-matches audio").forEach(audio => audio.pause());
  }

  function mediaView(media, caption, compact = false) {
    const figure = node("figure", null, compact ? "match-media compact" : "match-media");
    if (media.kind === "image") {
      const boxW = compact ? 112 : 180, boxH = compact ? 106 : 170, targetSpan = compact ? 92 : 150;
      const crop = node("div", null, compact ? "match-crop compact" : "match-crop");
      const img = document.createElement("img");
      img.alt = caption;
      img.loading = "lazy";
      img.src = window.GoodQLibrary?.url(media.url) || media.url;
      img.addEventListener("load", () => {
        const box = media.bbox;
        if (!Array.isArray(box) || box.length !== 4) return;
        const [x1, y1, x2, y2] = box;
        const width = x2 - x1, height = y2 - y1;
        if (width <= 0 || height <= 0) return;
        const scale = targetSpan / Math.max(width, height);
        img.style.width = `${img.naturalWidth * scale}px`;
        img.style.height = `${img.naturalHeight * scale}px`;
        img.style.left = `${(boxW - width * scale) / 2 - x1 * scale}px`;
        img.style.top = `${(boxH - height * scale) / 2 - y1 * scale}px`;
      });
      img.addEventListener("error", () => { crop.replaceChildren(node("span", "Source image unavailable")); });
      crop.append(img);
      figure.append(crop);
    } else {
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.preload = "none";
      audio.src = `${window.GoodQLibrary?.url(media.url) || media.url}#t=${media.start},${media.end}`;
      audio.setAttribute("aria-label", caption);
      audio.addEventListener("play", () => {
        document.querySelectorAll("#panel-matches audio").forEach(other => { if (other !== audio) other.pause(); });
        if (audio.currentTime < media.start || audio.currentTime >= media.end) audio.currentTime = media.start;
      });
      audio.addEventListener("timeupdate", () => { if (audio.currentTime >= media.end) audio.pause(); });
      figure.append(audio);
    }
    figure.append(node("figcaption", `${caption} · ${stamp(media.timestamp)}`));
    return figure;
  }

  function referenceName(reference) {
    if (reference.display_name) return reference.display_name;
    return `Unidentified voice ${report.references.filter(r => r.media.kind === "audio").findIndex(r => r.id === reference.id) + 1}`;
  }

  function buildInlineNewPersonForm(onCreated, onCancel) {
    const wrap = node("div", null, "match-inline-new-person");
    const title = node("p", "Add a new person to this movie's roster (fill out aliases & relationships later):", "match-inline-title");
    const row = node("div", null, "match-inline-fields");
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.className = "mini-input wide";
    nameInput.placeholder = "Person's display name (e.g. Uncle Frank)…";
    nameInput.setAttribute("aria-label", "New person display name");
    const roleInput = document.createElement("input");
    roleInput.type = "text";
    roleInput.className = "mini-input";
    roleInput.placeholder = "Role (optional)…";
    roleInput.setAttribute("aria-label", "Family role (optional)");
    const saveBtn = node("button", "Add & Assign", "toolbar-btn match-apply");
    saveBtn.type = "button";
    const cancelBtn = node("button", "Cancel", "toolbar-btn secondary");
    cancelBtn.type = "button";
    const feedback = node("p", "", "match-inline-feedback");
    feedback.hidden = true;

    async function submit() {
      if (busy || !currentDraft()) return;
      const enteredName = (nameInput.value || "").trim();
      if (!enteredName) {
        feedback.textContent = "Enter a name first.";
        feedback.hidden = false;
        return;
      }
      feedback.hidden = true;
      setBusy(true);
      try {
        const entry = await createRosterPersonInline(enteredName, roleInput.value);
        if (!entry) {
          feedback.textContent = "Roster addition cancelled.";
          feedback.hidden = false;
          return;
        }
        await onCreated(entry);
      } catch (err) {
        feedback.textContent = err.message || "Could not save person.";
        feedback.hidden = false;
      } finally {
        setBusy(false);
      }
    }

    nameInput.addEventListener("keydown", ev => {
      if (ev.key === "Enter" && !ev.isComposing && ev.keyCode !== 229) {
        ev.preventDefault?.();
        submit();
      } else if (ev.key === "Escape") {
        onCancel();
      }
    });
    roleInput.addEventListener("keydown", ev => {
      if (ev.key === "Enter" && !ev.isComposing && ev.keyCode !== 229) {
        ev.preventDefault?.();
        submit();
      }
    });
    saveBtn.addEventListener("click", submit);
    cancelBtn.addEventListener("click", onCancel);
    row.append(nameInput, roleInput, saveBtn, cancelBtn);
    wrap.append(title, row, feedback);
    return {wrap, focus: () => nameInput.focus?.()};
  }

  async function renderCrossFilmDrawer(drawer, record, assignedPersonId) {
    drawer.hidden = false;
    drawer.replaceChildren(node("p", "Scanning embeddings across this movie and your other films…", "match-secondary"));
    const cacheKey = `${report.id}:${record.id}`;
    try {
      let data = scanCache.get(cacheKey);
      if (!data) {
        data = await read(`/api/identity/cross-film-scan?report_id=${encodeURIComponent(report.id)}&evidence_id=${encodeURIComponent(record.id)}&min_similarity=0.50`);
        scanCache.set(cacheKey, data);
      }
      drawer.replaceChildren();
      const header = node("div", null, "cross-film-header");
      header.append(
        node("strong", "Cross-film & same-movie face analysis"),
        node("span", `Min similarity ${data.min_similarity.toFixed(2)}`, "match-state")
      );
      const closeBtn = node("button", "Hide scan", "toolbar-btn secondary");
      closeBtn.type = "button";
      closeBtn.addEventListener("click", () => {
        openScanIds.delete(record.id);
        drawer.hidden = true;
      });
      header.append(closeBtn);
      drawer.append(header);

      // 1) Same-film matches with 1-click batch draft assignment
      const sameHits = (data.current_movie?.matches || []).filter(m => m.evidence_id && m.evidence_id !== record.id);
      const sameSection = node("div", null, "cross-film-section");
      if (sameHits.length) {
        const targetPid = assignedPersonId || (decisions.get(record.id) === "incorrect" ? corrections.get(record.id) : decisions.get(record.id) === "correct" ? record.candidates?.[0]?.person_id : null);
        const assignableRecords = sameHits
          .map(h => report.records.find(r => r.id === h.evidence_id))
          .filter(r => r && !applied.has(r.id) && r.candidates?.[0]?.person_id);
        sameSection.append(node("p", `In this movie (${data.current_movie.video_name}): ${quantity(sameHits.length, "visually similar face")} across ${quantity(data.current_movie.scene_count, "scene")}.`, "cross-film-subtitle"));
        if (targetPid && assignableRecords.length) {
          const targetName = personName(targetPid);
          const batchBtn = node("button", `Also assign ${quantity(assignableRecords.length, "matching face")} in this film to ${targetName}`, "toolbar-btn match-apply");
          batchBtn.type = "button";
          batchBtn.addEventListener("click", () => {
            if (busy || !currentDraft()) return;
            let count = 0;
            assignableRecords.forEach(r => {
              if (assignRecordToPerson(r, targetPid)) count += 1;
            });
            syncSelected();
            invalidatePreview();
            saveDraft();
            render();
            reviewStatus(`Assigned ${count} visually similar ${count === 1 ? "face" : "faces"} in this film to ${targetName} (draft).`);
          });
          sameSection.append(batchBtn);
        }
        const strip = node("div", null, "cross-film-strip");
        sameHits.slice(0, 8).forEach(hit => {
          strip.append(mediaView({kind: "image", url: hit.media_url, bbox: hit.bbox, timestamp: hit.timestamp}, `Sim ${hit.similarity.toFixed(3)}`, true));
        });
        sameSection.append(strip);
      } else {
        sameSection.append(node("p", "No other visually matching shots above 0.50 in this movie.", "match-secondary"));
      }
      drawer.append(sameSection);

      // 2) Other movies retroactive scan
      const otherMovies = data.other_movies || [];
      if (!otherMovies.length) {
        drawer.append(node("p", "No prior films configured for cross-film comparison.", "match-secondary"));
        return;
      }
      const anyOtherHits = otherMovies.some(m => m.matches && m.matches.length);
      if (!anyOtherHits) {
        drawer.append(node("p", `Scanned ${quantity(otherMovies.length, "other movie")} (${otherMovies.map(m => m.video_name).join(", ")}) — no appearances above ${data.min_similarity.toFixed(2)} similarity.`, "match-secondary"));
        return;
      }
      otherMovies.filter(m => m.matches && m.matches.length).forEach(movie => {
        const block = node("div", null, "cross-film-movie-block");
        const missedNote = movie.missed_unlabeled_count
          ? ` · ${quantity(movie.missed_unlabeled_count, "unlabeled / missed appearance")} spotted!`
          : " · all matches already labeled";
        block.append(node("p", `Also spotted in ${movie.video_name}: ${quantity(movie.total_matches, "appearance")} across ${quantity(movie.scene_count, "scene")}${missedNote}`, "cross-film-movie-title"));
        const strip = node("div", null, "cross-film-strip");
        movie.matches.forEach(hit => {
          const badge = hit.missed
            ? "Unlabeled in that film"
            : `Labeled: ${hit.existing_names.join(", ") || hit.cluster_label || "cluster"}`;
          const cell = node("div", null, hit.missed ? "cross-film-hit missed" : "cross-film-hit");
          cell.append(
            mediaView({kind: "image", url: hit.media_url, bbox: hit.bbox, timestamp: hit.timestamp}, `${badge} · ${hit.similarity.toFixed(3)}`, true),
            node("span", badge, hit.missed ? "cross-film-badge missed" : "cross-film-badge")
          );
          strip.append(cell);
        });
        block.append(strip);
        drawer.append(block);
      });
    } catch (err) {
      drawer.replaceChildren(node("p", `Cross-film scan failed: ${err.message}`, "match-error"));
    }
  }

  function renderRecordCard(record, refs) {
    const top = record.candidates[0], reference = top && refs.get(top.reference_id);
    const card = node("article", null, "match-card");
    card.dataset.matchId = record.id;
    const heading = node("div", null, "match-card-heading");
    const title = record.status === "proposed" && top?.display_name ? `Possible ${top.display_name}`
      : record.status === "ambiguous" ? "Uncertain match"
      : kind.value === "voice" ? "Unidentified speaker" : "Unidentified face";
    heading.append(
      node("h2", title),
      node("span", labels[record.status] || record.status, `match-state ${record.status}`)
    );
    card.append(heading);

    const pair = node("div", null, "match-pair");
    pair.append(mediaView(record.media, `New ${kind.value === "face" ? "observation" : "voice clip"}`));
    if (reference) pair.append(mediaView(reference.media, `Reference: ${referenceName(reference)}`));
    card.append(pair);

    let scanDrawer = null;
    if (record.modality === "face" && top?.person_id && reference) {
      const isApplied = applied.has(record.id), decision = decisions.get(record.id);
      const controls = node("div", null, "match-review-actions");
      controls.setAttribute("role", "group");
      controls.setAttribute("aria-label", `Is this ${top.display_name}?`);
      ["correct", "incorrect", "unsure"].forEach(state => {
        const button = node("button", decisionNames[state], "toolbar-btn");
        button.dataset.decision = state;
        button.setAttribute("aria-pressed", String(decision === state));
        button.disabled = busy || isApplied;
        button.dataset.locked = String(isApplied);
        button.addEventListener("click", () => choose(record, state));
        controls.append(button);
      });

      const questionCopy = record.status === "no_match"
        ? `Below match threshold (closest saved reference: ${top.display_name}, ${top.similarity.toFixed(3)}). Is this ${top.display_name} or someone else?`
        : `Is this ${top.display_name}?`;
      const noteEl = node("p", formatDecisionNote(record, top.display_name), "match-review-note");
      card.append(node("p", questionCopy, "match-review-question"), controls, noteEl);

      const inlineFormHost = node("div", null, "match-inline-host");
      inlineFormHost.hidden = true;
      scanDrawer = node("div", null, "cross-film-drawer");
      scanDrawer.hidden = true;

      const openInlineNewPerson = () => {
        if (busy || isApplied) return;
        const built = buildInlineNewPersonForm(
          async entry => {
            decisions.set(record.id, "incorrect");
            corrections.set(record.id, entry.id);
            syncSelected();
            invalidatePreview();
            saveDraft();
            openScanIds.add(record.id);
            render();
            reviewStatus(`Added "${entry.display_name}" to Family Roster and assigned this face (draft). Scanning across films…`);
          },
          () => {
            inlineFormHost.replaceChildren();
            inlineFormHost.hidden = true;
          }
        );
        inlineFormHost.replaceChildren(built.wrap);
        inlineFormHost.hidden = false;
        built.focus();
      };

      const others = report.people.filter(p => p.id !== top.person_id);
      const chosen = corrections.get(record.id);
      if (decision === "incorrect" && others.length) {
        // Explicit sibling <label for="..."> + <div class="match-correction"><select> prevents
        // Windows Chromium <label> click-forwarding from snapping the native dropdown shut.
        const selectId = `match-correction-${record.id}`;
        const labelEl = node("label", "Who is this instead?", "match-correction-label");
        labelEl.setAttribute("for", selectId);
        const correctionWrap = node("div", null, "match-correction");
        const pick = document.createElement("select");
        pick.id = selectId;
        pick.append(new Option("Leave unassigned", ""), ...others.map(p => new Option(p.display_name, p.id)));
        pick.value = chosen || "";
        pick.disabled = busy || isApplied;
        pick.dataset.locked = String(isApplied);
        pick.addEventListener("change", () => {
          assign(record, pick.value, () => {
            noteEl.textContent = formatDecisionNote(record, top.display_name);
          });
        });
        correctionWrap.append(pick);
        if (!isApplied) {
          const addNotListed = node("button", "+ New person (not in list)…", "toolbar-btn secondary match-add-person-btn");
          addNotListed.type = "button";
          addNotListed.addEventListener("click", openInlineNewPerson);
          correctionWrap.append(addNotListed);
        }
        card.append(labelEl, correctionWrap);
      }

      if (!isApplied) {
        const quickActions = node("div", null, "match-quick-actions");
        const newPersonBtn = node("button", "+ New person…", "toolbar-btn secondary");
        newPersonBtn.type = "button";
        newPersonBtn.addEventListener("click", openInlineNewPerson);
        const scanBtn = node("button", "Scan across films", "toolbar-btn secondary");
        scanBtn.type = "button";
        scanBtn.addEventListener("click", () => {
          openScanIds.add(record.id);
          renderCrossFilmDrawer(scanDrawer, record);
        });
        quickActions.append(newPersonBtn, scanBtn);
        card.append(quickActions, inlineFormHost, scanDrawer);
      } else {
        const quickActions = node("div", null, "match-quick-actions");
        const scanBtn = node("button", "Scan across films", "toolbar-btn secondary");
        scanBtn.type = "button";
        scanBtn.addEventListener("click", () => {
          openScanIds.add(record.id);
          renderCrossFilmDrawer(scanDrawer, record, savedCorrections.get(record.id) || top.person_id);
        });
        quickActions.append(scanBtn);
        card.append(quickActions, scanDrawer);
      }

      if (openScanIds.has(record.id)) {
        renderCrossFilmDrawer(scanDrawer, record);
      }
    }

    if (top) card.append(node("p", `Similarity ${top.similarity.toFixed(3)}${record.margin == null ? "" : ` · Lead over next candidate ${record.margin.toFixed(3)}`}.`));
    if (record.candidates[1]) {
      const other = record.candidates[1], ref = refs.get(other.reference_id);
      card.append(node("p", `Next candidate: ${other.display_name || (ref ? referenceName(ref) : "unidentified")} · ${other.similarity.toFixed(3)}`, "match-secondary"));
    }
    if (record.hold_reason) card.append(node("p", "Multiple observations compete for the same identity here. Held for review.", "match-secondary"));
    card.append(node("p", `${report.video_name} · ${stamp(record.scene_start)} – ${stamp(record.scene_end)}`, "match-secondary"));
    const watch = node("a", "Watch this scene", "toolbar-btn match-watch");
    watch.href = `/ui/retro_console_v1/?${new URLSearchParams({
      watch_match: report.id,
      watch_evidence: record.id,
      watch_scene: record.scene_id,
      watch_video: report.video_id,
      watch_epoch: report.epoch_id,
    })}`;
    if (window.GoodQLibrary) watch.href = window.GoodQLibrary.url(watch.href);
    watch.addEventListener("click", pauseClips);
    card.append(watch);
    return card;
  }

  async function ensureVisualGroupsLoaded() {
    if (!report) return null;
    if (visualGroupsCache.has(report.id)) return visualGroupsCache.get(report.id);
    status.textContent = "Grouping visually similar faces in this movie…";
    const data = await read(`/api/identity/matches/${encodeURIComponent(report.id)}/visual-groups?min_similarity=0.58`);
    visualGroupsCache.set(report.id, data);
    status.textContent = `${report.video_name}: grouped into ${data.multi_face_group_count} recurring face clusters and ${data.singleton_count} singletons.`;
    return data;
  }

  function renderVisualClustersView(filteredRecords, refs) {
    const cached = visualGroupsCache.get(report.id);
    if (!cached) {
      list.append(node("p", "Grouping faces by visual similarity…", "match-secondary"));
      ensureVisualGroupsLoaded()
        .then(() => render())
        .catch(err => {
          if (layoutSelect) layoutSelect.value = "cards";
          reviewStatus(`Visual grouping failed: ${err.message}`, true);
          render();
        });
      return;
    }

    const visibleSet = new Set(filteredRecords.map(r => r.id));
    const recMap = new Map(report.records.map(r => [r.id, r]));
    const visibleGroups = cached.groups
      .map(g => ({...g, visibleMembers: g.record_ids.map(id => recMap.get(id)).filter(r => r && visibleSet.has(r.id))}))
      .filter(g => g.visibleMembers.length > 0);

    if (!visibleGroups.length) {
      list.append(node("p", "No visual clusters match these filters."));
      el("more-matches").hidden = true;
      return;
    }

    visibleGroups.slice(0, limit).forEach((group, idx) => {
      const members = group.visibleMembers;
      const editable = members.filter(r => !applied.has(r.id) && r.candidates?.[0]?.person_id);
      const card = node("article", null, "match-card match-cluster-card");
      const heading = node("div", null, "match-card-heading");
      const titleText = group.member_count > 1
        ? `Visual Cluster #${idx + 1} · ${quantity(members.length, "face")} across ${quantity(group.scene_count, "scene")}`
        : `Single appearance · ${stamp(members[0].media.timestamp)}`;
      const assignedNames = [...new Set(members.map(r => {
        if (decisions.get(r.id) === "correct") return r.candidates?.[0]?.display_name;
        if (decisions.get(r.id) === "incorrect" && corrections.get(r.id)) return personName(corrections.get(r.id));
        return null;
      }).filter(Boolean))];
      heading.append(
        node("h2", titleText),
        node("span", assignedNames.length ? `Draft: ${assignedNames.join(", ")}` : `${group.unmatched_count} unmatched`, assignedNames.length ? "match-state proposed" : "match-state no_match")
      );
      card.append(heading);

      const strip = node("div", null, "cross-film-strip");
      members.slice(0, 8).forEach(member => {
        strip.append(mediaView(member.media, `Scene ${stamp(member.scene_start)}`, true));
      });
      card.append(strip);

      const inlineHost = node("div", null, "match-inline-host");
      inlineHost.hidden = true;
      const scanDrawer = node("div", null, "cross-film-drawer");
      scanDrawer.hidden = true;

      if (editable.length) {
        const actionRow = node("div", null, "match-cluster-actions");
        const selectId = `cluster-assign-${group.group_id}`;
        const pickLabel = node("label", "Assign whole cluster to:", "match-correction-label");
        pickLabel.setAttribute("for", selectId);
        const pick = document.createElement("select");
        pick.id = selectId;
        pick.className = "cluster-assign-select";
        pick.append(new Option("Choose saved person…", ""), ...report.people.map(p => new Option(p.display_name, p.id)));
        const assignBtn = node("button", `Assign ${quantity(editable.length, "face")}`, "toolbar-btn match-apply");
        assignBtn.type = "button";
        assignBtn.addEventListener("click", () => {
          if (busy || !pick.value || !currentDraft()) return;
          editable.forEach(r => assignRecordToPerson(r, pick.value));
          syncSelected();
          invalidatePreview();
          saveDraft();
          render();
          reviewStatus(`Assigned ${quantity(editable.length, "face")} in ${group.group_id} to ${personName(pick.value)} (draft).`);
        });

        const newPersonBtn = node("button", "+ New person for cluster…", "toolbar-btn secondary");
        newPersonBtn.type = "button";
        newPersonBtn.addEventListener("click", () => {
          const built = buildInlineNewPersonForm(
            async entry => {
              editable.forEach(r => assignRecordToPerson(r, entry.id));
              syncSelected();
              invalidatePreview();
              saveDraft();
              openScanIds.add(members[0].id);
              render();
              reviewStatus(`Added "${entry.display_name}" and assigned ${quantity(editable.length, "face")} in this visual cluster (draft).`);
            },
            () => {
              inlineHost.replaceChildren();
              inlineHost.hidden = true;
            }
          );
          inlineHost.replaceChildren(built.wrap);
          inlineHost.hidden = false;
          built.focus();
        });

        const scanBtn = node("button", "Scan across films", "toolbar-btn secondary");
        scanBtn.type = "button";
        scanBtn.addEventListener("click", () => {
          openScanIds.add(members[0].id);
          renderCrossFilmDrawer(scanDrawer, members[0]);
        });

        actionRow.append(pickLabel, pick, assignBtn, newPersonBtn, scanBtn);
        card.append(actionRow, inlineHost, scanDrawer);
      }

      if (openScanIds.has(members[0].id)) {
        renderCrossFilmDrawer(scanDrawer, members[0]);
      }

      const details = node("details", null, "match-cluster-members");
      details.append(node("summary", `Inspect or override individual observations (${members.length})`));
      const innerList = node("div", null, "match-list");
      members.forEach(member => innerList.append(renderRecordCard(member, refs)));
      details.append(innerList);
      card.append(details);
      list.append(card);
    });
    el("more-matches").hidden = visibleGroups.length <= limit;
  }

  function render() {
    pauseClips();
    list.replaceChildren();
    const callout = el("matches-cluster-callout");
    if (callout) {
      callout.replaceChildren();
      callout.hidden = true;
    }
    if (!report) return;
    const refs = new Map(report.references.map(r => [r.id, r]));
    const records = report.records.filter(r => r.modality === kind.value && (!result.value || r.status === result.value)
      && (!el("matches-review").value || (decisions.get(r.id) || "unreviewed") === el("matches-review").value)
      && (!person.value || (person.value === "unknown"
        ? r.status !== "proposed" || !r.candidates[0]?.person_id
        : r.candidates[0]?.person_id === person.value)));
    const counts = report.summary[kind.value] || {};
    el("matches-summary").textContent = `${report.people.length} saved people · ${records.length} ${records.length === 1 ? "observation" : "observations"} in this view · ${counts.proposed || 0} proposed, ${counts.ambiguous || 0} uncertain in this film. ${applied.size ? `${applied.size} face observations applied after review.` : "None applied."}`;
    reviewStatus();
    el("phase-indicator").textContent = receipts.some(r => r.status === "applied") ? "MATCH REVIEW · REVIEW SAVED" : "MATCH REVIEW · NOTHING APPLIED";

    const useClusters = kind.value === "face" && layoutSelect && layoutSelect.value === "clusters";
    if (callout && kind.value === "face" && (counts.no_match || 0) >= 3 && !useClusters) {
      callout.hidden = false;
      callout.append(
        node("span", `${counts.no_match} faces in this movie are below the saved match threshold (often new people or new angles). Group similar faces together to name each person once instead of frame-by-frame.`),
        (() => {
          const btn = node("button", "Group into visual clusters", "toolbar-btn match-apply");
          btn.type = "button";
          btn.addEventListener("click", () => {
            if (layoutSelect) {
              layoutSelect.value = "clusters";
              limit = 30;
              render();
            }
          });
          return btn;
        })()
      );
    }

    if (useClusters) {
      renderVisualClustersView(records, refs);
    } else {
      records.slice(0, limit).forEach(record => {
        list.append(renderRecordCard(record, refs));
      });
      if (!records.length) list.append(node("p", "No observations match these filters."));
      el("more-matches").hidden = records.length <= limit;
    }

    const url = new URL(window.location.href);
    url.search = new URLSearchParams({matches: report.id, match_kind: kind.value, match_person: person.value}).toString();
    if (window.GoodQLibrary?.source) url.searchParams.set("library_source", window.GoodQLibrary.source);
    history.replaceState(null, "", url);
  }

  async function loadReport(id) {
    const current = ++request;
    report = null;
    selected = new Set();
    applied = new Set();
    decisions = new Map();
    savedDecisions = new Map();
    corrections = new Map();
    savedCorrections = new Map();
    completedReview = false;
    legacyDraft = false;
    draftRevision = null;
    draftReadFailed = false;
    notice = null;
    openScanIds.clear();
    invalidatePreview();
    pauseClips();
    list.replaceChildren();
    el("matches-references").replaceChildren();
    status.textContent = "Reading the frozen initial predictions…";
    try {
      const value = await read(`/api/identity/matches/${encodeURIComponent(id)}`);
      if (current !== request) return;
      const historyData = await read("/api/identity/appearances/history");
      if (current !== request) return;
      report = value;
      limit = 30;
      receipts = historyData.receipts.filter(r => r.review?.report_id === report.id);
      const active = receipts.filter(r => r.status === "applied");
      const appliedCorrect = new Set(active.flatMap(r => r.review.accepted_ids));
      const appliedCorrections = new Map(active.flatMap(r => Object.entries(r.review.corrections || {})));
      applied = new Set([...appliedCorrect, ...appliedCorrections.keys()]);
      savedDecisions = new Map(Object.entries(active[0]?.review.decisions || {}));
      appliedCorrect.forEach(eid => savedDecisions.set(eid, "correct"));
      appliedCorrections.forEach((_, eid) => savedDecisions.set(eid, "incorrect"));
      decisions = new Map(savedDecisions);
      savedCorrections = new Map(appliedCorrections);
      corrections = new Map(savedCorrections);
      completedReview = active[0]?.review.completed_review || false;
      el("reuse-confirmed-faces").checked = true;
      try {
        draftRevision = window.localStorage?.getItem(draftKey()) || null;
        const saved = JSON.parse(draftRevision || window.localStorage?.getItem(legacyKey()) || "null");
        const valid = new Set(report.records.filter(r => r.modality === "face" && r.candidates[0]?.person_id).map(r => r.id));
        if (Array.isArray(saved)) {
          saved.filter(eid => valid.has(eid)).forEach(eid => decisions.set(eid, "correct"));
          legacyDraft = true;
        } else if (saved?.version === 2) {
          Object.entries(saved.decisions).filter(([eid, state]) => valid.has(eid) && decisionNames[state]).forEach(([eid, state]) => decisions.set(eid, state));
          Object.entries(saved.corrections || {}).filter(([eid, pid]) => decisions.get(eid) === "incorrect" && report.people.some(p => p.id === pid))
            .forEach(([eid, pid]) => corrections.set(eid, pid));
          completedReview = saved.completed_review;
          legacyDraft = saved.legacy_draft;
          el("reuse-confirmed-faces").checked = saved.reuse_confirmed_faces || active.some(r => r.review.reuse_confirmed_faces);
        }
        appliedCorrect.forEach(eid => decisions.set(eid, "correct"));
        appliedCorrections.forEach((pid, eid) => { decisions.set(eid, "incorrect"); corrections.set(eid, pid); });
      } catch (_) {
        draftReadFailed = true;
        reviewStatus("The local draft could not be restored. Saved reviews are preserved; reload before editing.", true);
        // Leave unreadable storage intact instead of replacing the only recoverable draft.
        renderHistory();
        render();
        return;
      }
      syncSelected();
      saveDraft();
      renderHistory();
      refreshPersonFilterOptions();
      if (params.get("match_person")) person.value = params.get("match_person");
      const faceCount = report.references.filter(r => r.media.kind === "image").length;
      const voiceCount = report.references.filter(r => r.media.kind === "audio").length;
      status.textContent = `${report.video_name}: compared with ${faceCount} named face examples and ${voiceCount} voice references. ${report.status === "partial" ? `${report.errors.length} observations need attention.` : "Ready for your review."}`;
      report.references.forEach(ref => {
        const card = node("article", null, "match-card");
        card.append(node("h2", referenceName(ref)), mediaView(ref.media, ref.video_name || "Saved reference"));
        el("matches-references").append(card);
      });
      render();
    } catch (error) { if (current === request) status.textContent = error.message; }
  }

  async function load() {
    loaded = true;
    report = null;
    selected = new Set();
    applied = new Set();
    decisions = new Map();
    savedDecisions = new Map();
    corrections = new Map();
    savedCorrections = new Map();
    visualGroupsCache.clear();
    scanCache.clear();
    openScanIds.clear();
    notice = null;
    invalidatePreview();
    el("face-match-history").replaceChildren();
    reviewStatus();
    ++request;
    pauseClips();
    list.replaceChildren();
    el("matches-references").replaceChildren();
    el("matches-summary").textContent = "";
    el("more-matches").hidden = true;
    status.textContent = "Loading saved comparisons…";
    try {
      const response = await read("/api/identity/matches");
      const nameCounts = new Map();
      response.reports.forEach(r => nameCounts.set(r.video_name, (nameCounts.get(r.video_name) || 0) + 1));
      reportSelect.replaceChildren(...response.reports.map(r => {
        const label = (nameCounts.get(r.video_name) || 0) > 1
          ? `${r.video_name} (${r.people_count || 0} people · ${r.face_reference_count || 0} face refs · ${r.summary?.face?.proposed || 0} proposed)`
          : r.video_name;
        return new Option(label, r.id);
      }));
      if (!response.reports.length) {
        status.textContent = "No completed comparisons yet. Normal ingestion saves them when configured family references are available.";
        return;
      }
      if (params.get("matches") && response.reports.some(r => r.id === params.get("matches"))) reportSelect.value = params.get("matches");
      await loadReport(reportSelect.value);
    } catch (error) { status.textContent = error.message; }
  }

  async function refreshFromPriorFilms() {
    if (busy) return;
    setBusy(true);
    try {
      const outcome = await confirmedRequest(
        "/api/identity/matches/refresh",
        {},
        "Re-compare this movie's saved faces against the latest confirmed people and faces from earlier films? Prior comparison receipts stay intact."
      );
      if (!outcome) {
        reviewStatus("Refresh cancelled. Saved comparisons are unchanged.");
        return;
      }
      params.delete("matches");
      await load();
      if (outcome.latest_report_id && [...reportSelect.options].some(opt => opt.value === outcome.latest_report_id)) {
        reportSelect.value = outcome.latest_report_id;
        await loadReport(outcome.latest_report_id);
      }
      reviewStatus(outcome.refreshed
        ? `Refreshed comparisons against ${outcome.people_count} people (${outcome.face_reference_count} prior-film face references).`
        : (outcome.message || "Comparisons already include all latest prior-film references."));
    } catch (error) {
      reviewStatus(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  reportSelect.addEventListener("change", () => loadReport(reportSelect.value));
  [kind, layoutSelect, person, result, el("matches-review")].filter(Boolean).forEach(filter => {
    filter.addEventListener("change", () => { limit = 30; render(); });
  });
  if (el("open-face-clusters-tab")) {
    el("open-face-clusters-tab").addEventListener("click", () => { el("tab-faces")?.click(); });
  }
  if (el("refresh-prior-matches")) {
    el("refresh-prior-matches").addEventListener("click", refreshFromPriorFilms);
  }
  el("more-matches").addEventListener("click", () => { limit += 30; render(); });
  el("reload-matches").addEventListener("click", load);
  el("preview-face-matches").addEventListener("click", previewSelection);
  el("clear-face-selections").addEventListener("click", () => {
    if (!busy && currentDraft() && window.confirm("Clear only this unapplied draft? Saved reviews remain unchanged.")) {
      notice = null;
      decisions = new Map(savedDecisions);
      corrections = new Map(savedCorrections);
      completedReview = false;
      legacyDraft = false;
      syncSelected();
      invalidatePreview();
      saveDraft();
      render();
    }
  });
  el("complete-legacy-review").addEventListener("click", () => {
    if (busy || !report || !currentDraft()) return;
    report.records.filter(r => r.modality === "face").forEach(r => { if (!decisions.has(r.id)) decisions.set(r.id, "not_accepted"); });
    completedReview = true;
    notice = null;
    invalidatePreview();
    saveDraft();
    render();
  });
  el("reuse-confirmed-faces").addEventListener("change", () => {
    if (!busy && currentDraft()) {
      notice = null;
      invalidatePreview();
      saveDraft();
      render();
    }
  });
  el("tab-matches").addEventListener("click", () => {
    el("phase-indicator").textContent = "MATCH REVIEW · NOTHING APPLIED";
    if (!loaded) load();
  });
  document.querySelectorAll(".tab-btn").forEach(tab => tab.addEventListener("click", pauseClips));
  if (params.get("match_kind") === "voice") kind.value = "voice";
  if (params.has("matches")) el("tab-matches").click();
})();
