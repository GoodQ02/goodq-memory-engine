"""Regression tests for Area 1 (scene-truth) audit repairs and cross-slice hooks."""
from __future__ import annotations

import importlib
import json
import sqlite3
import sys
import types
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

from lib import llm_client
from steps.common import context_analyzer_llm as analyzer
from steps.common import memory
from steps.common import scene_summarizer
from steps.video import cross_modal_harmonizer as harmonizer
from steps.video_scene_detect import step as scene_detect_step
from steps.video_summarizer import step as video_summarizer_step


class _StubLLMClient:
    last_model_used = None
    last_provider_used = "fixture"

    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        self.calls: List[Dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> Dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(self.payload)},
                }
            ]
        }


def test_st01_valid_multimodal_summary_preserved_when_no_polarity_or_role_conflict():
    segment = {
        "scene_id": "s-valid",
        "start": 0.0,
        "end": 8.0,
        "content_state": "signal",
        "full_transcript": "We planted tomatoes in the garden today.",
        "visible_face_count": 1,
        "visible_person_object_count": 1,
        "detected_objects": [{"label": "person"}],
        "speaker_ids": ["SPEAKER_00"],
    }
    lookup = {
        "s-valid": {
            "scene_id": "s-valid",
            "index": 0,
            "caption": "A person stands in a garden.",
            "keyframe": {"caption": "A person stands in a garden.", "faces": [{"bbox": [0, 0, 10, 10]}]},
            "audio": {"transcript": segment["full_transcript"], "speakers": ["SPEAKER_00"]},
        }
    }
    client = _StubLLMClient(
        {
            "narrative_summary": "Garden conversation about tomatoes.",
            "activity_description": "Garden conversation about tomatoes.",
            "key_moments": ["They mention tomatoes."],
            "emotional_arc": "unqualified",
            "context_tags": ["tomatoes", "garden"],
        }
    )
    harmonizer._apply_scene_context_llm(
        [segment],
        lookup,
        {"llm": {"features": {"scene_context_analysis": True}}},
        llm_client=client,
    )
    result = segment["scene_context_llm"]
    assert result is not None
    assert "tomatoes" in result["narrative_summary"].lower()
    assert not result["narrative_summary"].startswith('Transcript: "')

    compound_tx = "You know, I never had a back problem until that night I slept on the convertible sofa."
    assert analyzer._has_transcript_polarity_or_role_conflict(
        "The man sleeps on the convertible sofa", compound_tx
    ) is False
    assert analyzer._has_transcript_polarity_or_role_conflict(
        "The speaker talks about his back problems", compound_tx
    ) is False
    assert analyzer._has_transcript_polarity_or_role_conflict(
        "Speaker says he had a back problem", compound_tx
    ) is True


def _install_cv2_and_torch_if_missing(
    monkeypatch: pytest.MonkeyPatch,
    frames: List[np.ndarray],
    *,
    fps: float = 10.0,
    reported_total_frames: int | None = None,
) -> None:
    total = len(frames) if reported_total_frames is None else reported_total_frames

    class _FakeCapture:
        def __init__(self, _path: str) -> None:
            self._idx = 0

        def isOpened(self) -> bool:
            return True

        def get(self, prop: int) -> float:
            if prop == 5:
                return float(fps)
            if prop == 7:
                return float(total)
            return 0.0

        def read(self) -> tuple[bool, Any]:
            if self._idx >= len(frames):
                return False, None
            frame = frames[self._idx]
            self._idx += 1
            return True, frame

        def release(self) -> None:
            return None

    fake_cv2 = types.ModuleType("cv2")
    fake_cv2.CAP_PROP_FPS = 5
    fake_cv2.CAP_PROP_FRAME_COUNT = 7
    fake_cv2.COLOR_BGR2GRAY = 6
    fake_cv2.VideoCapture = _FakeCapture
    fake_cv2.cvtColor = lambda img, _code: img[:, :, 0] if img.ndim == 3 else img
    fake_cv2.resize = lambda img, size: img[: size[1], : size[0]]
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    try:
        import torch as _real_torch  # noqa: F401
    except ImportError:
        class _FakeTensor:
            def __init__(self, arr: np.ndarray) -> None:
                self.arr = np.asarray(arr, dtype=np.float32)

            def float(self) -> "_FakeTensor":
                return self

            def to(self, _dev: Any) -> "_FakeTensor":
                return self

            def cpu(self) -> "_FakeTensor":
                return self

            def unsqueeze(self, axis: int) -> "_FakeTensor":
                return _FakeTensor(np.expand_dims(self.arr, axis=axis))

            def tolist(self) -> Any:
                return self.arr.tolist()

            def __len__(self) -> int:
                return len(self.arr)

            def __getitem__(self, item: Any) -> "_FakeTensor":
                return _FakeTensor(self.arr[item])

            def __truediv__(self, other: float) -> "_FakeTensor":
                return _FakeTensor(self.arr / other)

            def __mul__(self, other: float) -> "_FakeTensor":
                return _FakeTensor(self.arr * other)

            def __sub__(self, other: "_FakeTensor") -> "_FakeTensor":
                return _FakeTensor(self.arr - other.arr)

        fake_torch = types.ModuleType("torch")
        fake_torch.cuda = types.SimpleNamespace(is_available=lambda: False)
        fake_torch.device = lambda name: name
        fake_torch.from_numpy = lambda arr: _FakeTensor(arr)
        fake_torch.tensor = lambda vals, device=None: _FakeTensor(np.asarray(vals, dtype=np.float32))
        fake_torch.stack = lambda seq: _FakeTensor(np.stack([t.arr for t in seq], axis=0))
        fake_torch.cat = lambda seq, dim=0: _FakeTensor(np.concatenate([t.arr for t in seq], axis=dim))
        fake_torch.abs = lambda t: _FakeTensor(np.abs(t.arr))
        fake_torch.mean = lambda t, dim=None: _FakeTensor(np.mean(t.arr, axis=dim))
        fake_nn = types.ModuleType("torch.nn")
        fake_nn_func = types.ModuleType("torch.nn.functional")
        fake_nn.functional = fake_nn_func
        fake_torch.nn = fake_nn
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        monkeypatch.setitem(sys.modules, "torch.nn", fake_nn)
        monkeypatch.setitem(sys.modules, "torch.nn.functional", fake_nn_func)


def test_st02_gpu_scene_detect_reports_exact_cut_frames_within_and_across_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    height, width = 32, 32
    black = np.zeros((height, width, 3), dtype=np.uint8)
    white = np.full((height, width, 3), 255, dtype=np.uint8)
    # 64 frames across two 32-frame batches:
    # frames 0..19 black, frames 20..31 white (intra-batch cut at 20), frames 32..63 black (batch-boundary cut at 32)
    frames = [white if 20 <= idx <= 31 else black for idx in range(64)]

    _install_cv2_and_torch_if_missing(monkeypatch, frames, fps=10.0)
    sys.modules.pop("steps.video_scene_detect.gpu_scene_detect", None)
    gpu_scene_detect = importlib.import_module("steps.video_scene_detect.gpu_scene_detect")

    result = gpu_scene_detect.detect_scenes_gpu(
        str(tmp_path / "synthetic_cuts.mp4"),
        threshold=30.0,
        min_scene_len_sec=0.5,
        batch_size=32,
    )
    scenes = result["scenes"]
    assert [(s["start"], s["end"]) for s in scenes] == [
        (0.0, 2.0),
        (2.0, 3.2),
        (3.2, 6.4),
    ]


def test_st03_conflicting_sampled_captions_and_ungrounded_person_count_do_not_collapse_or_inflate():
    scene_obj = {
        "scene_id": "scene-5",
        "index": 5,
        "start": 40.0,
        "end": 65.0,
        "caption": "<ref>Two people</ref><box><10><20><300><400></box> standing on a porch.",
        "keyframe": {
            "caption": "<ref>Two people</ref><box><10><20><300><400></box> standing on a porch.",
            "caption_meta": {
                "distinct_captions": [
                    "Two people standing on a porch.",
                    "A person walking into a kitchen with cabinets.",
                ]
            },
            "caption_observations": [
                {"sample_index": 0, "caption": "Two people standing on a porch."},
                {"sample_index": 4, "caption": "A person walking into a kitchen with cabinets."},
            ],
            "faces": [],
            "face_observations": [
                {"sample_index": 0, "faces": [{"bbox": [1, 2, 20, 20]}, {"bbox": [30, 2, 50, 20]}]},
                {"sample_index": 2, "faces": []},
                {"sample_index": 4, "faces": [{"bbox": [5, 5, 25, 25]}]},
            ],
            "objects": [
                {"label": "person", "sample_index": 0},
                {"label": "person", "sample_index": 0},
                {"label": "person", "sample_index": 4},
            ],
        },
        "audio": {
            "transcript": "Did Person A tell Person B about the garden fence?",
            "speakers": ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"],
        },
    }

    visibility = harmonizer._derive_candidate_visible_people(
        entity_channels={
            "visible_people": [],
            "mentioned_people": [
                {"text": "Person A", "type": "PERSON"},
                {"text": "Person B", "type": "PERSON"},
            ],
        },
        scene=scene_obj,
        scene_objects=scene_obj["keyframe"]["objects"],
        scene_audio_payload=scene_obj["audio"],
        fallback_speakers=[],
        scene_start=40.0,
        scene_end=65.0,
        speaker_ids=["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"],
    )
    # Per-sample max is 2 (from sample_index 0), never 0 (midpoint) and never 3 (sum across samples).
    assert visibility["visible_face_count"] == 2
    assert visibility["visible_person_object_count"] == 2

    segment = {
        "scene_id": "scene-5",
        "start": 40.0,
        "end": 65.0,
        "content_state": "signal",
        "full_transcript": scene_obj["audio"]["transcript"],
        "detected_objects": scene_obj["keyframe"]["objects"],
        "visible_face_count": visibility["visible_face_count"],
        "visible_person_object_count": visibility["visible_person_object_count"],
        "speaker_ids": ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"],
        "visible_people": [{"text": "anonymous_person_1", "type": "PERSON"}],
        "mentioned_people": [
            {"text": "Person A", "type": "PERSON"},
            {"text": "Person B", "type": "PERSON"},
        ],
    }
    client = _StubLLMClient(
        {
            "narrative_summary": "Five people speaking indoors about the garden fence.",
            "activity_description": "Five people speaking in a kitchen about the garden fence.",
            "key_moments": ["Five speakers talk indoors about the garden fence."],
            "emotional_arc": "unqualified",
            "context_tags": ["garden fence"],
        }
    )
    harmonizer._apply_scene_context_llm(
        [segment],
        {"scene-5": scene_obj},
        {"llm": {"features": {"scene_context_analysis": True}}},
        llm_client=client,
    )
    prompt = client.calls[0]["messages"][1]["content"]
    assert "<ref>" not in prompt and "<box>" not in prompt
    assert "Sampled frame captions across scene:" in prompt
    assert "Max visible people in a single frame: 2" in prompt
    assert "Dialogue-mentioned people" in prompt

    context = segment["scene_context_llm"]
    assert context is not None
    serialized = json.dumps(context).lower()
    assert "five people" not in serialized
    assert "five speakers" not in serialized
    assert "indoors" not in serialized
    assert "kitchen conversation" not in serialized
    assert "porch conversation" not in serialized
    assert "garden fence" in context["narrative_summary"].lower()


def test_st05_register_scene_bundle_and_video_summarizer_withhold_restricted_asr_and_strip_markup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    db_path = tmp_path / "memory.sqlite"
    frame_file = tmp_path / "frame.jpg"
    audio_file = tmp_path / "audio.wav"
    frame_file.write_bytes(b"frame-bytes")
    audio_file.write_bytes(b"audio-bytes")

    cfg = {
        "paths": {"db_path": str(db_path), "db_dir": str(tmp_path)},
        "llm": {
            "features": {"video_summarization": True},
            "vllm_url": "http://127.0.0.1:38005/v1",
            "vllm_model": "goodq-qwen-quality",
            "ollama_url": "http://127.0.0.1:11434/v1",
            "ollama_model": "qwen2.5:14b",
        },
    }

    # Avoid loading sentence-transformers or external vector stores during unit test
    class _StubRouter:
        stores: Dict[str, Any] = {}

    monkeypatch.setattr("steps.common.memory_manager.build_memory_router", lambda _cfg: _StubRouter())

    restricted_coverage = {
        "policy": "source_audio_v2",
        "status": "completed",
        "recognition_accuracy": "unverified",
        "regions": [
            {
                "index": 0,
                "start": 0.0,
                "end": 10.0,
                "outcome": "text_returned",
                "quality_flags": ["compression_ratio_threshold_exceeded"],
            }
        ],
    }

    scene = {"index": 0, "start": 0.0, "end": 10.0, "confidence": 0.9}
    scene_id = memory._make_id("scene", ["vid-hash-1", "0.000", "10.000"])
    memory.register_scene_bundle(
        cfg,
        video_hash="vid-hash-1",
        scene=scene,
        scene_id=scene_id,
        frame={
            "path": str(frame_file),
            "data": {
                "caption": "<ref>A wooden porch</ref><box>[[10, 20, 100, 200]]</box> with two chairs<box><15",
                "objects": [{"label": "chair"}],
                "face_observations": [
                    {"sample_index": 0, "faces": [{"bbox": [0, 0, 10, 10]}, {"bbox": [20, 0, 30, 10]}]},
                    {"sample_index": 1, "faces": [{"bbox": [0, 0, 10, 10]}]},
                ],
            },
        },
        audio={
            "path": str(audio_file),
            "start": 0.0,
            "end": 10.0,
            "data": {
                "transcript": "Fabricated hallucination from noisy audio",
                "transcript_outcome": "withheld_recognition_uncertainty",
                "transcript_meta": {"transcription_decoding": {"source_regions": restricted_coverage}},
                "speakers": ["SPEAKER_00", "SPEAKER_01"],
            },
        },
    )

    with sqlite3.connect(db_path) as conn:
        fts_rows = conn.execute(
            "SELECT content_type, text FROM scene_text_fts WHERE scene_id=?",
            (scene_id,),
        ).fetchall()
        assert all(ctype != "transcript" for ctype, _ in fts_rows)

        summary_row = conn.execute(
            "SELECT content FROM summaries WHERE category='scene_summary' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert summary_row is not None
        summary_payload = json.loads(summary_row[0])
        scene_summary_text = summary_payload["summary"]
        assert "Fabricated hallucination" not in scene_summary_text
        assert "<ref>" not in scene_summary_text and "<box" not in scene_summary_text
        assert "A wooden porch with two chairs" in scene_summary_text
        assert "Faces detected: 2" in scene_summary_text
        assert "Speakers: 2 anonymous speakers" in scene_summary_text

        # Simulate a legacy stored scene_summary row that still contained restricted transcript + grounding tags
        legacy_payload = json.dumps(
            {
                "scene_id": scene_id,
                "summary": (
                    'Scene 0 (0.0s-10.0s, 10.0s duration). '
                    'Visual: <ref>A wooden porch</ref><box>[[10,20,30,40]]</box>. '
                    'Transcript: "Fabricated hallucination from noisy audio"'
                ),
                "index": 0,
                "start": 0.0,
                "end": 10.0,
                "duration": 10.0,
            }
        )
        conn.execute("DELETE FROM summaries WHERE category='scene_summary'")
        conn.execute(
            "INSERT INTO summaries(summary_type, category, content, created_at) VALUES ('scene', 'scene_summary', ?, datetime('now'))",
            (legacy_payload,),
        )

    template_out = video_summarizer_step.generate_video_summary_template(cfg, "vid-hash-1", str(db_path))
    assert "Fabricated hallucination" not in template_out
    assert "<ref>" not in template_out and "<box>" not in template_out
    assert "A wooden porch" in template_out


def test_st06_video_scene_detect_subdivides_overlong_detected_scenes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    dummy_video = tmp_path / "long_movie.mp4"
    dummy_video.write_bytes(b"video")

    monkeypatch.setattr(
        scene_detect_step,
        "_detect_with_scenedetect",
        lambda path, threshold, min_scene_len_sec: {
            "scenes": [
                {"index": 0, "start": 0.0, "end": 40.0, "duration": 40.0, "confidence": 0.8},
                {"index": 1, "start": 40.0, "end": 940.0, "duration": 900.0, "confidence": 0.6},
            ],
            "duration": 940.0,
        },
    )

    out = scene_detect_step.video_scene_detect(
        {"source_path": str(dummy_video), "scene_detect": {"max_scene_len_sec": 300.0}},
        {},
    )
    scenes = out["scenes"]
    assert out["scene_meta"]["status"] == "ok"
    assert out["scene_meta"]["scene_count"] == 4
    assert [(s["index"], s["start"], s["end"], s["duration"]) for s in scenes] == [
        (0, 0.0, 40.0, 40.0),
        (1, 40.0, 340.0, 300.0),
        (2, 340.0, 640.0, 300.0),
        (3, 640.0, 940.0, 300.0),
    ]


def test_vs01_harmonizer_evaluates_scene_context_when_optional_stage_marked_processing_error():
    segment = {
        "scene_id": "s-partial",
        "start": 0.0,
        "end": 12.0,
        "content_state": "processing_error",
        "full_transcript": "We planted rosemary near the porch steps.",
        "detected_objects": [],
        "visible_face_count": 0,
        "speaker_ids": ["SPEAKER_00"],
    }
    lookup = {
        "s-partial": {
            "scene_id": "s-partial",
            "index": 1,
            "content_state": "processing_error",
            "caption": "A wooden porch with steps.",
            "keyframe": {"caption": "A wooden porch with steps."},
            "audio": {"transcript": segment["full_transcript"], "speakers": ["SPEAKER_00"]},
        }
    }
    client = _StubLLMClient(
        {
            "narrative_summary": "Porch conversation about rosemary.",
            "activity_description": "Porch conversation about rosemary.",
            "key_moments": ["They mention rosemary."],
            "emotional_arc": "unqualified",
            "context_tags": ["rosemary", "porch"],
        }
    )
    stats = harmonizer._apply_scene_context_llm(
        [segment],
        lookup,
        {"llm": {"features": {"scene_context_analysis": True}}},
        llm_client=client,
    )
    assert stats["evaluated_count"] == 1
    assert segment["scene_context_llm"] is not None
    assert "rosemary" in segment["scene_context_llm"]["narrative_summary"].lower()


def test_vs05_shared_ollama_unload_retries_on_timeout_and_video_summarizer_unloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(llm_client.time, "sleep", lambda _s: None)

    unload_attempts: List[Dict[str, Any]] = []

    class _RetrySession:
        closed = False

        def post(self, url: str, **kwargs: Any) -> Any:
            unload_attempts.append({"url": url, **kwargs})
            if len(unload_attempts) == 1:
                raise llm_client.requests.Timeout("transient unload timeout")
            return types.SimpleNamespace(status_code=200, raise_for_status=lambda: None)

        def close(self) -> None:
            self.closed = True

    dummy_model = llm_client.ModelConfig(
        name="ollama-qwen",
        base_url="http://127.0.0.1",
        port=11434,
        model_id="qwen2.5:14b",
        backend="ollama",
        vram_gb=9.0,
        tokens_per_sec=30,
        context_length=8192,
        capabilities=["chat", "quality", "reasoning"],
    )
    dummy_client = types.SimpleNamespace(
        session=_RetrySession(),
        attempted_models=[dummy_model],
        last_model_used=dummy_model,
    )
    assert llm_client.unload_attempted_ollama_models(dummy_client, timeout=5.0, retries=1) is True
    assert len(unload_attempts) == 2

    # Verify generate_video_summary_llm calls unload_attempted_ollama_models before closing client
    db_path = tmp_path / "vid_sum.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE scenes (id TEXT PRIMARY KEY, video_hash TEXT, start REAL, end REAL, meta TEXT, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE summaries (id INTEGER PRIMARY KEY AUTOINCREMENT, summary_type TEXT, category TEXT, content TEXT, created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO scenes VALUES ('sc-1', 'vid-1', 0.0, 10.0, ?, '2026-11-15T00:00:00')",
            (json.dumps({"video_path": "clip.mp4"}),),
        )
        conn.execute(
            "INSERT INTO summaries(summary_type, category, content, created_at) VALUES ('scene', 'scene_summary', ?, '2026-11-15T00:00:00')",
            (json.dumps({"scene_id": "sc-1", "summary": "Scene 0 (0.0s-10.0s). Visual: A garden."}),),
        )

    post_log: List[str] = []

    class _FakeHTTP:
        def __init__(self) -> None:
            self.headers: Dict[str, str] = {}
            self.trust_env = True
            self.closed = False

        def get(self, url: str, **kwargs: Any) -> Any:
            return types.SimpleNamespace(
                status_code=200,
                raise_for_status=lambda: None,
                json=lambda: {"models": []},
            )

        def post(self, url: str, **kwargs: Any) -> Any:
            assert self.closed is False, "Unload must happen before session.close()"
            post_log.append(url)
            if url.endswith("/chat/completions"):
                return types.SimpleNamespace(
                    status_code=200,
                    raise_for_status=lambda: None,
                    json=lambda: {
                        "choices": [{"message": {"content": "<ref>Garden</ref><box><1><2><3><4></box> scene summary."}}]
                    },
                )
            return types.SimpleNamespace(status_code=200, raise_for_status=lambda: None)

        def close(self) -> None:
            self.closed = True

    fake_http = _FakeHTTP()
    monkeypatch.setattr(llm_client.requests, "Session", lambda: fake_http)
    monkeypatch.setattr(video_summarizer_step, "build_llm_models", lambda _cfg: [dummy_model])

    provenance: Dict[str, Any] = {}
    summary = video_summarizer_step.generate_video_summary_llm(
        {"llm": {"timeout": 10, "max_retries": 1}},
        "vid-1",
        str(db_path),
        generation_provenance=provenance,
    )
    assert summary == "Garden scene summary."
    assert post_log == [
        "http://127.0.0.1:11434/v1/chat/completions",
        "http://127.0.0.1:11434/api/generate",
    ]
    assert fake_http.closed is True
