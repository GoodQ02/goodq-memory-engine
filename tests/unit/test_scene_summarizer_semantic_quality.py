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
