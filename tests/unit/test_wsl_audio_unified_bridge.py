from __future__ import annotations


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
