from __future__ import annotations

from steps.audio_speaker_merge.step import audio_speaker_merge


def test_audio_speaker_merge_uses_top_level_segments_when_meta_segments_missing():
    item = {
        "segments": [
            {"start": 0.0, "end": 2.0, "text": "Hello there."},
            {"start": 2.0, "end": 4.0, "text": "General Kenobi."},
        ],
        "diarization": [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
            {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_01"},
        ],
        "transcript_meta": {"status": "success"},
    }

    result = audio_speaker_merge(item, {})

    assert result["speaker_transcript"] == [
        {"start": 0.0, "end": 2.0, "text": "Hello there.", "speaker": "SPEAKER_00"},
        {"start": 2.0, "end": 4.0, "text": "General Kenobi.", "speaker": "SPEAKER_01"},
    ]
    assert result["transcript_meta"]["segment_count"] == 2
    assert result["transcript_meta"]["speakers"] == ["SPEAKER_00", "SPEAKER_01"]


def test_audio_speaker_merge_falls_back_to_word_timestamps():
    item = {
        "word_timestamps": [
            {"start": 5.0, "end": 7.0, "text": "I know."},
        ],
        "diarization": [
            {"start": 4.5, "end": 7.5, "speaker": "SPEAKER_02"},
        ],
        "transcript_meta": {"status": "success"},
    }

    result = audio_speaker_merge(item, {})

    assert result["speaker_transcript"] == [
        {"start": 5.0, "end": 7.0, "text": "I know.", "speaker": "SPEAKER_02"},
    ]
    assert result["transcript_meta"]["segment_count"] == 1
    assert result["transcript_meta"]["speakers"] == ["SPEAKER_02"]
