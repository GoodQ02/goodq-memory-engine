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
