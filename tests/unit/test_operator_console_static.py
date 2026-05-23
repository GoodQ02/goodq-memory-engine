from pathlib import Path


def test_scene_inspector_surfaces_visual_caption_and_ocr_contract() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "Visual caption" in app_js
    assert "OCR text" in app_js
    assert "OCR date candidates" in app_js
    assert "CLAP commit status" in app_js
    assert "commit metadata only; not current-run Qdrant proof" in app_js
    assert "Scene context summary" in app_js
    assert '"visual_caption"' in app_js
    assert '"ocr_text"' in app_js
    assert '"ocr_date_candidates"' in app_js
    assert '"clap_meta"' in app_js
    assert '"scene_context_llm"' in app_js
    assert '"scene_context_epistemic"' in app_js
    assert '"scene_context_arbitration"' in app_js
    assert "narrative_summary" in app_js


def test_recurrence_console_surfaces_read_only_recommendation_boundary() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "/recommendations" in app_js
    assert "Recommended next inspection" in app_js
    assert "No comparable trend rows yet." in app_js
    assert "This panel only reads existing durable recurrence reports." in app_js
    assert "does not generate reports, trigger ingestion, heal, mutate configs, or activate ControlAgent" in app_js


def test_operator_console_surfaces_runtime_clarity_state_grammar_and_storage() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "api-environment-pill" in index_html
    assert 'data-testid="scope-banner"' in index_html
    assert 'data-testid="scope-banner-grid"' in index_html
    assert "[Live Data]" in app_js
    assert "[Demo]" in app_js
    assert "STATE_GRAMMAR" in app_js
    assert "RUN_SCOPE_GRAMMAR" in app_js
    assert "renderScopeBanner" in app_js
    assert "Direct CLI Output" in app_js
    assert "Standalone Scene Probe" in app_js
    assert "strict run-matched CLAP/Qdrant verdict" in app_js
    assert "does not mutate memory, ingestion, or config" in app_js
    assert ".scope-banner" in app_css
    assert ".scope-item" in app_css
    for label in [
        "Ready",
        "Optional Offline",
        "No Current-Run Evidence",
        "Historical Only",
        "Not Exposed",
        "Needs Explanation",
    ]:
        assert label in app_js

    assert "/api/storage/summary" in app_js
    assert "Storage and growth" in app_js
    assert "Make One Memory" in app_js
    assert "File name redacted" in app_js


def test_operator_console_surfaces_witness_truth_spine() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert 'data-testid="witness-spine"' in index_html
    assert 'data-testid="witness-spine-grid"' in index_html
    assert "#witness-spine" in index_html

    assert "renderWitnessSpine" in app_js
    assert "Witness Spine" in app_js
    assert "Passed with visible follow-up" in app_js
    assert "Step ledger" in app_js
    assert "Current-run audio proof" in app_js
    assert "Projection gaps" in app_js
    assert "Cognitive signal coverage" in app_js
    assert "Persistence agreement" in app_js
    assert "Qdrant + FAISS + SQLite + KG" in app_js
    assert "No private labels shown here" in app_js

    assert ".witness-spine" in app_css
    assert ".witness-metric-grid" in app_css
    assert ".witness-verdict-card" in app_css
    assert ".witness-proof-card" in app_css


def test_operator_console_surfaces_focus_queue_anomaly_tokens_and_scene_health() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert 'data-testid="operator-focus-panel"' in index_html
    assert 'data-testid="operator-focus-list"' in index_html
    assert "#operator-focus" in index_html

    assert "renderOperatorFocusPanel" in app_js
    assert "focusReviewItems" in app_js
    assert "What Should I Look At?" in app_js
    assert "Terminal step failure" in app_js
    assert "Recovered step errors" in app_js
    assert "witness-token-strip" in app_js
    assert "sceneHealthState" in app_js
    assert "Scene health" in app_js
    assert "makeSceneHealthBadge" in app_js

    assert ".operator-focus-panel" in app_css
    assert ".operator-focus-list" in app_css
    assert ".focus-review-item.error" in app_css
    assert ".witness-token.error" in app_css
    assert ".scene-health-badge.warn" in app_css


def test_operator_console_surfaces_guided_mode_without_endpoint_forking() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert 'data-testid="view-mode-toggle"' in index_html
    assert 'data-view-mode="guided"' in index_html
    assert 'data-guided="primary"' in index_html
    assert 'data-guided="operator"' in index_html
    assert 'data-guided-nav="primary"' in index_html
    assert 'data-guided-nav="operator"' in index_html
    assert 'id="guided-mode-button"' in index_html
    assert 'id="operator-mode-button"' in index_html

    assert "VIEW_MODE_KEY" in app_js
    assert "goodq_operator_view_mode" in app_js
    assert "readInitialViewMode" in app_js
    assert "applyViewMode" in app_js
    assert "setViewMode" in app_js
    assert "Guided mode hides operator-only panels" in app_js
    assert 'dataset.viewMode = state.viewMode' in app_js
    assert 'state.viewMode === "guided"' in app_js

    assert ".view-mode-toggle" in app_css
    assert '.app-shell[data-view-mode="guided"] [data-guided="operator"]' in app_css
    assert '.app-shell[data-view-mode="guided"] [data-guided-nav="operator"]' in app_css


def test_operator_console_modes_have_distinct_visual_orientation() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert 'data-testid="operator-mode-banner"' in index_html
    assert 'data-operator-mode-status' in index_html
    assert 'class="section split guided-surface"' in index_html
    assert 'class="section guided-surface"' in index_html

    assert "updateActiveRail" in app_js
    assert "rail-active" in app_js
    assert "aria-current" in app_js
    assert "hashchange" in app_js
    assert 'window.addEventListener("hashchange", updateActiveRail);\n    updateActiveRail();' in app_js

    assert ".guided-surface" in app_css
    assert ".guided-surface#scene-inspector" in app_css
    assert ".operator-mode-banner" in app_css
    assert '.app-shell[data-view-mode="operator"] .operator-mode-banner' in app_css
    assert '.app-shell[data-view-mode="operator"] [data-guided="operator"]:target' in app_css
    assert ".rail a.rail-active" in app_css
    assert '.rail a[data-guided-nav="operator"].rail-active' in app_css


def test_operator_console_mobile_readability_prevents_off_canvas_overflow() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert ".media-preview-panel:not(.active)" in app_css
    assert "visibility: hidden" in app_css
    assert "contain: inline-size" in app_css
    assert ".audio-inventory-row {\n    grid-template-columns: 1fr;" in app_css


def test_retrieval_console_uses_timeline_handoff_id_for_enriched_results() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "timeline_video_id" in app_js
    assert "retrievalTimelineVideoId" in app_js
    assert "scene_present_entities" in app_js
    assert "dialogue_mentioned_entities" in app_js
    assert "sceneEntityEvidenceBuckets" in app_js
    assert "Dialogue-mentioned entities" in app_js
    assert "not scene-present identity" in app_js
    assert "Candidate visible people" in app_js
    assert "Entity evidence" in app_js
    assert "Entity evidence summary" in app_js
    assert "segments_with_any_entity_evidence" in app_js
    assert "top_dialogue_mentioned_entities" in app_js
    assert "top_speaker_aligned_mentions" in app_js
    assert "kg_evidence" in app_js
    assert "KG / Entity Evidence" in app_js


def test_operator_console_uses_no_store_refresh_and_run_scope_cache_boundary() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "requestUrl" in app_js
    assert "__goodq_refresh" in app_js
    assert "__goodq_scope" in app_js
    assert 'cache: "no-store"' in app_js
    assert '"Cache-Control": "no-store"' in app_js
    assert "scopeSignature" in app_js
    assert "runtimeScopeSignature" in app_js
    assert "reconcileSelectedVideo" in app_js
    assert "clearRunScopedState" in app_js
    assert "latestEpisodeTimelineId" in app_js
    assert "selected inventory/timeline folder id" in app_js
    assert "no-store API reads; media cache tied to current run scope" in app_js


def test_video_inventory_surfaces_thumbnail_visibility_envelope() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "thumbnailEnvelopeLabel" in app_js
    assert "Thumbnail: local API ready" in app_js
    assert "raw path redacted" in app_js
    assert "Thumbnail: not exposed" in app_js


def test_operator_console_visual_grammar_reduces_repeated_binary_noise() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "confidenceBand" in app_js
    assert "Strong match" in app_js
    assert "Reviewable match" in app_js
    assert "Exploratory match" in app_js
    assert "Low signal" in app_js
    assert "compactIdentifier" in app_js
    assert "proof-rollup-strip" in app_js
    assert "appendIndicatorStrip" in app_js
    assert "Core runtime" in app_js
    assert "Optional model services" in app_js
    assert "Primary LLM (vLLM)" in app_js
    assert "Optional fallback (Ollama)" in app_js
    assert "core memory and read/search remain usable" in app_js
    assert "high memory with low utilization; likely model/runtime reservation before a long run" in app_js
    assert "WSL audio" in app_js
    assert "Historical processing artifacts" in app_js
    assert "thumbnailStatusCompact" in app_js
    assert "field-status-rollup" in app_js
    assert "makeStatusDot" in app_js
    assert "schema-field-details" in app_js

    assert ".indicator-strip" in app_css
    assert ".confidence-badge" in app_css
    assert ".compact-id" in app_css
    assert ".state-dot-mini" in app_css


def test_operator_console_surfaces_read_only_media_preview_layer() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert 'data-testid="media-preview"' in index_html
    assert "renderMediaPreview" in app_js
    assert "mediaPreviewPayload" in app_js
    assert "representative_frame_endpoint" in app_js
    assert "Scene keyframe" in app_js
    assert "Clip playback not exposed" in app_js
    assert "Export manifest not exposed" in app_js
    assert "Select a scene from inventory, timeline, or retrieval to preview." in app_js

    assert ".media-preview-panel" in app_css
    assert ".keyframe-container" in app_css
    assert ".modality-strip" in app_css
    assert ".mini-timeline" in app_css


def test_operator_console_surfaces_audio_emotion_distribution() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "app.css?v=20260521-emotion-ranking-1" in index_html
    assert "20260521-emotion-ranking-1" in index_html
    assert "renderAudioEmotionDistribution" in app_js
    assert "Audio Emotion Distribution" in app_js
    assert "reviewable audio emotion rankings, latest temporal index" in app_js
    assert "strict threshold labels only" in app_js
    assert "Text emotion rankings" in app_js
    assert "Text emotion ranking present" in app_js
    assert "Raw score buckets" in app_js
    assert "reviewable scores; not promoted labels" in app_js
    assert "Raw audio emotion score buckets are available for operator review" in app_js
    assert "Text sentiment labels not present in this run" in app_js
    assert "emotion-bar-list" in app_js
    assert "${count}/${denominator}" in app_js

    assert ".emotion-distribution" in app_css
    assert ".emotion-bar-fill" in app_css
    assert ".sentiment-empty-state" in app_css


def test_operator_console_surfaces_runtime_problem_scope_and_privacy_notes() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "runtime_step_errors" in app_js
    assert "Recovered step errors" in app_js
    assert "native recovered" in app_js
    assert "Vector counts are commits, not scenes" in app_js
    assert "CLIP/DINO may include original scene vectors plus Phase 6 scene-level commits" in app_js
    assert "Home-memory labels and transcript snippets stay local" in app_js
    assert "Human-review tier" in app_js


def test_proof_panel_surfaces_projection_gap_summary() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "Projection gap check" in app_js
    assert "projectionGapNote" in app_js
    assert "source truth not projected" in app_js
    assert "missing projections" in app_js
    assert "visual_caption" in app_js
    assert "clap_meta" in app_js


def test_proof_panel_separates_latest_structured_audio_proof_from_qdrant_inventory() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "/api/runs/audio-proof/latest" in app_js
    assert "Latest structured run" in app_js
    assert "Run-tagged Qdrant audio inventory" in app_js
    assert "does not override latest structured-run proof" in app_js
    assert "audioProvenance" in app_js


def test_proof_panel_surfaces_compact_audio_inventory_drilldown() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "appendAudioInventoryDrilldown" in app_js
    assert "Audio Provenance Inventory" in app_js
    assert "Run-tagged Qdrant audio payloads; historical until matched to the selected run." in app_js
    assert "audio-inventory-drilldown" in app_js
    assert ".audio-inventory-drilldown" in app_css
    assert ".audio-inventory-row" in app_css


def test_proof_panel_explains_standalone_scene_probe_scope() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "standaloneSceneScope" in app_js
    assert "Standalone scene probe" in app_js
    assert "Direct scene probes do not generate wrapper step ledgers." in app_js
    assert "Direct scene probes do not generate temporal indexes." in app_js
    assert "Scene results fallback" in app_js
    assert '"Scope"' in app_js


def test_operator_console_allows_slow_local_evidence_routes_to_finish() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "status: 30000" in app_js
    assert "run: 30000" in app_js
    assert "runEvidence: 30000" in app_js
    assert "memory: 30000" in app_js


def test_retrieval_console_surfaces_scene_context_lens() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "20260521-emotion-ranking-1" in index_html
    assert "appendRetrievalSceneContextLens" in app_js
    assert "Scene Context Lens" in app_js
    assert "Emotional arc" in app_js
    assert "Key moments" in app_js
    assert "No scene_context_llm payload returned for this retrieval result." in app_js

    assert ".retrieval-context-lens" in app_css
    assert ".retrieval-key-moments" in app_css
    assert ".retrieval-tag-strip" in app_css


def test_retrieval_console_explains_search_scope_vs_evidence_presence() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "retrievalModalitiesSearched" in app_js
    assert "Searched surfaces" in app_js
    assert "from API modalities_searched" in app_js
    assert "Text Evidence" in app_js
    assert "Visual Evidence" in app_js
    assert "Audio Proof" in app_js
    assert "Current-run Qdrant audio proof present; audio query not requested" in app_js
    assert "Searched: ${retrievalSearchedModalityLabel()}" in app_js
    assert ".retrieval-mode-detail" in app_css


def test_retrieval_console_has_modality_selector_and_sends_explicit_modalities() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert 'data-testid="retrieval-modality-selector"' in index_html
    assert 'data-retrieval-modality="text"' in index_html
    assert 'data-retrieval-modality="visual"' in index_html
    assert 'data-retrieval-modality="audio"' in index_html
    assert 'data-retrieval-modality="all"' in index_html
    assert 'modalityMode: "all"' in app_js
    assert "RETRIEVAL_MODALITY_OPTIONS" in app_js
    assert "retrievalModalitiesForRequest" in app_js
    assert "modalities: retrievalModalitiesForRequest()" in app_js
    assert "retrievalSelectedModalityLabel" in app_js
    assert ".retrieval-modality-selector" in app_css
    assert ".retrieval-modality-button" in app_css


def test_retrieval_console_surfaces_observed_search_chips() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert 'data-testid="retrieval-suggestion-strip"' in index_html
    assert "Try searches from observed tags/entities" in app_js
    assert "retrievalSuggestionChips" in app_js
    assert "top_scene_context_tags" in app_js
    assert "top_entities" in app_js
    assert "data-retrieval-suggestion" in app_js
    assert ".retrieval-suggestion-strip" in app_css
    assert ".retrieval-suggestion-chip" in app_css


def test_retrieval_console_splits_match_explanation_by_use() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "appendRetrievalSignalGroup" in app_js
    assert "Used for match" in app_js
    assert "Evidence present" in app_js
    assert "Not used" in app_js
    assert "usedForMatch" in app_js
    assert ".retrieval-signal-sections" in app_css
    assert ".retrieval-signal-group" in app_css


def test_retrieval_console_groups_result_rows_by_scene_contributions() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "retrievalResultModalities" in app_js
    assert "retrievalModalityScores" in app_js
    assert "appendRetrievalContributionStrip" in app_js
    assert "Matched modalities" in app_js
    assert "data-retrieval-contribution" in app_js
    assert ".retrieval-contribution-strip" in app_css
    assert ".retrieval-contribution-chip" in app_css


def test_retrieval_console_surfaces_find_similar_scene_action() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert 'data-testid="retrieval-find-similar"' in index_html
    assert 'data-testid="retrieval-similar-panel"' in index_html
    assert "findSimilarScenesForSelected" in app_js
    assert "/similar?top_k=6" in app_js
    assert "similarSceneAsRetrievalResult" in app_js
    assert "Similar Scenes" in app_js
    assert ".retrieval-similar-panel" in app_css
    assert ".retrieval-similar-row" in app_css


def test_retrieval_console_surfaces_diagnostics_and_full_transcript() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "retrievalDiagnosticsForModality" in app_js
    assert "Audio text-query encoder unavailable" in app_js
    assert "appendRetrievalDiagnostics" in app_js
    assert "retrievalFullTranscript" in app_js
    assert "Show Full Transcript" in app_js
    assert "Hide Full Transcript" in app_js
    assert ".retrieval-diagnostics" in app_css
    assert ".retrieval-transcript-panel" in app_css
    assert ".retrieval-transcript-text" in app_css


def test_retrieval_load_more_uses_requested_window_not_reported_total() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "results.length >= state.retrieval.limit" in app_js
    assert "Request a larger read-only result window." in app_js
    assert "All Returned" in app_js


def test_scene_inspector_surfaces_compact_evidence_summary() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "20260521-emotion-ranking-1" in index_html
    assert "appendSceneEvidenceSummary" in app_js
    assert "Scene Evidence Summary" in app_js
    assert "Meaning source" in app_js
    assert "Evidence present" in app_js
    assert "Evidence gaps" in app_js
    assert "No scene meaning summary exposed for this selected scene." in app_js

    assert ".scene-evidence-summary-panel" in app_css
    assert ".scene-meaning-card" in app_css
    assert ".scene-signal-chip-grid" in app_css
    assert ".scene-gap-list" in app_css


def test_media_preview_links_visual_proof_to_scene_evidence_summary() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "20260521-emotion-ranking-1" in index_html
    assert "previewMeaningPayload" in app_js
    assert "appendPreviewEvidenceBridge" in app_js
    assert "Visual proof linked to selected scene evidence summary" in app_js
    assert "Open Visual Proof" in app_js
    assert "Open Evidence Summary" in app_js
    assert "scene-open-visual-proof" in app_js
    assert "preview-evidence-bridge" in app_js

    assert ".preview-evidence-bridge" in app_css
    assert ".preview-meaning-card" in app_css
    assert ".preview-signal-compact" in app_css
    assert ".scene-evidence-actions" in app_css


def test_retrieval_handoff_surfaces_shared_scene_lineage() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "20260521-emotion-ranking-1" in index_html
    assert "setRetrievalSceneLineage" in app_js
    assert "lineageMatchesScene" in app_js
    assert "appendSceneLineageBridge" in app_js
    assert "appendRetrievalLineageStrip" in app_js
    assert "Scene handoff confirmed" in app_js
    assert "retrieval -> timeline -> inspector -> preview" in app_js
    assert "Same selected scene id" in app_js
    assert "Timeline handoff unresolved" in app_js

    assert ".scene-lineage-bridge" in app_css
    assert ".retrieval-lineage-strip" in app_css
    assert ".preview-lineage-note" in app_css


def test_retrieval_preview_surfaces_visual_proof_keyframe() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "20260521-emotion-ranking-1" in index_html
    assert "appendRetrievalVisualProof" in app_js
    assert "retrievalFrameEndpoint" in app_js
    assert "Retrieval result keyframe" in app_js
    assert "Redacted keyframe endpoint linked to this selected result." in app_js
    assert "retrieval-visual-proof" in app_js

    assert ".retrieval-visual-proof" in app_css
    assert ".retrieval-visual-frame" in app_css
    assert ".retrieval-visual-empty" in app_css
