"""OCR evidence contracts through the production step caller, independent of words."""
from __future__ import annotations

import calendar
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from steps.image_ocr import native, step


def _raw(texts):
    return {"rec_texts": texts, "rec_boxes": [[1, 2, 90, 15] for _ in texts],
            "rec_polys": [[[1, 2], [90, 2], [90, 15], [1, 15]] for _ in texts],
            "rec_scores": [0.91 for _ in texts]}


@pytest.fixture
def source(tmp_path):
    from PIL import Image
    path = tmp_path / "frame.png"
    Image.new("RGB", (100, 80)).save(path)
    return path


def _call(monkeypatch, source, raw, **item):
    from cli.step_runner import run_step
    monkeypatch.setattr(step, "run_native_ocr", lambda *_: (raw, {"config_sha256": "native-settings"}))
    return run_step("image_ocr", {"source_path": str(source), **item}, {"image_ocr": {"device": "cpu"}})


@pytest.mark.parametrize("item", [{"source_kind": "image"}, {"modality": "image", "timestamp": 0}, {"timestamp": 4.5, "is_midpoint_sample": True}])
def test_native_evidence_survives_image_and_video_callers(monkeypatch, source, item):
    raw = _raw(["A", "Native observed text", "Native observed text"])
    raw["rec_scores"] = [0.01, 0.96, 0.91]
    result = _call(monkeypatch, source, raw, **item)
    assert result["ocr_text"] == "A\nNative observed text\nNative observed text"
    meta = result["ocr_meta"]
    assert meta["status"] == "ok" and meta["engine"] == "paddleocr-3.7-onnxruntime-cpu"
    assert meta["raw_result"] == raw
    assert meta["accepted_regions"][0] == {"text": "A", "bbox": [1, 2, 90, 15],
        "polygon": [[1, 2], [90, 2], [90, 15], [1, 15]], "confidence": 0.01,
        "confidence_kind": "recognizer_sequence_score"}
    assert meta["input_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert meta["model_revision"] == native.MODEL_IDENTITIES["paddle_ocr_rec"][1]
    assert meta["detector_revision"] == native.MODEL_IDENTITIES["paddle_ocr_det"][1]
    assert meta["fallback_chain"] == [] and meta["duration_seconds"] >= 0
    if "timestamp" in item:
        assert meta["sample_timestamp"] == item["timestamp"]


def test_no_text_is_successful_absence_at_ledger_boundary(monkeypatch, source):
    from cli.step_runner import _derive_step_log_outcome
    result = _call(monkeypatch, source, _raw([]))
    assert result["ocr_text"] is None
    assert result["ocr_meta"]["status"] == "no_text"
    assert result["ocr_meta"]["accepted_regions"] == []
    outcome, error, _ = _derive_step_log_outcome("image_ocr", result, verbose=False)
    assert outcome == "not_applicable" and error is None


@pytest.mark.parametrize("reason", ["model_asset_missing", "model_asset_hash_mismatch", "selected_provider_unavailable", "selected_provider_not_executed", "runtime_version_mismatch"])
def test_runtime_failures_are_explicit_no_text_is_not_fabricated(monkeypatch, source, reason):
    from cli.step_runner import run_step, _derive_step_log_outcome
    def fail(*_):
        raise native.OCRRuntimeError(reason, "Selected OCR cannot run")
    monkeypatch.setattr(step, "run_native_ocr", fail)
    result = run_step("image_ocr", {"source_path": str(source)}, {})
    assert result["ocr_text"] is None
    assert result["ocr_meta"]["status"] == "error"
    assert result["ocr_meta"]["reason"] == reason
    assert result["ocr_meta"]["effective_implementation"] is None
    outcome, error, _ = _derive_step_log_outcome("image_ocr", result, verbose=False)
    assert outcome == "error" and error


def test_missing_dependency_is_observable(monkeypatch, source):
    def missing(*_):
        raise ModuleNotFoundError("paddleocr unavailable")
    monkeypatch.setattr(step, "run_native_ocr", missing)
    result = step.image_ocr({"source_path": str(source)}, {})
    assert result["ocr_meta"]["status"] == "dependency_missing"
    assert result["ocr_meta"]["reason"] == "ocr_dependency_missing"


def test_missing_source_does_not_initialize_runtime(monkeypatch):
    monkeypatch.setattr(step, "run_native_ocr", lambda *_: pytest.fail("unexpected runtime"))
    assert step.image_ocr({}, {})["ocr_meta"]["status"] == "no_source_path"


@pytest.mark.parametrize("key,value", [
    ("rec_texts", ["a", "b"]), ("rec_texts", [42]), ("rec_boxes", None),
    ("rec_boxes", [[-1, 0, 5, 5]]), ("rec_boxes", [[0, 0, 101, 5]]),
    ("rec_polys", [[[0, 0], [1, 1]]]), ("rec_scores", [float("nan")]),
    ("rec_scores", [95]), ("rec_scores", [True]),
])
def test_malformed_native_arrays_fail_without_partial_text(monkeypatch, source, key, value):
    raw = _raw(["observed"])
    raw[key] = value
    result = _call(monkeypatch, source, raw)
    assert result["ocr_text"] is None
    assert result["ocr_meta"]["reason"] == "malformed_native_result"
    assert result["ocr_meta"]["raw_result"] is raw


@pytest.mark.parametrize("text,expected", [
    ("MAY 19 2002", "2002-05-19"), ("SEP 11 2002", "2002-09-11"),
    ("OCT 23 2002", "2002-10-23"), ("December 16, 2002", "2002-12-16"),
    ("29 Feb. 2024", "2024-02-29"), ("2024-02-29", "2024-02-29"),
    ("12/25/1987", "1987-12-25"), ("25/12/1987", "1987-12-25"),
    ("SEP112002", "2002-09-11"), ("February292024", "2024-02-29"),
    ("Sept.112002", "2002-09-11"),
])
def test_calendar_valid_dates_retain_exact_region_and_offset(monkeypatch, source, text, expected):
    result = _call(monkeypatch, source, _raw([text]), timestamp=12.5)
    assert result["ocr_text"] == text
    assert result["time_hints"]["explicit_dates"] == [expected]
    assert result["time_hints"]["first_seen_ts"] == {expected: 12.5}
    evidence = result["ocr_meta"]["date_evidence"][0]
    assert evidence["raw_text"] == evidence["matched_text"] == text
    assert evidence["bbox"] == [1, 2, 90, 15]
    assert evidence["region_index"] == 0 and evidence["sample_timestamp"] == 12.5
    assert evidence["date"] == expected and evidence["status"] == "explicit"


@pytest.mark.parametrize("text,status", [
    ("FEB 29 2023", "invalid"), ("APR 31 2002", "invalid"),
    ("12/25/87", "ambiguous"), ("DEC 16 02", "ambiguous"), ("03/04/2002", "ambiguous"),
])
def test_dates_do_not_invent_calendar_validity_order_or_century(monkeypatch, source, text, status):
    result = _call(monkeypatch, source, _raw([text]))
    assert result["ocr_text"] == text
    assert not (result["time_hints"] or {}).get("explicit_dates")
    assert result["ocr_meta"]["date_evidence"][0]["status"] == status
    if status == "ambiguous":
        assert result["time_hints"]["ambiguous_dates"] == [text]


@pytest.mark.parametrize("text", ["EC 16 2002", "DEC 1G 2002", "MAY 19 2OO2"])
def test_no_character_repair_is_applied_to_recognized_dates(monkeypatch, source, text):
    result = _call(monkeypatch, source, _raw([text]))
    assert result["ocr_text"] == text and result["time_hints"] is None
    assert result["ocr_meta"]["date_evidence"] == []


@pytest.mark.parametrize("month", range(1, 13))
@pytest.mark.parametrize("day", [3, 19])
def test_compact_named_month_dates_preserve_native_text(monkeypatch, source, month, day):
    text = f"{calendar.month_abbr[month].upper()}{day}2002"
    result = _call(monkeypatch, source, _raw([text]), timestamp=3.0)
    expected = f"2002-{month:02d}-{day:02d}"
    assert result["ocr_text"] == text
    assert result["time_hints"]["explicit_dates"] == [expected]
    evidence = result["ocr_meta"]["date_evidence"][0]
    assert evidence["raw_text"] == evidence["matched_text"] == text
    assert evidence["date"] == expected and evidence["region_index"] == 0
    assert evidence["sample_timestamp"] == 3.0 and evidence["bbox"] == [1, 2, 90, 15]


@pytest.mark.parametrize("text,status", [
    ("FEB292023", "invalid"), ("APR312002", "invalid"),
    ("JAN002002", "invalid"), ("DEC1602", "ambiguous"), ("JUN387", "ambiguous"),
])
def test_compact_dates_still_require_calendar_validity_and_known_century(monkeypatch, source, text, status):
    result = _call(monkeypatch, source, _raw([text]))
    assert result["ocr_text"] == text
    assert not (result["time_hints"] or {}).get("explicit_dates")
    assert result["ocr_meta"]["date_evidence"][0]["status"] == status


@pytest.mark.parametrize("text", ["09112002", "112002", "031287"])
def test_compact_numbers_without_named_month_do_not_invent_dates(monkeypatch, source, text):
    result = _call(monkeypatch, source, _raw([text]))
    assert result["ocr_text"] == text and result["time_hints"] is None
    assert result["ocr_meta"]["date_evidence"] == []


def _registry(tmp_path):
    registry = {"huggingface_models": {}}
    for key, (repo, revision) in native.MODEL_IDENTITIES.items():
        folder = tmp_path / key
        folder.mkdir()
        files = {}
        for name in ("inference.onnx", "inference.yml", "inference.json"):
            data = (key + name).encode()
            (folder / name).write_bytes(data)
            files[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        registry["huggingface_models"][key] = {"repo_id": repo, "revision": revision, "local_path": key, "files": files}
    return registry


@pytest.mark.parametrize("failure", ["missing", "hash", "identity", "escape"])
def test_pinned_local_assets_fail_closed_before_model_import(monkeypatch, tmp_path, failure):
    from steps.common import model_provisioner
    registry = _registry(tmp_path)
    entry = registry["huggingface_models"]["paddle_ocr_det"]
    if failure == "missing":
        (tmp_path / "paddle_ocr_det" / "inference.onnx").unlink()
    elif failure == "hash":
        (tmp_path / "paddle_ocr_det" / "inference.onnx").write_bytes(b"changed")
    elif failure == "identity":
        entry["revision"] = "other"
    else:
        entry["local_path"] = "../outside"
    monkeypatch.setattr(model_provisioner, "load_registry", lambda: registry)
    with pytest.raises(native.OCRRuntimeError):
        native._resolve_assets({"paths": {"models_cache": str(tmp_path)}})


def _session(tmp_path, providers, kernels):
    path = tmp_path / (str(len(list(tmp_path.iterdir()))) + ".json")
    path.write_text(json.dumps([{"cat": "Node", "args": {"provider": provider}} for provider in kernels]))
    return SimpleNamespace(get_providers=lambda: providers, end_profiling=lambda: str(path))


def test_actual_cuda_kernels_distinguish_cpu_node_assignment(tmp_path):
    session = _session(tmp_path, ["CUDAExecutionProvider", "CPUExecutionProvider"],
                       ["CUDAExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"])
    receipt = native._execution_receipt(session, "CUDAExecutionProvider", required=True)
    assert receipt["executed_kernel_counts"] == {"CUDAExecutionProvider": 2, "CPUExecutionProvider": 1}
    assert receipt["cpu_node_assignment"] and not receipt["runtime_fallback_enabled"]


@pytest.mark.parametrize("kernels", [[], ["CPUExecutionProvider"]])
def test_provider_list_alone_cannot_establish_gpu_execution(tmp_path, kernels):
    session = _session(tmp_path, ["CUDAExecutionProvider", "CPUExecutionProvider"], kernels)
    with pytest.raises(native.OCRRuntimeError, match="selected provider"):
        native._execution_receipt(session, "CUDAExecutionProvider", required=True)


def test_recognizer_not_run_is_honest_on_empty_detection(tmp_path):
    receipt = native._execution_receipt(_session(tmp_path, ["CPUExecutionProvider"], []), "CPUExecutionProvider", required=False)
    assert receipt["status"] == "not_run_no_regions" and receipt["executed_kernel_counts"] == {}


def test_native_predictor_is_closed_after_inference_failure(monkeypatch, tmp_path):
    closed = []
    def fail(_):
        raise RuntimeError("native inference failed")
    ocr = SimpleNamespace(predict=fail, close=lambda: closed.append(True))
    monkeypatch.setattr(native, "_resolve_assets", lambda _: {})
    monkeypatch.setattr(native, "_create_ocr", lambda *_: (ocr, {}, "CPUExecutionProvider"))
    with pytest.raises(RuntimeError, match="native inference failed"):
        native.run_native_ocr("source.png", {}, "cpu")
    assert closed == [True]


def test_instance_provider_check_disables_fallback_without_global_patch(monkeypatch, tmp_path):
    marker = object()
    disabled = []
    captured = {}
    session = SimpleNamespace(disable_fallback=lambda: disabled.append(True), get_providers=lambda: ["CPUExecutionProvider"])
    predictor = SimpleNamespace(runner=SimpleNamespace(session=session))
    ocr = SimpleNamespace(paddlex_pipeline=SimpleNamespace(text_det_model=predictor, text_rec_model=predictor), close=lambda: None)
    def construct(**kwargs):
        captured.update(kwargs)
        return ocr
    ort = SimpleNamespace(__version__="1.23.2", InferenceSession=marker, get_available_providers=lambda: ["CPUExecutionProvider"])
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=construct))
    monkeypatch.setitem(sys.modules, "paddlex.inference", SimpleNamespace(load_pipeline_config=lambda _: {"SubModules": {"TextDetection": {}, "TextRecognition": {}}}))
    monkeypatch.setattr(native, "version", lambda name: native.RUNTIME_VERSIONS[name])
    native._create_ocr({"paddle_ocr_det": tmp_path, "paddle_ocr_rec": tmp_path}, "cpu", tmp_path)
    assert disabled == [True, True] and ort.InferenceSession is marker
    assert captured["engine"] == "onnxruntime" and captured["device"] == "cpu"
    assert captured["use_doc_orientation_classify"] is False
    assert captured["use_doc_unwarping"] is False and captured["use_textline_orientation"] is False


def test_failed_provider_initialization_closes_profiles_before_cleanup(monkeypatch, tmp_path):
    ended, closed = [], []
    session = SimpleNamespace(disable_fallback=lambda: None,
        get_providers=lambda: ["CPUExecutionProvider"], end_profiling=lambda: ended.append(True))
    predictor = SimpleNamespace(runner=SimpleNamespace(session=session))
    ocr = SimpleNamespace(paddlex_pipeline=SimpleNamespace(text_det_model=predictor, text_rec_model=predictor),
                          close=lambda: closed.append(True))
    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(__version__="1.23.2",
        preload_dlls=lambda **_: None, get_available_providers=lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"]))
    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=lambda **_: ocr))
    monkeypatch.setitem(sys.modules, "paddlex.inference", SimpleNamespace(load_pipeline_config=lambda _: {
        "SubModules": {"TextDetection": {}, "TextRecognition": {}}}))
    monkeypatch.setattr(native, "version", lambda name: native.RUNTIME_VERSIONS[name])
    with pytest.raises(native.OCRRuntimeError) as failed:
        native._create_ocr({"paddle_ocr_det": tmp_path, "paddle_ocr_rec": tmp_path}, "cuda:0", tmp_path)
    assert failed.value.reason == "selected_provider_unavailable"
    assert ended == [True, True] and closed == [True]


@pytest.mark.parametrize("device", ["auto", "cuda:1", "gpu", "tesseract"])
def test_unsupported_device_never_selects_an_implicit_backend(device):
    with pytest.raises(native.OCRRuntimeError):
        native.resolve_ocr_device({"image_ocr": {"device": device}})
