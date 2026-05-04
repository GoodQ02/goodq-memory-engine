from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "diagnostics" / "native_model_stability_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("native_model_stability_smoke", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_classifies_native_crash_return_code():
    smoke = _load_module()

    result = {"return_code": 3221226505, "probe": None, "timeout": False}

    assert smoke._classify_probe_result(result) == "native_crash"


def test_classifies_missing_model_cache_from_probe():
    smoke = _load_module()

    result = {
        "return_code": 0,
        "timeout": False,
        "probe": {
            "imports": [{"module": "torch", "ok": True}],
            "model_load": {"attempted": True, "status": "missing_model_cache"},
        },
    }

    assert smoke._classify_probe_result(result) == "missing_model_cache"


def test_classifies_import_failure_before_model_load():
    smoke = _load_module()

    result = {
        "return_code": 0,
        "timeout": False,
        "probe": {
            "imports": [{"module": "ultralytics", "ok": False, "error_type": "ImportError"}],
            "model_load": {"attempted": False, "status": "not_requested"},
        },
    }

    assert smoke._classify_probe_result(result) == "import_failed"


def test_run_smoke_has_read_only_safety_boundary(monkeypatch):
    smoke = _load_module()

    def fake_run_target(target, **kwargs):
        return {
            "target": target,
            "step": smoke.TARGETS[target]["step"],
            "env": smoke.TARGETS[target]["env"],
            "classification": "metadata_only",
        }

    monkeypatch.setattr(smoke, "_run_target", fake_run_target)

    report = smoke.run_smoke(["object_detect"], conda_exe="conda", model_load=False)

    assert report["mode"] == "metadata"
    assert report["targets"][0]["step"] == "object_detect"
    assert report["safety_boundary"] == {
        "ingestion_triggered": False,
        "scene_artifacts_written": False,
        "qdrant_written": False,
        "kg_written": False,
        "reports_written": False,
        "network_downloads_allowed": False,
    }


def test_no_model_load_is_default():
    smoke = _load_module()

    args = smoke._parse_args(["--json"])

    assert args.model_load is False
    assert args.no_model_load is False
    assert args.allow_downloads is False


def test_model_load_targets_record_runtime_like_loaders():
    smoke = _load_module()

    assert smoke.TARGETS["object_detect"]["loader"] == "yolo"
    assert smoke.TARGETS["image_caption"]["loader"] == "blip"
    assert smoke.TARGETS["image_embed_dino"]["loader"] == "auto_model"
    assert smoke.TARGETS["audio_embed_clap"]["loader"] == "clap"
    assert "pytorch_model.bin" in smoke.TARGETS["audio_embed_clap"]["required_files"]


def test_child_probe_uses_goodq_model_cache_for_model_loads():
    smoke = _load_module()

    child = smoke.CHILD_PROBE

    assert "get_runtime_paths(load_configs({}), \"models_cache\")" in child
    assert "HF_HOME" in child
    assert "BlipForConditionalGeneration" in child
    assert "AutoFeatureExtractor" in child
    assert "ClapModel" in child
