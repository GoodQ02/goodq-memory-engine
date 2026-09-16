from __future__ import annotations


def test_audio_unified_wsl2_success_preserves_bridge_runtime_probe(monkeypatch):
    from steps.audio import audio_wsl2_bridge

    runtime_probe = {
        "torch_lane_status": "differs_from_expected",
        "torchcodec_ready": False,
        "runtime_warnings": ["torchcodec_decoder_unavailable"],
    }

    class _Bridge:
        def process_audio(self, audio_path, timeout=None, audio_duration=None):  # noqa: ANN001
            return {
                "status": "success",
                "transcription": "hello there",
                "transcription_status": "success",
                "device": "cuda",
                "diarization_status": "success",
                "emotion_status": "success",
                "speaker_count": 1,
                "bridge_runtime_probe": runtime_probe,
            }

    monkeypatch.setattr(audio_wsl2_bridge, "WSL2AudioBridge", _Bridge)

    result = audio_wsl2_bridge.audio_unified_wsl2("scene_0001.wav", duration=12.0)

    assert result["status"] == "success"
    assert result["bridge_runtime_probe"] == runtime_probe


def test_audio_unified_wsl2_success_preserves_wav2vec_enrichment_fields(monkeypatch):
    from steps.audio import audio_wsl2_bridge

    class _Bridge:
        def process_audio(self, audio_path, timeout=None, audio_duration=None):  # noqa: ANN001
            return {
                "status": "success",
                "transcription": "hello there",
                "transcription_status": "success",
                "device": "cuda",
                "diarization_status": "success",
                "emotion": "calm",
                "emotion_scores": {"calm": 0.9},
                "emotion_status": "success",
                "emotion_note": "wav2vec_ready",
                "embeddings": [0.1, 0.2],
                "embedding_dim": 2,
                "embeddings_status": "success",
                "embeddings_note": "wav2vec_ready",
                "speaker_voice_signatures": [{"speaker": "SPEAKER_00", "embedding": [1.0]}],
                "speaker_voice_signature_meta": {"status": "ok", "emitted": 1},
            }

    monkeypatch.setattr(audio_wsl2_bridge, "WSL2AudioBridge", _Bridge)

    result = audio_wsl2_bridge.audio_unified_wsl2("scene_0001.wav", duration=12.0)

    assert result["emotion_status"] == "success"
    assert result["emotion_note"] == "wav2vec_ready"
    assert result["embeddings_status"] == "success"
    assert result["embeddings_note"] == "wav2vec_ready"
    assert result["speaker_voice_signature_meta"]["status"] == "ok"


def test_audio_unified_wsl2_exposes_five_independent_capability_outcomes(monkeypatch):
    from steps.audio import audio_wsl2_bridge

    class _Bridge:
        def process_audio(self, audio_path, timeout=None, audio_duration=None):  # noqa: ANN001
            return {
                "status": "success",
                "transcription": "hello there",
                "transcription_status": "success",
                "diarization": [
                    {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}
                ],
                "diarization_status": "success",
                "emotion": "calm",
                "emotion_scores": {"calm": 0.9},
                "emotion_status": "success",
                "embeddings": [0.1, 0.2],
                "embedding_dim": 2,
                "embeddings_status": "success",
            }

    monkeypatch.setattr(audio_wsl2_bridge, "WSL2AudioBridge", _Bridge)

    result = audio_wsl2_bridge.audio_unified_wsl2("scene_0001.wav", duration=12.0)

    outcomes = result["wsl_capability_outcomes"]
    assert set(outcomes) == {
        "transcription",
        "diarization",
        "acoustic_emotion",
        "wav2vec2",
        "clap_handoff",
    }
    assert all(outcomes[name]["status"] == "ok" for name in outcomes)
    assert outcomes["wav2vec2"]["embedding_dim"] == 2
    assert outcomes["clap_handoff"]["reason"] == "canonical_clap_required"
    assert outcomes["clap_handoff"]["required_step"] == "audio_embed_clap"


def test_audio_unified_wsl2_marks_missing_wav2vec_output_as_error(monkeypatch):
    from steps.audio import audio_wsl2_bridge

    class _Bridge:
        def process_audio(self, audio_path, timeout=None, audio_duration=None):  # noqa: ANN001
            return {
                "status": "success",
                "transcription": "hello there",
                "transcription_status": "success",
                "diarization": [],
                "diarization_status": "completed_no_speakers",
                "emotion": "calm",
                "emotion_scores": {"calm": 0.9},
                "emotion_status": "success",
                "embeddings": [],
                "embedding_dim": 768,
                "embeddings_status": "success",
            }

    monkeypatch.setattr(audio_wsl2_bridge, "WSL2AudioBridge", _Bridge)

    result = audio_wsl2_bridge.audio_unified_wsl2("scene_0001.wav", duration=12.0)

    assert result["status"] == "success"
    assert result["wsl_capability_outcomes"]["diarization"] == {
        "status": "not_applicable",
        "reason": "content_appropriate_empty",
        "raw_status": "completed_no_speakers",
    }
    assert result["wsl_capability_outcomes"]["wav2vec2"]["status"] == "error"
    assert (
        result["wsl_capability_outcomes"]["wav2vec2"]["reason"]
        == "successful_status_without_embedding"
    )


def test_audio_unified_wsl2_error_preserves_bridge_runtime_probe(monkeypatch):
    from steps.audio import audio_wsl2_bridge

    runtime_probe = {
        "torch_lane_status": "differs_from_expected",
        "torchcodec_ready": False,
        "runtime_warnings": ["torchcodec_decoder_unavailable"],
    }

    class _Bridge:
        def process_audio(self, audio_path, timeout=None, audio_duration=None):  # noqa: ANN001
            return {
                "status": "error",
                "error": "WSL audio processor failed",
                "bridge_error_reason": "wsl_subprocess_nonzero",
                "bridge_error_details": {"processor_diarization_status": "error"},
                "bridge_runtime_probe": runtime_probe,
            }

    monkeypatch.setattr(audio_wsl2_bridge, "WSL2AudioBridge", _Bridge)

    result = audio_wsl2_bridge.audio_unified_wsl2("scene_0001.wav", duration=12.0)

    assert result["status"] == "error"
    assert result["bridge_error_reason"] == "wsl_subprocess_nonzero"
    assert result["bridge_runtime_probe"] == runtime_probe
    assert result["wsl_capability_outcomes"]["clap_handoff"]["status"] == "error"
    assert (
        result["wsl_capability_outcomes"]["clap_handoff"]["reason"]
        == "wsl_composite_failed_before_clap_handoff"
    )
