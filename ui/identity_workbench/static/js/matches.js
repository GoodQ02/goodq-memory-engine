/* Frozen comparisons, local review drafts, and explicitly confirmed appearance links. */
(function () {
  "use strict";
  const el = id => document.getElementById(id);
  const list = el("matches-list"), status = el("matches-status");
  const reportSelect = el("matches-report"), kind = el("matches-kind");
  const person = el("matches-person"), result = el("matches-result");
  let report = null, request = 0, limit = 30, loaded = false;
  let selected = new Set(), applied = new Set(), receipts = [], preview = null, busy = false, draftSaved = false, notice = null;
  let decisions = new Map(), savedDecisions = new Map(), completedReview = false, legacyDraft = false, draftRevision = null;
  let draftReadFailed = false;
  // Right saved person for faces marked Incorrect. The decision itself stays Incorrect.
  let corrections = new Map(), savedCorrections = new Map();
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
  async function read(url) {
    const response = await fetch(window.GoodQLibrary?.url(url) || url);
    if (!response.ok) throw new Error(`Saved comparison unavailable (${response.status}).`);
    return response.json();
  }
  async function post(url, payload) {
    const response = await fetch(window.GoodQLibrary?.url(url) || url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
    const body = await response.json();
    if (!response.ok) {
      const error = new Error(typeof body.detail === "string" ? body.detail : `Request failed (${response.status}). Reload and preview again.`);
      error.status = response.status; error.body = body; throw error;
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
  function syncSelected() { selected = new Set([...decisions].filter(([id, value]) => value === "correct" && !applied.has(id)).map(([id]) => id)); }
  function saveDraft() {
    draftSaved = false;
    if (!currentDraft()) return;
    try {
      if (window.localStorage) {
        const serialized = JSON.stringify({version: 2, decisions: Object.fromEntries(decisions), corrections: Object.fromEntries(corrections), completed_review: completedReview,
          legacy_draft: legacyDraft, reuse_confirmed_faces: el("reuse-confirmed-faces").checked});
        window.localStorage.setItem(draftKey(), serialized); draftRevision = serialized; draftSaved = true;
      }
    } catch (_) { /* The visible status discloses a page-only draft. */ }
  }
  function selectionPayload() {
    const payload = {report_id: report.id, report_sha256: report.content_sha256,
      accepted_ids: [...decisions].filter(([, state]) => state === "correct").map(([id]) => id).sort(),
      decisions: Object.fromEntries([...decisions].sort()), completed_review: completedReview,
      reuse_confirmed_faces: el("reuse-confirmed-faces").checked};
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
  function invalidatePreview() { preview = null; el("face-match-preview").hidden = true; }
  function choose(record, decision) {
    if (busy || applied.has(record.id) || !currentDraft()) return;
    notice = null;
    decisions.set(record.id, decision); syncSelected();
    if (decision !== "incorrect") corrections.delete(record.id);
    invalidatePreview(); saveDraft(); render();
  }
  function assign(record, personId) {
    if (busy || applied.has(record.id) || decisions.get(record.id) !== "incorrect" || !currentDraft()) return;
    notice = null;
    if (personId) corrections.set(record.id, personId); else corrections.delete(record.id);
    invalidatePreview(); saveDraft(); render();
  }
  const personName = id => report.people.find(p => p.id === id)?.display_name || "another saved person";
  function setBusy(value) {
    busy = value;
    [kind, person, result, reportSelect, el("matches-review"), el("reload-matches"), el("more-matches")].forEach(control => { control.disabled = value; });
    document.querySelectorAll(".match-review-actions button, .match-correction select, .match-preview button, .match-history-row button").forEach(button => { button.disabled = value || button.dataset.locked === "true"; });
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
    const historyList = el("face-match-history"); historyList.replaceChildren();
    receipts.forEach(receipt => {
      const row = node("div", null, "match-history-row");
      row.append(node("span", `${receipt.status === "applied" ? "Applied" : "Undone"}: ${receipt.summary.observations} confirmed faces across ${receipt.summary.scenes} scenes${receipt.summary.corrected ? ` (${receipt.summary.corrected} reassigned to the right person)` : ""}; ${receipt.summary.reusable_faces || 0} reusable examples.${receipt.summary.decisions ? ` Decisions: ${Object.entries(receipt.summary.decisions).map(([state, n]) => `${n} ${decisionNames[state]}`).join(" · ")}.` : ""}`));
      if (receipt.status === "applied") {
        const undo = node("button", "Undo this review", "toolbar-btn");
        undo.addEventListener("click", async () => {
          if (busy) return; setBusy(true);
          try {
            const outcome = await confirmedRequest("/api/identity/appearances/undo", {receipt_id: receipt.id, receipt_sha256: receipt.receipt_sha256},
              "Undo this receipt's decisions, added scene links and reusable examples? Labels and movies stay intact. Later changes will stop Undo.");
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
    setBusy(true); invalidatePreview();
    try {
      const value = await post("/api/identity/matches/preview", selectionPayload());
      preview = value;
      const panel = el("face-match-preview"); panel.replaceChildren(); panel.hidden = false;
      panel.append(node("h2", "Preview · nothing new applied"), node("p", `${quantity(value.summary.observations, "Correct face observation")} for ${quantity(value.summary.people, "person", "people")} in ${quantity(value.summary.scenes, "scene")}.`));
      if (value.summary.decisions) panel.append(node("p", Object.entries(value.summary.decisions).map(([state, n]) => `${n} ${decisionNames[state]}`).join(" · ")));
      if (value.summary.corrected) panel.append(node("p", `${quantity(value.summary.corrected, "Incorrect face")} will be linked to the person you chose instead.`));
      panel.append(node("p", `${value.summary.reusable_faces || 0} confirmed faces will be reusable reference examples after Apply. Incorrect rejects only the displayed person; a face you reassigned is linked only to the person you chose. Unsure stays unresolved and never becomes a reference. All voices and mentions remain held.`));
      if (value.summary.decisions?.not_accepted) panel.append(node("p", "Your completed earlier review is preserved: these remaining pairings were mostly incorrect. The old controls did not record which were uncertain, so they remain reviewed, not accepted. You do not need to repeat the batch."));
      const records = new Map(report.records.map(r => [r.id, r]));
      value.appearances.forEach(link => {
        const row = node("div", null, "match-preview-row");
        row.append(node("h3", `${link.display_name} · ${stamp(link.scene_start)} – ${stamp(link.scene_end)}`));
        const evidence = node("div", null, "match-preview-evidence");
        [...link.evidence].sort((a, b) => a.timestamp - b.timestamp).forEach(item => evidence.append(mediaView(records.get(item.evidence_id).media, item.assignment === "human_corrected" ? `Reassigned to ${link.display_name}` : `Selected as ${link.display_name}`)));
        row.append(evidence); panel.append(row);
      });
      panel.append(node("p", "Apply saves the review decisions, these appearance links and the approved reusable examples. Existing labels and source movies are preserved. Undo remains available."));
      const apply = node("button", "Apply review and confirmed faces", "toolbar-btn match-apply");
      apply.disabled = !value.summary.new_edges && !value.summary.updated_edges && !value.review_changed;
      apply.dataset.locked = String(apply.disabled);
      apply.addEventListener("click", applySelection); panel.append(apply);
      const back = node("button", "Keep reviewing", "toolbar-btn");
      back.addEventListener("click", invalidatePreview); panel.append(back);
      panel.scrollIntoView?.({block: "start"});
    } catch (error) { reviewStatus(error.message, true); }
    finally { setBusy(false); }
  }
  async function applySelection() {
    if (busy || !preview || !currentDraft()) return;
    const plan = preview; setBusy(true);
    try {
      const outcome = await confirmedRequest("/api/identity/appearances/apply", {plan_sha256: plan.plan_sha256, match_review: plan.review},
        `Save this review, ${plan.summary.observations} confirmed observations${plan.summary.corrected ? ` (${plan.summary.corrected} reassigned)` : ""} across ${plan.summary.scenes} scenes, and ${plan.summary.reusable_faces || 0} reusable examples? Rejected people, Unsure and earlier not-accepted faces receive no identity links. Voices and mentions remain held.`);
      if (!outcome) { reviewStatus("Apply cancelled. Your draft and preview remain available."); return; }
      invalidatePreview(); await loadReport(report.id);
      reviewStatus("Review and confirmed faces saved. You can undo this receipt above.");
    } catch (error) { invalidatePreview(); reviewStatus(`${error.message} Reload history before trying again.`, true); }
    finally { setBusy(false); render(); }
  }
  function pauseClips() { document.querySelectorAll("#panel-matches audio").forEach(audio => audio.pause()); }
  function mediaView(media, caption) {
    const figure = node("figure", null, "match-media");
    if (media.kind === "image") {
      const crop = node("div", null, "match-crop"), img = document.createElement("img");
      img.alt = caption; img.loading = "lazy"; img.src = window.GoodQLibrary?.url(media.url) || media.url;
      img.addEventListener("load", () => {
        const box = media.bbox;
        if (!Array.isArray(box) || box.length !== 4) return;
        const [x1, y1, x2, y2] = box;
        const width = x2 - x1, height = y2 - y1;
        if (width <= 0 || height <= 0) return;
        const scale = 150 / Math.max(width, height);
        img.style.width = `${img.naturalWidth * scale}px`;
        img.style.height = `${img.naturalHeight * scale}px`;
        img.style.left = `${(180 - width * scale) / 2 - x1 * scale}px`;
        img.style.top = `${(170 - height * scale) / 2 - y1 * scale}px`;
      });
      img.addEventListener("error", () => { crop.replaceChildren(node("span", "Source image unavailable")); });
      crop.append(img); figure.append(crop);
    } else {
      const audio = document.createElement("audio");
      audio.controls = true; audio.preload = "none";
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
  function render() {
    pauseClips(); list.replaceChildren();
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
    records.slice(0, limit).forEach(record => {
      const top = record.candidates[0], reference = top && refs.get(top.reference_id);
      const card = node("article", null, "match-card"); card.dataset.matchId = record.id;
      const heading = node("div", null, "match-card-heading");
      const title = record.status === "proposed" && top?.display_name ? `Possible ${top.display_name}`
        : record.status === "ambiguous" ? "Uncertain match"
        : kind.value === "voice" ? "Unidentified speaker" : "Unidentified face";
      heading.append(node("h2", title),
        node("span", labels[record.status] || record.status, `match-state ${record.status}`));
      card.append(heading);
      const pair = node("div", null, "match-pair");
      pair.append(mediaView(record.media, `New ${kind.value === "face" ? "observation" : "voice clip"}`));
      if (reference) pair.append(mediaView(reference.media, `Reference: ${referenceName(reference)}`));
      card.append(pair);
      if (record.modality === "face" && top?.person_id && reference) {
        const isApplied = applied.has(record.id), decision = decisions.get(record.id);
        const controls = node("div", null, "match-review-actions");
        controls.setAttribute("role", "group"); controls.setAttribute("aria-label", `Is this ${top.display_name}?`);
        ["correct", "incorrect", "unsure"].forEach(state => {
          const button = node("button", decisionNames[state], "toolbar-btn"); button.dataset.decision = state;
          button.setAttribute("aria-pressed", String(decision === state)); button.disabled = busy || isApplied;
          button.dataset.locked = String(isApplied); button.addEventListener("click", () => choose(record, state)); controls.append(button);
        });
        const chosen = corrections.get(record.id);
        const notes = {correct: `Correct: ${top.display_name}`,
          incorrect: chosen ? `Incorrect: this is ${personName(chosen)}, not ${top.display_name}` : `Incorrect: this is not ${top.display_name}`,
          unsure: `Unsure whether this is ${top.display_name}`, not_accepted: "Reviewed in the earlier batch, not accepted. Wrong versus uncertain was not recorded."};
        card.append(node("p", `Is this ${top.display_name}?`, "match-review-question"), controls,
          node("p", `${notes[decision] || "Not reviewed yet."}${isApplied ? " · Applied. Undo the saved review to change it." : decision && decision !== "not_accepted" ? " · Draft, not applied." : ""}`, "match-review-note"));
        const others = report.people.filter(p => p.id !== top.person_id);
        if (decision === "incorrect" && others.length) {
          const label = node("label", "Who is this instead? ", "match-correction"), pick = document.createElement("select");
          pick.append(new Option("Leave unassigned", ""), ...others.map(p => new Option(p.display_name, p.id)));
          pick.value = chosen || ""; pick.disabled = busy || isApplied; pick.dataset.locked = String(isApplied);
          pick.addEventListener("change", () => assign(record, pick.value));
          label.append(pick); card.append(label);
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
      watch.href = `/ui/retro_console_v1/?${new URLSearchParams({watch_match: report.id, watch_evidence: record.id,
        watch_scene: record.scene_id, watch_video: report.video_id, watch_epoch: report.epoch_id})}`;
      if (window.GoodQLibrary) watch.href = window.GoodQLibrary.url(watch.href);
      watch.addEventListener("click", pauseClips); card.append(watch); list.append(card);
    });
    if (!records.length) list.append(node("p", "No observations match these filters."));
    el("more-matches").hidden = records.length <= limit;
    const url = new URL(window.location.href);
    url.search = new URLSearchParams({matches: report.id, match_kind: kind.value, match_person: person.value}).toString();
    if (window.GoodQLibrary?.source) url.searchParams.set("library_source", window.GoodQLibrary.source);
    history.replaceState(null, "", url);
  }
  async function loadReport(id) {
    const current = ++request;
    report = null; selected = new Set(); applied = new Set(); decisions = new Map(); savedDecisions = new Map(); corrections = new Map(); savedCorrections = new Map(); completedReview = false; legacyDraft = false; draftRevision = null; draftReadFailed = false; notice = null; invalidatePreview(); pauseClips(); list.replaceChildren(); el("matches-references").replaceChildren();
    status.textContent = "Reading the frozen initial predictions…";
    try {
      const value = await read(`/api/identity/matches/${encodeURIComponent(id)}`);
      if (current !== request) return;
      const historyData = await read("/api/identity/appearances/history");
      if (current !== request) return;
      report = value; limit = 30;
      receipts = historyData.receipts.filter(r => r.review?.report_id === report.id);
      const active = receipts.filter(r => r.status === "applied");
      const appliedCorrect = new Set(active.flatMap(r => r.review.accepted_ids));
      const appliedCorrections = new Map(active.flatMap(r => Object.entries(r.review.corrections || {})));
      applied = new Set([...appliedCorrect, ...appliedCorrections.keys()]);
      savedDecisions = new Map(Object.entries(active[0]?.review.decisions || {}));
      appliedCorrect.forEach(id => savedDecisions.set(id, "correct"));
      appliedCorrections.forEach((_, id) => savedDecisions.set(id, "incorrect"));
      decisions = new Map(savedDecisions); savedCorrections = new Map(appliedCorrections); corrections = new Map(savedCorrections);
      completedReview = active[0]?.review.completed_review || false;
      el("reuse-confirmed-faces").checked = true;
      try {
        draftRevision = window.localStorage?.getItem(draftKey()) || null;
        const saved = JSON.parse(draftRevision || window.localStorage?.getItem(legacyKey()) || "null");
        const valid = new Set(report.records.filter(r => r.modality === "face" && r.candidates[0]?.person_id).map(r => r.id));
        if (Array.isArray(saved)) { saved.filter(id => valid.has(id)).forEach(id => decisions.set(id, "correct")); legacyDraft = true; }
        else if (saved?.version === 2) {
          Object.entries(saved.decisions).filter(([id, state]) => valid.has(id) && decisionNames[state]).forEach(([id, state]) => decisions.set(id, state));
          Object.entries(saved.corrections || {}).filter(([id, pid]) => decisions.get(id) === "incorrect" && report.people.some(p => p.id === pid))
            .forEach(([id, pid]) => corrections.set(id, pid));
          completedReview = saved.completed_review; legacyDraft = saved.legacy_draft;
          el("reuse-confirmed-faces").checked = saved.reuse_confirmed_faces || active.some(r => r.review.reuse_confirmed_faces);
        }
        appliedCorrect.forEach(id => decisions.set(id, "correct"));
        appliedCorrections.forEach((pid, id) => { decisions.set(id, "incorrect"); corrections.set(id, pid); });
      } catch (_) {
        draftReadFailed = true;
        reviewStatus("The local draft could not be restored. Saved reviews are preserved; reload before editing.", true);
        // Leave unreadable storage intact instead of replacing the only recoverable draft.
        renderHistory(); render(); return;
      }
      syncSelected(); saveDraft(); renderHistory();
      person.replaceChildren(new Option("Everyone", ""), ...report.people.map(p => new Option(p.display_name, p.id)), new Option("Unidentified", "unknown"));
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
    loaded = true; report = null; selected = new Set(); applied = new Set(); decisions = new Map(); savedDecisions = new Map(); corrections = new Map(); savedCorrections = new Map(); notice = null; invalidatePreview();
    el("face-match-history").replaceChildren(); reviewStatus(); ++request; pauseClips(); list.replaceChildren();
    el("matches-references").replaceChildren(); el("matches-summary").textContent = "";
    el("more-matches").hidden = true; status.textContent = "Loading saved comparisons…";
    try {
      const response = await read("/api/identity/matches");
      reportSelect.replaceChildren(...response.reports.map(r => new Option(r.video_name, r.id)));
      if (!response.reports.length) { status.textContent = "No completed comparisons yet. Normal ingestion saves them when configured family references are available."; return; }
      if (params.get("matches") && response.reports.some(r => r.id === params.get("matches"))) reportSelect.value = params.get("matches");
      await loadReport(reportSelect.value);
    } catch (error) { status.textContent = error.message; }
  }
  reportSelect.addEventListener("change", () => loadReport(reportSelect.value));
  [kind, person, result, el("matches-review")].forEach(filter => filter.addEventListener("change", () => { limit = 30; render(); }));
  el("more-matches").addEventListener("click", () => { limit += 30; render(); });
  el("reload-matches").addEventListener("click", load);
  el("preview-face-matches").addEventListener("click", previewSelection);
  el("clear-face-selections").addEventListener("click", () => { if (!busy && currentDraft() && window.confirm("Clear only this unapplied draft? Saved reviews remain unchanged.")) { notice = null; decisions = new Map(savedDecisions); corrections = new Map(savedCorrections); completedReview = false; legacyDraft = false; syncSelected(); invalidatePreview(); saveDraft(); render(); } });
  el("complete-legacy-review").addEventListener("click", () => {
    if (busy || !report || !currentDraft()) return;
    report.records.filter(r => r.modality === "face").forEach(r => { if (!decisions.has(r.id)) decisions.set(r.id, "not_accepted"); });
    completedReview = true; notice = null; invalidatePreview(); saveDraft(); render();
  });
  el("reuse-confirmed-faces").addEventListener("change", () => { if (!busy && currentDraft()) { notice = null; invalidatePreview(); saveDraft(); render(); } });
  el("tab-matches").addEventListener("click", () => { el("phase-indicator").textContent = "MATCH REVIEW · NOTHING APPLIED"; if (!loaded) load(); });
  document.querySelectorAll(".tab-btn").forEach(tab => tab.addEventListener("click", pauseClips));
  if (params.get("match_kind") === "voice") kind.value = "voice";
  if (params.has("matches")) el("tab-matches").click();
})();
