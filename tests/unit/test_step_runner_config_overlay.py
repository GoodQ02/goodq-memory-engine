from __future__ import annotations

import json


def test_load_step_config_overlays_isolated_witness_values_on_runtime_defaults(
    monkeypatch,
    tmp_path,
) -> None:
    from cli import step_runner

    witness_cfg = tmp_path / "witness-config.json"
    witness_cfg.write_text(
        json.dumps({"paths": {"data_root": "C:/isolated/data"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        step_runner,
        "load_cfg",
        lambda overrides=None: {
            "audio": {"transcribe": {"model": "small", "chunk_seconds": 10}},
            "paths": {"data_root": "C:/default/data", "models_cache": "C:/models"},
        },
    )

    resolved = step_runner.load_step_config(witness_cfg)

    assert resolved["audio"]["transcribe"]["model"] == "small"
    assert resolved["paths"] == {
        "data_root": "C:/isolated/data",
        "models_cache": "C:/models",
    }


def test_image_ocr_derive_step_log_outcome_distinguishes_empty_uncertain_and_errors() -> None:
    from cli.step_runner import _derive_step_log_outcome

    status, err, extra = _derive_step_log_outcome(
        "image_ocr",
        {
            "ocr_text": None,
            "ocr_meta": {
                "status": "no_text",
                "reason": "empty_ocr_text",
                "sample_timestamp": 1.5,
                "is_midpoint_sample": False,
            },
        },
        verbose=False,
    )
    assert status == "not_applicable"
    assert err is None
    assert extra is not None
    assert extra["reason"] == "no_ocr_text"

    for uncertain_reason in ("unvalidated_vhs_candidates", "low_confidence_primary_text"):
        u_status, u_err, u_extra = _derive_step_log_outcome(
            "image_ocr",
            {
                "ocr_text": None,
                "ocr_meta": {"status": "no_text", "reason": uncertain_reason},
            },
            verbose=False,
        )
        assert u_status == "skipped"
        assert u_err is None
        assert u_extra is not None
        assert u_extra["reason"] == f"image_ocr_{uncertain_reason}"

    f_status, f_err, f_extra = _derive_step_log_outcome(
        "image_ocr",
        {
            "ocr_text": None,
            "ocr_meta": {
                "status": "no_text",
                "reason": "empty_ocr_text",
                "fallback_error": "tesseract crop failed",
            },
        },
        verbose=False,
    )
    assert f_status == "error"
    assert f_err == "tesseract crop failed"
    assert f_extra is not None
    assert f_extra["reason"] == "image_ocr_empty_ocr_text"

    d_status, d_err, d_extra = _derive_step_log_outcome(
        "image_ocr",
        {
            "ocr_text": None,
            "ocr_meta": {
                "status": "dependency_missing",
                "reason": "ocr_dependency_missing",
                "error": "No module named paddleocr",
            },
        },
        verbose=False,
    )
    assert d_status == "error"
    assert d_err == "No module named paddleocr"
    assert d_extra is not None
    assert d_extra["reason"] == "image_ocr_ocr_dependency_missing"


def test_image_ocr_step_surfaces_provider_exception_as_error_and_preserves_sample_provenance(
    monkeypatch,
    tmp_path,
) -> None:
    from PIL import Image
    from steps.image_ocr import step as ocr_step

    img_file = tmp_path / "sample.jpg"
    Image.new("RGB", (64, 32), color=(0, 0, 0)).save(img_file)

    def _boom(*args):
        raise ocr_step.OCRRuntimeError("ocr_provider_unavailable", "selected provider unavailable")

    monkeypatch.setattr(ocr_step, "run_native_ocr", _boom)

    out = ocr_step.image_ocr(
        {"source_path": str(img_file), "timestamp": 1.5, "is_midpoint_sample": False},
        {},
    )
    assert out["ocr_text"] is None
    meta = out["ocr_meta"]
    assert meta["status"] == "error"
    assert meta["reason"] == "ocr_provider_unavailable"
    assert "selected provider unavailable" in meta["error"]
    assert meta["fallback_chain"] == []
    assert meta["sample_timestamp"] == 1.5
    assert meta["is_midpoint_sample"] is False


def test_step_logger_records_sample_timestamp_in_jsonl_entry(
    monkeypatch,
    tmp_path,
) -> None:
    from steps.common import step_logger

    monkeypatch.setattr(step_logger, "MISSION_LOGGER_AVAILABLE", False)
    log_dir = tmp_path / "logs"
    cfg = {"paths": {"log_dir": str(log_dir)}, "run": {"id": "run_ocr_ts"}}
    step_logger.log_step_run(
        cfg,
        "image_ocr",
        {"scene_id": "scene_0000", "scene_index": 0, "timestamp": 1.5},
        12.0,
        "ok",
        extra={"reason": "ok"},
    )
    rows = [
        json.loads(line)
        for line in (log_dir / "step_runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["timestamp"] == 1.5
