from __future__ import annotations

from steps.common.scene_summarizer import generate_scene_summary_template


def test_scene_summary_prefers_clean_semantic_lists():
    scene_meta = {
        "index": 2,
        "start": 10.0,
        "end": 18.0,
        "caption": "Jerry stands in an apartment kitchen.",
        "tags": ["Well", "Apartment"],
        "tag_details": [{"label": "coffee", "score": 5.0}, {"label": "Apartment", "score": 4.5}],
        "entities": ["I'm", "Jerry"],
        "ner_entities": [
            {"name": "Jerry", "type": "PERSON"},
            {"name": "Vermont", "type": "LOCATION"},
        ],
    }

    summary = generate_scene_summary_template(scene_meta)

    assert "Tags: coffee, Apartment" in summary
    assert "Entities: Jerry, Vermont" in summary
    assert "Well" not in summary
    assert "I'm" not in summary


def test_scene_summary_suppresses_placeholder_speaker_ids():
    scene_meta = {
        "index": 3,
        "start": 18.0,
        "end": 26.0,
        "caption": "George talks to Jerry in the apartment.",
        "speaker_transcript": [
            {"speaker": "SPEAKER_00", "text": "Hello Jerry."},
            {"speaker": "SPEAKER_01", "text": "Hi George."},
        ],
    }

    summary = generate_scene_summary_template(scene_meta)

    assert "SPEAKER_00" not in summary
    assert "SPEAKER_01" not in summary
    assert "2 anonymous speakers" in summary


def test_scene_summary_keeps_named_speakers_and_collapses_anonymous_suffix():
    scene_meta = {
        "index": 4,
        "start": 26.0,
        "end": 35.0,
        "caption": "Jerry and an unseen caller speak on the phone.",
        "speakers": [
            {"name": "Jerry"},
            {"speaker": "SPEAKER_00"},
        ],
    }

    summary = generate_scene_summary_template(scene_meta)

    assert "Speakers: Jerry + anonymous speaker" in summary
    assert "SPEAKER_00" not in summary


def test_scene_summary_reads_modern_nested_keyframe_and_audio_fields():
    scene_meta = {
        "index": 5,
        "start": 35.0,
        "end": 47.0,
        "keyframe": {
            "caption": "Jerry and George sit in a diner booth.",
            "objects": [{"label": "person"}, {"label": "table"}],
            "tags": ["Diner", "Conversation"],
            "entities": ["Jerry"],
        },
        "audio": {
            "transcript": "Jerry tells George about the stock tip.",
            "speaker_transcript": [
                {"speaker": "Jerry", "text": "I got a stock tip."},
                {"speaker": "SPEAKER_01", "text": "From who?"},
            ],
            "sentiment": {"label": "positive", "score": 0.91},
            "emotion": "excited",
            "emotion_scores": {"excited": 0.82, "neutral": 0.18},
            "tags": ["finance"],
            "entities": ["George"],
        },
        "visible_face_count": 2,
    }

    summary = generate_scene_summary_template(scene_meta)

    assert "Visual: Jerry and George sit in a diner booth." in summary
    assert "Objects: person, table" in summary
    assert 'Transcript: "Jerry tells George about the stock tip."' in summary
    assert "Faces detected: 2" in summary
    assert "Speakers: Jerry + anonymous speaker" in summary
    assert "Emotions: excited (82%), neutral (18%)" in summary
    assert "Sentiment: positive (91%)" in summary
    assert "Tags: Diner, Conversation, finance" in summary
    assert "Entities: Jerry, George" in summary


def test_scene_summary_uses_nested_speaker_ids_when_only_audio_shape_is_present():
    scene_meta = {
        "index": 6,
        "start": 47.0,
        "end": 54.0,
        "audio": {
            "speaker_ids": ["SPEAKER_00", "SPEAKER_01"],
            "transcript": "Hello there.",
        },
    }

    summary = generate_scene_summary_template(scene_meta)

    assert "2 anonymous speakers" in summary
    assert "SPEAKER_00" not in summary
    assert "SPEAKER_01" not in summary
