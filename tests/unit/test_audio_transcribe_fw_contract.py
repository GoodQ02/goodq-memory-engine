from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from steps.audio_transcribe.step import _transcribe_chunk_fw


class _FakeWhisperModel:
    def transcribe(
        self,
        audio,
        *,
        beam_size,
        vad_filter,
        vad_parameters,
        word_timestamps,
        condition_on_previous_text,
        temperature,
        compression_ratio_threshold,
        log_prob_threshold,
        no_speech_threshold,
    ):
        assert audio == "chunk.wav"
        assert beam_size == 5
        assert vad_filter is True
        assert word_timestamps is True
        assert condition_on_previous_text is True
        assert temperature == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        assert compression_ratio_threshold == 2.4
        assert log_prob_threshold == -1.0
        assert no_speech_threshold == 0.6
        assert vad_parameters["threshold"] == 0.4

        segment = SimpleNamespace(
            start=0.0,
            end=1.0,
            text="hello world",
            words=[
                SimpleNamespace(start=0.0, end=0.5, word="hello", probability=0.95),
                SimpleNamespace(start=0.5, end=1.0, word="world", probability=0.91),
            ],
        )
        info = SimpleNamespace(language="en", duration=1.0)
        return [segment], info


def test_transcribe_chunk_fw_matches_installed_faster_whisper_contract():
    result = _transcribe_chunk_fw("chunk.wav", 12.0, _FakeWhisperModel())

    assert result is not None
    assert result["engine"] == "faster-whisper"
    assert result["language"] == "en"
    assert result["duration"] == 1.0
    assert result["transcript"] == "hello world"
    assert len(result["segments"]) == 1
    assert result["segments"][0]["start"] == 12.0
    assert result["segments"][0]["end"] == 13.0
    assert result["segments"][0]["text"] == "hello world"
    assert len(result["segments"][0]["words"]) == 2
    assert result["segments"][0]["words"][0]["start"] == 12.0
    assert result["segments"][0]["words"][1]["end"] == 13.0


@patch("steps.audio_transcribe.step.require_wsl_audio", return_value=False)
@patch("steps.audio_transcribe.step._detect_transcription_device")
@patch("steps.audio_transcribe.step._audio_duration")
@patch("steps.audio_transcribe.step._build_chunks")
@patch("steps.audio_transcribe.step._load_fw_model")
@patch("lib.model_lifecycle.ModelLifecycleManager.load")
def test_audio_transcribe_lifecycle_guard(
    mock_load_lifecycle,
    mock_load_fw,
    mock_build_chunks,
    mock_duration,
    mock_device,
    mock_require_wsl_audio
):
    from unittest.mock import patch, MagicMock
    from steps.audio_transcribe.step import audio_transcribe
    
    # Setup mocks
    mock_device.return_value = ("cpu", "probe")
    mock_duration.return_value = 5.0
    mock_build_chunks.return_value = [{"start": 0.0, "end": 5.0, "speaker": None}]
    
    mock_fw_model = MagicMock()
    mock_load_fw.return_value = mock_fw_model
    
    # Mock context manager
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = mock_fw_model
    mock_load_lifecycle.return_value = mock_ctx
    
    cfg = {
        "audio": {
            "transcribe": {
                "model": "medium",
                "chunk_seconds": 10.0,
                "use_wsl2": False
            }
        },
        "config": {
            "tools": {
                "whisper_cli": None
            }
        },
        "gpu_budget": {
            "total_vram_gb": 16.0
        },
        "huggingface_models": {
            "faster_whisper_medium": {
                "vram_estimate_gb": 1.5,
                "engines": {"CTranslate2": "yes"}
            }
        }
    }
    
    # We patch _transcribe_chunk_fw to avoid real transcription runs
    with patch("steps.audio_transcribe.step._transcribe_chunk_fw") as mock_transcribe, \
         patch("steps.audio_transcribe.step._slice_to_wav") as mock_slice:
        mock_slice.return_value = "chunk_temp.wav"
        mock_transcribe.return_value = {
            "transcript": "mock transcript",
            "segments": [{"start": 0.0, "end": 5.0, "text": "mock transcript"}]
        }
        
        # Run audio_transcribe with the path to this test file itself (guaranteed to exist)
        res = audio_transcribe({"source_path": __file__}, cfg)
        
    # Verify ModelLifecycleManager.load was called for faster_whisper_medium
    mock_load_lifecycle.assert_called_once()
    args, kwargs = mock_load_lifecycle.call_args
    assert args[0] == "faster_whisper_medium"
    assert kwargs.get("target_engine") == "CTranslate2"
    
    # Verify context manager entered and exited
    mock_ctx.__enter__.assert_called_once()
    mock_ctx.__exit__.assert_called_once()

