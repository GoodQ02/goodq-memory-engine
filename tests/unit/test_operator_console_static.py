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

    assert "api-environment-pill" in index_html
    assert "[Live Data]" in app_js
    assert "[Demo]" in app_js
    assert "STATE_GRAMMAR" in app_js
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


def test_retrieval_console_uses_timeline_handoff_id_for_enriched_results() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "timeline_video_id" in app_js
    assert "retrievalTimelineVideoId" in app_js
    assert "scene_present_entities" in app_js
    assert "kg_evidence" in app_js
    assert "KG / Entity Evidence" in app_js


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

    assert "app.css?v=20260520-projection-gap-1" in index_html
    assert "20260520-projection-gap-1" in index_html
    assert "renderAudioEmotionDistribution" in app_js
    assert "Audio Emotion Distribution" in app_js
    assert "Audio classifier labels, latest temporal index" in app_js
    assert "Text sentiment labels not present in this run" in app_js
    assert "emotion-bar-list" in app_js
    assert "${count}/${denominator}" in app_js

    assert ".emotion-distribution" in app_css
    assert ".emotion-bar-fill" in app_css
    assert ".sentiment-empty-state" in app_css


def test_proof_panel_surfaces_projection_gap_summary() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "Projection gap check" in app_js
    assert "projectionGapNote" in app_js
    assert "source truth not projected" in app_js
    assert "missing projections" in app_js
    assert "visual_caption" in app_js
    assert "clap_meta" in app_js


def test_retrieval_console_surfaces_scene_context_lens() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "20260520-projection-gap-1" in index_html
    assert "appendRetrievalSceneContextLens" in app_js
    assert "Scene Context Lens" in app_js
    assert "Emotional arc" in app_js
    assert "Key moments" in app_js
    assert "No scene_context_llm payload returned for this retrieval result." in app_js

    assert ".retrieval-context-lens" in app_css
    assert ".retrieval-key-moments" in app_css
    assert ".retrieval-tag-strip" in app_css


def test_scene_inspector_surfaces_compact_evidence_summary() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_html = (repo_root / "ui" / "operator_console_v1" / "index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "ui" / "operator_console_v1" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (repo_root / "ui" / "operator_console_v1" / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert "20260520-projection-gap-1" in index_html
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

    assert "20260520-projection-gap-1" in index_html
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

    assert "20260520-projection-gap-1" in index_html
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
