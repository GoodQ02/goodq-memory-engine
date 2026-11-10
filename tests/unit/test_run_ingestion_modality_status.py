from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest


def _load_run_ingestion_module():
    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

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


def test_aggregate_modality_status_defaults_to_not_attempted():
    run_ingestion = _load_run_ingestion_module()

    status = run_ingestion._aggregate_modality_status([])

    assert status == {
        "vision_clip": "not_attempted",
        "vision_dino": "not_attempted",
        "text_embed": "not_attempted",
        "audio_embed": "not_attempted",
    }


def test_aggregate_modality_status_marks_available_and_unavailable_from_scene_payloads():
    run_ingestion = _load_run_ingestion_module()

    scene_outputs = [
        {
            "keyframe": {
                "clip_embedding": [0.1, 0.2],
                "dino_embedding": [0.3, 0.4],
                "frame_text_embed_meta": {"status": "unavailable"},
            },
            "audio": {
                "clap_meta": {"status": "unavailable"},
                "audio_text_embed_meta": {"status": "unavailable"},
            },
        }
    ]

    status = run_ingestion._aggregate_modality_status(scene_outputs)

    assert status == {
        "vision_clip": "available",
        "vision_dino": "available",
        "text_embed": "unavailable",
        "audio_embed": "unavailable",
    }


def test_aggregate_modality_status_uses_phase6_attempts_for_vision_unavailable():
    run_ingestion = _load_run_ingestion_module()

    phase6_embeddings_result = {
        "clip_embeddings": 3,
        "dino_embeddings": 2,
        "clip_committed": False,
        "dino_committed": False,
        "scene_clip_vectors_written": 0,
        "scene_dino_vectors_written": 0,
    }

    status = run_ingestion._aggregate_modality_status(
        [],
        phase6_embeddings_result=phase6_embeddings_result,
    )

    assert status["vision_clip"] == "unavailable"
    assert status["vision_dino"] == "unavailable"
    assert status["text_embed"] == "not_attempted"
    assert status["audio_embed"] == "not_attempted"


def test_aggregate_modality_status_prefers_available_when_any_scene_succeeds():
    run_ingestion = _load_run_ingestion_module()

    scene_outputs = [
        {"audio": {"audio_text_embed_meta": {"status": "unavailable"}}},
        {"audio": {"audio_text_embed_meta": {"status": "ok"}}},
    ]

    status = run_ingestion._aggregate_modality_status(scene_outputs)

    assert status["text_embed"] == "available"


def test_wsl_wav2vec_embeddings_do_not_count_as_persisted_clap():
    run_ingestion = _load_run_ingestion_module()

    audio_payload = {
        "wsl2_unified": True,
        "audio_backend_effective": "wsl",
        "embeddings": [0.1, 0.2, 0.3],
        "embedding_dim": 768,
        "embeddings_status": "success",
        "clap_meta": {"status": "skipped", "reason": "wsl_unified_embeddings_present"},
    }

    assert run_ingestion._has_wsl_unified_audio_embeddings(audio_payload) is False

    status = run_ingestion._aggregate_modality_status([{"audio": audio_payload}])

    assert status["audio_embed"] == "not_attempted"


def test_aggregate_ocr_sample_results_retains_non_midpoint_observations_and_errors():
    run_ingestion = _load_run_ingestion_module()

    sample_records = [
        {
            "sample_index": 0,
            "timestamp": 0.0,
            "is_midpoint_sample": False,
            "source_path": "scene_0000_ocr_00.jpg",
            "status": "ok",
            "outputs": {
                "ocr_text": None,
                "ocr_meta": {"status": "no_text", "reason": "empty_ocr_text", "engine": "tesseract"},
            },
            "error": None,
        },
        {
            "sample_index": 1,
            "timestamp": 1.5,
            "is_midpoint_sample": False,
            "source_path": "scene_0000_ocr_01.jpg",
            "status": "ok",
            "outputs": {
                "ocr_text": "HARBOR MARINE LABORATORY PERMIT APPROVED",
                "ocr_meta": {"status": "ok", "engine": "tesseract"},
            },
            "error": None,
        },
        {
            "sample_index": 2,
            "timestamp": 3.0,
            "is_midpoint_sample": True,
            "source_path": "scene_0000.jpg",
            "status": "ok",
            "outputs": {
                "ocr_text": None,
                "ocr_meta": {"status": "no_text", "reason": "empty_ocr_text", "engine": "tesseract"},
            },
            "error": None,
        },
    ]

    agg = run_ingestion._aggregate_ocr_sample_results(sample_records, midpoint_timestamp=3.0)
    assert agg["ocr_text"] == "HARBOR MARINE LABORATORY PERMIT APPROVED"
    assert agg["ocr_meta"]["status"] == "ok"
    assert agg["ocr_meta"]["accepted_sample_timestamps"] == [1.5]
    assert agg["ocr_meta"]["non_midpoint_text_observed"] is True
    assert len(agg["ocr_observations"]) == 1
    assert agg["ocr_observations"][0]["timestamp"] == 1.5
    assert agg["ocr_observations"][0]["is_midpoint_sample"] is False
    assert agg["ocr_sampling_errors"] == []

    # Verify sample errors are preserved
    err_records = list(sample_records) + [
        {
            "sample_index": 3,
            "timestamp": 4.5,
            "is_midpoint_sample": False,
            "source_path": "scene_0000_ocr_03.jpg",
            "status": "error",
            "outputs": {
                "ocr_text": None,
                "ocr_meta": {"status": "error", "reason": "ocr_fallback_exception", "fallback_error": "crop failed"},
            },
            "error": "crop failed",
        }
    ]
    agg_err = run_ingestion._aggregate_ocr_sample_results(err_records, midpoint_timestamp=3.0)
    assert len(agg_err["ocr_sampling_errors"]) == 1
    assert "4.500s" in agg_err["ocr_sampling_errors"][0]


def test_aggregate_caption_and_object_detect_sample_results_recovers_non_midpoint_observations():
    run_ingestion = _load_run_ingestion_module()
    caption_records = [
        {
            "sample_index": 0,
            "timestamp": 0.0,
            "is_midpoint_sample": False,
            "source_path": "scene_0000_cap_00.jpg",
            "status": "ok",
            "outputs": {
                "caption": None,
                "caption_meta": {
                    "status": "not_applicable",
                    "reason": "blank_or_low_variance_frame",
                    "engine": "blip",
                    "image_stats": {"gray_std": 0.0, "rgb_std_max": 0.0, "p99_p1": 0.0},
                },
            },
            "error": None,
        },
        {
            "sample_index": 1,
            "timestamp": 1.0,
            "is_midpoint_sample": False,
            "source_path": "scene_0000_cap_01.jpg",
            "status": "ok",
            "outputs": {
                "caption": "a person holding a cup at a wooden table",
                "caption_meta": {
                    "status": "ok",
                    "engine": "blip",
                    "image_stats": {"gray_std": 42.1, "rgb_std_max": 45.0, "p99_p1": 160.0},
                },
            },
            "error": None,
        },
        {
            "sample_index": 2,
            "timestamp": 2.0,
            "is_midpoint_sample": True,
            "source_path": "scene_0000.jpg",
            "status": "ok",
            "outputs": {
                "caption": "an empty wooden table in a room",
                "caption_meta": {
                    "status": "ok",
                    "engine": "blip",
                    "image_stats": {"gray_std": 35.4, "rgb_std_max": 38.2, "p99_p1": 140.0},
                },
            },
            "error": None,
        },
    ]

    cap_agg = run_ingestion._aggregate_caption_sample_results(caption_records, midpoint_timestamp=2.0)
    assert cap_agg["caption"] == "an empty wooden table in a room"
    assert cap_agg["caption_meta"]["status"] == "ok"
    assert cap_agg["caption_meta"]["accepted_sample_timestamps"] == [1.0, 2.0]
    assert cap_agg["caption_meta"]["non_midpoint_caption_observed"] is True
    assert cap_agg["caption_meta"]["distinct_captions"] == [
        "a person holding a cup at a wooden table",
        "an empty wooden table in a room",
    ]
    assert len(cap_agg["caption_observations"]) == 2
    assert cap_agg["caption_observations"][0]["timestamp"] == 1.0
    assert cap_agg["caption_observations"][0]["is_midpoint_sample"] is False

    # All-blank caption scene preserves not_applicable + reason + midpoint stats
    blank_only = [
        {
            "sample_index": 0,
            "timestamp": 0.0,
            "is_midpoint_sample": False,
            "source_path": "scene_0001_cap_00.jpg",
            "status": "ok",
            "outputs": {
                "caption": None,
                "caption_meta": {
                    "status": "not_applicable",
                    "reason": "blank_or_low_variance_frame",
                    "engine": "blip",
                    "image_stats": {"gray_std": 0.2, "rgb_std_max": 0.2, "p99_p1": 1.0},
                },
            },
            "error": None,
        },
        {
            "sample_index": 1,
            "timestamp": 1.0,
            "is_midpoint_sample": True,
            "source_path": "scene_0001.jpg",
            "status": "ok",
            "outputs": {
                "caption": None,
                "caption_meta": {
                    "status": "not_applicable",
                    "reason": "blank_or_low_variance_frame",
                    "engine": "blip",
                    "image_stats": {"gray_std": 0.0, "rgb_std_max": 0.0, "p99_p1": 0.0},
                },
            },
            "error": None,
        },
    ]
    blank_agg = run_ingestion._aggregate_caption_sample_results(blank_only, midpoint_timestamp=1.0)
    assert blank_agg["caption"] is None
    assert blank_agg["caption_meta"]["status"] == "not_applicable"
    assert blank_agg["caption_meta"]["reason"] == "blank_or_low_variance_frame"
    assert blank_agg["caption_meta"]["image_stats"]["gray_std"] == 0.0

    # Object detection aggregation where midpoint has 0 objects and non-midpoint has 2 objects
    object_records = [
        {
            "sample_index": 0,
            "timestamp": 1.0,
            "is_midpoint_sample": False,
            "source_path": "scene_0000_obj_01.jpg",
            "status": "ok",
            "outputs": {
                "objects": [
                    {"label": "person", "score": 0.92, "bbox": [10.0, 20.0, 110.0, 220.0]},
                    {"label": "cup", "score": 0.81, "bbox": [120.0, 140.0, 150.0, 180.0]},
                ],
                "detect_meta": {"status": "ok", "engine": "opencv-dnn", "model": "opencv_yolox", "device": "cuda"},
            },
            "error": None,
        },
        {
            "sample_index": 1,
            "timestamp": 2.0,
            "is_midpoint_sample": True,
            "source_path": "scene_0000.jpg",
            "status": "ok",
            "outputs": {
                "objects": [],
                "detect_meta": {"status": "ok", "engine": "opencv-dnn", "model": "opencv_yolox", "device": "cuda"},
            },
            "error": None,
        },
    ]
    obj_agg = run_ingestion._aggregate_object_detect_sample_results(object_records, midpoint_timestamp=2.0)
    assert obj_agg["detect_meta"]["status"] == "ok"
    assert obj_agg["detect_meta"]["count"] == 2
    assert obj_agg["detect_meta"]["accepted_sample_timestamps"] == [1.0]
    assert obj_agg["detect_meta"]["non_midpoint_objects_observed"] is True
    assert len(obj_agg["objects"]) == 2
    assert obj_agg["objects"][0]["label"] == "person"
    assert obj_agg["objects"][0]["timestamp"] == 1.0
    assert obj_agg["objects"][0]["is_midpoint_sample"] is False
    assert obj_agg["objects"][0]["source_path"] == "scene_0000_obj_01.jpg"
    assert len(obj_agg["object_observations"]) == 1
    assert obj_agg["object_observations"][0]["timestamp"] == 1.0


@pytest.mark.parametrize("visual_timestamp", [0.0, 1.0])
@pytest.mark.parametrize("fail_first_extraction", [False, True])
def test_process_frame_and_process_frame_async_both_recover_non_midpoint_caption_and_objects(monkeypatch, tmp_path, visual_timestamp, fail_first_extraction):
    import asyncio

    run_ingestion = _load_run_ingestion_module()
    cfg_json = tmp_path / "cfg.json"
    cfg_json.write_text("{}", encoding="utf-8")
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"video")
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    scene = {"index": 0, "start": 0.0, "end": 4.0, "duration": 4.0}
    extracted_timestamps = []

    def _fake_extract_keyframe(
        _ffmpeg,
        _video_path,
        _scene,
        out_dir,
        *,
        scene_id=None,
        video_id=None,
        sample_timestamp=None,
        sample_suffix="",
    ):
        extracted_timestamps.append(2.0 if sample_timestamp is None else sample_timestamp)
        if fail_first_extraction and sample_timestamp == 3.0 and extracted_timestamps.count(3.0) == 1:
            raise RuntimeError("transient sample decode failure")
        name = f"{scene_id or 'scene_0000'}{sample_suffix}.jpg"
        p = Path(out_dir) / name
        p.write_bytes(b"jpg")
        return p

    def _step_outputs_for(step_name: str, payload: dict) -> dict:
        ts = float(payload.get("timestamp", 2.0))
        is_mid = bool(payload.get("is_midpoint_sample", abs(ts - 2.0) <= 1e-6))
        if step_name == "image_ocr":
            if abs(ts - 1.0) <= 1e-6:
                return {
                    "ocr_text": "DOCK 4 CARGO MANIFEST",
                    "ocr_meta": {"status": "ok", "engine": "tesseract", "sample_timestamp": ts, "is_midpoint_sample": is_mid},
                }
            return {
                "ocr_text": None,
                "ocr_meta": {"status": "no_text", "reason": "empty_ocr_text", "engine": "tesseract", "sample_timestamp": ts, "is_midpoint_sample": is_mid},
            }
        if step_name == "image_caption":
            if isinstance(payload.get("samples"), list):
                return {
                    "samples": [
                        _step_outputs_for("image_caption", sample)
                        for sample in payload["samples"]
                    ]
                }
            if abs(ts - visual_timestamp) <= 1e-6:
                return {
                    "caption": "a person carrying a suitcase near dock 4",
                    "caption_meta": {"status": "ok", "engine": "wevisone-vl", "sample_timestamp": ts, "is_midpoint_sample": is_mid},
                }
            return {
                "caption": "an empty pier walkway by the water",
                "caption_meta": {"status": "ok", "engine": "wevisone-vl", "sample_timestamp": ts, "is_midpoint_sample": is_mid},
            }
        if step_name == "object_detect":
            if abs(ts - visual_timestamp) <= 1e-6:
                return {
                    "objects": [
                        {"label": "person", "score": 0.91, "bbox": [12.0, 18.0, 120.0, 240.0]},
                        {"label": "suitcase", "score": 0.86, "bbox": [125.0, 150.0, 190.0, 235.0]},
                    ],
                    "detect_meta": {"status": "ok", "engine": "opencv-dnn", "model": "opencv_yolox", "sample_timestamp": ts, "is_midpoint_sample": is_mid},
                }
            return {
                "objects": [],
                "detect_meta": {"status": "ok", "engine": "opencv-dnn", "model": "opencv_yolox", "sample_timestamp": ts, "is_midpoint_sample": is_mid},
            }
        if step_name == "face_embed":
            return {"faces": [], "faces_meta": {"status": "ok", "engine": "opencv-yunet-sface"}}
        if step_name == "text_embed":
            return {"embedding_meta": {"status": "ok", "point_id": "pt_1", "collection": "goodq_text"}}
        return {}

    monkeypatch.setattr(run_ingestion, "_extract_keyframe", _fake_extract_keyframe)
    monkeypatch.setattr(run_ingestion, "_persist_frame_semantic_entities", lambda *a, **kw: None)
    monkeypatch.setattr(run_ingestion, "_log_visual_to_ucf_ledger", lambda *a, **kw: None)
    monkeypatch.setattr(run_ingestion, "_run_step", lambda _env, step_name, item, _cfg: _step_outputs_for(step_name, item))

    async def _fake_run_step_async(_env, step_name, item, _cfg):
        return {"status": "ok", "outputs": _step_outputs_for(step_name, item)}

    monkeypatch.setattr(run_ingestion, "_run_step_async", _fake_run_step_async)

    sync_res = run_ingestion._process_frame(
        cfg_json,
        "ffmpeg",
        video_path,
        scene,
        frame_dir,
        "vid_hash_01",
        "scene_0000",
    )
    expected_extractions = sorted([0.0, 1.0, 2.0, 3.0, 3.95] + ([3.0] if fail_first_extraction else []))
    assert sorted(extracted_timestamps) == expected_extractions
    extracted_timestamps.clear()
    async_res = asyncio.run(
        run_ingestion._process_frame_async(
            cfg_json,
            "ffmpeg",
            video_path,
            scene,
            frame_dir,
            "vid_hash_01",
            "scene_0000",
            asyncio.Lock(),
            asyncio.Lock(),
        )
    )
    assert sorted(extracted_timestamps) == expected_extractions

    for caller_name, res in (("sync", sync_res), ("async", async_res)):
        data = res["data"]
        errors = sum((data.get(f"{kind}_sampling_errors", []) for kind in ("ocr", "caption", "object", "face")), [])
        assert len(errors) == int(fail_first_extraction), caller_name
        # Midpoint caption is preserved as primary while non-midpoint caption is captured in caption_observations
        assert data["caption"] == "an empty pier walkway by the water", caller_name
        assert data["caption_meta"]["non_midpoint_caption_observed"] is True, caller_name
        assert visual_timestamp in data["caption_meta"]["accepted_sample_timestamps"], caller_name
        non_mid_caps = [obs for obs in data["caption_observations"] if not obs["is_midpoint_sample"] and abs(obs["timestamp"] - visual_timestamp) <= 1e-6]
        assert len(non_mid_caps) == 1, caller_name
        assert non_mid_caps[0]["caption"] == "a person carrying a suitcase near dock 4", caller_name

        # Non-midpoint objects are recovered with exact timestamp and provenance
        assert data["detect_meta"]["non_midpoint_objects_observed"] is True, caller_name
        assert data["detect_meta"]["accepted_sample_timestamps"] == [visual_timestamp], caller_name
        assert [o["label"] for o in data["objects"]] == ["person", "suitcase"], caller_name
        assert all(abs(o["timestamp"] - visual_timestamp) <= 1e-6 and o["is_midpoint_sample"] is False for o in data["objects"]), caller_name
        assert len(data["object_observations"]) == 1, caller_name
        assert data["object_observations"][0]["timestamp"] == visual_timestamp, caller_name

        # Both distinct captions and detected object labels are embedded in frame_text
        assert "a person carrying a suitcase near dock 4" in data["frame_text"], caller_name
        assert "an empty pier walkway by the water" in data["frame_text"], caller_name
        assert "suitcase" in data["frame_text"], caller_name
        assert "DOCK 4 CARGO MANIFEST" in data["frame_text"], caller_name


@pytest.mark.parametrize("failed_sample", [False, True])
def test_object_sample_absence_does_not_hide_failed_inference(failed_sample):
    run_ingestion = _load_run_ingestion_module()
    records = [
        {
            "sample_index": index,
            "timestamp": timestamp,
            "status": "ok",
            "outputs": {"objects": [], "detect_meta": {"status": "ok", "model": "opencv_nanodet"}},
        }
        for index, timestamp in enumerate([0.0, 1.0, 2.0])
    ]
    if failed_sample:
        records[0]["outputs"]["detect_meta"] = {"status": "unavailable", "error": "missing model"}
    result = run_ingestion._aggregate_object_detect_sample_results(records, midpoint_timestamp=1.0)
    assert result["objects"] == []
    assert result["detect_meta"]["sample_timestamps"] == [0.0, 1.0, 2.0]
    if failed_sample:
        assert result["detect_meta"]["status"] == "unavailable"
        assert result["object_sampling_warnings"]
    else:
        assert result["detect_meta"]["status"] == "not_applicable"
        assert result["detect_meta"]["reason"] == "no_detected_object"
        assert result["detect_meta"]["accepted_sample_count"] == 0
