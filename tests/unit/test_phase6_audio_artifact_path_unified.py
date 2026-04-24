from __future__ import annotations

import json
from pathlib import Path

from steps.video import cross_modal_harmonizer as harmonizer_module
from steps.video.cross_modal_harmonizer import run_cross_modal_harmonization


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_harmonizer_uses_explicit_audio_artifact_dir(tmp_path: Path) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_001"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 2.0,
                    "duration": 2.0,
                    "confidence": 0.9,
                }
            ],
        },
    )

    # Deliberately place conflicting transcript data at processing_dir/audio.
    _write_json(
        processing_dir / "audio" / "transcript.json",
        {"segments": [{"start": 0.0, "end": 1.0, "text": "WRONG_SOURCE"}]},
    )

    # Canonical source of truth for Phase 6b audio artifacts.
    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(
        audio_artifact_dir / "transcript.json",
        {"segments": [{"start": 0.0, "end": 1.0, "text": "RIGHT_SOURCE"}]},
    )
    _write_json(
        audio_artifact_dir / "diarization.json",
        {"speakers": []},
    )
    _write_json(
        audio_artifact_dir / "segmentation.json",
        {"segments": []},
    )

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    result = run_cross_modal_harmonization(item, cfg)
    assert result["harmonization_status"] == "complete"

    temporal_index_path = processing_dir / "temporal_index.json"
    temporal_index = json.loads(temporal_index_path.read_text(encoding="utf-8"))
    full_transcript = temporal_index["segments"][0]["full_transcript"]

    assert "RIGHT_SOURCE" in full_transcript
    assert "WRONG_SOURCE" not in full_transcript


def test_harmonizer_transcript_truth_uses_scene_payload_even_without_commits(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_payload_truth"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 5.0,
                    "duration": 5.0,
                    "confidence": 0.9,
                    "audio": {
                        "path": "audio/scene_0000.wav",
                        "audio_meta": {"duration_sec": 5.0, "sample_rate": 16000},
                        "transcript": "PAYLOAD_TRANSCRIPT",
                        "segments": [{"start": 0.0, "end": 1.0, "text": "PAYLOAD_SEGMENT"}],
                    },
                }
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})

    monkeypatch.setattr(
        harmonizer_module,
        "_load_commit_presence",
        lambda *_args, **_kwargs: {
            "available": True,
            "has_audio": False,
            "has_transcripts": False,
            "audio_scene_ids": set(),
            "transcript_scene_ids": set(),
        },
    )

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    result = run_cross_modal_harmonization(item, cfg)
    assert result["harmonization_status"] == "complete"

    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    segment = temporal_index["segments"][0]

    assert temporal_index["has_transcripts"] is True
    assert temporal_index["has_audio"] is True
    assert segment["has_transcript"] is True
    assert segment["has_audio"] is True
    assert "PAYLOAD_TRANSCRIPT" in segment["full_transcript"]
    assert temporal_index["committed_modalities"]["audio_transcript"] is False


def test_harmonizer_reports_no_transcript_truth_when_no_transcript_sources(tmp_path: Path) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_no_transcript"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 2.0,
                    "duration": 2.0,
                    "confidence": 0.9,
                }
            ],
        },
    )

    # Missing transcript.json should keep degraded warning behavior.
    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    result = run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))

    assert result["harmonization_status"] == "degraded"
    assert temporal_index["has_transcripts"] is False
    assert temporal_index["phase6_warning"] == "missing_audio_artifacts"


def test_harmonizer_keeps_complete_for_empty_classified_scenes_without_processing_error(
    tmp_path: Path,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_empty_not_error"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 0.6,
                    "duration": 0.6,
                    "confidence": 0.9,
                    "content_state": "empty",
                    "audio": {
                        "path": "audio/scene_0000.wav",
                        "transcript_meta": {"status": "success", "duration": 0.0},
                        "transcript": "",
                        "segments": [],
                    },
                }
            ],
        },
    )

    # Missing required audio artifacts (no transcript/diarization) should not degrade
    # when all classified scenes are empty and none are processing_error.
    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    result = run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))

    assert result["harmonization_status"] == "complete"
    assert "phase6_warning" not in temporal_index


def test_harmonizer_uses_scene_payload_objects_when_legacy_file_missing(tmp_path: Path) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_payload_objects"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    expected_objects = [
        {"label": "person", "score": 0.98, "bbox": [10, 20, 100, 200]},
        {"label": "chair", "score": 0.87, "bbox": [120, 40, 200, 210]},
    ]

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 2.0,
                    "duration": 2.0,
                    "confidence": 0.9,
                    "keyframe": {
                        "objects": expected_objects,
                    },
                }
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    result = run_cross_modal_harmonization(item, cfg)
    assert result["harmonization_status"] == "complete"

    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    assert temporal_index["segments"][0]["detected_objects"] == expected_objects
    assert temporal_index["segments"][0]["visible_person_object_count"] == 1
    assert temporal_index["segments"][0]["visible_anonymous_people_count"] == 1


def test_harmonizer_rolls_up_audio_context_surfaces(tmp_path: Path, monkeypatch) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_audio_context_rollups"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    music_events = [
        {"label": "applause", "score": 0.91},
        {"event": "laugh", "score": 0.82},
    ]
    time_hints = {
        "dayparts": ["night"],
        "weekdays": ["friday"],
        "first_seen_ts": 1.25,
    }
    metadata_time_hints = {
        "raw": {"date": "1991-07-04"},
        "normalized": ["1991-07-04"],
    }

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 2.0,
                    "duration": 2.0,
                    "confidence": 0.9,
                    "audio": {
                        "path": "audio/scene_0000.wav",
                        "audio_meta": {
                            "duration_sec": 2.0,
                            "sample_rate": 16000,
                            "tag_time_hints": metadata_time_hints,
                        },
                        "transcript": "The crowd is going wild on Friday night.",
                        "segments": [{"start": 0.0, "end": 1.0, "text": "The crowd is going wild on Friday night."}],
                        "emotion": "neutral",
                        "emotion_scores": {"neutral": 0.9, "joy": 0.1},
                        "diarization_status": "success",
                        "diarization_error": None,
                        "diarization_note": "wsl_unified",
                        "emotion_status": "success",
                        "emotion_error": None,
                        "music_events": music_events,
                        "time_hints": time_hints,
                        "speaker_voice_signatures": [{"speaker": "SPEAKER_00", "embedding_id": "sig-001"}],
                        "speaker_voice_signature_meta": {
                            "status": "ok",
                            "emitted": 1,
                            "attempted_speakers": 1,
                            "min_voiced_seconds": 4.0,
                            "min_segment_count": 2,
                        },
                    },
                }
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", False)

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    result = run_cross_modal_harmonization(item, cfg)
    assert result["harmonization_status"] == "complete"

    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    segment = temporal_index["segments"][0]

    assert segment["speaker_voice_signature_count"] == 1
    assert segment["music_events"] == music_events
    assert segment["time_hints"] == time_hints
    assert segment["metadata_time_hints"] == metadata_time_hints
    assert segment["audio_emotion"] == "neutral"
    assert segment["audio_emotion_scores"] == {"neutral": 0.9, "joy": 0.1}
    assert segment["diarization_status"] == "success"
    assert segment["diarization_error"] is None
    assert segment["diarization_note"] == "wsl_unified"
    assert segment["emotion_status"] == "success"
    assert segment["emotion_error"] is None
    assert segment["speaker_voice_signature_meta"] == {
        "status": "ok",
        "emitted": 1,
        "attempted_speakers": 1,
        "min_voiced_seconds": 4.0,
        "min_segment_count": 2,
    }

    assert temporal_index["segments_with_music_events"] == 1
    assert temporal_index["segments_with_time_hints"] == 1
    assert temporal_index["segments_with_metadata_time_hints"] == 1
    assert temporal_index["segments_with_audio_emotion"] == 1
    assert temporal_index["segments_with_speaker_voice_signatures"] == 1
    assert {"event": "applause", "count": 1} in temporal_index["top_music_events"]
    assert {"event": "laugh", "count": 1} in temporal_index["top_music_events"]
    assert {"hint": "night", "count": 1} in temporal_index["top_time_hints"]
    assert {"hint": "friday", "count": 1} in temporal_index["top_time_hints"]
    assert {"hint": "1991-07-04", "count": 1} in temporal_index["top_metadata_time_hints"]
    assert temporal_index["top_audio_emotions"] == [{"emotion": "neutral", "count": 1}]

    persisted_manifest = json.loads(scene_manifest_path.read_text(encoding="utf-8"))
    persisted_scene = persisted_manifest["scenes"][0]
    assert persisted_scene["speaker_voice_signature_count"] == 1
    assert persisted_scene["diarization_status"] == "success"
    assert persisted_scene["diarization_error"] is None
    assert persisted_scene["diarization_note"] == "wsl_unified"
    assert persisted_scene["emotion_status"] == "success"
    assert persisted_scene["emotion_error"] is None
    assert persisted_scene["speaker_voice_signature_meta"] == {
        "status": "ok",
        "emitted": 1,
        "attempted_speakers": 1,
        "min_voiced_seconds": 4.0,
        "min_segment_count": 2,
    }


def test_harmonizer_applies_scene_context_llm_when_feature_enabled(tmp_path: Path, monkeypatch) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_scene_context_llm"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "index": 0,
                    "start": 0.0,
                    "end": 4.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "caption": "Jerry and George talk in the apartment kitchen.",
                    "audio": {
                        "transcript": "Jerry tells George the plan in the kitchen.",
                        "segments": [{"start": 0.0, "end": 2.0, "text": "Jerry tells George the plan."}],
                        "emotion": "anxious",
                        "emotion_scores": {"anxious": 0.7, "neutral": 0.3},
                    },
                    "keyframe": {
                        "objects": [{"label": "person", "score": 0.95}],
                        "faces": [{"bbox": [0, 0, 10, 10], "confidence": 0.9}],
                    },
                }
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})

    monkeypatch.setattr(harmonizer_module, "SCENE_CONTEXT_LLM_AVAILABLE", True)
    monkeypatch.setattr(
        harmonizer_module,
        "analyze_scene_context_llm",
        lambda scene_meta, cfg: {
            "narrative_summary": "Jerry outlines a tense plan to George in the kitchen.",
            "key_moments": ["Jerry explains the plan", "George listens carefully"],
            "emotional_arc": "tense but controlled",
            "context_tags": ["planning", "kitchen", "conversation"],
            "activity_description": "Two friends discuss their next move.",
            "relationships": [{"entities": ["Jerry", "George"], "type": "conversation"}],
        },
    )

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {
        "paths": {"processing": str(processing_root)},
        "llm": {"features": {"scene_context_analysis": True}},
    }

    result = run_cross_modal_harmonization(item, cfg)
    assert result["harmonization_status"] == "complete"

    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    segment = temporal_index["segments"][0]

    assert segment["scene_context_llm"] == {
        "narrative_summary": "Jerry outlines a tense plan to George in the kitchen.",
        "key_moments": ["Jerry explains the plan", "George listens carefully"],
        "emotional_arc": "tense but controlled",
        "context_tags": ["planning", "kitchen"],
        "primary_tags": [],
        "contextual_tags": [],
        "structural_tags": [],
        "activity_description": "Two friends discuss their next move.",
        "source": "scene_context_llm",
    }
    assert segment["scene_context_epistemic"]["read_model_version"] == 1
    assert segment["scene_context_epistemic"]["state"] in {"supported", "partially_supported"}
    assert segment["scene_context_epistemic"]["dominant_evidence"] in {"transcript", "visual", "mixed"}
    assert any(
        item["role"] == "support" and item["kind"] in {"transcript_topic", "visual_signal"}
        for item in segment["scene_context_epistemic"]["evidence"]
    )
    assert segment["scene_context_arbitration"]["read_model_version"] == 1
    assert segment["scene_context_arbitration"]["resolved_by"] in {"transcript", "visual", "mixed"}
    assert any(
        hypothesis["axis"] == "setting" and hypothesis["claim"] == "kitchen"
        for hypothesis in segment["scene_context_arbitration"]["hypotheses"]
    )
    assert temporal_index["segments_with_scene_context_llm"] == 1
    assert temporal_index["segments_with_scene_context_epistemic"] == 1
    assert temporal_index["segments_with_scene_context_arbitration"] == 1
    assert {"tag": "planning", "count": 1} in temporal_index["top_scene_context_tags"]
    assert not any(item["tag"] == "conversation" for item in temporal_index["top_scene_context_tags"])
    assert temporal_index["top_scene_context_epistemic_states"]
    assert temporal_index["top_scene_context_epistemic_dominant_evidence"]
    assert temporal_index["top_scene_context_arbitration_resolved_by"]

    persisted_manifest = json.loads(scene_manifest_path.read_text(encoding="utf-8"))
    persisted_scene = persisted_manifest["scenes"][0]
    assert persisted_scene["scene_context_llm"] == segment["scene_context_llm"]
    assert persisted_scene["scene_context_epistemic"] == segment["scene_context_epistemic"]
    assert persisted_scene["scene_context_arbitration"] == segment["scene_context_arbitration"]


def test_scene_context_epistemic_marks_low_signal_fallback() -> None:
    result = harmonizer_module._derive_scene_context_epistemic(  # type: ignore[attr-defined]
        {
            "caption": "a black background with a white and red light",
            "transcript": "",
            "objects": [],
            "face_count": 0,
            "emotions": [],
        },
        {
            "narrative_summary": "Minimal visual or dialogue content.",
            "key_moments": ["Minimal visual or dialogue content"],
            "emotional_arc": "low-signal scene",
            "context_tags": ["low-signal scene"],
            "activity_description": "Minimal visual or dialogue content.",
            "source": "scene_context_llm",
        },
    )

    assert result == {
        "read_model_version": 1,
        "state": "unknown",
        "dominant_evidence": "fallback",
        "evidence_family": "fallback",
        "fallback_mode": "low_signal",
        "conflict_detected": False,
        "evidence": [{"role": "meta", "kind": "fallback_mode", "value": "low_signal"}],
        "limits": ["low_signal_scene"],
        "next_steps": [
            {
                "action": "inspect scene manually",
                "rationale": "Low-signal fallback was used because transcript and visual evidence were weak.",
            }
        ],
    }


def test_scene_context_epistemic_uses_transcript_and_visual_support() -> None:
    result = harmonizer_module._derive_scene_context_epistemic(  # type: ignore[attr-defined]
        {
            "caption": "a man and a woman sit in the living room",
            "transcript": "How much is the rental car in Florida?",
            "objects": [{"label": "person"}],
            "face_count": 2,
            "emotions": [{"label": "tense", "score": 0.8}],
        },
        {
            "narrative_summary": "Living room conversation about rental car.",
            "key_moments": ["They mention the rental car"],
            "emotional_arc": "tense discussion",
            "context_tags": ["living room", "rental car"],
            "activity_description": "Living room conversation about rental car.",
            "source": "scene_context_llm",
        },
    )

    assert result["state"] == "supported"
    assert result["dominant_evidence"] == "mixed"
    assert result["evidence_family"] == "transcript+visual+audio"
    assert result["fallback_mode"] is None
    assert result["conflict_detected"] is False
    assert any(
        item["role"] == "support" and item["kind"] == "transcript_topic" and item["value"] == "rental car"
        for item in result["evidence"]
    )
    assert any(
        item["role"] == "support" and item["kind"] == "visual_signal" and item["value"] == "living room"
        for item in result["evidence"]
    )
    assert any(
        item["kind"] == "audio_emotion" and item["value"] == "tense"
        for item in result["evidence"]
    )


def test_scene_context_arbitration_records_supported_hypotheses_and_conflicts() -> None:
    epistemic = {
        "read_model_version": 1,
        "state": "partially_supported",
        "dominant_evidence": "transcript",
        "evidence_family": "transcript+audio",
        "fallback_mode": None,
        "conflict_detected": False,
        "evidence": [],
        "limits": [],
        "next_steps": [],
    }

    result = harmonizer_module._derive_scene_context_arbitration(  # type: ignore[attr-defined]
        {
            "caption": "two people stand by a couch in a living room",
            "transcript": "The rental car in Florida is still too expensive.",
            "objects": [{"label": "couch"}],
            "emotions": [{"label": "tense", "score": 0.8}],
            "conversation_owner": {"text": "Jerry", "type": "PERSON"},
        },
        {
            "narrative_summary": "Indoor conversation about rental car.",
            "key_moments": ["They mention the rental car"],
            "emotional_arc": "tense discussion",
            "context_tags": ["rental car", "living room"],
            "activity_description": "Indoor conversation about rental car.",
            "source": "scene_context_llm",
        },
        epistemic,
    )

    assert result["resolved_by"] == "transcript"
    assert any(
        item["axis"] == "topic" and item["claim"] == "rental car"
        for item in result["hypotheses"]
    )
    assert any(
        item["axis"] == "setting" and item["claim"] == "living room"
        for item in result["hypotheses"]
    )
    assert any(
        item["axis"] == "tone" and item["claim"] == "tense"
        for item in result["hypotheses"]
    )
    assert any(
        item["axis"] == "conversation_focus" and item["claim"] == "Jerry"
        for item in result["hypotheses"]
    )
    assert result["evidence_conflicts"] == []
    assert result["unresolved_axes"] == []


def test_scene_context_arbitration_marks_unreflected_topics() -> None:
    epistemic = {
        "read_model_version": 1,
        "state": "partially_supported",
        "dominant_evidence": "visual",
        "evidence_family": "visual",
        "fallback_mode": None,
        "conflict_detected": False,
        "evidence": [],
        "limits": [],
        "next_steps": [],
    }

    result = harmonizer_module._derive_scene_context_arbitration(  # type: ignore[attr-defined]
        {
            "caption": "a stage with a spotlight",
            "transcript": "The pharmacist keeps asking about pills.",
            "objects": [{"label": "stage"}],
            "emotions": [],
        },
        {
            "narrative_summary": "Spoken monologue about stage.",
            "key_moments": ["Minimal visual or dialogue content."],
            "emotional_arc": "spoken monologue",
            "context_tags": ["spoken monologue"],
            "activity_description": "Spoken monologue.",
            "source": "scene_context_llm",
        },
        epistemic,
    )

    assert result["resolved_by"] == "visual"
    assert result["evidence_conflicts"] == [
        {
            "axis": "topic",
            "reason": "transcript_topics_not_reflected",
            "transcript_topics": ["pharmacist", "pills"],
        }
    ]
    assert result["unresolved_axes"] == ["topic"]


def test_scene_context_arbitration_filters_discourse_fragments_and_identity_names() -> None:
    epistemic = {
        "read_model_version": 1,
        "state": "supported",
        "dominant_evidence": "mixed",
        "evidence_family": "transcript+visual",
        "fallback_mode": None,
        "conflict_detected": False,
        "evidence": [],
        "limits": [],
        "next_steps": [],
    }

    result = harmonizer_module._derive_scene_context_arbitration(  # type: ignore[attr-defined]
        {
            "caption": "two men sit by a table",
            "transcript": "Maybe George should go to Long Island. Thanks for the ride.",
            "objects": [{"label": "table"}],
            "emotions": [],
            "mentioned_people": [{"text": "George", "type": "PERSON"}],
        },
        {
            "narrative_summary": "Table conversation about Long Island.",
            "key_moments": ["They mention Long Island"],
            "emotional_arc": "calm discussion",
            "context_tags": ["table", "Long Island"],
            "activity_description": "Table conversation about Long Island.",
            "source": "scene_context_llm",
        },
        epistemic,
    )

    topic_claims = [item["claim"] for item in result["hypotheses"] if item["axis"] == "topic"]
    assert "Long Island" in topic_claims
    assert "Maybe" not in topic_claims
    assert "Thanks" not in topic_claims
    assert "George" not in topic_claims


def test_scene_context_arbitration_avoids_person_false_positive_from_personal_phrase() -> None:
    epistemic = {
        "read_model_version": 1,
        "state": "supported",
        "dominant_evidence": "visual",
        "evidence_family": "visual",
        "fallback_mode": None,
        "conflict_detected": False,
        "evidence": [],
        "limits": [],
        "next_steps": [],
    }

    result = harmonizer_module._derive_scene_context_arbitration(  # type: ignore[attr-defined]
        {
            "caption": "people talking indoors",
            "transcript": "Let's discuss the personal project later.",
            "objects": [{"label": "person"}],
            "emotions": [],
        },
        {
            "narrative_summary": "A group of coworkers discuss their plans for the day.",
            "key_moments": ["They talk about a personal project"],
            "emotional_arc": "neutral discussion",
            "context_tags": ["personal project", "group conversation"],
            "activity_description": "Coworkers talk indoors.",
            "source": "scene_context_llm",
        },
        epistemic,
    )

    assert result is None


def test_scene_context_arbitration_ignores_generic_visual_gender_claims() -> None:
    epistemic = {
        "read_model_version": 1,
        "state": "supported",
        "dominant_evidence": "mixed",
        "evidence_family": "transcript+visual",
        "fallback_mode": None,
        "conflict_detected": False,
        "evidence": [],
        "limits": [],
        "next_steps": [],
    }

    result = harmonizer_module._derive_scene_context_arbitration(  # type: ignore[attr-defined]
        {
            "caption": "a man in a white robe is standing in front of a woman",
            "transcript": "I knew the exit on the Long Island Expressway.",
            "objects": [{"label": "person"}],
            "emotions": [],
        },
        {
            "narrative_summary": "Conversation about Long Island Expressway.",
            "key_moments": ["They mention Long Island Expressway."],
            "emotional_arc": "neutral tone",
            "context_tags": ["man", "woman", "conversation", "Long Island Expressway", "Long Island"],
            "activity_description": "Conversation about Long Island Expressway.",
            "source": "scene_context_llm",
        },
        epistemic,
    )

    assert result is not None
    assert result["resolved_by"] == "mixed"
    assert result["hypotheses"] == [
        {
            "axis": "topic",
            "claim": "Long Island Expressway",
            "evidence_family": "transcript",
            "weight": "primary",
        },
        {
            "axis": "topic",
            "claim": "Long Island",
            "evidence_family": "transcript",
            "weight": "primary",
        },
    ]


def test_scene_context_arbitration_respects_tiered_transcript_tags() -> None:
    epistemic = {
        "read_model_version": 1,
        "state": "supported",
        "dominant_evidence": "transcript",
        "evidence_family": "transcript",
        "fallback_mode": None,
        "conflict_detected": False,
        "evidence": [],
        "limits": [],
        "next_steps": [],
    }

    result = harmonizer_module._derive_scene_context_arbitration(  # type: ignore[attr-defined]
        {
            "caption": "a man sitting on a couch",
            "transcript": (
                "They're making that Woody Allen movie in the block. "
                "Right out of the Clear Blue Sky? Clear Blue Sky!"
            ),
            "objects": [{"label": "couch"}],
            "emotions": [],
            "conversation_owner": {"text": "Jerry", "type": "PERSON"},
        },
        {
            "narrative_summary": "Couch conversation about Woody Allen.",
            "key_moments": ["They mention Woody Allen."],
            "emotional_arc": "neutral tone",
            "context_tags": ["Woody Allen", "Clear Blue Sky"],
            "primary_tags": ["Woody Allen"],
            "contextual_tags": ["Clear Blue Sky"],
            "structural_tags": [],
            "activity_description": "Couch conversation about Woody Allen.",
            "source": "scene_context_llm",
        },
        epistemic,
    )

    assert result is not None
    assert result["resolved_by"] == "transcript"
    assert any(
        item["axis"] == "topic"
        and item["claim"] == "Woody Allen"
        and item["evidence_family"] == "transcript"
        and item["weight"] == "primary"
        for item in result["hypotheses"]
    )
    assert any(
        item["axis"] == "context"
        and item["claim"] == "Clear Blue Sky"
        and item["evidence_family"] == "transcript"
        and item["weight"] == "supporting"
        for item in result["hypotheses"]
    )
    assert not any(
        item["axis"] == "topic" and item["claim"] == "Clear Blue Sky"
        for item in result["hypotheses"]
    )
    assert result["evidence_conflicts"] == []
    assert result["unresolved_axes"] == []


def test_scene_context_arbitration_excludes_structural_tags_from_setting_claims() -> None:
    epistemic = {
        "read_model_version": 1,
        "state": "partially_supported",
        "dominant_evidence": "visual",
        "evidence_family": "visual",
        "fallback_mode": None,
        "conflict_detected": False,
        "evidence": [],
        "limits": [],
        "next_steps": [],
    }

    result = harmonizer_module._derive_scene_context_arbitration(  # type: ignore[attr-defined]
        {
            "caption": "a man and woman sitting at a table in a restaurant",
            "transcript": "",
            "objects": [{"label": "table"}],
            "emotions": [],
        },
        {
            "narrative_summary": "Restaurant conversation.",
            "key_moments": ["Restaurant conversation."],
            "emotional_arc": "neutral tone",
            "context_tags": ["restaurant"],
            "primary_tags": [],
            "contextual_tags": ["restaurant"],
            "structural_tags": ["table"],
            "activity_description": "Restaurant conversation.",
            "source": "scene_context_llm",
        },
        epistemic,
    )

    assert result is not None
    assert result["resolved_by"] == "visual"
    assert result["hypotheses"] == [
        {
            "axis": "setting",
            "claim": "restaurant",
            "evidence_family": "visual",
            "weight": "supporting",
        }
    ]
    assert result["evidence_conflicts"] == []
    assert result["unresolved_axes"] == []


def test_scene_context_arbitration_tolerates_none_tier_fields() -> None:
    epistemic = {
        "read_model_version": 1,
        "state": "partially_supported",
        "dominant_evidence": "transcript",
        "evidence_family": "transcript",
        "fallback_mode": None,
        "conflict_detected": False,
        "evidence": [],
        "limits": [],
        "next_steps": [],
    }

    result = harmonizer_module._derive_scene_context_arbitration(  # type: ignore[attr-defined]
        {
            "caption": "two people at a table",
            "transcript": "We're talking about the reservation.",
            "objects": [{"label": "table"}],
            "emotions": [],
        },
        {
            "narrative_summary": "Restaurant conversation about reservation.",
            "key_moments": ["They mention the reservation."],
            "emotional_arc": "neutral tone",
            "context_tags": ["reservation", "restaurant"],
            "primary_tags": None,
            "contextual_tags": None,
            "structural_tags": None,
            "activity_description": "Restaurant conversation about reservation.",
            "source": "scene_context_llm",
        },
        epistemic,
    )

    assert result is not None
    assert result["resolved_by"] == "transcript"
    assert any(
        item["axis"] == "topic" and item["claim"] == "reservation"
        for item in result["hypotheses"]
    )
    assert result["evidence_conflicts"] == []
    assert result["unresolved_axes"] == []


def test_harmonizer_preserves_empty_tier_arrays_for_low_signal_scene(tmp_path: Path, monkeypatch) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_scene_context_minimal_contract"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "index": 0,
                    "start": 0.0,
                    "end": 3.0,
                    "duration": 3.0,
                    "confidence": 0.9,
                    "caption": "a dark room",
                    "audio": {
                        "transcript": "",
                        "segments": [],
                        "emotion": "neutral",
                        "emotion_scores": {"neutral": 1.0},
                    },
                    "keyframe": {
                        "objects": [{"label": "room", "score": 0.9}],
                        "faces": [],
                    },
                }
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})

    monkeypatch.setattr(harmonizer_module, "SCENE_CONTEXT_LLM_AVAILABLE", True)
    monkeypatch.setattr(
        harmonizer_module,
        "analyze_scene_context_llm",
        lambda scene_meta, cfg: {
            "narrative_summary": "Minimal visual or dialogue content.",
            "key_moments": ["Minimal visual or dialogue content."],
            "emotional_arc": "low-signal scene",
            "context_tags": ["low-signal scene"],
            "primary_tags": [],
            "contextual_tags": [],
            "structural_tags": ["low-signal scene"],
            "activity_description": "Minimal visual or dialogue content.",
        },
    )

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {
        "paths": {"processing": str(processing_root)},
        "llm": {"features": {"scene_context_analysis": True}},
    }

    result = run_cross_modal_harmonization(item, cfg)
    assert result["harmonization_status"] == "complete"

    manifest = json.loads(scene_manifest_path.read_text(encoding="utf-8"))
    scene_context = manifest["scenes"][0]["scene_context_llm"]
    assert scene_context["primary_tags"] == []
    assert scene_context["contextual_tags"] == []
    assert scene_context["structural_tags"] == ["low-signal scene"]


def test_harmonizer_rollup_uses_payload_truth_and_normalized_entities(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_rollup_truth"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 5.0,
                    "duration": 5.0,
                    "confidence": 0.9,
                    "content_state": "empty",
                    "keyframe": {
                        "caption": "Jerry stands in the apartment",
                        "ocr_text": "",
                        "tags": ["apartment"],
                    },
                    "audio": {
                        "path": "audio/scene_0000.wav",
                        "audio_meta": {"duration_sec": 5.0},
                        "transcript": "Jerry is talking in the apartment",
                        "segments": [{"start": 0.0, "end": 2.0, "text": "Jerry is talking"}],
                    },
                }
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(
        audio_artifact_dir / "transcript.json",
        {"segments": [{"start": 0.0, "end": 2.0, "text": "Jerry is talking"}]},
    )
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", True)
    monkeypatch.setattr(
        harmonizer_module,
        "extract_entities_from_scene",
        lambda **_kwargs: {
            "entity_count": 2,
            "entities": [
                {"name": "Jerry", "entity_type": "PERSON"},
                {"name": "Apartment", "entity_type": "LOCATION"},
            ],
        },
    )

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))

    assert temporal_index["content_summary"] == {"signal": 1, "empty": 0, "processing_error": 0}
    assert temporal_index["total_entities"] == 2
    assert temporal_index["unique_entities"] == 2
    assert temporal_index["top_entities"] == [
        {"entity": "jerry", "type": "PERSON", "count": 1},
        {"entity": "apartment", "type": "LOCATION", "count": 1},
    ]
    assert temporal_index["top_objects"] == []


def test_harmonizer_rollup_separates_object_inventory_from_top_entities(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_rollup_object_separation"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 5.0,
                    "duration": 5.0,
                    "confidence": 0.9,
                    "audio": {"transcript": "George walks into the apartment."},
                }
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", True)
    monkeypatch.setattr(
        harmonizer_module,
        "extract_entities_from_scene",
        lambda **_kwargs: {
            "entity_count": 2,
            "entities": [
                {"name": "George", "entity_type": "PERSON"},
                {"name": "bottle", "entity_type": "object"},
            ],
        },
    )

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))

    assert temporal_index["top_entities"] == [
        {"entity": "george", "type": "PERSON", "count": 1},
    ]
    assert temporal_index["top_objects"] == [
        {"entity": "bottle", "type": "object", "count": 1},
    ]


def test_harmonizer_partitions_scene_presence_and_dialogue_mentions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_partition_scene_vs_dialogue"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 5.0,
                    "duration": 5.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {"transcript": "Jerry talks about Superman in the kitchen."},
                }
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", True)
    monkeypatch.setattr(
        harmonizer_module,
        "extract_entities_from_scene",
        lambda **_kwargs: {
            "entity_count": 3,
            "entities": [
                {
                    "name": "Superman",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                },
                {
                    "name": "Kitchen",
                    "entity_type": "LOCATION",
                    "source_modalities": ["vision", "metadata"],
                    "source_steps": ["image_caption", "scene_payload"],
                },
                {
                    "name": "Jerry",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio", "vision"],
                    "source_steps": ["tagger", "face_embed"],
                },
            ],
        },
    )

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    segment = temporal_index["segments"][0]

    assert segment["scene_present_entities"] == [
        {"text": "Kitchen", "type": "LOCATION"},
        {"text": "Jerry", "type": "PERSON"},
    ]
    assert segment["dialogue_mentioned_entities"] == [
        {"text": "Superman", "type": "PERSON"},
    ]
    assert segment["visible_people"] == [
        {"text": "Jerry", "type": "PERSON"},
    ]
    assert segment["mentioned_people"] == [
        {"text": "Superman", "type": "PERSON"},
    ]
    assert segment["candidate_visible_people"] == []
    assert segment["conversation_owner"] is None
    assert segment["scene_locations"] == [
        {"text": "Kitchen", "type": "LOCATION"},
    ]
    assert segment["dialogue_topics"] == [
        {"text": "Superman", "type": "PERSON"},
    ]
    assert segment["visible_face_count"] == 0
    assert segment["visible_person_object_count"] == 0
    assert segment["visible_anonymous_people_count"] == 0
    assert segment["speaker_count"] == 0
    assert segment["dominant_speaker_id"] is None
    assert segment["dominant_speaker_share"] == 0.0

    assert temporal_index["top_visible_people"] == [
        {"entity": "jerry", "type": "PERSON", "count": 1},
    ]
    assert temporal_index["top_mentioned_people"] == [
        {"entity": "superman", "type": "PERSON", "count": 1},
    ]
    assert temporal_index["top_candidate_visible_people"] == []
    assert temporal_index["top_conversation_owners"] == []
    assert temporal_index["segments_with_scene_present_entities"] == 1
    assert temporal_index["segments_with_dialogue_mentioned_entities"] == 1
    assert temporal_index["segments_with_visible_people"] == 1
    assert temporal_index["segments_with_mentioned_people"] == 1
    assert temporal_index["segments_with_candidate_visible_people"] == 0
    assert temporal_index["segments_with_conversation_owner"] == 0
    assert temporal_index["top_scene_present_entities"] == [
        {"entity": "kitchen", "type": "LOCATION", "count": 1},
        {"entity": "jerry", "type": "PERSON", "count": 1},
    ]
    assert temporal_index["top_dialogue_mentioned_entities"] == [
        {"entity": "superman", "type": "PERSON", "count": 1},
    ]


def test_harmonizer_candidate_visible_people_uses_continuity_chain_confirmation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_candidate_visible_people"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 4.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "I will be right there. Okay.",
                        "speaker_transcript": [
                            {"start": 0.0, "end": 3.2, "text": "I will be right there.", "speaker": "SPEAKER_00"},
                            {"start": 3.2, "end": 4.0, "text": "Okay.", "speaker": "SPEAKER_01"},
                        ],
                    },
                    "keyframe": {
                        "faces": [{}],
                    },
                    "objects": [
                        {"label": "person", "score": 0.99},
                    ],
                },
                {
                    "scene_id": "scene_0001",
                    "start": 4.0,
                    "end": 8.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Where's Jerry? Jerry is coming down now.",
                        "speaker_transcript": [
                            {"start": 4.0, "end": 5.0, "text": "Where's Jerry?", "speaker": "SPEAKER_01"},
                            {"start": 5.0, "end": 8.0, "text": "Jerry is coming down now.", "speaker": "SPEAKER_00"},
                        ],
                    },
                },
                {
                    "scene_id": "scene_0002",
                    "start": 8.0,
                    "end": 12.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Hang on. All right.",
                        "speaker_transcript": [
                            {"start": 8.0, "end": 11.2, "text": "Hang on.", "speaker": "SPEAKER_00"},
                            {"start": 11.2, "end": 12.0, "text": "All right.", "speaker": "SPEAKER_01"},
                        ],
                    },
                    "keyframe": {
                        "faces": [{}],
                    },
                    "objects": [
                        {"label": "person", "score": 0.97},
                    ],
                }
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", True)
    monkeypatch.setattr(
        harmonizer_module,
        "extract_entities_from_scene",
        lambda **_kwargs: (
            {
                "entity_count": 1,
                "entities": [
                    {
                        "name": "Jerry",
                        "entity_type": "PERSON",
                        "source_modalities": ["audio"],
                        "source_steps": ["tagger"],
                    }
                ],
            }
            if "Jerry" in str(_kwargs.get("scene_data", {}).get("transcription", ""))
            else {
                "entity_count": 0,
                "entities": [],
            }
        ),
    )

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    first_segment = temporal_index["segments"][0]
    second_segment = temporal_index["segments"][1]
    third_segment = temporal_index["segments"][2]

    assert first_segment["visible_people"] == []
    assert first_segment["mentioned_people"] == []
    assert first_segment["candidate_visible_people"] == [
        {
            "text": "anonymous_person_1",
            "name": "anonymous_person_1",
            "type": "PERSON",
            "source": "visual_scene_presence",
            "confidence": "supported",
            "evidence": {
                "source_modalities": ["object_detect", "face_embed"],
                "frame_consistency": "keyframe_only",
                "visible_person_object_count": 1,
                "visible_face_count": 1,
                "crowd_risk": "low",
            },
        }
    ]
    assert first_segment["visible_face_count"] == 1
    assert first_segment["visible_person_object_count"] == 1
    assert first_segment["visible_anonymous_people_count"] == 1
    assert first_segment["visible_person_confidence"] == {
        "source_modalities": ["object_detect", "face_embed"],
        "frame_consistency": "keyframe_only",
        "face_support": True,
        "object_support": True,
        "crowd_risk": "low",
    }
    assert first_segment["speaker_count"] == 2
    assert first_segment["dominant_speaker_id"] == "SPEAKER_00"
    assert first_segment["dominant_speaker_share"] == 0.8
    assert first_segment["dominance_confidence"] == "strong"
    assert first_segment["conversation_speaker_ids"] == ["SPEAKER_00", "SPEAKER_01"]
    assert first_segment["continuity_key"] == "conversation:SPEAKER_00|SPEAKER_01"
    assert first_segment["interaction_dominance"] == {
        "speaker_id": "SPEAKER_00",
        "dominant_share": 0.7833,
        "segments": 3,
        "stability": 1.0,
        "confidence": "strong",
        "continuity_key": "conversation:SPEAKER_00|SPEAKER_01",
    }
    assert second_segment["mentioned_people"] == [{"text": "Jerry", "type": "PERSON"}]
    assert second_segment["speaker_aligned_mentions"] == [{"text": "Jerry", "type": "PERSON", "count": 1}]
    assert third_segment["mentioned_people"] == []
    assert second_segment["candidate_visible_people"] == []
    assert third_segment["candidate_visible_people"] == [
        {
            "text": "anonymous_person_1",
            "name": "anonymous_person_1",
            "type": "PERSON",
            "source": "visual_scene_presence",
            "confidence": "supported",
            "evidence": {
                "source_modalities": ["object_detect", "face_embed"],
                "frame_consistency": "keyframe_only",
                "visible_person_object_count": 1,
                "visible_face_count": 1,
                "crowd_risk": "low",
            },
        }
    ]
    assert first_segment["conversation_owner"] is None
    assert second_segment["conversation_owner"] is None
    assert third_segment["conversation_owner"] is None
    assert temporal_index["segments_with_candidate_visible_people"] == 2
    assert temporal_index["segments_with_interaction_dominance"] == 3
    assert temporal_index["segments_with_conversation_owner"] == 0
    assert temporal_index["top_candidate_visible_people"] == [
        {"entity": "anonymous_person_1", "type": "PERSON", "count": 2},
    ]
    assert temporal_index["top_interaction_dominance"] == [
        {"speaker_id": "SPEAKER_00", "count": 3},
    ]
    assert temporal_index["top_conversation_owners"] == []

    persisted_manifest = json.loads(scene_manifest_path.read_text(encoding="utf-8"))
    persisted_first_segment = persisted_manifest["scenes"][0]
    persisted_second_segment = persisted_manifest["scenes"][1]
    assert persisted_first_segment["continuity_key"] == "conversation:SPEAKER_00|SPEAKER_01"
    assert persisted_first_segment["dominant_speaker_id"] == "SPEAKER_00"
    assert persisted_first_segment["dominant_speaker_share"] == 0.8
    assert persisted_first_segment["dominance_confidence"] == "strong"
    assert persisted_first_segment["conversation_speaker_ids"] == ["SPEAKER_00", "SPEAKER_01"]
    assert persisted_first_segment["visible_anonymous_people_count"] == 1
    assert persisted_first_segment["visible_person_confidence"] == first_segment["visible_person_confidence"]
    assert persisted_first_segment["candidate_visible_people"] == first_segment["candidate_visible_people"]
    assert persisted_first_segment["interaction_dominance"] == first_segment["interaction_dominance"]
    assert persisted_second_segment["mentioned_people"] == [{"text": "Jerry", "type": "PERSON"}]
    assert persisted_second_segment["speaker_aligned_mentions"] == [{"text": "Jerry", "type": "PERSON", "count": 1}]


def test_harmonizer_candidate_visible_people_scores_dominant_person_across_chain(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_candidate_chain_scoring"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 4.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Wait here. Okay.",
                        "speaker_transcript": [
                            {"start": 0.0, "end": 3.2, "text": "Wait here.", "speaker": "SPEAKER_00"},
                            {"start": 3.2, "end": 4.0, "text": "Okay.", "speaker": "SPEAKER_01"},
                        ],
                    },
                    "keyframe": {"faces": [{}]},
                    "objects": [{"label": "person", "score": 0.99}],
                },
                {
                    "scene_id": "scene_0001",
                    "start": 4.0,
                    "end": 8.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                        "audio": {
                            "transcript": "Jerry is coming. Right, Jerry is downstairs.",
                            "speaker_transcript": [
                                {"start": 4.0, "end": 5.2, "text": "Jerry is coming.", "speaker": "SPEAKER_01"},
                                {"start": 5.2, "end": 8.0, "text": "Right, Jerry is downstairs.", "speaker": "SPEAKER_00"},
                            ],
                        },
                },
                {
                    "scene_id": "scene_0002",
                    "start": 8.0,
                    "end": 12.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Jerry knows George from work.",
                        "speaker_transcript": [
                            {"start": 8.0, "end": 9.6, "text": "Jerry knows", "speaker": "SPEAKER_00"},
                            {"start": 9.6, "end": 11.0, "text": "George from", "speaker": "SPEAKER_01"},
                            {"start": 11.0, "end": 12.0, "text": "work.", "speaker": "SPEAKER_02"},
                        ],
                    },
                },
                {
                    "scene_id": "scene_0003",
                    "start": 12.0,
                    "end": 16.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "All right, let's go.",
                        "speaker_transcript": [
                            {"start": 12.0, "end": 14.8, "text": "All right,", "speaker": "SPEAKER_00"},
                            {"start": 14.8, "end": 16.0, "text": "let's go.", "speaker": "SPEAKER_01"},
                        ],
                    },
                    "keyframe": {"faces": [{}]},
                    "objects": [{"label": "person", "score": 0.98}],
                },
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    def _extract_entities(**kwargs):
        transcription = str(kwargs.get("scene_data", {}).get("transcription", ""))
        entities = []
        if "Jerry" in transcription:
            entities.append(
                {
                    "name": "Jerry",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        if "George" in transcription:
            entities.append(
                {
                    "name": "George",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        return {"entity_count": len(entities), "entities": entities}

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", True)
    monkeypatch.setattr(harmonizer_module, "extract_entities_from_scene", _extract_entities)

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    first_segment = temporal_index["segments"][0]
    second_segment = temporal_index["segments"][1]
    third_segment = temporal_index["segments"][2]
    fourth_segment = temporal_index["segments"][3]

    assert first_segment["candidate_visible_people"] == [
        {
            "text": "anonymous_person_1",
            "name": "anonymous_person_1",
            "type": "PERSON",
            "source": "visual_scene_presence",
            "confidence": "supported",
            "evidence": {
                "source_modalities": ["object_detect", "face_embed"],
                "frame_consistency": "keyframe_only",
                "visible_person_object_count": 1,
                "visible_face_count": 1,
                "crowd_risk": "low",
            },
        }
    ]
    assert first_segment["interaction_dominance"] == {
        "speaker_id": "SPEAKER_00",
        "dominant_share": 0.65,
        "segments": 4,
        "stability": 1.0,
        "confidence": "stable",
        "continuity_key": "conversation:SPEAKER_00|SPEAKER_01",
    }
    expected_owner = {
        "name": "Jerry",
        "text": "Jerry",
        "type": "PERSON",
        "confidence": "candidate",
        "source": "interaction_chain",
        "continuity_key": "conversation:SPEAKER_00|SPEAKER_01",
        "chain_length": 4,
        "mention_dominance_ratio": 1.0,
        "speaker_dominance_ratio": 0.65,
        "competitor_gap": 2,
        "evidence": {
            "speaker_aligned_mentions": 2,
            "total_mentions": 2,
            "segments_involved": ["scene_0001", "scene_0002"],
        },
    }
    assert second_segment["mentioned_people"] == [{"text": "Jerry", "type": "PERSON"}]
    assert third_segment["mentioned_people"] == [
        {"text": "Jerry", "type": "PERSON"},
        {"text": "George", "type": "PERSON"},
    ]
    assert second_segment["speaker_aligned_mentions"] == [{"text": "Jerry", "type": "PERSON", "count": 1}]
    assert third_segment["speaker_aligned_mentions"] == [{"text": "Jerry", "type": "PERSON", "count": 1}]
    assert fourth_segment["candidate_visible_people"] == [
        {
            "text": "anonymous_person_1",
            "name": "anonymous_person_1",
            "type": "PERSON",
            "source": "visual_scene_presence",
            "confidence": "supported",
            "evidence": {
                "source_modalities": ["object_detect", "face_embed"],
                "frame_consistency": "keyframe_only",
                "visible_person_object_count": 1,
                "visible_face_count": 1,
                "crowd_risk": "low",
            },
        }
    ]
    assert first_segment["conversation_owner"] == expected_owner
    assert second_segment["conversation_owner"] == expected_owner
    assert third_segment["conversation_owner"] == expected_owner
    assert fourth_segment["conversation_owner"] == expected_owner
    assert temporal_index["segments_with_candidate_visible_people"] == 2
    assert temporal_index["segments_with_interaction_dominance"] == 4
    assert temporal_index["segments_with_conversation_owner"] == 4
    assert temporal_index["top_candidate_visible_people"] == [
        {"entity": "anonymous_person_1", "type": "PERSON", "count": 2},
    ]
    assert temporal_index["top_interaction_dominance"] == [
        {"speaker_id": "SPEAKER_00", "count": 4},
    ]
    assert temporal_index["top_conversation_owners"] == [
        {"entity": "jerry", "type": "PERSON", "count": 4},
    ]


def test_harmonizer_normalizes_scene_relative_speaker_segments_for_dominance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_relative_speaker_segments"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 100.0,
                    "end": 110.0,
                    "duration": 10.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Jerry? Yeah, Jerry.",
                        "speaker_transcript": [
                            {"start": 0.0, "end": 6.0, "text": "Jerry?", "speaker": "SPEAKER_00"},
                            {"start": 6.0, "end": 10.0, "text": "Yeah, Jerry.", "speaker": "SPEAKER_01"},
                        ],
                    },
                    "keyframe": {"faces": [{}]},
                    "objects": [{"label": "person", "score": 0.99}],
                },
                {
                    "scene_id": "scene_0001",
                    "start": 110.0,
                    "end": 120.0,
                    "duration": 10.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Jerry is coming.",
                        "speaker_transcript": [
                            {"start": 0.0, "end": 8.0, "text": "Jerry is coming.", "speaker": "SPEAKER_00"},
                            {"start": 8.0, "end": 10.0, "text": "Okay.", "speaker": "SPEAKER_01"},
                        ],
                    },
                    "keyframe": {"faces": [{}]},
                    "objects": [{"label": "person", "score": 0.98}],
                },
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", True)
    monkeypatch.setattr(
        harmonizer_module,
        "extract_entities_from_scene",
        lambda **_kwargs: {
            "entity_count": 1,
            "entities": [
                {
                    "name": "Jerry",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            ],
        },
    )

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    first_segment = temporal_index["segments"][0]
    second_segment = temporal_index["segments"][1]

    assert first_segment["dominant_speaker_id"] == "SPEAKER_00"
    assert first_segment["dominant_speaker_share"] == 0.6
    assert first_segment["dominance_confidence"] == "strong"
    assert first_segment["conversation_speaker_ids"] == ["SPEAKER_00", "SPEAKER_01"]
    assert first_segment["continuity_key"] == "conversation:SPEAKER_00|SPEAKER_01"
    assert second_segment["dominant_speaker_id"] == "SPEAKER_00"
    assert second_segment["dominant_speaker_share"] == 0.8
    assert second_segment["dominance_confidence"] == "strong"
    assert second_segment["continuity_key"] == "conversation:SPEAKER_00|SPEAKER_01"


def test_harmonizer_candidate_visible_people_stays_empty_for_topic_mentions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_candidate_topic_guardrail"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 5.0,
                    "duration": 5.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Jerry keeps talking about Superman all day.",
                        "speaker_transcript": [
                            {"start": 0.0, "end": 2.5, "text": "Jerry keeps talking about Superman all day.", "speaker": "SPEAKER_00"},
                            {"start": 2.5, "end": 5.0, "text": "I know, he will not stop.", "speaker": "SPEAKER_01"},
                        ],
                    },
                    "keyframe": {
                        "faces": [{}, {}],
                    },
                    "objects": [
                        {"label": "person", "score": 0.99},
                        {"label": "person", "score": 0.97},
                    ],
                }
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", True)
    monkeypatch.setattr(
        harmonizer_module,
        "extract_entities_from_scene",
        lambda **_kwargs: {
            "entity_count": 1,
            "entities": [
                {
                    "name": "Superman",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            ],
        },
    )

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    segment = temporal_index["segments"][0]

    assert segment["mentioned_people"] == [{"text": "Superman", "type": "PERSON"}]
    assert segment["candidate_visible_people"] == []
    assert temporal_index["segments_with_mentioned_people"] == 1
    assert temporal_index["segments_with_candidate_visible_people"] == 0
    assert temporal_index["top_candidate_visible_people"] == []


def test_harmonizer_candidate_visible_people_rejects_single_speaker_reference_chain(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_candidate_single_speaker_reference_chain"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 4.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "This is like a note from your mother.",
                        "speaker_transcript": [
                            {"start": 0.0, "end": 4.0, "text": "This is like a note from your mother.", "speaker": "SPEAKER_00"},
                        ],
                    },
                    "keyframe": {"faces": [{}]},
                    "objects": [{"label": "person", "score": 0.98}],
                },
                {
                    "scene_id": "scene_0001",
                    "start": 4.0,
                    "end": 8.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Anyway, let's keep moving.",
                        "speaker_transcript": [
                            {"start": 4.0, "end": 8.0, "text": "Anyway, let's keep moving.", "speaker": "SPEAKER_00"},
                        ],
                    },
                    "keyframe": {"faces": [{}]},
                    "objects": [{"label": "person", "score": 0.97}],
                },
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", True)
    monkeypatch.setattr(
        harmonizer_module,
        "extract_entities_from_scene",
        lambda **_kwargs: (
            {
                "entity_count": 1,
                "entities": [
                    {
                        "name": "Mother",
                        "entity_type": "PERSON",
                        "source_modalities": ["audio"],
                        "source_steps": ["tagger"],
                    }
                ],
            }
            if "mother" in str(_kwargs.get("scene_data", {}).get("transcription", "")).lower()
            else {
                "entity_count": 0,
                "entities": [],
            }
        ),
    )

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    first_segment = temporal_index["segments"][0]
    second_segment = temporal_index["segments"][1]

    assert temporal_index["segments_with_mentioned_people"] == 1
    assert temporal_index["segments_with_candidate_visible_people"] == 2
    assert first_segment["candidate_visible_people"][0]["text"] == "anonymous_person_1"
    assert second_segment["candidate_visible_people"][0]["text"] == "anonymous_person_1"
    assert first_segment["conversation_owner"] is None
    assert second_segment["conversation_owner"] is None
    assert temporal_index["segments_with_interaction_dominance"] == 2
    assert temporal_index["segments_with_conversation_owner"] == 0
    assert temporal_index["top_candidate_visible_people"] == [
        {"entity": "anonymous_person_1", "type": "PERSON", "count": 2},
    ]


def test_harmonizer_conversation_owner_uses_chain_level_aligned_mentions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_chain_level_owner"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 4.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Jerry, Jerry, listen to me.",
                        "speaker_transcript": [
                            {"start": 0.0, "end": 2.8, "text": "Jerry, Jerry,", "speaker": "SPEAKER_01"},
                            {"start": 2.8, "end": 4.0, "text": "listen to me.", "speaker": "SPEAKER_00"},
                        ],
                    },
                },
                {
                    "scene_id": "scene_0001",
                    "start": 4.0,
                    "end": 8.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Jerry, let's go.",
                        "speaker_transcript": [
                            {"start": 4.0, "end": 6.8, "text": "Jerry,", "speaker": "SPEAKER_00"},
                            {"start": 6.8, "end": 8.0, "text": "let's go.", "speaker": "SPEAKER_01"},
                        ],
                    },
                    "keyframe": {"faces": [{}]},
                    "objects": [{"label": "person", "score": 0.98}],
                },
                {
                    "scene_id": "scene_0002",
                    "start": 8.0,
                    "end": 12.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Elaine can wait.",
                        "speaker_transcript": [
                            {"start": 8.0, "end": 10.8, "text": "Elaine", "speaker": "SPEAKER_00"},
                            {"start": 10.8, "end": 12.0, "text": "can wait.", "speaker": "SPEAKER_01"},
                        ],
                    },
                },
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    def _extract_entities(**kwargs):
        transcription = str(kwargs.get("scene_data", {}).get("transcription", ""))
        entities = []
        if "Jerry" in transcription:
            entities.append(
                {
                    "name": "Jerry",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        if "Elaine" in transcription:
            entities.append(
                {
                    "name": "Elaine",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        return {"entity_count": len(entities), "entities": entities}

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", True)
    monkeypatch.setattr(harmonizer_module, "extract_entities_from_scene", _extract_entities)

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    first_segment = temporal_index["segments"][0]
    second_segment = temporal_index["segments"][1]
    third_segment = temporal_index["segments"][2]

    expected_owner = {
        "name": "Jerry",
        "text": "Jerry",
        "type": "PERSON",
        "confidence": "candidate",
        "source": "interaction_chain",
        "continuity_key": "conversation:SPEAKER_00|SPEAKER_01",
        "chain_length": 3,
        "mention_dominance_ratio": 0.6667,
        "speaker_dominance_ratio": 0.7,
        "competitor_gap": 1,
        "evidence": {
            "speaker_aligned_mentions": 2,
            "total_mentions": 3,
            "segments_involved": ["scene_0000", "scene_0001"],
        },
    }

    assert first_segment["interaction_dominance"] == {
        "speaker_id": "SPEAKER_00",
        "dominant_share": 0.7,
        "segments": 2,
        "stability": 0.6667,
        "confidence": "stable",
        "continuity_key": "conversation:SPEAKER_00|SPEAKER_01",
    }
    assert first_segment["speaker_aligned_mentions"] == [{"text": "Jerry", "type": "PERSON", "count": 1}]
    assert second_segment["speaker_aligned_mentions"] == [{"text": "Jerry", "type": "PERSON", "count": 1}]
    assert third_segment["speaker_aligned_mentions"] == [{"text": "Elaine", "type": "PERSON", "count": 1}]
    assert first_segment["conversation_owner"] == expected_owner
    assert second_segment["conversation_owner"] == expected_owner
    assert third_segment["conversation_owner"] == expected_owner
    assert temporal_index["segments_with_speaker_aligned_mentions"] == 3
    assert temporal_index["segments_with_conversation_owner"] == 3
    assert temporal_index["top_speaker_aligned_mentions"] == [
        {"entity": "jerry", "type": "PERSON", "count": 2},
        {"entity": "elaine", "type": "PERSON", "count": 1},
    ]
    assert temporal_index["top_conversation_owners"] == [
        {"entity": "jerry", "type": "PERSON", "count": 3},
    ]


def test_harmonizer_conversation_owner_aggregates_single_token_full_name_variants(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_chain_owner_full_name_variant"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 4.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Monica Seles is unstoppable.",
                        "speaker_transcript": [
                            {"start": 0.0, "end": 3.0, "text": "Monica Seles is unstoppable.", "speaker": "SPEAKER_00"},
                            {"start": 3.0, "end": 4.0, "text": "Absolutely.", "speaker": "SPEAKER_01"},
                        ],
                    },
                },
                {
                    "scene_id": "scene_0001",
                    "start": 4.0,
                    "end": 8.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Monica has the advantage.",
                        "speaker_transcript": [
                            {"start": 4.0, "end": 7.0, "text": "Monica has the advantage.", "speaker": "SPEAKER_00"},
                            {"start": 7.0, "end": 8.0, "text": "Yep.", "speaker": "SPEAKER_01"},
                        ],
                    },
                },
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    def _extract_entities(**kwargs):
        transcription = str(kwargs.get("scene_data", {}).get("transcription", ""))
        entities = []
        if "Monica Seles" in transcription:
            entities.append(
                {
                    "name": "Monica Seles",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        if "Monica has" in transcription:
            entities.append(
                {
                    "name": "Monica",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        return {"entity_count": len(entities), "entities": entities}

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", True)
    monkeypatch.setattr(harmonizer_module, "extract_entities_from_scene", _extract_entities)

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    first_segment = temporal_index["segments"][0]
    second_segment = temporal_index["segments"][1]

    expected_owner = {
        "name": "Monica Seles",
        "text": "Monica Seles",
        "type": "PERSON",
        "confidence": "candidate",
        "source": "interaction_chain",
        "continuity_key": "conversation:SPEAKER_00|SPEAKER_01",
        "chain_length": 2,
        "mention_dominance_ratio": 1.0,
        "speaker_dominance_ratio": 0.75,
        "competitor_gap": 2,
        "evidence": {
            "speaker_aligned_mentions": 2,
            "total_mentions": 2,
            "segments_involved": ["scene_0000", "scene_0001"],
        },
    }

    assert first_segment["speaker_aligned_mentions"] == [{"text": "Monica Seles", "type": "PERSON", "count": 1}]
    assert second_segment["speaker_aligned_mentions"] == [{"text": "Monica", "type": "PERSON", "count": 1}]
    assert first_segment["conversation_owner"] == expected_owner
    assert second_segment["conversation_owner"] == expected_owner
    assert temporal_index["segments_with_conversation_owner"] == 2
    assert temporal_index["top_conversation_owners"] == [
        {"entity": "monica seles", "type": "PERSON", "count": 2},
    ]


def test_harmonizer_conversation_owner_aggregates_title_stripped_variants(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_chain_owner_title_variant"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 4.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Mayor Dinkins is late again.",
                        "speaker_transcript": [
                            {"start": 0.0, "end": 3.0, "text": "Mayor Dinkins is late again.", "speaker": "SPEAKER_00"},
                            {"start": 3.0, "end": 4.0, "text": "Right.", "speaker": "SPEAKER_01"},
                        ],
                    },
                },
                {
                    "scene_id": "scene_0001",
                    "start": 4.0,
                    "end": 8.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Dinkins never calls ahead.",
                        "speaker_transcript": [
                            {"start": 4.0, "end": 7.0, "text": "Dinkins never calls ahead.", "speaker": "SPEAKER_00"},
                            {"start": 7.0, "end": 8.0, "text": "Nope.", "speaker": "SPEAKER_01"},
                        ],
                    },
                },
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    def _extract_entities(**kwargs):
        transcription = str(kwargs.get("scene_data", {}).get("transcription", ""))
        entities = []
        if "Mayor Dinkins" in transcription:
            entities.append(
                {
                    "name": "Mayor Dinkins",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        if "Dinkins never" in transcription:
            entities.append(
                {
                    "name": "Dinkins",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        return {"entity_count": len(entities), "entities": entities}

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", True)
    monkeypatch.setattr(harmonizer_module, "extract_entities_from_scene", _extract_entities)

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    first_segment = temporal_index["segments"][0]
    second_segment = temporal_index["segments"][1]

    expected_owner = {
        "name": "Dinkins",
        "text": "Dinkins",
        "type": "PERSON",
        "confidence": "candidate",
        "source": "interaction_chain",
        "continuity_key": "conversation:SPEAKER_00|SPEAKER_01",
        "chain_length": 2,
        "mention_dominance_ratio": 1.0,
        "speaker_dominance_ratio": 0.75,
        "competitor_gap": 2,
        "evidence": {
            "speaker_aligned_mentions": 2,
            "total_mentions": 2,
            "segments_involved": ["scene_0000", "scene_0001"],
        },
    }

    assert first_segment["speaker_aligned_mentions"] == [{"text": "Mayor Dinkins", "type": "PERSON", "count": 1}]
    assert second_segment["speaker_aligned_mentions"] == [{"text": "Dinkins", "type": "PERSON", "count": 1}]
    assert first_segment["conversation_owner"] == expected_owner
    assert second_segment["conversation_owner"] == expected_owner
    assert temporal_index["segments_with_conversation_owner"] == 2
    assert temporal_index["top_conversation_owners"] == [
        {"entity": "dinkins", "type": "PERSON", "count": 2},
    ]


def test_harmonizer_reports_speaker_aligned_mention_variant_groups_read_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_aligned_variant_audit"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 4.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Mayor Dinkins should be here.",
                        "speaker_transcript": [
                            {"start": 0.0, "end": 3.0, "text": "Mayor Dinkins should be here.", "speaker": "SPEAKER_00"},
                            {"start": 3.0, "end": 4.0, "text": "Okay.", "speaker": "SPEAKER_01"},
                        ],
                    },
                },
                {
                    "scene_id": "scene_0001",
                    "start": 4.0,
                    "end": 8.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Dinkins is late again.",
                        "speaker_transcript": [
                            {"start": 4.0, "end": 7.0, "text": "Dinkins is late again.", "speaker": "SPEAKER_00"},
                            {"start": 7.0, "end": 8.0, "text": "Right.", "speaker": "SPEAKER_01"},
                        ],
                    },
                },
                {
                    "scene_id": "scene_0002",
                    "start": 8.0,
                    "end": 12.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Monica Seles is playing tonight.",
                        "speaker_transcript": [
                            {"start": 8.0, "end": 11.0, "text": "Monica Seles is playing tonight.", "speaker": "SPEAKER_00"},
                            {"start": 11.0, "end": 12.0, "text": "Sure.", "speaker": "SPEAKER_01"},
                        ],
                    },
                },
                {
                    "scene_id": "scene_0003",
                    "start": 12.0,
                    "end": 16.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Monica has the advantage.",
                        "speaker_transcript": [
                            {"start": 12.0, "end": 15.0, "text": "Monica has the advantage.", "speaker": "SPEAKER_00"},
                            {"start": 15.0, "end": 16.0, "text": "Yep.", "speaker": "SPEAKER_01"},
                        ],
                    },
                },
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    def _extract_entities(**kwargs):
        transcription = str(kwargs.get("scene_data", {}).get("transcription", ""))
        entities = []
        if "Mayor Dinkins" in transcription:
            entities.append(
                {
                    "name": "Mayor Dinkins",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        if "Dinkins" in transcription and "Mayor Dinkins" not in transcription:
            entities.append(
                {
                    "name": "Dinkins",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        if "Monica Seles" in transcription:
            entities.append(
                {
                    "name": "Monica Seles",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        if "Monica has" in transcription:
            entities.append(
                {
                    "name": "Monica",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        return {"entity_count": len(entities), "entities": entities}

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", True)
    monkeypatch.setattr(harmonizer_module, "extract_entities_from_scene", _extract_entities)

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))

    assert temporal_index["segments_with_speaker_aligned_mentions"] == 4
    assert temporal_index["top_speaker_aligned_mentions"] == [
        {"entity": "dinkins", "type": "PERSON", "count": 1},
        {"entity": "mayor dinkins", "type": "PERSON", "count": 1},
        {"entity": "monica", "type": "PERSON", "count": 1},
        {"entity": "monica seles", "type": "PERSON", "count": 1},
    ]
    assert temporal_index["speaker_aligned_mention_variant_groups"] == [
        {
            "group_key": "person::dinkins",
            "type": "PERSON",
            "reason": "title_stripped_overlap",
            "total_count": 2,
            "variants": [
                {"entity": "dinkins", "count": 1},
                {"entity": "mayor dinkins", "count": 1},
            ],
        },
        {
            "group_key": "person::monica seles",
            "type": "PERSON",
            "reason": "single_token_full_name_overlap",
            "total_count": 2,
            "variants": [
                {"entity": "monica", "count": 1},
                {"entity": "monica seles", "count": 1},
            ],
        },
    ]


def test_harmonizer_reports_transcript_entity_disagreement_hotspots_read_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_transcript_entity_disagreement_audit"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 4.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Mr. Costanza will see you now.",
                        "speaker_transcript": [
                            {"start": 0.0, "end": 4.0, "text": "Mr. Costanza will see you now.", "speaker": "SPEAKER_00"},
                        ],
                    },
                },
                {
                    "scene_id": "scene_0001",
                    "start": 4.0,
                    "end": 8.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Jerry Seinfeld is waiting outside.",
                        "speaker_transcript": [
                            {"start": 4.0, "end": 8.0, "text": "Jerry Seinfeld is waiting outside.", "speaker": "SPEAKER_00"},
                        ],
                    },
                },
                {
                    "scene_id": "scene_0002",
                    "start": 8.0,
                    "end": 12.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Monica Selis is serving for the match.",
                        "speaker_transcript": [
                            {"start": 8.0, "end": 12.0, "text": "Monica Selis is serving for the match.", "speaker": "SPEAKER_00"},
                        ],
                    },
                },
                {
                    "scene_id": "scene_0003",
                    "start": 12.0,
                    "end": 16.0,
                    "duration": 4.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "transcript": "Now, Mrs. Swedler should sign here.",
                        "speaker_transcript": [
                            {"start": 12.0, "end": 16.0, "text": "Now, Mrs. Swedler should sign here.", "speaker": "SPEAKER_00"},
                        ],
                    },
                },
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    def _extract_entities(**kwargs):
        transcription = str(kwargs.get("scene_data", {}).get("transcription", ""))
        entities = []
        if "Costanza" in transcription:
            entities.append(
                {
                    "name": "Costanza",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        if "Jerry Seinfeld" in transcription:
            entities.append(
                {
                    "name": "Jerry",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        if "Monica Selis" in transcription:
            entities.append(
                {
                    "name": "Monica Seles",
                    "entity_type": "PERSON",
                    "source_modalities": ["audio"],
                    "source_steps": ["tagger"],
                }
            )
        return {"entity_count": len(entities), "entities": entities}

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", True)
    monkeypatch.setattr(harmonizer_module, "extract_entities_from_scene", _extract_entities)

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))

    assert temporal_index["segments_with_transcript_entity_disagreements"] == 4
    category_counts = {
        item["category"]: item["count"]
        for item in temporal_index["transcript_entity_disagreement_category_counts"]
    }
    assert category_counts == {
        "title_elision_in_entity_projection": 1,
        "transcript_full_name_reduced_to_partial_entity": 1,
        "transcript_spelling_drift_vs_entity_name": 1,
        "title_bearing_transcript_name_not_resolved": 1,
    }

    families = {
        (item["category"], item["family_key"]): item
        for item in temporal_index["top_transcript_entity_disagreement_families"]
    }
    assert families[
        ("title_elision_in_entity_projection", "title::costanza")
    ]["example"]["transcript_candidate"] == "Mr. Costanza"
    assert families[
        ("transcript_full_name_reduced_to_partial_entity", "partial::jerry")
    ]["example"]["entity_names"] == ["Jerry"]
    assert families[
        ("transcript_spelling_drift_vs_entity_name", "spelling::monica selis")
    ]["example"]["entity_names"] == ["Monica Seles"]
    assert families[
        ("title_bearing_transcript_name_not_resolved", "title_unresolved::mrs swedler")
    ]["example"]["transcript_candidate"] == "Mrs. Swedler"

    persisted_manifest = json.loads(scene_manifest_path.read_text(encoding="utf-8"))
    assert persisted_manifest["scenes"][0]["speaker_aligned_mentions"] == [
        {"text": "Costanza", "type": "PERSON", "count": 1}
    ]
    assert persisted_manifest["scenes"][1]["speaker_aligned_mentions"] == [
        {"text": "Jerry", "type": "PERSON", "count": 1}
    ]
    assert persisted_manifest["scenes"][2]["mentioned_people"] == [
        {"text": "Monica Seles", "type": "PERSON"}
    ]
    assert persisted_manifest["scenes"][2].get("speaker_aligned_mentions", []) == []
    assert persisted_manifest["scenes"][3].get("speaker_aligned_mentions", []) == []


def test_transcript_entity_disagreement_ignores_discourse_lead_ins() -> None:
    disagreements = harmonizer_module._segment_transcript_entity_disagreements(
        {
            "full_transcript": "Maybe Gwen should call later.",
            "entities": [{"text": "Gwen", "type": "PERSON"}],
            "mentioned_people": [{"text": "Gwen", "type": "PERSON"}],
            "speaker_aligned_mentions": [{"text": "Gwen", "type": "PERSON", "count": 1}],
        }
    )

    assert disagreements == []


def test_harmonizer_does_not_promote_unknown_speaker_fallback_ids(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_unknown_speaker_filter"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 5.0,
                    "duration": 5.0,
                    "confidence": 0.9,
                    "content_state": "signal",
                    "audio": {
                        "path": "audio/scene_0000.wav",
                        "audio_meta": {"duration_sec": 5.0},
                        "transcript": "Hello there",
                        "speakers": [{"start": 0.0, "end": 5.0}],
                    },
                }
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})

    monkeypatch.setattr(harmonizer_module, "ENTITY_EXTRACTION_AVAILABLE", False)

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))

    assert temporal_index["segments"][0]["speaker_ids"] == []
