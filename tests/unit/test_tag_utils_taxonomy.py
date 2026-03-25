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
