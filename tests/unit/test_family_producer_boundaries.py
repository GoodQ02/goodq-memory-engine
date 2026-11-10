"""Caller regressions from the isolated full-movie baseline."""
from __future__ import annotations

import builtins
import json
import sys
import types
from datetime import datetime

import pytest


def test_ocr_step_runner_ignores_gpu_policy_and_runs_cpu_engine(monkeypatch, tmp_path):
    from cli import step_runner
    from steps.common import step_logger
    from steps.image_ocr import step as ocr_step
    from PIL import Image

    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "1")
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")
    gpu_calls = []
    monkeypatch.setitem(sys.modules, "common.gpu_manager", types.SimpleNamespace(
        initialize_gpu_for_step=lambda **kw: gpu_calls.append(kw),
    ))
    original_import = builtins.__import__

    def import_without_cuda(name, *args, **kwargs):
        if name == "steps.common.gpu_config":
            raise RuntimeError("GOODQ_REQUIRE_GPU=1 but GPU auto-config is disabled (GOODQ_NO_AUTO_GPU=1)")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_cuda)
    image = tmp_path / "frame.jpg"
    Image.new("RGB", (100, 80)).save(image)
    monkeypatch.setattr(ocr_step, "run_native_ocr", lambda *_: ({
        "rec_texts": ["OCT 23 2002"], "rec_boxes": [[1, 2, 90, 15]],
        "rec_polys": [[[1, 2], [90, 2], [90, 15], [1, 15]]], "rec_scores": [0.95]}, {}))
    cfg = {"ingestion_isolation": True, "image_ocr": {"device": "cpu"},
           "paths": {"log_dir": str(tmp_path / "logs")}}
    monkeypatch.setattr(step_runner, "load_step_config", lambda *_: cfg)
    monkeypatch.setattr(step_logger, "MISSION_LOGGER_AVAILABLE", False)
    inp, out = tmp_path / "input.json", tmp_path / "output.json"
    inp.write_text(json.dumps({"source_path": str(image)}))
    monkeypatch.setattr(sys, "argv", ["step_runner", "--step", "image_ocr", "--in", str(inp), "--out", str(out)])
    step_runner.main()
    result = json.loads(out.read_text())
    assert result["ocr_text"] == "OCT 23 2002"
    assert result["ocr_meta"]["status"] == "ok"
    assert result["ocr_meta"]["engine"] == "paddleocr-3.7-onnxruntime-cpu"
    assert result["time_hints"]["explicit_dates"] == ["2002-10-23"]
    assert gpu_calls == []
    assert json.loads((tmp_path / "logs/step_runs.jsonl").read_text())["status"] == "ok"


def test_ocr_reserves_vram_only_for_selected_cuda():
    from common.vram_allocator import STEP_VRAM_FRACTIONS, step_uses_gpu_backend
    assert STEP_VRAM_FRACTIONS["image_ocr"] > 0
    assert not step_uses_gpu_backend("image_ocr", cfg={"image_ocr": {"device": "cpu"}})
    assert step_uses_gpu_backend("image_ocr", cfg={"image_ocr": {"device": "cuda:0"}})


@pytest.mark.parametrize("truncated", [False, True])
def test_scene_context_uses_supported_nonthinking_request_and_reports_truncation(monkeypatch, truncated):
    from lib.llm_client import LLMClient, HealthStatus
    from steps.common.llm_model_factory import build_llm_models
    from steps.common.context_analyzer_llm import analyze_scene_context_llm

    monkeypatch.setenv("GOODQ_HOST_PROFILE", "GPU_ENHANCED")
    cfg = {"llm": {"vllm_url": "http://127.0.0.1:38005/v1", "ollama_url": "http://127.0.0.1:11434/v1"}}
    model = build_llm_models(cfg)[0]
    client = LLMClient(models=[model], health_check_interval=60, max_retries=1,
        timeout=5, cache_ttl=60, enable_health_checks=False, allow_auto_activation=False)
    client.health_status[model.name] = HealthStatus(True, datetime.now(), 0)
    client.last_health_check = datetime.now()
    payloads = []
    def post(_url, **kwargs):
        payload = kwargs["json"]
        payloads.append(payload)
        no_thinking = payload.get("reasoning_effort") == "none"
        complete = no_thinking and not truncated
        content = json.dumps({"narrative_summary": "A person plays piano.", "key_moments": ["Playing piano"],
            "emotional_arc": "", "context_tags": ["piano"], "activity_description": "A person plays piano."}) if complete else ""
        return types.SimpleNamespace(status_code=200, json=lambda: {"choices": [{
            "finish_reason": "stop" if complete else "length", "message": {"content": content}}]})
    monkeypatch.setattr(client.session, "post", post)
    try:
        result = analyze_scene_context_llm({"caption": "a person at a piano", "objects": [{"label": "piano"}],
            "transcript": "I will play a few piano songs for you now.", "speakers": ["SPEAKER_00"]}, cfg, llm_client=client)
    finally:
        client.close()
    assert result["status"] == ("fallback" if truncated else "ok")
    assert result["reason"] == ("llm_output_truncated" if truncated else "model_output")
    assert payloads[0]["reasoning_effort"] == "none"
    assert "think" not in payloads[0]


def test_cross_modal_harmonization_caller_preserves_raw_observations_and_projects_distinct_objects_after_tenth_slot(
    monkeypatch,
    tmp_path,
):
    from pathlib import Path
    from api.routes.scenes import _build_scene_response
    from cli import step_runner
    from steps.common import step_logger
    from steps.common.context_analyzer_llm import _build_scene_context_prompts, _normalize_scene_context_payload
    from steps.video import cross_modal_harmonizer

    monkeypatch.setattr(step_logger, "MISSION_LOGGER_AVAILABLE", False)

    video_dir = tmp_path / "processing" / "sample_clip" / "video"
    objects_dir = tmp_path / "processing" / "sample_clip" / "objects"
    video_dir.mkdir(parents=True)
    objects_dir.mkdir(parents=True)

    scene_id = "scene_dup_objects_001"
    raw_detections = [
        {"label": "book", "score": round(0.20 + idx * 0.01, 4), "score_kind": "detector_confidence", "box": [10, 10, 40, 40]}
        for idx in range(11)
    ] + [
        {"label": "chair", "score": 0.52, "score_kind": "detector_confidence", "box": [50, 50, 120, 140]},
        {"label": "curtain", "score": 0.61, "score_kind": "detector_confidence", "box": [0, 0, 90, 200]},
        {"label": "lamp", "score": 0.58, "score_kind": "detector_confidence", "box": [130, 40, 160, 110]},
        {"label": "chair", "score": 0.74, "score_kind": "detector_confidence", "box": [55, 52, 122, 142]},
    ]
    sample_observations = [
        {
            "sample_index": 0,
            "timestamp": 1.0,
            "frame_path": str(video_dir / "f0.jpg"),
            "detections": raw_detections[:11],
            "detect_meta": {"status": "ok", "model": "yolov8m-worldv2"},
        },
        {
            "sample_index": 1,
            "timestamp": 3.0,
            "frame_path": str(video_dir / "f1.jpg"),
            "detections": raw_detections[11:],
            "detect_meta": {"status": "ok", "model": "yolov8m-worldv2"},
        },
    ]
    (objects_dir / f"{scene_id}_objects.json").write_text(
        json.dumps(
            {
                "scene_id": scene_id,
                "detections": raw_detections,
                "sample_observations": sample_observations,
                "detect_meta": {"status": "ok", "model": "yolov8m-worldv2"},
            }
        ),
        encoding="utf-8",
    )

    manifest_path = video_dir / "scene_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "video_id": "sample_clip",
                "scenes": [
                    {
                        "id": scene_id,
                        "scene_id": scene_id,
                        "index": 0,
                        "start": 0.0,
                        "end": 4.0,
                        "duration": 4.0,
                        "visual_caption": "an indoor room with a chair",
                        "caption": "an indoor room with a chair",
                        "audio": {"full_text": "Look at the curtain over there."},
                        "objects": raw_detections,
                        "object_observations": sample_observations,
                        "detect_meta": {"status": "ok", "model": "yolov8m-worldv2"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    captured_prompts: list[str] = []

    def fake_analyze_scene_context(scene_meta, cfg, **_kwargs):
        _sys_prompt, user_prompt = _build_scene_context_prompts(scene_meta)
        captured_prompts.append(user_prompt)
        normalized = _normalize_scene_context_payload(
            {
                "narrative_summary": "An indoor room with a chair and a curtain.",
                "activity_description": "Static view of an indoor room with a chair and a curtain.",
                "key_moments": ["An indoor room with a chair and a curtain"],
                "emotional_arc": "calm indoor setting",
                "context_tags": ["room", "chair", "curtain", "lamp"],
            },
            scene_meta,
        )
        assert normalized is not None
        return {**normalized, "status": "ok", "reason": "model_output", "source": "scene_context_llm"}

    monkeypatch.setattr(cross_modal_harmonizer, "analyze_scene_context_llm", fake_analyze_scene_context)
    cfg = {
        "ingestion_isolation": True,
        "features": {"enable_llm_refinement": False, "enable_scene_context_llm": True},
        "llm": {"features": {"scene_context_analysis": True}},
        "paths": {
            "processing": str(tmp_path / "processing"),
            "processing_dir": str(tmp_path / "processing"),
            "log_dir": str(tmp_path / "logs"),
        },
    }
    monkeypatch.setattr(step_runner, "load_step_config", lambda *_: cfg)

    step_in_path = tmp_path / "step_input.json"
    step_in_path.write_text(
        json.dumps({"scene_manifest_path": str(manifest_path), "video_id": "sample_clip"}),
        encoding="utf-8",
    )
    step_out_path = tmp_path / "step_output.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["step_runner", "--step", "cross_modal_harmonization", "--in", str(step_in_path), "--out", str(step_out_path)],
    )
    step_runner.main()

    assert len(captured_prompts) == 1
    assert "- Visible objects: book, chair, curtain, lamp" in captured_prompts[0]
    assert "book, book" not in captured_prompts[0]

    step_result = json.loads(step_out_path.read_text(encoding="utf-8"))
    persisted_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    persisted_scene = persisted_manifest["scenes"][0]
    persisted_tidx = json.loads(Path(step_result["temporal_index_path"]).read_text(encoding="utf-8"))
    persisted_seg = persisted_tidx["segments"][0]

    assert len(persisted_scene["objects"]) == 15
    assert persisted_scene["objects"] == raw_detections
    assert len(persisted_seg["detected_objects"]) == 15
    assert persisted_seg["detected_objects"] == raw_detections
    assert len(persisted_seg["object_observations"]) == 2
    assert persisted_seg["object_observations"][0]["timestamp"] == 1.0
    assert persisted_seg["object_observations"][1]["timestamp"] == 3.0
    assert persisted_seg["object_observations"][1]["detections"][3]["score"] == 0.74

    ctx_llm = persisted_seg["scene_context_llm"]
    assert "curtain" in ctx_llm["context_tags"]
    assert "chair" in ctx_llm["context_tags"]
    assert "object_detect" in ctx_llm["claim_provenance"]["tag_sources"]["curtain"]["sources"]
    assert "object_detect" in ctx_llm["claim_provenance"]["tag_sources"]["chair"]["sources"]

    epistemic = persisted_seg["scene_context_epistemic"]
    object_evidence = {
        item["value"]: item
        for item in epistemic["evidence"]
        if item.get("source_step") == "object_detect"
    }
    assert "curtain" in object_evidence
    assert object_evidence["curtain"]["score"] == 0.61
    assert "lamp" in object_evidence
    assert object_evidence["lamp"]["score"] == 0.58
    extracted_scores = cross_modal_harmonizer._extract_scene_object_scores(persisted_seg["detected_objects"])
    assert extracted_scores["chair"] == 0.74
    assert extracted_scores["curtain"] == 0.61
    assert extracted_scores["lamp"] == 0.58

    arbitration = persisted_seg["scene_context_arbitration"]
    assert {"axis": "setting", "claim": "chair", "evidence_family": "visual", "weight": "candidate"} in arbitration["hypotheses"]
    assert {"axis": "object", "claim": "curtain", "evidence_family": "visual", "weight": "candidate"} in arbitration["hypotheses"]

    api_scene = _build_scene_response("sample_clip", persisted_seg)
    assert len(api_scene.detected_objects) == 15
    assert len(api_scene.object_observations) == 2
    assert api_scene.scene_context_llm["context_tags"] == ctx_llm["context_tags"]
    assert api_scene.scene_context_epistemic == epistemic
    assert api_scene.scene_context_arbitration == arbitration


def test_cross_modal_harmonization_caller_counts_concurrent_people_per_sampled_frame(
    tmp_path,
    monkeypatch,
) -> None:
    from pathlib import Path
    from api.routes.scenes import _build_scene_response
    from cli import step_runner

    video_dir = tmp_path / "processing" / "family_may_clip" / "video"
    audio_dir = tmp_path / "processing" / "family_may_clip" / "audio"
    video_dir.mkdir(parents=True)
    audio_dir.mkdir(parents=True)

    raw_detections = [
        {"label": "person", "score": 0.93, "bbox": [10.0, 10.0, 80.0, 180.0], "timestamp": 1.0, "sample_index": 1, "is_midpoint_sample": False},
        {"label": "person", "score": 0.90, "bbox": [12.0, 11.0, 82.0, 181.0], "timestamp": 2.0, "sample_index": 2, "is_midpoint_sample": True},
        {"label": "person", "score": 0.87, "bbox": [14.0, 12.0, 84.0, 182.0], "timestamp": 3.0, "sample_index": 3, "is_midpoint_sample": False},
        {"label": "person", "score": 0.90, "bbox": [15.0, 12.0, 85.0, 182.0], "timestamp": 4.0, "sample_index": 4, "is_midpoint_sample": False},
    ]
    raw_observations = [
        {"sample_index": idx, "timestamp": float(idx), "is_midpoint_sample": idx == 2, "detections": [raw_detections[idx - 1]]}
        for idx in range(1, 5)
    ]

    manifest_path = video_dir / "scene_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "video_id": "family_may_clip",
                "scenes": [
                    {
                        "scene_id": "scene_may_0001",
                        "index": 0,
                        "start": 0.0,
                        "end": 5.0,
                        "duration": 5.0,
                        "caption": "a child smiling indoors",
                        "objects": raw_detections,
                        "object_observations": raw_observations,
                        "keyframe": {
                            "caption": "a child smiling indoors",
                            "faces": [{"bbox": [20, 20, 60, 60], "score": 0.98}],
                            "objects": raw_detections,
                            "object_observations": raw_observations,
                        },
                        "audio": {"transcript": ""},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    for name, empty_payload in (
        ("segmentation.json", {"segments": []}),
        ("transcript.json", {"segments": []}),
        ("diarization.json", {"speakers": []}),
    ):
        (audio_dir / name).write_text(json.dumps(empty_payload), encoding="utf-8")

    cfg = {
        "ingestion_isolation": True,
        "features": {"enable_llm_refinement": False, "enable_scene_context_llm": False},
        "llm": {"features": {"scene_context_analysis": False}},
        "paths": {
            "processing": str(tmp_path / "processing"),
            "processing_dir": str(tmp_path / "processing"),
            "log_dir": str(tmp_path / "logs"),
        },
    }
    monkeypatch.setattr(step_runner, "load_step_config", lambda *_: cfg)

    step_in_path = tmp_path / "step_input_may.json"
    step_in_path.write_text(
        json.dumps({"scene_manifest_path": str(manifest_path), "video_id": "family_may_clip"}),
        encoding="utf-8",
    )
    step_out_path = tmp_path / "step_output_may.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["step_runner", "--step", "cross_modal_harmonization", "--in", str(step_in_path), "--out", str(step_out_path)],
    )
    step_runner.main()

    step_result = json.loads(step_out_path.read_text(encoding="utf-8"))
    persisted_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    persisted_scene = persisted_manifest["scenes"][0]
    persisted_tidx = json.loads(Path(step_result["temporal_index_path"]).read_text(encoding="utf-8"))
    persisted_seg = persisted_tidx["segments"][0]

    assert len(persisted_seg["detected_objects"]) == 4
    assert len(persisted_seg["object_observations"]) == 4
    assert persisted_seg["visible_face_count"] == 1
    assert persisted_seg["visible_person_object_count"] == 1
    assert persisted_seg["visible_anonymous_people_count"] == 1
    assert persisted_seg["visible_person_confidence"]["crowd_risk"] == "low"
    assert len(persisted_seg["candidate_visible_people"]) == 1
    assert persisted_seg["candidate_visible_people"][0]["text"] == "anonymous_person_1"
    assert persisted_scene["visible_person_object_count"] == 1
    assert persisted_scene["candidate_visible_people"] == persisted_seg["candidate_visible_people"]

    api_scene = _build_scene_response("family_may_clip", persisted_seg)
    assert len(api_scene.detected_objects) == 4
    assert len(api_scene.object_observations) == 4
    assert len(api_scene.candidate_visible_people) == 1
    assert api_scene.candidate_visible_people[0]["text"] == "anonymous_person_1"