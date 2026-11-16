from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import numpy as np
from PIL import Image
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_run_ingestion():
    try:
        importlib.import_module("typer")
    except ModuleNotFoundError:
        typer = types.ModuleType("typer")

        class _DummyTyper:
            def __init__(self, *args, **kwargs):
                pass

            def command(self, *args, **kwargs):
                def _decorator(fn):
                    return fn

                return _decorator

        typer.Typer = _DummyTyper
        typer.Option = lambda default=None, *args, **kwargs: default
        typer.echo = lambda *args, **kwargs: None
        typer.BadParameter = Exception
        sys.modules["typer"] = typer

    return importlib.import_module("cli.run_ingestion")


def test_vs01_async_ocr_and_object_aggregators_preserve_error_status_on_empty_worker_outputs():
    run_ingestion = _load_run_ingestion()

    ocr_records = [
        {
            "sample_index": idx,
            "timestamp": float(idx),
            "is_midpoint_sample": (idx == 2),
            "source_path": f"scene_0058_s{idx:02d}.jpg",
            "status": "error",
            "outputs": {},
            "error": "Step image_ocr timed out after 300s",
        }
        for idx in range(5)
    ]
    ocr_agg = run_ingestion._aggregate_ocr_sample_results(ocr_records, midpoint_timestamp=2.0)
    assert ocr_agg["ocr_text"] is None
    assert ocr_agg["ocr_meta"]["status"] == "error"
    assert len(ocr_agg["ocr_sampling_errors"]) == 5
    assert all(s["ocr_meta"]["status"] == "error" for s in ocr_agg["ocr_meta"]["samples"])

    obj_records = [
        {
            "sample_index": idx,
            "timestamp": float(idx),
            "is_midpoint_sample": (idx == 2),
            "source_path": f"scene_0058_s{idx:02d}.jpg",
            "status": "error",
            "outputs": {},
            "error": "Step object_detect failed (goodq_object_detect) [returncode=1]",
        }
        for idx in range(5)
    ]
    obj_agg = run_ingestion._aggregate_object_detect_sample_results(obj_records, midpoint_timestamp=2.0)
    assert obj_agg["objects"] == []
    assert obj_agg["detect_meta"]["status"] == "error"
    assert obj_agg["detect_meta"].get("reason") != "no_detected_object"
    assert len(obj_agg["object_sampling_errors"]) == 5
    assert all(s["detect_meta"]["status"] == "error" for s in obj_agg["detect_meta"]["samples"])


def test_vs01_process_frame_async_and_content_state_preserve_signal_on_optional_vision_failure(monkeypatch, tmp_path):
    run_ingestion = _load_run_ingestion()

    cfg_json = tmp_path / "cfg.json"
    cfg_json.write_text("{}", encoding="utf-8")
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"video")
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    scene = {"index": 58, "start": 0.0, "end": 4.0, "duration": 4.0}

    def _fake_extract_keyframe(_ffmpeg, _video_path, _scene, out_dir, *, scene_id=None, sample_suffix="", **_kw):
        p = Path(out_dir) / f"{scene_id or 'scene_0058'}{sample_suffix}.jpg"
        p.write_bytes(b"jpg")
        return p

    async def _fake_run_step_async(_env, step_name, payload, _cfg):
        if step_name in {"image_ocr", "object_detect", "face_embed"}:
            return {"status": "error", "outputs": {}, "errors": f"{step_name} timed out"}
        if step_name == "image_caption":
            samples = payload.get("samples") or []
            return {
                "status": "ok",
                "outputs": {
                    "samples": [
                        {
                            "caption": "two people talking in a living room",
                            "caption_meta": {
                                "status": "ok",
                                "engine": "wevisone-vl",
                                "sample_timestamp": s["timestamp"],
                                "is_midpoint_sample": s["is_midpoint_sample"],
                            },
                        }
                        for s in samples
                    ]
                },
            }
        if step_name == "image_embed_dino":
            return {"status": "ok", "outputs": {"dino_embedding": [0.1, 0.2], "dino_meta": {"status": "ok"}}}
        if step_name == "image_embed_clip":
            return {"status": "ok", "outputs": {"clip_embedding": [0.3, 0.4], "clip_meta": {"status": "ok"}}}
        if step_name == "tagger":
            return {"status": "ok", "outputs": {"tags": ["living_room"]}}
        if step_name == "text_embed":
            return {"status": "ok", "outputs": {"embedding_meta": {"status": "ok", "point_id": "pt_1"}}}
        return {"status": "ok", "outputs": {}}

    monkeypatch.setattr(run_ingestion, "_extract_keyframe", _fake_extract_keyframe)
    monkeypatch.setattr(run_ingestion, "_persist_frame_semantic_entities", lambda *a, **kw: None)
    monkeypatch.setattr(run_ingestion, "_log_visual_to_ucf_ledger", lambda *a, **kw: None)
    monkeypatch.setattr(run_ingestion, "_run_step_async", _fake_run_step_async)

    res = asyncio.run(
        run_ingestion._process_frame_async(
            cfg_json,
            "ffmpeg",
            video_path,
            scene,
            frame_dir,
            "vid_hash_vs01",
            "scene_0058",
            asyncio.Lock(),
            asyncio.Lock(),
        )
    )

    assert isinstance(res["errors"], list) and len(res["errors"]) == 15
    joined_errors = "; ".join(res["errors"])
    assert "face sample at " in joined_errors
    assert "ocr sample at " in joined_errors
    assert "object_detect@" in joined_errors
    data = res["data"]
    assert data["ocr_meta"]["status"] == "error"
    assert data["detect_meta"]["status"] == "error"
    assert data["faces_meta"]["status"] == "error"
    assert set(data["optional_stage_errors"].keys()) == {"face_embed", "image_ocr", "object_detect"}

    signal_scene = {
        "duration": 4.0,
        "keyframe": data,
        "audio": {
            "transcript": "Let us set the table before dinner.",
            "segments": [{"start": 0.2, "end": 2.8, "text": "Let us set the table before dinner."}],
            "transcript_meta": {"status": "ok", "duration": 2.6},
        },
        "errors": {
            "frame_processing": joined_errors,
            "optional_stage_errors": data["optional_stage_errors"],
        },
    }
    assert run_ingestion._classify_scene_content(signal_scene, empty_duration_threshold_sec=1.0) == "signal"

    # Legacy frame_processing string (including semicolon inside timeout text) also preserves core signal
    legacy_opt_scene = {
        **signal_scene,
        "errors": {"frame_processing": "ocr sample at 2.000s: Step image_ocr timed out; worker exit was not confirmed"},
    }
    assert run_ingestion._classify_scene_content(legacy_opt_scene, empty_duration_threshold_sec=1.0) == "signal"

    # Mixed optional + core step error or total absence of core signal still classifies as processing_error
    core_err_scene = {
        **signal_scene,
        "errors": {
            "frame_processing": f"{joined_errors}; image_embed_dino error",
            "optional_stage_errors": data["optional_stage_errors"],
        },
    }
    assert run_ingestion._classify_scene_content(core_err_scene, empty_duration_threshold_sec=1.0) == "processing_error"

    no_core_signal_scene = {
        "duration": 4.0,
        "keyframe": {"ocr_meta": {"status": "error"}},
        "audio": {"transcript": "", "segments": [], "transcript_meta": {"status": "empty", "duration": 0.0}},
        "errors": {"optional_stage_errors": {"image_ocr": ["ocr sample at 2.000s: timed out"]}},
    }
    assert run_ingestion._classify_scene_content(no_core_signal_scene, empty_duration_threshold_sec=1.0) == "processing_error"


def test_vs02_postlaunch_timeout_crash_corrupt_output_and_face_extract_write_step_runs_errors(monkeypatch, tmp_path):
    from lib.ingestion_capability_contract import build_capability_receipt
    from steps.common.step_logger import log_step_run

    run_ingestion = _load_run_ingestion()

    log_dir = tmp_path / "logs"
    cfg = {
        "paths": {"log_dir": str(log_dir)},
        "run": {"id": "run_vs02"},
        "image_ocr": {"device": "cpu"},
        "ocr": {"device": "cpu"},
    }
    cfg_json = tmp_path / "cfg.json"
    cfg_json.write_text(json.dumps(cfg), encoding="utf-8")

    # Prior scene 0 succeeded for image_ocr
    log_step_run(
        cfg,
        "image_ocr",
        {"video_id": "v1", "scene_id": "sc_0000", "scene_index": 0, "timestamp": 1.0, "source_path": "f0.jpg"},
        12.0,
        "ok",
        None,
        extra={"result_meta": {"ocr_meta": {"status": "ok", "accepted_text": "PARK", "sample_timestamp": 1.0, "is_midpoint_sample": True}}},
    )

    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(
        run_ingestion,
        "prepare_worker_launch",
        lambda req, env, **_kw: SimpleNamespace(
            command=[sys.executable, "-c", "pass"],
            kind="direct_python",
            direct_python=Path(sys.executable),
            environment=dict(env),
        ),
    )

    mode = {"kind": "timeout"}

    class _FakeProc:
        def __init__(self):
            self.pid = 43210
            self.returncode = None

        async def communicate(self):
            if mode["kind"] == "timeout":
                mode["kind"] = "reaped"
                raise asyncio.TimeoutError()
            if mode["kind"] == "reaped":
                self.returncode = -9
                return b"", b"killed"
            if mode["kind"] == "nonzero_unlogged":
                self.returncode = 1
                return b"", b"native crash before step_runner log"
            if mode["kind"] == "nonzero_already_logged":
                log_step_run(
                    cfg,
                    "object_detect",
                    {"video_id": "v1", "scene_id": "sc_0002", "scene_index": 2, "timestamp": 1.0, "source_path": "f2.jpg"},
                    4.0,
                    "error",
                    "worker logged before raising",
                )
                self.returncode = 1
                return b"", b"worker raised"
            if mode["kind"] == "missing_output":
                self.returncode = 0
                return b"not json", b""
            self.returncode = 0
            return b"{}", b""

        def terminate(self):
            self.returncode = -15

        def kill(self):
            self.returncode = -9

        async def wait(self):
            self.returncode = -9
            return -9

    async def _fake_create_subprocess_exec(*_cmd, **_kw):
        return _FakeProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    # 1. Batch timeout on scene 1 (5 samples) -> writes 5 synthetic error rows
    batch_payloads = [
        {
            "video_id": "v1",
            "video_hash": "v1",
            "scene_id": "sc_0001",
            "scene_index": 1,
            "timestamp": float(i),
            "is_midpoint_sample": (i == 2),
            "source_path": f"sc1_{i}.jpg",
        }
        for i in range(5)
    ]
    batch_res = asyncio.run(
        run_ingestion._run_step_batch_async("goodq_ocr", "image_ocr", batch_payloads, cfg_json)
    )
    assert all(r["status"] == "error" for r in batch_res)

    # 2. Nonzero exit without child ledger write -> writes 1 synthetic error row
    mode["kind"] = "nonzero_unlogged"
    nz_res = asyncio.run(
        run_ingestion._run_step_async(
            "goodq_object_detect",
            "object_detect",
            {"video_id": "v1", "scene_id": "sc_0001", "scene_index": 1, "timestamp": 0.5, "source_path": "obj1.jpg"},
            cfg_json,
        )
    )
    assert nz_res["status"] == "error"

    # 3. Nonzero exit where child already wrote error row -> no duplicate error row
    mode["kind"] = "nonzero_already_logged"
    dup_res = asyncio.run(
        run_ingestion._run_step_async(
            "goodq_object_detect",
            "object_detect",
            {"video_id": "v1", "scene_id": "sc_0002", "scene_index": 2, "timestamp": 1.0, "source_path": "f2.jpg"},
            cfg_json,
        )
    )
    assert dup_res["status"] == "error"

    # 4. Exit 0 with unreadable worker output -> writes 1 synthetic error row
    mode["kind"] = "missing_output"
    corrupt_res = asyncio.run(
        run_ingestion._run_step_async(
            "goodq_face_embed",
            "face_embed",
            {"video_id": "v1", "scene_id": "sc_0003", "scene_index": 3, "timestamp": 1.5, "source_path": "f3.jpg"},
            cfg_json,
        )
    )
    assert corrupt_res["status"] == "error"

    rows = [
        json.loads(line)
        for line in (log_dir / "step_runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ocr_err_rows = [r for r in rows if r["step"] == "image_ocr" and r["status"] == "error"]
    assert len(ocr_err_rows) == 5
    assert all(r.get("extra", {}).get("reason") == "step_timeout" for r in ocr_err_rows)

    sc2_obj_rows = [r for r in rows if r["step"] == "object_detect" and r.get("scene_id") == "sc_0002"]
    assert len(sc2_obj_rows) == 1

    face_corrupt_rows = [r for r in rows if r["step"] == "face_embed" and r.get("scene_id") == "sc_0003"]
    assert len(face_corrupt_rows) == 1
    assert face_corrupt_rows[0]["extra"]["reason"] == "worker_result_read_failed"

    receipt = build_capability_receipt(
        run_id="run_vs02",
        profile="GPU_ENHANCED",
        terminal_status="completed",
        step_rows=rows,
        warnings=[],
        scenes=[],
        evidence_paths={"step_runs": str(log_dir / "step_runs.jsonl")},
    )
    caps_by_step = {c["step"]: c for c in receipt["capabilities"]}
    assert caps_by_step["image_ocr"]["status"] == "error"
    assert "sc_0001" in caps_by_step["image_ocr"]["affected_scene_ids"]
    assert receipt["summary"]["optional_errors"] >= 1
    assert receipt["outcome"] == "degraded"

    # 4b. Pre-launch GPU-required conflict under BASELINE logs pre_launch error row
    prelaunch_res = asyncio.run(
        run_ingestion._run_step_async(
            "goodq_object_detect",
            "object_detect",
            {"video_id": "v1", "scene_id": "sc_prelaunch", "scene_index": 9, "timestamp": 0.0, "source_path": "fp.jpg"},
            cfg_json,
            _step_env_overrides={"GOODQ_HOST_PROFILE": "BASELINE", "GOODQ_REQUIRE_GPU": "1"},
        )
    )
    assert prelaunch_res["status"] == "error"
    rows_prelaunch = [
        json.loads(line)
        for line in (log_dir / "step_runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    prelaunch_rows = [
        r for r in rows_prelaunch
        if r["step"] == "object_detect" and r.get("scene_id") == "sc_prelaunch" and r["status"] == "error"
    ]
    assert len(prelaunch_rows) == 1
    assert prelaunch_rows[0]["extra"] == {"reason": "gpu_auto_config_disabled", "pre_launch": True}

    # 5. Keyframe extraction failure in run_face_samples logs face_embed error row
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"video")
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    def _extract_fail_non_mid(_ffmpeg, _video_path, _scene, out_dir, *, scene_id=None, sample_timestamp=None, sample_suffix="", **_kw):
        if sample_timestamp == 3.0:
            raise RuntimeError("seek failed at 3.0s")
        p = Path(out_dir) / f"{scene_id or 'sc_0004'}{sample_suffix}.jpg"
        p.write_bytes(b"jpg")
        return p

    async def _noop_step_async(_env, step_name, payload, _cfg):
        if step_name == "face_embed":
            return {"status": "ok", "outputs": {"faces": [], "faces_meta": {"status": "ok", "engine": "opencv-yunet-sface"}}}
        if step_name == "image_caption":
            return {"status": "ok", "outputs": {"samples": [{"caption": None, "caption_meta": {"status": "not_applicable", "reason": "blank_or_low_variance_frame"}} for _ in payload.get("samples", [])]}}
        if step_name == "image_ocr":
            return {"status": "ok", "outputs": {"ocr_text": None, "ocr_meta": {"status": "no_text", "reason": "empty_ocr_text"}}}
        if step_name == "object_detect":
            return {"status": "ok", "outputs": {"objects": [], "detect_meta": {"status": "ok", "engine": "onnxruntime"}}}
        return {"status": "ok", "outputs": {}}

    monkeypatch.setattr(run_ingestion, "_extract_keyframe", _extract_fail_non_mid)
    monkeypatch.setattr(run_ingestion, "_persist_frame_semantic_entities", lambda *a, **kw: None)
    monkeypatch.setattr(run_ingestion, "_log_visual_to_ucf_ledger", lambda *a, **kw: None)
    monkeypatch.setattr(run_ingestion, "_run_step_async", _noop_step_async)

    asyncio.run(
        run_ingestion._process_frame_async(
            cfg_json,
            "ffmpeg",
            video_path,
            {"index": 4, "start": 0.0, "end": 4.0, "duration": 4.0},
            frame_dir,
            "v1",
            "sc_0004",
            asyncio.Lock(),
            asyncio.Lock(),
        )
    )
    rows_after = [
        json.loads(line)
        for line in (log_dir / "step_runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    face_extract_rows = [
        r for r in rows_after
        if r["step"] == "face_embed" and r.get("scene_id") == "sc_0004" and r["status"] == "error"
    ]
    assert len(face_extract_rows) >= 1
    assert face_extract_rows[0]["extra"]["reason"] == "face_embed_keyframe_extract_failed"


def test_vs03_filter_vhs_ocr_regions_retains_explicit_and_ambiguous_date_hints_from_real_ocr_step():
    from steps.image_ocr.step import _date_hints

    run_ingestion = _load_run_ingestion()

    regions = [
        {"text": "雨", "bbox": [0, 0, 8, 8], "polygon": [[0, 0], [8, 0], [8, 8], [0, 8]], "confidence": 0.21, "confidence_kind": "recognizer_sequence_score"},
        {"text": "DEC 16 2002", "bbox": [10, 80, 90, 95], "polygon": [[10, 80], [90, 80], [90, 95], [10, 95]], "confidence": 0.91, "confidence_kind": "recognizer_sequence_score"},
        {"text": "05/06/98", "bbox": [10, 60, 80, 75], "polygon": [[10, 60], [80, 60], [80, 75], [10, 75]], "confidence": 0.88, "confidence_kind": "recognizer_sequence_score"},
        {"text": "01/02/99", "bbox": [10, 40, 80, 55], "polygon": [[10, 40], [80, 40], [80, 55], [10, 55]], "confidence": 0.30, "confidence_kind": "recognizer_sequence_score"},
    ]
    orig_hints, orig_evidence = _date_hints(regions, 5.0)
    assert orig_hints is not None
    orig_hints["first_seen_ts"]["2002-12-16"] = 1.25

    ocr_meta = {
        "status": "ok",
        "engine": "paddleocr-3.7-onnxruntime-cuda",
        "accepted_regions": regions,
        "date_evidence": orig_evidence,
    }
    raw_text = "\n".join(r["text"] for r in regions)

    filtered_text, filtered_meta, filtered_hints = run_ingestion._filter_vhs_ocr_regions(
        raw_text,
        ocr_meta,
        orig_hints,
        5.0,
    )

    assert filtered_text == "DEC 16 2002\n05/06/98"
    assert len(filtered_meta["date_evidence"]) == 2
    assert filtered_hints is not None
    assert filtered_hints["explicit_dates"] == ["2002-12-16"]
    assert filtered_hints["ambiguous_dates"] == ["05/06/98"]
    assert "01/02/99" not in filtered_hints["ambiguous_dates"]
    assert filtered_hints["months"] == ["december"]
    assert filtered_hints["first_seen_ts"]["2002-12-16"] == 1.25


def test_vs04_degraded_zero_face_samples_and_per_item_primary_errors(monkeypatch, tmp_path):
    from cli import step_runner
    from steps.face_embed import step as face_step

    run_ingestion = _load_run_ingestion()

    # Part A: degraded 0-face result maps to skipped in step_runner, yet produces 0 face_sampling_errors in run_face_samples
    degraded_empty = {
        "faces": [],
        "faces_meta": {
            "status": "degraded",
            "engine": "face_recognition",
            "primary_engine": "opencv-yunet-sface",
            "fallback_used": True,
            "fallback_reason": "primary missing",
            "embedding_dimension": 0,
        },
    }
    log_status, log_err, extra = step_runner._derive_step_log_outcome("face_embed", degraded_empty, verbose=False)
    assert log_status == "skipped"
    assert log_err is None
    assert extra["reason"] == "face_embed_degraded_no_output"

    cfg_json = tmp_path / "cfg.json"
    cfg_json.write_text("{}", encoding="utf-8")
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"video")
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        run_ingestion,
        "_extract_keyframe",
        lambda _f, _v, _s, out_dir, *, scene_id=None, sample_suffix="", **_k: (
            Path(out_dir).joinpath(f"{scene_id or 'sc'}{sample_suffix}.jpg").write_bytes(b"jpg")
            or Path(out_dir).joinpath(f"{scene_id or 'sc'}{sample_suffix}.jpg")
        ),
    )
    monkeypatch.setattr(run_ingestion, "_persist_frame_semantic_entities", lambda *a, **kw: None)
    monkeypatch.setattr(run_ingestion, "_log_visual_to_ucf_ledger", lambda *a, **kw: None)

    async def _fake_step_async(_env, step_name, payload, _cfg):
        if step_name == "face_embed":
            return {"status": "skipped", "outputs": degraded_empty, "errors": None}
        if step_name == "image_caption":
            return {"status": "ok", "outputs": {"samples": [{"caption": "indoor scene", "caption_meta": {"status": "ok", "engine": "wevisone-vl"}} for _ in payload.get("samples", [])]}}
        if step_name == "image_ocr":
            return {"status": "ok", "outputs": {"ocr_text": None, "ocr_meta": {"status": "no_text", "reason": "empty_ocr_text"}}}
        if step_name == "object_detect":
            return {"status": "ok", "outputs": {"objects": [], "detect_meta": {"status": "ok", "engine": "onnxruntime"}}}
        return {"status": "ok", "outputs": {}}

    monkeypatch.setattr(run_ingestion, "_run_step_async", _fake_step_async)
    frame_res = asyncio.run(
        run_ingestion._process_frame_async(
            cfg_json,
            "ffmpeg",
            video_path,
            {"index": 0, "start": 0.0, "end": 4.0, "duration": 4.0},
            frame_dir,
            "v_face",
            "sc_face",
            asyncio.Lock(),
            asyncio.Lock(),
        )
    )
    assert frame_res["data"]["face_sampling_errors"] == []
    assert len(frame_res["data"]["face_sampling_warnings"]) == 5
    assert len(frame_res["data"]["face_observations"]) == 5
    assert "face_embed" not in (frame_res["data"].get("optional_stage_errors") or {})

    # Part B: per-item image decode or alignCrop error stays on primary engine (never calls _face_recognition_embed)
    bad_img = tmp_path / "corrupt.jpg"
    bad_img.write_bytes(b"not-a-jpeg")
    det_model = tmp_path / "yunet.onnx"
    rec_model = tmp_path / "sface.onnx"
    det_model.write_bytes(b"onnx")
    rec_model.write_bytes(b"onnx")

    monkeypatch.setattr(face_step, "_sealed_model_paths", lambda: (det_model, rec_model))
    monkeypatch.setattr(
        face_step,
        "_face_recognition_embed",
        lambda _p: (_ for _ in ()).throw(AssertionError("fallback must not be called on per-frame errors")),
    )
    monkeypatch.setattr(face_step, "_YUNET_SFACE_CACHE", {})

    state = {"imread": None}

    class _FakeDetector:
        def setInputSize(self, _size):
            return None

        def detect(self, _img):
            return 1, np.array([[0.0, 0.0, 12.0, 12.0]], dtype=np.float32)

    class _FakeRecognizer:
        def alignCrop(self, _img, _det):
            raise RuntimeError("degenerate bbox crop")

    fake_cv2 = SimpleNamespace(
        imread=lambda _p: state["imread"],
        FaceDetectorYN=SimpleNamespace(create=lambda *_a, **_k: _FakeDetector()),
        FaceRecognizerSF=SimpleNamespace(create=lambda *_a, **_k: _FakeRecognizer()),
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    decode_err_out = face_step.face_embed({"source_path": str(bad_img)}, {})
    assert decode_err_out["faces"] == []
    assert decode_err_out["faces_meta"]["status"] == "error"
    assert decode_err_out["faces_meta"]["engine"] == "opencv-yunet-sface"

    state["imread"] = np.zeros((32, 32, 3), dtype=np.uint8)
    crop_err_out = face_step.face_embed({"source_path": str(bad_img)}, {})
    assert crop_err_out["faces"] == []
    assert crop_err_out["faces_meta"]["status"] == "error"
    assert crop_err_out["faces_meta"]["engine"] == "opencv-yunet-sface"


def test_vs05_scene_visual_embeddings_vram_registration_and_cuda0_amp(monkeypatch, tmp_path):
    import torch
    from common.vram_allocator import STEP_VRAM_FRACTIONS, step_uses_gpu_backend
    from steps.video import scene_embedder

    assert "scene_visual_embeddings" in STEP_VRAM_FRACTIONS
    assert STEP_VRAM_FRACTIONS["scene_visual_embeddings"] > 0
    assert step_uses_gpu_backend(
        "scene_visual_embeddings",
        env={"GOODQ_HOST_PROFILE": "GPU_ENHANCED", "CUDA_VISIBLE_DEVICES": "0"},
    ) is True
    assert step_uses_gpu_backend(
        "scene_visual_embeddings",
        env={"GOODQ_FORCE_CPU": "1"},
    ) is False

    img_path = tmp_path / "f0.jpg"
    Image.new("RGB", (16, 16), color=(64, 128, 192)).save(img_path)

    autocast_calls: List[tuple[str, Any]] = []

    @contextmanager
    def _spy_autocast(*, device_type: str, dtype: Any):
        autocast_calls.append((device_type, dtype))
        yield

    class _FakeTensorDict(dict):
        def items(self):
            return super().items()

    class _FakeVal:
        def to(self, _dev):
            return self

    class _FakeClipModel:
        config = SimpleNamespace(projection_dim=4)

        def get_image_features(self, **_kw):
            return torch.ones((1, 4), dtype=torch.float32)

    class _FakeDinoModel:
        config = SimpleNamespace(hidden_size=4)

        def __call__(self, **_kw):
            return SimpleNamespace(last_hidden_state=torch.ones((1, 2, 4), dtype=torch.float32))

    monkeypatch.setattr(torch.amp, "autocast", _spy_autocast)
    monkeypatch.delenv("GOODQ_CLIP_DISABLE_AMP", raising=False)
    monkeypatch.delenv("GOODQ_DINO_DISABLE_AMP", raising=False)
    monkeypatch.setattr(scene_embedder, "_load_clip_model", lambda: None)
    monkeypatch.setattr(scene_embedder, "_load_dino_model", lambda: None)
    monkeypatch.setitem(
        scene_embedder._MODELS,
        "clip",
        {
            "model": _FakeClipModel(),
            "processor": lambda **_kw: _FakeTensorDict({"pixel_values": _FakeVal()}),
            "device": "cuda:0",
            "status": "loaded",
        },
    )
    monkeypatch.setitem(
        scene_embedder._MODELS,
        "dino",
        {
            "model": _FakeDinoModel(),
            "processor": lambda **_kw: _FakeTensorDict({"pixel_values": _FakeVal()}),
            "device": "cuda:0",
            "status": "loaded",
        },
    )

    clip_vecs = scene_embedder.embed_frames_clip([str(img_path)])
    dino_vecs = scene_embedder.embed_frames_dino([str(img_path)])
    assert len(clip_vecs) == 1 and isinstance(clip_vecs[0], np.ndarray)
    assert len(dino_vecs) == 1 and isinstance(dino_vecs[0], np.ndarray)
    assert len(autocast_calls) == 2
    assert all(call == ("cuda", torch.float16) for call in autocast_calls)


def test_vs06_corrupt_yolox_pack_fails_closed_while_missing_pack_selects_nanodet(monkeypatch, tmp_path):
    from steps.common import model_provisioner
    from steps.object_detect import step as obj_step

    frame_path = tmp_path / "frame.jpg"
    frame_path.write_bytes(b"jpg")
    nanodet_file = tmp_path / "nanodet.onnx"
    nanodet_file.write_bytes(b"nanodet")

    # 1. Corrupt YOLOX asset -> raises DetectorUnavailable(invalid_pack=True), NO silent NanoDet downgrade
    def _corrupt_yolox(model_id: str, offline: bool = True):
        if model_id == obj_step.GPU_MODEL_ID:
            return SimpleNamespace(
                status="invalid_cached_asset",
                local_path=str(tmp_path / "corrupt_yolox.onnx"),
                error="SHA-256 mismatch on opencv_yolox",
            )
        return SimpleNamespace(status="cached", local_path=str(nanodet_file), error=None)

    monkeypatch.setattr(model_provisioner, "ensure_model_cached", _corrupt_yolox)
    monkeypatch.setattr(obj_step, "_RUNTIMES", {})
    corrupt_res = obj_step.object_detect({"source_path": str(frame_path)}, {})
    assert corrupt_res["objects"] == []
    assert corrupt_res["detect_meta"]["status"] == "unavailable"
    assert corrupt_res["detect_meta"]["engine"] == "onnxruntime"
    assert "SHA-256 mismatch" in corrupt_res["detect_meta"]["error"]

    # 2. Uninstalled YOLOX pack (bundled_missing) -> still selects opencv_nanodet cleanly
    def _missing_yolox(model_id: str, offline: bool = True):
        if model_id == obj_step.GPU_MODEL_ID:
            return SimpleNamespace(status="bundled_missing", local_path=None, error="bundled pack absent")
        return SimpleNamespace(status="cached", local_path=str(nanodet_file), error=None)

    monkeypatch.setattr(model_provisioner, "ensure_model_cached", _missing_yolox)
    assert obj_step._select_model_id({}) == "opencv_nanodet"

    # 3. Runtime exception on YOLOX preserves onnxruntime engine provenance
    yolox_cpu_rt = obj_step.DetectorRuntime(
        model_id=obj_step.GPU_MODEL_ID,
        device="cpu",
        net=object(),
        engine=obj_step.YOLOX_ENGINE,
    )
    monkeypatch.setattr(obj_step, "_select_model_id", lambda _cfg: obj_step.GPU_MODEL_ID)
    monkeypatch.setattr(obj_step, "_load_detector", lambda _cfg: yolox_cpu_rt)
    monkeypatch.setattr(
        obj_step,
        "_detect_with_runtime",
        lambda _rt, _p: (_ for _ in ()).throw(ValueError("ORT tensor shape failure")),
    )
    err_res = obj_step.object_detect({"source_path": str(frame_path)}, {})
    assert err_res["detect_meta"]["status"] == "error"
    assert err_res["detect_meta"]["engine"] == "onnxruntime"


def test_vs07_vision_pipeline_doc_matches_sealed_runtime_contracts():
    doc_path = REPO_ROOT / "docs" / "architecture" / "components" / "VISION_PIPELINE.md"
    text = doc_path.read_text(encoding="utf-8")

    assert "openai/clip-vit-large-patch14" not in text
    assert "laion/CLIP-ViT-L-14-DataComp.XL-s13B-b90K" in text
    assert "opencv_yolox" in text
    assert "opencv_nanodet" in text
    assert "opencv_yunet" in text
    assert "opencv_sface" in text


def test_cross_slice_hooks_st05_as01_and_as04(monkeypatch, tmp_path):
    from cli import step_runner
    from lib.ingestion_capability_contract import _closure_status, _normalize_capability

    run_ingestion = _load_run_ingestion()

    # AS-01 Gap 1: _build_kg_scene_data hoists speaker_change_review
    review_payload = [{"boundary_ts": 4.2, "left_speaker": "SPEAKER_00", "right_speaker": "SPEAKER_01"}]
    kg_scene = run_ingestion._build_kg_scene_data(
        {"index": 0, "start": 0.0, "end": 8.0},
        scene_id="sc_kg_01",
        video_id="vid_kg_01",
        frame_data={"caption": "family room"},
        audio_data={
            "transcript": "hello there",
            "speaker_segments": [{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"}],
            "speaker_change_review": review_payload,
        },
    )
    assert kg_scene["speaker_change_review"] == review_payload

    # AS-04: silent Windows transcription is a valid empty completion, not a backend downgrade/failure
    silent_win_audio = {
        "path": "audio/scene_0001.wav",
        "data": {
            "transcript": None,
            "segments": [],
            "transcript_outcome": "no_speech",
            "transcript_meta": {
                "status": "empty",
                "engine": "faster-whisper",
                "model": "whisper-large-v3",
                "device": "cpu",
            },
        },
    }
    inferred = run_ingestion._infer_audio_backend_fields(
        silent_win_audio,
        skip_audio=False,
        audio_error=None,
    )
    assert inferred["audio_backend_selected"] == "windows"

    attribution = run_ingestion._resolve_audio_backend_attribution(
        silent_win_audio,
        skip_audio=False,
        audio_error=None,
        audio_runtime_contract={"selected": "windows", "reason": "wsl_disabled"},
        run_context={},
        scene_id="sc_silent_01",
        scene_index=1,
    )
    assert attribution["audio_backend_effective"] == "windows"
    assert attribution["audio_backend_downgraded"] is False

    log_status, log_err, extra = step_runner._derive_step_log_outcome(
        "audio_transcribe_local",
        silent_win_audio["data"],
        verbose=False,
    )
    assert log_status == "not_applicable"
    assert log_err is None
    assert extra["reason"] == "no_speech_detected"
    cap = _normalize_capability(
        {
            "step": "audio_transcribe_local",
            "status": log_status,
            "scene_id": "sc_silent_01",
            "extra": extra,
        }
    )
    assert _closure_status(cap) == "ran_content_appropriate_empty"

    # Unavailable backend still resolves to 'none' (not masked as valid silence)
    unavail_audio = {
        "path": "audio/scene_0002.wav",
        "data": {
            "transcript": None,
            "segments": [],
            "transcript_meta": {"status": "unavailable", "engine": "faster-whisper"},
        },
    }
    assert (
        run_ingestion._infer_audio_backend_fields(unavail_audio, skip_audio=False, audio_error=None)[
            "audio_backend_selected"
        ]
        == "none"
    )

    # ST-05 caller hook: _prepare_scene_bundle_identity_kwargs + real register_scene_bundle
    import sqlite3
    from steps.common.memory import register_scene_bundle

    frame_file = tmp_path / "st05_mid.jpg"
    frame_file.write_bytes(b"jpg")
    audio_file = tmp_path / "st05.wav"
    audio_file.write_bytes(b"wav")
    db_file = tmp_path / "st05_memory.db"

    frame_info_sample: Dict[str, Any] = {
        "path": str(frame_file),
        "data": {
            "caption": "They are opening presents in the living room.",
            "faces": [],  # midpoint has 0 faces
            "face_observations": [
                {"timestamp": 0.0, "is_midpoint_sample": False, "faces": []},
                {
                    "timestamp": 3.0,
                    "is_midpoint_sample": False,
                    "faces": [{"bbox": [1, 1, 20, 20]}, {"bbox": [30, 1, 50, 20]}],
                },
            ],
        },
    }
    audio_info_sample: Dict[str, Any] = {
        "path": str(audio_file),
        "data": {
            "transcript": "Look at that ribbon.",
            "speaker_segments": [
                {"start": 0.0, "end": 1.2, "speaker": "SPEAKER_00"},
                {"start": 1.2, "end": 2.4, "speaker": "SPEAKER_01"},
            ],
        },
    }
    st05_kwargs = run_ingestion._prepare_scene_bundle_identity_kwargs(
        frame_info_sample,
        audio_info_sample,
        register_fn=register_scene_bundle,
    )
    assert st05_kwargs == {"face_count": 2, "speaker_ids": ["SPEAKER_00", "SPEAKER_01"]}
    assert frame_info_sample["data"]["face_count"] == 2
    assert audio_info_sample["data"]["speaker_ids"] == ["SPEAKER_00", "SPEAKER_01"]
    assert audio_info_sample["data"]["speaker_count"] == 2

    st05_cfg = {
        "paths": {
            "db_path": str(db_file),
            "db_dir": str(tmp_path),
            "long_term_summary": str(tmp_path / "lt_summary.jsonl"),
        },
        "vector_store": {"enabled": False},
    }
    register_scene_bundle(
        st05_cfg,
        video_hash="vid_st05",
        scene={"index": 0, "start": 0.0, "end": 4.0},
        scene_id="sc_st05_0000",
        epoch_id="epoch_test",
        frame=frame_info_sample,
        audio=audio_info_sample,
        **st05_kwargs,
    )
    with sqlite3.connect(db_file) as conn:
        row = conn.execute("SELECT meta FROM scenes LIMIT 1").fetchone()
    assert row is not None
    persisted_meta = json.loads(row[0])
    assert persisted_meta["face_count"] == 2
    assert persisted_meta["keyframe"]["face_count"] == 2
    assert persisted_meta["speaker_ids"] == ["SPEAKER_00", "SPEAKER_01"]


def test_vs05_phase6_gpu_config_fraction_and_sequential_model_unload(monkeypatch):
    from common.vram_allocator import STEP_VRAM_FRACTIONS
    from steps.video import scene_embedder

    recorded_fractions: list[float] = []

    class _FakeProps:
        name = "Fake RTX 16GB"
        total_memory = 16 * (1024**3)
        major = 8
        minor = 9

    fake_cuda = SimpleNamespace(
        is_available=lambda: True,
        set_per_process_memory_fraction=lambda frac, _dev=0: recorded_fractions.append(frac),
        empty_cache=lambda: None,
        get_device_properties=lambda _dev=0: _FakeProps(),
    )
    fake_torch = SimpleNamespace(
        cuda=fake_cuda,
        backends=SimpleNamespace(
            cuda=SimpleNamespace(matmul=SimpleNamespace(allow_tf32=False)),
            cudnn=SimpleNamespace(allow_tf32=False, benchmark=False, enabled=True, deterministic=False),
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "0")
    from steps.common import gpu_config
    recorded_fractions.clear()

    for step_key in ("scene_visual_embeddings", "scene_embedder_clip", "scene_embedder_dino"):
        res = gpu_config.configure_gpu(step_key)
        assert res["memory_fraction"] == pytest.approx(STEP_VRAM_FRACTIONS["scene_visual_embeddings"])
        assert res["memory_fraction"] == pytest.approx(0.35)

    assert recorded_fractions == pytest.approx([0.35, 0.35, 0.35])

    # Verify unload_model honors only_if_loaded_by_embedder for test sentinels vs real loads
    scene_embedder._MODELS["clip"] = {"model": object(), "processor": object(), "device": "cuda:0"}
    scene_embedder._LOADED_BY_EMBEDDER["clip"] = False
    assert scene_embedder.unload_model("clip", only_if_loaded_by_embedder=True) is False
    assert scene_embedder._MODELS["clip"]["model"] is not None

    scene_embedder._LOADED_BY_EMBEDDER["clip"] = True
    assert scene_embedder.unload_model("clip", only_if_loaded_by_embedder=True) is True
    assert scene_embedder._MODELS["clip"]["model"] is None
    assert scene_embedder._MODELS["clip"]["processor"] is None
    assert scene_embedder._LOADED_BY_EMBEDDER["clip"] is False


def test_vs02_step_runner_logs_scene_visual_embeddings_failure_as_error():
    from cli.step_runner import _derive_step_log_outcome

    status, err, extra = _derive_step_log_outcome(
        "scene_visual_embeddings",
        {
            "video_id": "vid_oom",
            "phase6_status": "failed",
            "error": "missing_scene_embeddings",
            "frame_error_summary": {"total": 318, "clip": 0, "dino": 318},
        },
        verbose=True,
    )
    assert status == "error"
    assert err == "missing_scene_embeddings"
    assert extra is not None
    assert extra["reason"] == "scene_visual_embeddings_missing_scene_embeddings"
    assert extra["frame_error_summary"] == {"total": 318, "clip": 0, "dino": 318}

    ok_status, ok_err, ok_extra = _derive_step_log_outcome(
        "scene_visual_embeddings",
        {
            "video_id": "vid_ok",
            "phase6_status": "complete",
            "scenes_processed": 106,
            "clip_embeddings": 106,
            "dino_embeddings": 106,
            "qdrant_ok": True,
            "faiss_ok": True,
        },
        verbose=True,
    )
    assert ok_status == "ok"
    assert ok_err is None
    assert ok_extra is not None
    assert ok_extra["phase6_status"] == "complete"
    assert ok_extra["scenes_processed"] == 106



