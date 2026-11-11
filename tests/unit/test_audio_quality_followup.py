import json
import pytest


def test_active_async_video_caller_passes_vocabulary(monkeypatch, tmp_path):
    import asyncio
    from cli import run_ingestion as runner
    from steps.audio import audio_wsl2_bridge as bridge
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"fixture")
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"audio": {"transcribe": {"vocabulary": ["Joe"]}}}))
    monkeypatch.setattr(runner, "_extract_audio_chunk", lambda *a, **kw: wav)
    for name in ("_log_audio_to_ucf_ledger", "log_step_run", "_record_run_warning"):
        monkeypatch.setattr(runner, name, lambda *a, **kw: None)
    calls = []
    def worker(*args, **kwargs):
        calls.append(kwargs)
        return {"status": "success", "transcript": "Joe says hello.", "segments": []}
    async def step(*args, **kwargs):
        return {"status": "ok", "outputs": {}}
    monkeypatch.setattr(bridge, "audio_unified_wsl2", worker)
    monkeypatch.setattr(runner, "_run_step_async", step)
    async def run():
        return await runner._process_audio_async(cfg, "ffmpeg", wav,
            {"index": 0, "start": 0., "end": 5.}, tmp_path, tmp_path / "artifacts", "v", "s",
            asyncio.Lock(), asyncio.Lock(), audio_runtime_contract={"selected": "wsl", "reason": "test"},
            wsl_audio_lock=asyncio.Lock())
    asyncio.run(run())
    assert calls[0]["transcription_vocabulary"] == ["Joe"]
    assert calls[0]["transcription_temperature"] == 0.0


def test_step_dispatch_preserves_explicit_vocabulary(monkeypatch):
    from cli.step_runner import run_step
    from steps.audio import audio_wsl2_bridge as bridge
    calls = []
    monkeypatch.setattr(bridge, "audio_unified_wsl2", lambda *a, **kw: calls.append(kw) or {})
    run_step("audio_unified_wsl2", {"audio_path": "clip.wav", "duration": 4},
             {"audio": {"transcribe": {"vocabulary": ["Joe", "Elena Vance"], "temperature": 0.2}}})
    assert calls[0]["transcription_vocabulary"] == ["Joe", "Elena Vance"]
    assert calls[0]["transcription_temperature"] == 0.2


def test_unified_bridge_keeps_vocabulary_provenance(monkeypatch):
    from steps.audio import audio_wsl2_bridge as bridge
    context = {"status": "applied", "words": ["Joe"], "identity_claim": False}
    class Runner:
        def process_audio(self, path, **kwargs):
            assert kwargs["transcription_vocabulary"] == ["Joe"]
            return {"status": "success", "transcription": "Joe says hello.",
                    "transcription_status": "success", "transcription_context": context}
    monkeypatch.setattr(bridge, "WSL2AudioBridge", Runner)
    result = bridge.audio_unified_wsl2("clip.wav", transcription_vocabulary=["Joe"])
    assert result["transcript_meta"]["transcription_context"] == context


@pytest.mark.parametrize("value", ["Joe", [1], [""], ["x" * 65], ["Joe"] * 33])
def test_vocabulary_rejects_malformed_or_excessive_input(value):
    from wsl2_audio.process_audio import _normalize_transcription_vocabulary
    with pytest.raises(ValueError):
        _normalize_transcription_vocabulary(value)


def test_vocabulary_deduplicates_without_inventing_names():
    from wsl2_audio.process_audio import _normalize_transcription_vocabulary
    assert _normalize_transcription_vocabulary([" Joe ", "joe", "Elena Vance"]) == ["Joe", "Elena Vance"]
    assert _normalize_transcription_vocabulary(None) == []


def test_vocabulary_configuration_is_supported_by_strict_schema():
    from scripts.config_schema import AudioConfig, GoodQConfig
    from steps.audio.audio_wsl2_bridge import unified_transcription_options
    assert GoodQConfig.model_fields['audio'].annotation is not None
    cfg = AudioConfig.model_validate({'transcribe': {'vocabulary': ['Joe']}})
    assert unified_transcription_options({'audio': cfg.model_dump()}) == {
        'transcription_vocabulary': ['Joe'], 'transcription_temperature': 0.0}
    assert unified_transcription_options({'audio': None}) == {'transcription_temperature': 0.0}
    with pytest.raises(ValueError):
        AudioConfig.model_validate({'transcribe': {'vocabulary': ['Joe'] * 33}})
    with pytest.raises(ValueError):
        AudioConfig.model_validate({'transcribe': {'vocabulary': ['']}})
    with pytest.raises(ValueError):
        AudioConfig.model_validate({'transcribe': {'unknown': True}})


def test_summary_receives_distribution_instead_of_only_winning_label(monkeypatch):
    from steps.video import cross_modal_harmonizer as h
    from steps.common.context_analyzer_llm import _build_scene_context_prompts
    segment = {"scene_id": "s", "start": 0, "end": 3, "content_state": "signal", "full_transcript": "Yay Joe!",
        "emotion_segments": [{"start": 0, "end": 2, "speaker": "A", "label": "disgust",
                              "scores": {"disgust": .36, "sad": .33, "happy": .31}}],
        "transcript_meta": {"transcription_context": {"status": "applied", "words": ["Joe"], "identity_claim": False}}}
    captured = []
    monkeypatch.setattr(h, "analyze_scene_context_llm", lambda meta, cfg, **kw: captured.append(meta))
    h._apply_scene_context_llm([segment], {"s": {"index": 0, "audio": {}}},
        {"llm": {"features": {"scene_context_analysis": True}}})
    _, prompt = _build_scene_context_prompts(captured[0])
    assert '"disgust": 0.36' in prompt and '"sad": 0.33' in prompt
    assert '"identity_claim": false' in prompt
    assert "uncalibrated" in prompt


def test_mixed_scene_strips_prompt_echo_and_preserves_genuine_family_speech(monkeypatch):
    import copy
    from steps.audio import audio_wsl2_bridge as bridge

    vocab = ["Elena Vance", "Joe", "Marco", "Eleanor", "Claire", "Clara Reed", "Sam"]
    echo_words = [
        {"text": w, "start": float(i), "end": float(i) + 0.4, "timing_status": "aligned", "probability": 0.01}
        for i, w in enumerate(["Eleanor,", "Claire,", "Clara", "Reed,", "Sam,", "Clara", "Reed,", "Sam"])
    ]
    canoe_words = [
        {"text": w, "start": 30.0 + i * 0.4, "end": 30.3 + i * 0.4, "timing_status": "aligned", "probability": 0.92}
        for i, w in enumerate(
            ["We", "are", "going", "to", "put", "Eleanor", "in", "the", "middle", "of", "the", "canoe."]
        )
    ]
    clara_turn_words = [{"text": "Clara", "start": 40.0, "end": 40.5, "timing_status": "aligned", "probability": 0.001}]
    joe_call_words = [
        {"text": "Hey,", "start": 45.0, "end": 45.3, "timing_status": "aligned", "probability": 0.88},
        {"text": "Joe!", "start": 45.3, "end": 45.7, "timing_status": "aligned", "probability": 0.91},
        {"text": "Joe!", "start": 45.8, "end": 46.2, "timing_status": "aligned", "probability": 0.94},
    ]
    ghost_words = [{"text": "Eleanor", "start": 59.5, "end": 59.9, "timing_status": "aligned", "probability": 0.0007}]

    segments = [
        {
            "start": 0.0,
            "end": 7.0,
            "source_region_index": 0,
            "text": "Eleanor, Claire, Clara Reed, Sam, Clara Reed, Sam",
            "words": echo_words,
            "phrase_timing": {"status": "model_estimated", "start": 0.0, "end": 7.0, "reason": "native_phrase_touches_decode_boundary"},
        },
        {
            "start": 30.0,
            "end": 36.0,
            "source_region_index": 0,
            "text": "We are going to put Eleanor in the middle of the canoe.",
            "words": canoe_words,
            "phrase_timing": {"status": "model_estimated", "start": 30.0, "end": 36.0, "reason": None},
        },
        {
            "start": 40.0,
            "end": 41.0,
            "source_region_index": 0,
            "text": "Clara",
            "words": clara_turn_words,
            "phrase_timing": {"status": "model_estimated", "start": 40.0, "end": 41.0, "reason": "native_phrase_not_closed"},
        },
        {
            "start": 45.0,
            "end": 46.5,
            "source_region_index": 0,
            "text": "Hey, Joe! Joe!",
            "words": joe_call_words,
            "phrase_timing": {"status": "model_estimated", "start": 45.0, "end": 46.5, "reason": None},
        },
        {
            "start": 59.5,
            "end": 59.9,
            "source_region_index": 0,
            "text": "Eleanor",
            "words": ghost_words,
            "phrase_timing": {"status": "unavailable", "reason": "native_bounds_outside_input"},
        },
    ]
    all_words = echo_words + canoe_words + clara_turn_words + joe_call_words + ghost_words
    raw = {
        "status": "success",
        "transcription_status": "success",
        "transcription": " ".join(s["text"] for s in segments),
        "segments": segments,
        "word_timestamps": all_words,
        "word_alignment": {
            "method": "whisper_cross_attention_dtw",
            "status": "available",
            "timebase": "input_audio_seconds",
            "review_status": "unreviewed",
            "words": all_words,
        },
        "transcription_context": {
            "status": "applied",
            "source": "request_config",
            "kind": "vocabulary_hints",
            "words": vocab,
            "identity_claim": False,
        },
        "transcription_quality": {
            "status": "completed",
            "scope": "per_source_region",
            "region_results": [
                {
                    "source_region_index": 0,
                    "accepted_segment_count": 5,
                    "decoded_segment_count": 5,
                    "confidence_override": {
                        "segments": [
                            {"segment_index": 0, "word_geometric_mean_probability": 0.01, "decision": "reject"},
                            {"segment_index": 4, "word_geometric_mean_probability": 0.0007, "decision": "reject"},
                        ]
                    },
                }
            ],
        },
        "speech_detection": {
            "status": "completed",
            "method": "silero_vad",
            "input_duration_seconds": 60.0,
            "speech_duration_seconds": 12.0,
        },
        "emotion_status": "success",
        "emotion": None,
        "emotion_scores": {},
        "emotion_input": {"policy": "clear_speech_only_v2", "selected": [{"start": 30.0, "end": 36.0}]},
        "emotion_segments": [
            {"start": 30.0, "end": 36.0, "source_segment_index": 1, "label": "happy", "scores": {"happy": 0.8}}
        ],
    }
    before = copy.deepcopy(raw)

    class Worker:
        def process_audio(self, *args, **kwargs):
            return raw

    monkeypatch.setattr(bridge, "WSL2AudioBridge", Worker)
    result = bridge.audio_unified_wsl2("scene_023.wav", duration=60.0, transcription_vocabulary=vocab)

    assert raw == before
    assert result["transcript"] == "We are going to put Eleanor in the middle of the canoe. Clara Hey, Joe! Joe!"
    assert [s["text"] for s in result["segments"]] == [
        "We are going to put Eleanor in the middle of the canoe.",
        "Clara",
        "Hey, Joe! Joe!",
    ]
    assert len(result["word_timestamps"]) == len(canoe_words) + len(clara_turn_words) + len(joe_call_words)
    assert [p["source_segment_index"] for p in result["transcript_meta"]["phrase_observations"]] == [0, 1, 2]
    assert result["emotion_segments"][0]["source_segment_index"] == 0
    receipt = result["transcript_meta"]["prompt_echo_filter"]
    assert receipt["policy"] == "bridge_prompt_echo_filter_v1"
    assert receipt["filtered_segment_count"] == 2
    assert receipt["kept_segment_count"] == 3
    assert [f["reason"] for f in receipt["filtered_segments"]] == [
        "vocabulary_prompt_echo",
        "vocabulary_short_ghost",
    ]


def test_pure_hum_prompt_echo_scene_resolves_to_no_intelligible_speech_and_binds_cleanly(monkeypatch):
    from cli.run_ingestion import _derive_transcript_outcome
    from steps.audio import audio_wsl2_bridge as bridge
    from steps.common import transcript_binding

    vocab = ["Elena Vance", "Joe", "Marco", "Eleanor", "Claire", "Clara Reed", "Sam"]
    echo_words = [
        {"text": w, "start": float(i) * 0.5, "end": float(i) * 0.5 + 0.3, "timing_status": "aligned", "probability": 0.001}
        for i, w in enumerate(["Elena", "Vance,", "Joe,", "Eleanor,", "Claire,", "Clara", "Reed,", "Sam"])
    ]
    base_raw = {
        "status": "success",
        "transcription_status": "success",
        "transcription": "Elena Vance, Joe, Eleanor, Claire, Clara Reed, Sam",
        "segments": [
            {
                "start": 0.0,
                "end": 7.0,
                "source_region_index": 0,
                "text": "Elena Vance, Joe, Eleanor, Claire, Clara Reed, Sam",
                "words": echo_words,
                "phrase_timing": {"status": "model_estimated", "start": 0.0, "end": 7.0},
            }
        ],
        "word_timestamps": echo_words,
        "word_alignment": {
            "method": "whisper_cross_attention_dtw",
            "status": "available",
            "timebase": "input_audio_seconds",
            "review_status": "unreviewed",
            "words": echo_words,
        },
        "transcription_context": {"status": "applied", "words": vocab, "identity_claim": False},
        "speech_detection": {
            "status": "completed",
            "method": "silero_vad",
            "input_duration_seconds": 33.5,
            "speech_duration_seconds": 11.5,
        },
        "emotion_status": "success",
        "emotion": None,
        "emotion_scores": {},
        "emotion_input": {
            "policy": "clear_speech_only_v2",
            "selected": [{"start": 1.0, "end": 2.0}],
            "phrase_selection": {"policy": "complete_observed_phrases_v1", "selected": [{"start": 1.0, "end": 2.0}]},
        },
        "emotion_segments": [
            {"start": 1.0, "end": 2.0, "source_segment_index": 0, "label": "surprised", "scores": {"surprised": 0.9}}
        ],
    }

    class Worker:
        def process_audio(self, *args, **kwargs):
            return base_raw

    monkeypatch.setattr(bridge, "WSL2AudioBridge", Worker)
    result = bridge.audio_unified_wsl2("scene_038.wav", duration=33.5, transcription_vocabulary=vocab)

    assert result["transcript"] == ""
    assert result["segments"] == []
    assert result["word_timestamps"] == []
    assert result["transcript_meta"]["word_alignment"]["status"] == "no_word_alignment"
    assert result["transcript_outcome"] == "no_intelligible_speech"
    assert result["transcript_outcome_reason"] == "speech_detected_without_words"
    assert result["wsl_capability_outcomes"]["transcription"]["status"] == "skipped"
    assert result["emotion_segments"] == []
    assert result["wsl_capability_outcomes"]["acoustic_emotion"]["status"] == "not_applicable"

    derived = _derive_transcript_outcome({"data": result}, audio_error=None, audio_backend_fields={"audio_backend_effective": "wsl"})
    assert derived == {
        "transcript_outcome": "no_intelligible_speech",
        "transcript_outcome_reason": "speech_detected_without_words",
    }
    expected_scope = {"video_id": "v1", "scene_id": "s38", "run_id": "r1", "epoch_id": "e1"}
    record = {
        "schema": 1,
        **expected_scope,
        "outcome": derived["transcript_outcome"],
        "outcome_reason": derived["transcript_outcome_reason"],
        "text_sha256": transcript_binding.digest(""),
    }
    assert transcript_binding.validate(record, expected_scope, "")["status"] == "bound"

    without_vad = bridge._sanitize_transcription_result({k: v for k, v in base_raw.items() if k != "speech_detection"})
    no_vad_outcome = bridge._build_wsl_capability_outcomes(without_vad)["transcription"]
    assert no_vad_outcome["transcript_outcome"] == "low_confidence"
    assert no_vad_outcome["reason"] == "vocabulary_prompt_echo_filtered"


def test_unterminated_decoder_loop_and_stock_boilerplate_and_tail_loop_sanitization():
    from steps.audio.audio_wsl2_bridge import _sanitize_transcription_result

    monologue = (
        "Well everybody came over to grandma and grandpa's house this afternoon "
        "because the weather finally cleared up after the snowstorm and the kids "
        "wanted to open all the presents together in the living room before dinner."
    )
    raw = {
        "status": "success",
        "transcription_status": "success",
        "transcription": "placeholder",
        "transcription_context": {"status": "applied", "words": ["Joe", "Sofia"], "identity_claim": False},
        "segments": [
            {
                "start": 0.0,
                "end": 10.0,
                "text": "Jumping" * 24,
                "words": [],
                "phrase_timing": {"status": "unavailable", "reason": "paired_native_timestamps_unavailable"},
            },
            {
                "start": 10.0,
                "end": 20.0,
                "text": monologue,
                "words": [],
                "phrase_timing": {"status": "unavailable", "reason": "paired_native_timestamps_unavailable"},
            },
            {
                "start": 20.0,
                "end": 28.0,
                "text": "Fiat, Sofia, Sit, Joe, Joe, Kiss, Be Nice, Joe, Joe, Joe, Joe, Joe, Joe, Joe, Joe, Joe,",
                "words": [
                    {"text": tok, "start": 20.0 + i * 0.2, "end": 20.15 + i * 0.2, "probability": 0.8}
                    for i, tok in enumerate(
                        ["Fiat,", "Sofia,", "Sit,", "Joe,", "Joe,", "Kiss,", "Be", "Nice,", "Joe,", "Joe,", "Joe,", "Joe,", "Joe,", "Joe,", "Joe,", "Joe,", "Joe,"]
                    )
                ],
                "phrase_timing": {"status": "model_estimated", "start": 20.0, "end": 28.0},
            },
            {
                "start": 28.5,
                "end": 29.8,
                "text": "Thank you for watching!",
                "words": [{"text": "Thank", "start": 28.5, "end": 28.8, "probability": 0.2}],
                "phrase_timing": {"status": "unavailable", "reason": "native_bounds_outside_input"},
            },
        ],
        "word_timestamps": [],
        "word_alignment": {"method": "whisper_cross_attention_dtw", "status": "available", "words": []},
    }
    sanitized = _sanitize_transcription_result(raw)
    assert [s["text"] for s in sanitized["segments"]] == [
        monologue,
        "Fiat, Sofia, Sit, Joe, Joe, Kiss, Be Nice, Joe",
    ]
    assert len(sanitized["segments"][1]["words"]) == 9
    receipt = sanitized["prompt_echo_filter"]
    assert receipt["filtered_segment_count"] == 2
    assert receipt["trimmed_segment_count"] == 1
    assert [f["reason"] for f in receipt["filtered_segments"]] == [
        "unterminated_decoder_loop",
        "stock_boilerplate_hallucination",
    ]


def test_post_filter_only_vocabulary_mode_withholds_worker_hotwords_and_records_gated_context(monkeypatch):
    from scripts.config_schema import AudioConfig
    from steps.audio import audio_wsl2_bridge as bridge

    cfg = AudioConfig.model_validate({
        "transcribe": {
            "vocabulary": ["Joe", "Elena Vance"],
            "vocabulary_mode": "post_filter_only",
            "temperature": 0.0,
        }
    })
    opts = bridge.unified_transcription_options({"audio": cfg.model_dump()})
    assert opts == {
        "transcription_temperature": 0.0,
        "post_filter_vocabulary": ["Joe", "Elena Vance"],
    }

    seen_worker_kwargs = []

    class Worker:
        def process_audio(self, path, **kwargs):
            seen_worker_kwargs.append(kwargs)
            return {
                "status": "success",
                "transcription_status": "success",
                "transcription": "Elena Vance, Joe, Elena Vance, Joe Hello everyone!",
                "transcription_decoding": {
                    "policy": "single_temperature_v1",
                    "temperature": 0.0,
                    "source_regions": {"policy": "source_audio_v2"},
                },
                "segments": [
                    {
                        "start": 0.0,
                        "end": 3.0,
                        "text": "Elena Vance, Joe, Elena Vance, Joe",
                        "words": [{"text": "Elena", "start": 0.0, "end": 0.5, "probability": 0.01}],
                        "phrase_timing": {"status": "unavailable", "reason": "native_bounds_outside_input"},
                    },
                    {
                        "start": 3.5,
                        "end": 5.0,
                        "text": "Hello everyone!",
                        "words": [
                            {"text": "Hello", "start": 3.5, "end": 4.1, "probability": 0.95},
                            {"text": "everyone!", "start": 4.1, "end": 5.0, "probability": 0.97},
                        ],
                        "phrase_timing": {"status": "model_estimated", "start": 3.5, "end": 5.0},
                    },
                ],
                "word_timestamps": [],
                "word_alignment": {"method": "whisper_cross_attention_dtw", "status": "available", "words": []},
            }

    monkeypatch.setattr(bridge, "WSL2AudioBridge", Worker)
    result = bridge.audio_unified_wsl2("clip.wav", duration=5.0, **opts)
    assert "transcription_vocabulary" not in seen_worker_kwargs[0]
    assert result["transcript_meta"]["transcription_context"] == {
        "status": "gated_post_filter_only",
        "source": "request_config",
        "kind": "vocabulary_hints",
        "words": ["Joe", "Elena Vance"],
        "identity_claim": False,
    }
    assert result["transcript"] == "Hello everyone!"


def test_watchdog_accepts_evidenced_prompt_echo_filtered_empty_wsl_result(tmp_path, monkeypatch):
    import cli.watchdog as watchdog
    from tests.unit.test_watchdog_processed_prefix_idempotent import _watchdog_cfg
    from tests.unit.test_watchdog_safety import _write_fixture_wav

    monkeypatch.setattr(watchdog, "CONTROL_AGENT_AVAILABLE", False)
    monkeypatch.setattr(watchdog, "wsl_audio_auto_enabled", lambda: False)
    monkeypatch.setattr(watchdog, "require_wsl_audio", lambda: True)
    monkeypatch.setattr(watchdog.shutil, "which", lambda name: "wsl.exe" if name == "wsl" else None)
    monkeypatch.setattr("steps.common.conda_runner.run_conda_step", lambda *_a, **_kw: {})

    def fake_unified(*_a, **_kw):
        return {
            "status": "success",
            "transcript": "",
            "segments": [],
            "wsl2_unified": True,
            "transcript_outcome": "no_intelligible_speech",
            "transcript_outcome_reason": "speech_detected_without_words",
            "transcript_meta": {
                "status": "success",
                "prompt_echo_filter": {
                    "policy": "bridge_prompt_echo_filter_v1",
                    "input_segment_count": 1,
                    "kept_segment_count": 0,
                    "filtered_segment_count": 1,
                },
            },
            "wsl_capability_outcomes": {
                "transcription": {
                    "status": "skipped",
                    "reason": "speech_detected_without_words",
                    "transcript_outcome": "no_intelligible_speech",
                }
            },
        }

    monkeypatch.setattr("steps.audio.audio_wsl2_bridge.audio_unified_wsl2", fake_unified)
    processor = watchdog.WatchdogProcessor(_watchdog_cfg(tmp_path))
    wav = tmp_path / "hum_only.wav"
    _write_fixture_wav(wav)
    assert processor.ingest_audio(wav, "run-filtered-empty") is True
