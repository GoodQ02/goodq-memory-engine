from __future__ import annotations

import importlib
import sys
import types
from contextlib import nullcontext
import pytest


def _load_image_caption_module():
    return importlib.import_module("steps.image_caption.step")


def _load_object_detect_module():
    return importlib.import_module("steps.object_detect.step")


@pytest.mark.parametrize("generation_fails", [True, False])
def test_image_caption_generation_and_diagnostics(monkeypatch, tmp_path, capsys, generation_fails):
    import numpy as np
    from PIL import Image

    module = _load_image_caption_module()

    arr = np.full((180, 320, 3), 20, dtype=np.uint8)
    arr[40:140, 80:240] = [200, 180, 140]
    image_path = tmp_path / "scene_0010.jpg"
    Image.fromarray(arr, mode="RGB").save(image_path, quality=95)

    class _FakeTokens:
        shape = (1, 6)

    class _FakeGenerated:
        def __getitem__(self, _idx):
            return _FakeTokens()

    class _FakeInputIds:
        shape = (1, 10)

    class _FakeBatch(dict):
        input_ids = _FakeInputIds()

        def to(self, _device):
            return self

    class _FakeProc:
        def apply_chat_template(self, *_args, **_kwargs):
            return _FakeBatch()

        def batch_decode(self, *_args, **_kwargs):
            return ["a man holding a microphone"]

    class _FakeModel:
        device = "cuda"

        def generate(self, **_kwargs):
            assert _kwargs["max_new_tokens"] == 256
            assert _kwargs["do_sample"] is False
            if generation_fails:
                raise RuntimeError("synthetic caption failure")
            return _FakeGenerated()

    torch_mod = types.ModuleType("torch")
    torch_mod.bfloat16 = "bfloat16"
    torch_mod.float32 = "float32"
    torch_mod.inference_mode = lambda: nullcontext()
    torch_mod.cuda = types.SimpleNamespace(is_available=lambda: True)

    monkeypatch.setitem(sys.modules, "torch", torch_mod)
    monkeypatch.setattr(module, "_load_model", lambda _cfg: False)
    monkeypatch.setattr(
        module,
        "_MODEL",
        {"model": _FakeModel(), "processor": _FakeProc(), "device": "cuda", "load_seconds": 0.1},
    )
    monkeypatch.setattr(module.GPUManager, "clear_cache", lambda: None)

    from cli.step_runner import run_step
    result = run_step("image_caption", {"source_path": str(image_path)}, {})
    caption_meta = result["caption_meta"]

    if generation_fails:
        assert caption_meta["status"] == "error"
        assert caption_meta["exc_type"] == "RuntimeError"
    else:
        assert result["caption"] == "a man holding a microphone"
        assert caption_meta["status"] == "ok"
        assert caption_meta["engine"] == "wevisone-vl"
        assert caption_meta["generation"] == {"max_new_tokens": 256, "do_sample": False}
    stderr = capsys.readouterr().err
    assert '"event": "image_caption_diagnostics"' in stderr
    assert '"stage": "before_inference"' in stderr


def test_object_detect_reports_diagnostics_on_python_error(monkeypatch, tmp_path, capsys):
    module = _load_object_detect_module()

    image_path = tmp_path / "scene_0013.jpg"
    image_path.write_bytes(b"fake")

    runtime = module.DetectorRuntime(model_id="opencv_nanodet", device="cpu", net=object())
    monkeypatch.setattr(module, "_select_model_id", lambda _cfg: "opencv_nanodet")
    monkeypatch.setattr(module, "_load_detector", lambda _cfg: runtime)
    monkeypatch.setattr(module, "_detect_with_runtime", lambda *_args: (_ for _ in ()).throw(RuntimeError("synthetic detect failure")))
    monkeypatch.setattr(module.GPUManager, "clear_cache", lambda: None)

    result = module.object_detect({"source_path": str(image_path)}, {})
    detect_meta = result["detect_meta"]

    assert detect_meta["status"] == "error"
    assert detect_meta["exc_type"] == "RuntimeError"
    stderr = capsys.readouterr().err
    assert '"event": "object_detect_diagnostics"' in stderr
    assert '"stage": "before_inference"' in stderr


@pytest.mark.parametrize("fill_value", [(240, 240, 240), (30, 30, 30), (0, 0, 0)])
def test_image_caption_suppresses_blank_frames_and_records_stats(monkeypatch, tmp_path, fill_value):
    from PIL import Image
    from cli.step_runner import _derive_step_log_outcome, run_step

    module = _load_image_caption_module()
    image_path = tmp_path / "blank_frame.jpg"
    Image.new("RGB", (320, 180), color=fill_value).save(image_path, quality=95)

    load_called = {"vlm": False}

    def _forbid_vlm_load(_cfg):
        load_called["vlm"] = True
        return False

    monkeypatch.setattr(module, "_load_model", _forbid_vlm_load)

    result = run_step("image_caption", {"source_path": str(image_path)}, {})
    assert load_called["vlm"] is False
    assert result["caption"] is None
    caption_meta = result["caption_meta"]
    assert caption_meta["status"] == "not_applicable"
    assert caption_meta["reason"] == "blank_or_low_variance_frame"
    assert caption_meta["engine"] == "wevisone-vl"

    stats = caption_meta["image_stats"]
    assert isinstance(stats, dict)
    assert stats["gray_std"] < 1.0
    assert stats["rgb_std_max"] < 1.0
    assert stats["p99_p1"] < 2.0
    assert stats["grad_mean"] < 0.5

    status, err, extra = _derive_step_log_outcome("image_caption", result, verbose=False)
    assert status == "not_applicable"
    assert err is None
    assert extra is not None
    assert extra["reason"] == "blank_or_low_variance_frame"
    assert extra["result_meta"]["caption_meta"]["image_stats"] == stats


def test_image_caption_allows_dark_or_sparse_real_frames_and_records_stats(monkeypatch, tmp_path):
    import numpy as np
    from PIL import Image
    from cli.step_runner import _derive_step_log_outcome, run_step

    module = _load_image_caption_module()
    # Dark night scene with a localized feature (std > 10, p99_p1 > 40)
    arr = np.full((180, 320, 3), 12, dtype=np.uint8)
    arr[60:120, 110:210] = [165, 150, 130]
    image_path = tmp_path / "dark_sparse_scene.jpg"
    Image.fromarray(arr, mode="RGB").save(image_path, quality=95)

    monkeypatch.setattr(module, "_load_model", lambda _cfg: False)
    monkeypatch.setattr(module, "_describe", lambda _img: ("a dark street with a car", 6))
    monkeypatch.setitem(module._MODEL, "device", "cpu")
    monkeypatch.setattr(module.GPUManager, "clear_cache", lambda: None)

    result = run_step("image_caption", {"source_path": str(image_path)}, {})
    assert result["caption"] == "a dark street with a car"
    caption_meta = result["caption_meta"]
    assert caption_meta["status"] == "ok"
    stats = caption_meta["image_stats"]
    assert stats["rgb_std_max"] > 10.0
    assert stats["p99_p1"] > 40.0

    status, err, extra = _derive_step_log_outcome("image_caption", result, verbose=False)
    assert status == "ok"
    assert err is None
    assert extra["result_meta"]["caption_meta"]["image_stats"] == stats


def test_visual_observation_projection_and_downstream_consumers():
    from api.utils.media_projection import (
        sanitize_detected_objects,
        sanitize_visual_meta,
        sanitize_visual_observations,
    )
    from steps.common.scene_summarizer import generate_scene_summary_template
    from steps.video.entity_extractor import EntityExtractor

    raw_obs = [
        {
            "sample_index": 1,
            "timestamp": 1.0,
            "is_midpoint_sample": False,
            "source_path": "L:\\_DATA\\GoodQ_Data\\processing\\frames\\scene_0000_cap_01.jpg",
            "caption": "Avery holding a coffee mug in Central Park",
            "caption_meta": {"status": "ok", "engine": "blip"},
        },
        {
            "sample_index": 2,
            "timestamp": 2.0,
            "is_midpoint_sample": True,
            "source_path": "L:\\_DATA\\GoodQ_Data\\processing\\frames\\scene_0000.jpg",
            "caption": "an empty wooden booth in a diner",
            "caption_meta": {"status": "ok", "engine": "blip"},
        },
    ]
    safe_obs = sanitize_visual_observations("vid_hash_123", raw_obs)
    assert len(safe_obs) == 2
    assert "source_path" not in safe_obs[0]
    assert safe_obs[0]["frame_name"] == "scene_0000_cap_01.jpg"
    assert safe_obs[0]["frame_endpoint"] == "/api/media/video/vid_hash_123/frame/scene_0000_cap_01.jpg"

    raw_objs = [
        {
            "label": "cup",
            "score": 0.91,
            "bbox": [10.0, 20.0, 50.0, 80.0],
            "timestamp": 1.0,
            "sample_index": 1,
            "is_midpoint_sample": False,
            "source_path": "L:\\_DATA\\GoodQ_Data\\processing\\frames\\scene_0000_obj_01.jpg",
        }
    ]
    safe_objs = sanitize_detected_objects("vid_hash_123", raw_objs)
    assert len(safe_objs) == 1
    assert "source_path" not in safe_objs[0]
    assert safe_objs[0]["frame_name"] == "scene_0000_obj_01.jpg"
    assert safe_objs[0]["frame_endpoint"] == "/api/media/video/vid_hash_123/frame/scene_0000_obj_01.jpg"
    assert safe_objs[0]["timestamp"] == 1.0
    assert safe_objs[0]["is_midpoint_sample"] is False

    safe_meta = sanitize_visual_meta(
        "vid_hash_123",
        {
            "status": "ok",
            "engine": "blip",
            "source_path": "L:\\_DATA\\GoodQ_Data\\processing\\frames\\scene_0000.jpg",
            "observations": raw_obs,
        },
    )
    assert "source_path" not in safe_meta
    assert safe_meta["frame_endpoint"] == "/api/media/video/vid_hash_123/frame/scene_0000.jpg"
    assert safe_meta["observations"][0]["frame_endpoint"] == "/api/media/video/vid_hash_123/frame/scene_0000_cap_01.jpg"

    bundle = {
        "scene_id": 0,
        "start_time": 0.0,
        "end_time": 4.0,
        "duration": 4.0,
        "frame": {
            "caption": "an empty wooden booth in a diner",
            "caption_observations": raw_obs,
            "objects": [{"label": "cup", "score": 0.91, "timestamp": 1.0}],
            "faces": [],
            "ocr_text": None,
        },
        "keyframe": {
            "caption": "an empty wooden booth in a diner",
            "caption_observations": raw_obs,
            "objects": [{"label": "cup", "score": 0.91, "timestamp": 1.0}],
            "faces": [],
            "ocr_text": None,
        },
        "audio": {"transcript": ""},
    }
    summary = generate_scene_summary_template(bundle)
    assert "an empty wooden booth in a diner" in summary
    assert "Avery holding a coffee mug in Central Park" in summary

    entities = EntityExtractor({"family_names": ["avery"]}).extract_from_scene(bundle, scene_id="scene_0000", video_id="vid_hash_123")
    entity_names = {e.name.lower() for e in entities}
    assert "avery" in entity_names
    assert "cup" in entity_names
    cup_ent = next(e for e in entities if e.name.lower() == "cup")
    assert cup_ent.timestamps == [1.0]
