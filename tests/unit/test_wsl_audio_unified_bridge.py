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
