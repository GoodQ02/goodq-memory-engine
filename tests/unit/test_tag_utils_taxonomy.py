from __future__ import annotations

from steps.common.tag_utils import canonicalize_taxonomy


def test_canonicalize_taxonomy_filters_stopwords_and_merges_typed_entities():
    item = {
        "tags": ["Well", "Apartment"],
        "entities": ["I'm", "Jerry"],
        "ner_entities": [{"name": "George", "type": "PERSON"}],
        "objects": [{"label": "coffee"}],
        "time_hints": {"relative_phrases": ["tonight", "well"]},
    }

    canonicalize_taxonomy(item)

    assert item["tags"] == ["Apartment", "coffee", "tonight"]
    assert item["entities"] == ["Jerry", "George"]
    assert item["vocabulary"] == ["apartment", "coffee", "tonight", "jerry", "george"]


def test_canonicalize_taxonomy_rejects_placeholder_entity_labels():
    item = {
        "entities": ["SPEAKER_00", "FACE_1", "Jerry"],
        "ner_entities": [{"name": "SPEAKER_02", "type": "PERSON"}, {"name": "George", "type": "PERSON"}],
    }

    canonicalize_taxonomy(item)

    assert item["entities"] == ["Jerry", "George"]


def test_canonicalize_taxonomy_blocks_person_and_santa_from_tags_but_keeps_entities():
    item = {
        "tags": ["Clara Reed", "Santa Claus", "Santa", "Christmas Tree", "Chicago"],
        "entities": ["Clara Reed", "Santa Claus"],
        "ner_entities": [
            {"name": "Clara Reed", "type": "PERSON"},
            {"name": "Sam Vance", "type": "PER"},
            {"name": "Chicago", "type": "LOCATION"},
        ],
    }

    canonicalize_taxonomy(item)

    assert item["tags"] == ["Christmas Tree", "Chicago"]
    assert "Clara Reed" in item["entities"]
    assert "Sam Vance" in item["entities"]
    assert "Santa Claus" in item["entities"]
