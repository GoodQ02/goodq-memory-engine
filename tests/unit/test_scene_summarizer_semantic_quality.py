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
