from __future__ import annotations

from steps.tagger import step as tagger_step


def test_gather_text_fuses_transcript_ocr_caption_and_speaker_text():
    item = {
        "transcript": "Jerry is here.",
        "ocr_text": "Monk's Cafe",
        "caption": "A man inside an apartment.",
        "speaker_transcript": [{"speaker": "SPEAKER_00", "text": "George walks in."}],
    }

    text = tagger_step._gather_text(item)

    assert "Jerry is here." in text
    assert "Monk's Cafe" in text
    assert "A man inside an apartment." in text
    assert "George walks in." in text
    assert "\n" in text


def test_fallback_entities_uses_phrases_and_filters_fillers():
    text = "Well, Jerry meets George in New York while I'm waiting."

    entities = tagger_step._fallback_entities(text)

    assert entities == ["Jerry", "George", "New York"]


def test_tagger_filters_noisy_entities_before_persisting(monkeypatch):
    item = {
        "transcript": "I'm meeting Jerry in Vermont tonight.",
        "caption": "A man standing in an apartment kitchen.",
        "objects": [{"label": "kitchen"}, {"label": "coffee"}],
        "place_tags": ["Apartment"],
        "time_hints": {"relative_phrases": ["tonight"]},
    }

    def fake_extract(_text, _cfg):
        return (
            ["I'm", "Jerry", "Vermont", "Well"],
            [
                {"name": "Jerry", "type": "PERSON", "source_step": "tagger", "source_modality": "text"},
                {"name": "Vermont", "type": "LOCATION", "source_step": "tagger", "source_modality": "text"},
            ],
        )

    monkeypatch.setattr(tagger_step, "_extract_entities_transformers", fake_extract)
    result = tagger_step.tagger(item, {})

    assert result["entities"] == ["Jerry", "Vermont"]
    assert result["tags"][:4] == ["Vermont", "coffee", "kitchen", "Apartment"]
    assert "Jerry" not in result["tags"]
    assert [entry["name"] for entry in result["ner_entities"]] == ["Jerry", "Vermont"]
    assert result["tag_details"][0]["sources"] == ["typed_entity"]
    assert result["entity_details"][0]["label"] == "Jerry"
    assert result["entity_details"][0]["type"] == "PERSON"
