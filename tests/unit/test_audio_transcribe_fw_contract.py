from __future__ import annotations

from types import SimpleNamespace

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
