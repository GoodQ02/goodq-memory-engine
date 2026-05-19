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
