import json
import sqlite3
import subprocess
from pathlib import Path

import pytest


def test_as02_untimed_words_inherit_exclusive_containing_segment_only_when_all_untimed():
    from steps.audio_speaker_merge.step import audio_speaker_merge

    untimed_words = [
        {"text": tok, "start": None, "end": None, "timing_status": "unaligned"}
        for tok in ("Happy", "birthday", "to", "you")
    ]
    exclusive = audio_speaker_merge(
        {
            "transcript": "Happy birthday to you",
            "segments": [{"start": 1.0, "end": 3.0, "text": "Happy birthday to you", "words": untimed_words}],
            "diarization": [{"start": 0.5, "end": 3.5, "speaker": "SPEAKER_00"}],
            "transcript_meta": {"status": "success"},
        },
        {},
    )
    assert len(exclusive["speaker_transcript"]) == 1
    turn = exclusive["speaker_transcript"][0]
    assert turn["text"] == "Happy birthday to you"
    assert turn["speaker"] == "SPEAKER_00"
    assert turn["attribution_status"] == "unreviewed"
    assert turn["attribution_reason"] is None
    assert turn["timing_scope"] == "containing_segment"
    assert exclusive["transcript_meta"]["speakers"] == ["SPEAKER_00"]

    # Mixed-timing segment: untimed word inside a segment that also has aligned words must NOT claim the whole segment span.
    mixed_timing = audio_speaker_merge(
        {
            "transcript": "Hello there friend",
            "segments": [
                {
                    "start": 1.0,
                    "end": 4.0,
                    "text": "Hello there friend",
                    "words": [
                        {"text": "Hello", "start": 1.0, "end": 1.8, "timing_status": "aligned"},
                        {"text": "there", "start": None, "end": None, "timing_status": "unaligned"},
                        {"text": "friend", "start": 2.2, "end": 3.0, "timing_status": "aligned"},
                    ],
                }
            ],
            "diarization": [{"start": 0.5, "end": 4.5, "speaker": "SPEAKER_00"}],
            "transcript_meta": {"status": "success"},
        },
        {},
    )
    assert len(mixed_timing["speaker_transcript"]) == 3
    assert mixed_timing["speaker_transcript"][0]["speaker"] == "SPEAKER_00"
    assert mixed_timing["speaker_transcript"][0]["timing_scope"] == "word_alignment"
    assert mixed_timing["speaker_transcript"][1]["speaker"] is None
    assert mixed_timing["speaker_transcript"][1]["attribution_status"] == "unresolved"
    assert mixed_timing["speaker_transcript"][1]["attribution_reason"] == "timing_unavailable"
    assert mixed_timing["speaker_transcript"][1]["timing_scope"] == "containing_segment"
    assert mixed_timing["speaker_transcript"][2]["speaker"] == "SPEAKER_00"

    # Partial diarization support over coarse segment returns speaker is None (incomplete_speaker_support).
    partial_support = audio_speaker_merge(
        {
            "transcript": "Happy birthday to you",
            "segments": [{"start": 1.0, "end": 3.0, "text": "Happy birthday to you", "words": untimed_words}],
            "diarization": [{"start": 1.0, "end": 2.4, "speaker": "SPEAKER_00"}],
            "transcript_meta": {"status": "success"},
        },
        {},
    )
    assert partial_support["speaker_transcript"][0]["speaker"] is None
    assert partial_support["speaker_transcript"][0]["attribution_reason"] == "incomplete_speaker_support"

    # Multi-speaker coarse segment returns speaker is None (multiple_speakers).
    split_speakers = audio_speaker_merge(
        {
            "transcript": "Happy birthday to you",
            "segments": [{"start": 1.0, "end": 3.0, "text": "Happy birthday to you", "words": untimed_words}],
            "diarization": [
                {"start": 1.0, "end": 2.0, "speaker": "SPEAKER_00"},
                {"start": 2.0, "end": 3.0, "speaker": "SPEAKER_01"},
            ],
            "transcript_meta": {"status": "success"},
        },
        {},
    )
    assert len(split_speakers["speaker_transcript"]) == 1
    unresolved_turn = split_speakers["speaker_transcript"][0]
    assert unresolved_turn["speaker"] is None
    assert unresolved_turn["attribution_status"] == "unresolved"
    assert unresolved_turn["attribution_reason"] == "multiple_speakers"
    assert unresolved_turn["timing_scope"] == "containing_segment"

    missing_bounds = audio_speaker_merge(
        {
            "transcript": "Hello there",
            "segments": [
                {
                    "start": None,
                    "end": None,
                    "text": "Hello there",
                    "words": [{"text": "Hello", "start": None, "end": None, "timing_status": "unaligned"}],
                }
            ],
            "diarization": [{"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"}],
            "transcript_meta": {"status": "success"},
        },
        {},
    )
    assert missing_bounds["speaker_transcript"][0]["speaker"] is None
    assert missing_bounds["speaker_transcript"][0]["attribution_reason"] == "timing_unavailable"


def test_as02_speaker_duration_share_and_kg_caller_preserve_dominant_speaker_on_mixed_timing(tmp_path):
    from lib.kg_realtime_integration import _speaker_duration_share, update_kg_for_scene
    from steps.audio_speaker_merge.step import audio_speaker_merge

    # Production caller pipeline: audio_speaker_merge -> update_kg_for_scene on a mixed-timing [0.0, 20.0] scene
    # where SPEAKER_00 has 14.0s of aligned words + 2 untimed words in the middle (70% dominant share of 20.0s).
    merged = audio_speaker_merge(
        {
            "transcript": "Bill is speaking clearly right here",
            "segments": [
                {
                    "start": 0.0,
                    "end": 20.0,
                    "text": "Bill is speaking clearly right here",
                    "words": [
                        {"text": "Bill", "start": 0.0, "end": 3.5, "timing_status": "aligned"},
                        {"text": "is", "start": 3.5, "end": 7.0, "timing_status": "aligned"},
                        {"text": "speaking", "start": None, "end": None, "timing_status": "unaligned"},
                        {"text": "clearly", "start": None, "end": None, "timing_status": "unaligned"},
                        {"text": "right", "start": 10.0, "end": 13.5, "timing_status": "aligned"},
                        {"text": "here", "start": 13.5, "end": 17.0, "timing_status": "aligned"},
                    ],
                }
            ],
            "diarization": [{"start": 0.0, "end": 20.0, "speaker": "SPEAKER_00"}],
            "transcript_meta": {"status": "success"},
        },
        {},
    )
    scene_data = {
        "index": 1,
        "start": 0.0,
        "end": 20.0,
        "entities": [{"name": "Bill", "type": "PERSON"}],
        "speaker_transcript": merged["speaker_transcript"],
    }
    assert _speaker_duration_share(scene_data, "SPEAKER_00") == pytest.approx(0.70)

    kg_db = tmp_path / "kg_as02.db"
    kg_res = update_kg_for_scene(
        scene_data=scene_data,
        scene_id="scene_as02_0001",
        video_id="video_as02",
        video_path="samples/synthetic/clip.mp4",
        cfg={"paths": {"knowledge_graph_db": str(kg_db)}},
    )
    assert kg_res["status"] == "success"
    conn = sqlite3.connect(str(kg_db))
    try:
        edge_count = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE edge_type = ?",
            ("identity_candidate",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert edge_count == 1

    # Genuine word-level overlapping speech still counts against dominant_share.
    overlap_scene = {
        "speaker_transcript": [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00", "timing_scope": "word_alignment"},
            {
                "start": 2.0,
                "end": 12.0,
                "speaker": None,
                "timing_scope": "word_alignment",
                "attribution_status": "unresolved",
                "attribution_reason": "overlapping_speakers",
            },
        ]
    }
    assert _speaker_duration_share(overlap_scene, "SPEAKER_00") == pytest.approx(2.0 / 12.0, abs=1e-4)


def test_as03_prompt_echo_outcome_and_binding_parity(monkeypatch):
    from cli.run_ingestion import _derive_transcript_outcome
    from steps.audio import audio_wsl2_bridge as bridge
    from steps.common import transcript_binding

    vocab = ["Person A", "Person B", "Person C", "Person D"]
    echo_words = [
        {"text": tok, "start": float(i) * 0.5, "end": float(i) * 0.5 + 0.3, "timing_status": "aligned", "probability": 0.002}
        for i, tok in enumerate(["Person", "A,", "Person", "B,", "Person", "C,", "Person", "D"])
    ]
    raw_without_vad = {
        "status": "success",
        "transcription_status": "success",
        "transcription": "Person A, Person B, Person C, Person D",
        "segments": [
            {
                "start": 0.0,
                "end": 5.0,
                "text": "Person A, Person B, Person C, Person D",
                "words": echo_words,
                "phrase_timing": {"status": "model_estimated", "start": 0.0, "end": 5.0},
            }
        ],
        "word_timestamps": echo_words,
        "word_alignment": {"method": "whisper_cross_attention_dtw", "status": "available", "words": echo_words},
        "transcription_context": {"status": "applied", "words": vocab, "identity_claim": False},
    }

    # Without VAD speech_detection, prompt_echo_filter emits low_confidence / vocabulary_prompt_echo_filtered.
    sanitized_no_vad = bridge._sanitize_transcription_result(raw_without_vad)
    no_vad_outcome = bridge._build_wsl_capability_outcomes(sanitized_no_vad)["transcription"]
    assert no_vad_outcome["transcript_outcome"] == "low_confidence"
    assert no_vad_outcome["reason"] == "vocabulary_prompt_echo_filtered"

    # With positive VAD speech_detection, outcome matches _derive_transcript_outcome & transcript_binding parity
    # while retaining prompt_echo_filter receipt in both transcript_meta and wsl_capability_outcomes.
    raw_with_vad = {
        **raw_without_vad,
        "speech_detection": {
            "status": "completed",
            "method": "silero_vad",
            "input_duration_seconds": 25.0,
            "speech_duration_seconds": 9.5,
        },
    }

    class EchoWorker:
        def process_audio(self, *_a, **_kw):
            return raw_with_vad

    monkeypatch.setattr(bridge, "WSL2AudioBridge", EchoWorker)
    out = bridge.audio_unified_wsl2("scene_echo.wav", duration=25.0, transcription_vocabulary=vocab)
    assert out["transcript"] == ""
    assert out["transcript_outcome"] == "no_intelligible_speech"
    assert out["transcript_outcome_reason"] == "speech_detected_without_words"
    assert out["transcript_meta"]["prompt_echo_filter"]["filtered_segment_count"] == 1
    assert out["wsl_capability_outcomes"]["transcription"]["prompt_echo_filter"]["filtered_segment_count"] == 1

    derived = _derive_transcript_outcome(
        {"data": out},
        audio_error=None,
        audio_backend_fields={"audio_backend_effective": "wsl"},
    )
    assert derived == {
        "transcript_outcome": out["transcript_outcome"],
        "transcript_outcome_reason": out["transcript_outcome_reason"],
    }
    scope = {"video_id": "v1", "scene_id": "s1", "run_id": "r1", "epoch_id": "e1"}
    record = {
        "schema": 1,
        **scope,
        "outcome": derived["transcript_outcome"],
        "outcome_reason": derived["transcript_outcome_reason"],
        "text_sha256": transcript_binding.digest(""),
    }
    assert transcript_binding.validate(record, scope, "")["status"] == "bound"


def test_as03_prunes_voice_signatures_and_emotions_from_dropped_and_trimmed_echo_spans(monkeypatch):
    from steps.audio import audio_wsl2_bridge as bridge

    vocab = ["Alice", "Bob", "Clara", "David"]

    # Part A: Pure prompt-echo scene prunes all voice signatures and emotions.
    pure_echo_raw = {
        "status": "success",
        "transcription_status": "success",
        "transcription": "Alice, Bob, Clara, David",
        "transcription_context": {"status": "applied", "words": vocab, "identity_claim": False},
        "segments": [
            {
                "start": 1.0,
                "end": 6.0,
                "text": "Alice, Bob, Clara, David",
                "words": [{"text": "Alice,", "start": 1.0, "end": 2.0, "timing_status": "aligned", "probability": 0.01}],
                "phrase_timing": {"status": "unavailable", "reason": "native_bounds_outside_input"},
            }
        ],
        "diarization_status": "success",
        "diarization": [{"start": 1.0, "end": 6.0, "speaker": "SPEAKER_00"}],
        "speaker_voice_signatures": [
            {
                "speaker": "SPEAKER_00",
                "embedding": [0.1] * 192,
                "embedding_dim": 192,
                "selected_segments": [{"speaker": "SPEAKER_00", "start": 1.0, "end": 5.8, "duration": 4.8}],
            }
        ],
        "speaker_voice_signature_meta": {"status": "ok", "emitted": 1, "reason": None},
        "emotion_status": "success",
        "emotion": None,
        "emotion_scores": {},
        "emotion_input": {
            "policy": "clear_speech_only_v2",
            "selected": [{"speaker": "SPEAKER_00", "start": 1.0, "end": 5.8}],
            "phrase_selection": {
                "policy": "complete_observed_phrases_v1",
                "selected": [{"speaker": "SPEAKER_00", "start": 1.0, "end": 5.8, "source_segment_index": 0}],
            },
        },
        "emotion_segments": [
            {"start": 1.0, "end": 5.8, "speaker": "SPEAKER_00", "source_segment_index": 0, "label": "happy"}
        ],
    }

    class PureEchoWorker:
        def process_audio(self, *_a, **_kw):
            return pure_echo_raw

    monkeypatch.setattr(bridge, "WSL2AudioBridge", PureEchoWorker)
    pure_out = bridge.audio_unified_wsl2("pure_echo.wav", duration=10.0, transcription_vocabulary=vocab)
    assert pure_out["speaker_voice_signatures"] == []
    assert pure_out["speaker_voice_signature_meta"]["status"] == "skipped"
    assert pure_out["speaker_voice_signature_meta"]["emitted"] == 0
    assert pure_out["speaker_voice_signature_meta"]["reason"] == "prompt_echo_filtered"
    assert pure_out["emotion_segments"] == []
    assert pure_out["emotion_status"] == "insufficient_evidence"
    assert pure_out["wsl_capability_outcomes"]["acoustic_emotion"]["status"] == "not_applicable"

    # Part B: Trailing vocabulary loop [20.0, 28.0] trimmed to [20.0, 20.6] prunes loop-tail signatures/emotions
    # while retaining clean speech signatures/emotions at [2.0, 6.0].
    loop_words = [
        {"text": tok, "start": 20.0 + i * 0.2, "end": 20.15 + i * 0.2, "timing_status": "aligned", "probability": 0.85}
        for i, tok in enumerate(["Look", "there", "Clara", "Clara", "Clara", "Clara", "Clara", "Clara", "Clara"])
    ]
    trimmed_raw = {
        "status": "success",
        "transcription_status": "success",
        "transcription": "Welcome home everyone. Look there Clara Clara Clara Clara Clara Clara Clara",
        "transcription_context": {"status": "applied", "words": vocab, "identity_claim": False},
        "segments": [
            {
                "start": 2.0,
                "end": 6.0,
                "text": "Welcome home everyone.",
                "words": [
                    {"text": "Welcome", "start": 2.0, "end": 3.0, "timing_status": "aligned", "probability": 0.95},
                    {"text": "home", "start": 3.0, "end": 4.2, "timing_status": "aligned", "probability": 0.94},
                    {"text": "everyone.", "start": 4.2, "end": 6.0, "timing_status": "aligned", "probability": 0.96},
                ],
                "phrase_timing": {"status": "model_estimated", "start": 2.0, "end": 6.0},
            },
            {
                "start": 20.0,
                "end": 28.0,
                "text": "Look there Clara Clara Clara Clara Clara Clara Clara",
                "words": loop_words,
                "phrase_timing": {"status": "model_estimated", "start": 20.0, "end": 28.0},
            },
        ],
        "diarization_status": "success",
        "diarization": [
            {"start": 2.0, "end": 6.0, "speaker": "SPEAKER_00"},
            {"start": 20.0, "end": 28.0, "speaker": "SPEAKER_01"},
        ],
        "speaker_voice_signatures": [
            {
                "speaker": "SPEAKER_00",
                "embedding": [0.2] * 192,
                "embedding_dim": 192,
                "selected_segments": [{"speaker": "SPEAKER_00", "start": 2.0, "end": 5.8, "duration": 3.8}],
            },
            {
                "speaker": "SPEAKER_01",
                "embedding": [0.3] * 192,
                "embedding_dim": 192,
                "selected_segments": [{"speaker": "SPEAKER_01", "start": 20.0, "end": 27.5, "duration": 7.5}],
            },
        ],
        "speaker_voice_signature_meta": {"status": "ok", "emitted": 2, "reason": None},
        "emotion_status": "success",
        "emotion": None,
        "emotion_scores": {},
        "emotion_input": {
            "policy": "clear_speech_only_v2",
            "selected": [
                {"speaker": "SPEAKER_00", "start": 2.0, "end": 5.8},
                {"speaker": "SPEAKER_01", "start": 20.0, "end": 27.5},
            ],
            "phrase_selection": {
                "policy": "complete_observed_phrases_v1",
                "selected": [
                    {"speaker": "SPEAKER_00", "start": 2.0, "end": 5.8, "source_segment_index": 0},
                    {"speaker": "SPEAKER_01", "start": 20.0, "end": 27.5, "source_segment_index": 1},
                ],
            },
        },
        "emotion_segments": [
            {"start": 2.0, "end": 5.8, "speaker": "SPEAKER_00", "source_segment_index": 0, "label": "calm"},
            {"start": 20.0, "end": 27.5, "speaker": "SPEAKER_01", "source_segment_index": 1, "label": "angry"},
        ],
    }

    sanitized_trimmed = bridge._sanitize_transcription_result(trimmed_raw)
    assert [s["speaker"] for s in sanitized_trimmed["speaker_voice_signatures"]] == ["SPEAKER_00"]
    assert sanitized_trimmed["speaker_voice_signature_meta"]["emitted"] == 1
    assert sanitized_trimmed["speaker_voice_signature_meta"]["pruned_prompt_echo_count"] == 1
    assert [e["speaker"] for e in sanitized_trimmed["emotion_segments"]] == ["SPEAKER_00"]
    assert len(sanitized_trimmed["emotion_input"]["phrase_selection"]["selected"]) == 1


def test_as03_preserves_high_confidence_aligned_comma_greetings_while_dropping_roster_echoes():
    from steps.audio.audio_wsl2_bridge import _sanitize_transcription_result

    vocab = ["Person A", "Person B", "Person C", "Person D"]
    greeting_words = [
        {"text": tok, "start": i * 0.4, "end": i * 0.4 + 0.35, "timing_status": "aligned", "probability": 0.93}
        for i, tok in enumerate(["Hi", "Person", "A,", "Person", "B,", "Person", "C,", "Person", "D"])
    ]
    aligned_greeting = {
        "status": "success",
        "transcription_status": "success",
        "transcription": "Hi Person A, Person B, Person C, Person D",
        "transcription_context": {"status": "applied", "words": vocab, "identity_claim": False},
        "segments": [
            {
                "start": 0.0,
                "end": 4.0,
                "text": "Hi Person A, Person B, Person C, Person D",
                "words": greeting_words,
                "phrase_timing": {"status": "model_estimated", "start": 0.0, "end": 4.0},
            }
        ],
    }
    kept = _sanitize_transcription_result(aligned_greeting)
    assert kept["transcription"] == "Hi Person A, Person B, Person C, Person D"
    assert len(kept["segments"]) == 1

    # Unaligned prompt-echo roster without word timestamps is still dropped.
    unaligned_roster = {
        **aligned_greeting,
        "segments": [
            {
                "start": 0.0,
                "end": 4.0,
                "text": "Person A, Person B, Person C, Person D",
                "words": [],
                "phrase_timing": {"status": "model_estimated", "start": 0.0, "end": 4.0},
            }
        ],
    }
    dropped_unaligned = _sanitize_transcription_result(unaligned_roster)
    assert dropped_unaligned["segments"] == []
    assert dropped_unaligned["prompt_echo_filter"]["filtered_segment_count"] == 1

    # Repeated vocabulary loop is dropped even if word probabilities look high.
    loop_words = [
        {"text": tok, "start": i * 0.3, "end": i * 0.3 + 0.25, "timing_status": "aligned", "probability": 0.90}
        for i, tok in enumerate(["Person", "A,", "Person", "B,", "Person", "A,", "Person", "B"])
    ]
    repeated_roster = {
        **aligned_greeting,
        "segments": [
            {
                "start": 0.0,
                "end": 3.0,
                "text": "Person A, Person B, Person A, Person B",
                "words": loop_words,
                "phrase_timing": {"status": "model_estimated", "start": 0.0, "end": 3.0},
            }
        ],
    }
    dropped_loop = _sanitize_transcription_result(repeated_roster)
    assert dropped_loop["segments"] == []
    assert dropped_loop["prompt_echo_filter"]["filtered_segment_count"] == 1


def test_as06_native_audio_runner_deletes_stale_result_json_and_blocks_nonzero_exit_reuse(monkeypatch, tmp_path):
    from scripts.wsl2_audio_bridge import NativeAudioRunner

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    workspace_dir = tmp_path / "wsl2_audio_stub"
    workspace_dir.mkdir()
    (workspace_dir / "process_audio.py").write_text("# stub\n", encoding="utf-8")

    runner = object.__new__(NativeAudioRunner)
    runner.output_dir = str(out_dir)
    runner.audio_workspace = str(workspace_dir)

    audio_file = tmp_path / "scene_current.wav"
    audio_file.write_bytes(b"RIFF0000WAVE")
    stale_path = out_dir / "result.json"
    stale_path.write_text(
        json.dumps({"status": "success", "audio_file": "scene_previous.wav", "transcription": "stale text"}),
        encoding="utf-8",
    )

    observed_pre_unlink = []

    def failing_run(*_args, **_kwargs):
        observed_pre_unlink.append(not stale_path.exists())
        stale_path.write_text(
            json.dumps({"status": "success", "audio_file": str(audio_file), "transcription": "partial crash"}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args=["python"], returncode=1, stdout="", stderr="worker crashed")

    monkeypatch.setattr(subprocess, "run", failing_run)
    err_res = runner.process_audio(str(audio_file))
    assert observed_pre_unlink == [True]
    assert err_res["status"] == "error"
    assert err_res["bridge_error_reason"] == "native_process_failed"
    assert not stale_path.exists()

    # Zero exit code with mismatched audio_file basename in fallback result.json must also fail closed.
    def mismatched_fallback_run(*_args, **_kwargs):
        stale_path.write_text(
            json.dumps({"status": "success", "audio_file": "other_scene.wav", "transcription": "wrong scene"}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args=["python"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mismatched_fallback_run)
    mismatch_res = runner.process_audio(str(audio_file))
    assert mismatch_res["status"] == "error"
    assert mismatch_res["bridge_error_reason"] == "stdout_json_parse_failed"
    assert not stale_path.exists()

    # Zero exit code with matching audio_file basename succeeds via result.json fallback and cleans up.
    def valid_fallback_run(*_args, **_kwargs):
        stale_path.write_text(
            json.dumps({"status": "success", "audio_file": str(audio_file), "transcription": "clean fallback"}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args=["python"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", valid_fallback_run)
    ok_res = runner.process_audio(str(audio_file))
    assert ok_res["status"] == "success"
    assert ok_res["transcription"] == "clean fallback"
    assert ok_res["used_fallback_result_json"] is True
    assert not stale_path.exists()


def test_as06_phase4_audio_processor_routes_through_audio_unified_wsl2_with_vocab_options(monkeypatch, tmp_path):
    from steps.audio import audio_wsl2_bridge as bridge
    from steps.audio.segmentation import phase4_audio_processor as phase4_mod

    cfg = {
        "audio": {
            "transcribe": {
                "vocabulary": ["Alice", "Bob", "Clara", "David"],
                "vocabulary_mode": "post_filter_only",
                "temperature": 0.0,
            }
        }
    }
    processor = phase4_mod.Phase4AudioProcessor(cfg)
    wav_path = tmp_path / "chunk_000.wav"
    wav_path.write_bytes(b"RIFF0000WAVE")

    captured_worker_kwargs = []

    class FakeWorker:
        def process_audio(self, _path, **kwargs):
            captured_worker_kwargs.append(kwargs)
            return {
                "status": "success",
                "transcription_status": "success",
                "transcription": "Alice, Bob, Clara, David Hello from chunk zero.",
                "transcription_decoding": {
                    "policy": "single_temperature_v1",
                    "temperature": 0.0,
                    "source_regions": {"policy": "source_audio_v2"},
                },
                "segments": [
                    {
                        "start": 0.0,
                        "end": 2.0,
                        "text": "Alice, Bob, Clara, David",
                        "words": [],
                        "phrase_timing": {"status": "unavailable", "reason": "native_bounds_outside_input"},
                    },
                    {
                        "start": 2.5,
                        "end": 5.0,
                        "text": "Hello from chunk zero.",
                        "words": [
                            {"text": "Hello", "start": 2.5, "end": 3.1, "timing_status": "aligned", "probability": 0.95},
                            {"text": "from", "start": 3.1, "end": 3.6, "timing_status": "aligned", "probability": 0.94},
                            {"text": "chunk", "start": 3.6, "end": 4.2, "timing_status": "aligned", "probability": 0.96},
                            {"text": "zero.", "start": 4.2, "end": 5.0, "timing_status": "aligned", "probability": 0.97},
                        ],
                        "phrase_timing": {"status": "model_estimated", "start": 2.5, "end": 5.0},
                    },
                ],
                "diarization_status": "success",
                "diarization": [{"start": 2.5, "end": 5.0, "speaker": "SPEAKER_00"}],
                "speaker_count": 1,
            }

    monkeypatch.setattr(bridge, "WSL2AudioBridge", FakeWorker)
    monkeypatch.setattr(phase4_mod, "audio_unified_wsl2", bridge.audio_unified_wsl2)

    enhanced = processor._process_single_chunk(
        {"id": "seg_0", "chunk_path": str(wav_path), "duration": 5.0},
        tmp_path,
    )
    assert "transcription_vocabulary" not in captured_worker_kwargs[0]
    assert captured_worker_kwargs[0]["transcription_temperature"] == 0.0
    assert enhanced["transcript"] == "Hello from chunk zero."
    assert len(enhanced["transcript_segments"]) == 1
    assert enhanced["transcript_meta"]["prompt_echo_filter"]["filtered_segment_count"] == 1
    assert enhanced["diarization"] == [{"start": 2.5, "end": 5.0, "speaker": "SPEAKER_00"}]



def test_asr_loop_gate_scene93_scene99_scene100_and_downstream_summarizer(monkeypatch):
    import sys
    import types
    from steps.common.context_analyzer_llm import is_scene_transcript_restricted
    from steps.common.scene_summarizer import generate_scene_summary_template
    from steps.common.tag_utils import reliable_transcript_for_entities
    from steps.emotion_classify import step as emotion_step
    from steps.sentiment import step as sentiment_step
    from steps.tagger import step as tagger_step

    # Anonymized Scene 93: 17 words split across [8, 8, 1] segments repeating tok_0.
    scene_93_phrases = [
        {"text": " ".join(["tok_0"] * 8), "source_segment_index": 0, "status": "model_estimated"},
        {"text": " ".join(["tok_0"] * 8), "source_segment_index": 1, "status": "model_estimated"},
        {"text": "tok_0", "source_segment_index": 2, "status": "model_estimated"},
    ]
    scene_93 = {
        "transcript": " ".join(p["text"] for p in scene_93_phrases),
        "transcript_meta": {
            "status": "success",
            "phrase_observations": scene_93_phrases,
        },
        "speaker_transcript": [{"speaker": "SPEAKER_00", "text": p["text"]} for p in scene_93_phrases],
    }

    # Anonymized Scene 99: 19 short (<8-word) segments totaling 23 words where tok_0 appears 13 times (56.5% >= 45%).
    scene_99_texts = (
        ["tok_0"] * 9
        + ["tok_0 tok_1"] * 4
        + ["tok_2"] * 6
    )
    assert len(scene_99_texts) == 19
    assert sum(len(t.split()) for t in scene_99_texts) == 23
    scene_99_phrases = [
        {"text": txt, "source_segment_index": idx, "status": "model_estimated"}
        for idx, txt in enumerate(scene_99_texts)
    ]
    scene_99 = {
        "transcript": " ".join(scene_99_texts),
        "transcript_meta": {
            "status": "success",
            "phrase_observations": scene_99_phrases,
        },
        "speaker_transcript": [{"speaker": "SPEAKER_00", "text": txt} for txt in scene_99_texts],
    }

    # Anonymized Scene 100: 50 words [20, 9, 8, 7, 6] flagged restricted via source_regions / transcript_outcome.
    scene_100_counts = [20, 9, 8, 7, 6]
    assert sum(scene_100_counts) == 50
    scene_100_texts = [
        " ".join(["happy"] * (n - 1) + [f"word_{idx}"])
        for idx, n in enumerate(scene_100_counts)
    ]
    scene_100 = {
        "transcript": " ".join(scene_100_texts),
        "transcript_outcome": "low_confidence",
        "transcript_meta": {
            "status": "success",
            "transcription_decoding": {
                "source_regions": {
                    "status": "completed",
                    "regions": [{"outcome": "text_returned", "quality_flags": ["compression_ratio_exceeded"]}],
                }
            },
            "phrase_observations": [
                {"text": txt, "source_segment_index": idx, "status": "model_estimated"}
                for idx, txt in enumerate(scene_100_texts)
            ],
        },
        "speaker_transcript": [{"speaker": "SPEAKER_00", "text": txt} for txt in scene_100_texts],
    }
    assert is_scene_transcript_restricted(scene_100) is True

    # Ensure model tokenizer is never invoked for restricted/loop audio-only scenes even if cached in _EMO.
    tokenized_inputs = []

    class GuardTokenizer:
        def __call__(self, text, **_kwargs):
            tokenized_inputs.append(text)

            class _Inputs(dict):
                def to(self, _dev):
                    return self

            return _Inputs()

    class GuardLogits:
        def cpu(self):
            return self

        def numpy(self):
            return self

        def tolist(self):
            return [[0.91, 0.88, 0.05]]

    class GuardModel:
        def __call__(self, **_kwargs):
            return types.SimpleNamespace(logits=GuardLogits())

    class _NoGrad:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    fake_torch = types.ModuleType("torch")
    fake_torch.sigmoid = lambda logits: logits
    fake_torch.no_grad = _NoGrad
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr("steps.common.memory.update_fields", lambda *_a, **_kw: None)
    monkeypatch.setattr("steps.text_embed.step._content_fingerprint", lambda _item: "fp-test")
    monkeypatch.setattr(emotion_step, "_load_emotion", lambda: None)
    monkeypatch.setitem(emotion_step._EMO, "model", GuardModel())
    monkeypatch.setitem(emotion_step._EMO, "tok", GuardTokenizer())
    monkeypatch.setitem(emotion_step._EMO, "labels", ["joy", "love", "anger"])
    monkeypatch.setitem(emotion_step._EMO, "problem_type", "multi_label_classification")
    monkeypatch.setitem(emotion_step._EMO, "device", "cpu")

    for restricted_item in (scene_93, scene_99, scene_100):
        assert reliable_transcript_for_entities(restricted_item) == ""
        sent_out = sentiment_step.sentiment(restricted_item, {})
        assert sent_out == {"sentiment": None, "sentiment_meta": {"status": "no_text", "reason": "no_text"}}

        emo_out = emotion_step.emotion_classify(restricted_item, {"config": {}})
        assert emo_out == {"emotions": None, "emotion_meta": {"status": "no_text", "reason": "no_text"}}

        tag_out = tagger_step.tagger(restricted_item, {})
        assert tag_out["tags"] == []
        assert tag_out["entities"] == []
        assert tag_out["tagger_meta"]["status"] == "no_text"

        # Downstream scene_summarizer receives zero bogus POSITIVE / joy / love labels from gated audio steps.
        merged_scene_meta = {
            "index": 100,
            "start": 10.0,
            "end": 25.0,
            "caption": "Children playing near a snowy porch",
            "objects": [{"label": "sled"}],
            **restricted_item,
            "audio": {
                **restricted_item,
                **sent_out,
                **emo_out,
                **tag_out,
            },
        }
        summary_text = generate_scene_summary_template(merged_scene_meta)
        assert "Children playing near a snowy porch" in summary_text
        for bogus in ("POSITIVE", "joy", "love", "optimism", "tok_0", "happy word_0"):
            assert bogus not in summary_text

    assert tokenized_inputs == []


def test_asr_loop_gate_preserves_unrestricted_plain_dicts_and_reliable_model_scoring(monkeypatch):
    import asyncio
    import sys
    import types
    from cli import run_ingestion
    from steps.emotion_classify import step as emotion_step
    from steps.sentiment import step as sentiment_step

    seen_emotion_texts = []

    class RecordingTokenizer:
        def __call__(self, text, **_kwargs):
            seen_emotion_texts.append(text)

            class _Inputs(dict):
                def to(self, _dev):
                    return self

            return _Inputs()

    class FakeLogits:
        def cpu(self):
            return self

        def numpy(self):
            return self

        def tolist(self):
            return [[0.85, 0.15]]

    class FakeModel:
        def __call__(self, **_kwargs):
            return types.SimpleNamespace(logits=FakeLogits())

    class _NoGrad:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    fake_torch = types.ModuleType("torch")
    fake_torch.sigmoid = lambda logits: logits
    fake_torch.no_grad = _NoGrad
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr("steps.common.memory.update_fields", lambda *_a, **_kw: None)
    monkeypatch.setattr("steps.text_embed.step._content_fingerprint", lambda _item: "fp-clean")
    monkeypatch.setattr(emotion_step, "_load_emotion", lambda: None)
    monkeypatch.setitem(emotion_step._EMO, "model", FakeModel())
    monkeypatch.setitem(emotion_step._EMO, "tok", RecordingTokenizer())
    monkeypatch.setitem(emotion_step._EMO, "labels", ["joy", "anger"])
    monkeypatch.setitem(emotion_step._EMO, "problem_type", "multi_label_classification")
    monkeypatch.setitem(emotion_step._EMO, "device", "cpu")

    # 1. Plain unit-test dict without transcript_meta continues to classify raw transcript directly.
    plain_res = emotion_step.emotion_classify({"transcript": "Plain fixture sentence"}, {"config": {}})
    assert plain_res["emotion_meta"]["status"] == "ok"
    assert seen_emotion_texts[-1] == "Plain fixture sentence"

    # 2. Mixed governed item (clean phrase + runaway loop phrase): _rank_model_emotions scores ONLY the reliable phrase!
    mixed_item = {
        "transcript": "We opened all the gifts together. " + " ".join(["tok_0"] * 12),
        "transcript_meta": {
            "status": "success",
            "phrase_observations": [
                {"text": "We opened all the gifts together.", "source_segment_index": 0, "status": "model_estimated"},
                {"text": " ".join(["tok_0"] * 12), "source_segment_index": 1, "status": "model_estimated"},
            ],
        },
    }
    mixed_res = emotion_step.emotion_classify(mixed_item, {"config": {}})
    assert mixed_res["emotion_meta"]["status"] == "ok"
    assert seen_emotion_texts[-1] == "We opened all the gifts together."
    assert sentiment_step._gather_text(mixed_item) == "We opened all the gifts together."

    # 3. Restricted transcript item with non-empty visual caption falls back cleanly to caption.
    multimodal_restricted = {
        "transcript": " ".join(["tok_0"] * 12),
        "transcript_outcome": "low_confidence",
        "transcript_meta": {"status": "error"},
        "caption": "A bright birthday cake on a table",
    }
    assert sentiment_step._gather_text(multimodal_restricted) == "A bright birthday cake on a table"
    emo_fallback = emotion_step.emotion_classify(multimodal_restricted, {"config": {}})
    assert emo_fallback["emotion_meta"]["status"] == "ok"
    assert seen_emotion_texts[-1] == "A bright birthday cake on a table"

    # 4. cli.run_ingestion._process_audio_async skips audio_transcript text_embed on loop/restricted scenes
    #    while embedding reliable clean speech on unrestricted scenes.
    embedded_payloads = []

    async def fake_run_step_async(_env, step_name, payload, _cfg_json, **_kwargs):
        if step_name == "text_embed":
            embedded_payloads.append(dict(payload))
            return {"status": "ok", "outputs": {"embedding_meta": {"status": "ok", "embedding_id": "e" * 64}}}
        return {"status": "ok", "outputs": {}}

    def make_wsl_worker(transcript_text, phrase_list, outcome="transcript_available"):
        def _worker(*_a, **_kw):
            return {
                "status": "success",
                "wsl2_unified": True,
                "transcript": transcript_text,
                "transcript_outcome": outcome,
                "transcript_meta": {"status": "success", "phrase_observations": phrase_list},
                "segments": [],
                "clap_meta": {
                    "status": "ok",
                    "component": "audio_embed_clap",
                    "embedding_id": "c" * 64,
                    "qdrant_committed": True,
                    "qdrant_collection": "goodq_audio",
                },
            }

        return _worker

    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        wav = tmp / "clip.wav"
        wav.write_bytes(b"RIFF0000WAVE")
        cfg_file = tmp / "cfg.json"
        cfg_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(run_ingestion, "_extract_audio_chunk", lambda *_a, **_kw: wav)
        for helper_name in ("_log_audio_to_ucf_ledger", "log_step_run", "_record_run_warning"):
            monkeypatch.setattr(run_ingestion, helper_name, lambda *_a, **_kw: None)
        monkeypatch.setattr(run_ingestion, "_run_step_async", fake_run_step_async)

        # Restricted / fragmented loop scene -> text_embed NOT invoked
        loop_phrases = [{"text": "tok_0", "source_segment_index": i} for i in range(12)]
        monkeypatch.setattr(
            "steps.audio.audio_wsl2_bridge.audio_unified_wsl2",
            make_wsl_worker(" ".join(["tok_0"] * 12), loop_phrases),
        )
        res_loop = asyncio.run(
            run_ingestion._process_audio_async(
                cfg_file,
                "ffmpeg",
                wav,
                {"index": 0, "start": 0.0, "end": 5.0},
                tmp,
                tmp / "artifacts",
                "vh",
                "s_loop",
                asyncio.Lock(),
                asyncio.Lock(),
                audio_runtime_contract={"selected": "wsl", "reason": "test"},
                wsl_audio_lock=asyncio.Lock(),
            )
        )
        assert embedded_payloads == []
        assert res_loop["data"]["audio_text_embed_meta"] == {
            "status": "skipped",
            "reason": "transcript_restricted_or_unreliable",
        }

        # Unrestricted clean scene -> text_embed invoked with reliable transcript
        clean_phrases = [{"text": "Everyone waved at the camera.", "source_segment_index": 0}]
        monkeypatch.setattr(
            "steps.audio.audio_wsl2_bridge.audio_unified_wsl2",
            make_wsl_worker("Everyone waved at the camera.", clean_phrases),
        )
        res_clean = asyncio.run(
            run_ingestion._process_audio_async(
                cfg_file,
                "ffmpeg",
                wav,
                {"index": 1, "start": 5.0, "end": 10.0},
                tmp,
                tmp / "artifacts2",
                "vh",
                "s_clean",
                asyncio.Lock(),
                asyncio.Lock(),
                audio_runtime_contract={"selected": "wsl", "reason": "test"},
                wsl_audio_lock=asyncio.Lock(),
            )
        )
        assert len(embedded_payloads) == 1
        assert embedded_payloads[0]["text"] == "Everyone waved at the camera."
        assert res_clean["data"]["audio_text_embed_meta"]["status"] == "ok"
