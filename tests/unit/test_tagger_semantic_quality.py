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


def test_fallback_entities_rejects_sentence_start_scaffolding():
    text = "Do you know why we're here? To be out. Can he go? Hold on."

    entities = tagger_step._fallback_entities(text)

    assert entities == []


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


def test_tagger_promotes_concrete_caption_memory_tags(monkeypatch):
    item = {
        "caption": "a girl playing a trumpet in a room",
        "objects": [{"label": "person"}],
        "time_hints": {"explicit_dates": ["2002-12-16"], "months": ["december"]},
    }

    monkeypatch.setattr(tagger_step, "_extract_entities_transformers", lambda _text, _cfg: ([], []))

    result = tagger_step.tagger(item, {})

    assert result["tags"][:4] == ["indoor", "music", "performance", "trumpet"]
    assert "december" in result["tags"]
    assert "person" not in result["tags"]
    assert {
        (detail["label"], tuple(detail["sources"]))
        for detail in result["tag_details"]
        if detail["label"] in {"trumpet", "music", "performance"}
    } == {
        ("trumpet", ("caption",)),
        ("music", ("caption_inference",)),
        ("performance", ("caption_inference",)),
    }


def test_tagger_rejects_contextual_artifact_entities_and_fake_ner_fallback(monkeypatch):
    item = {
        "transcript": "Shirt grabs the underwear. Oh my God. This is the signal. George arrives.",
    }

    def fake_extract(_text, _cfg):
        return (
            ["Shi", "God", "Signal", "George"],
            [
                {"name": "Shi", "type": "PER", "source_step": "tagger", "source_modality": "text"},
                {"name": "God", "type": "PER", "source_step": "tagger", "source_modality": "text"},
                {"name": "Signal", "type": "PER", "source_step": "tagger", "source_modality": "text"},
                {"name": "George", "type": "PERSON", "source_step": "tagger", "source_modality": "text"},
            ],
        )

    monkeypatch.setattr(tagger_step, "_extract_entities_transformers", fake_extract)
    monkeypatch.setattr(tagger_step, "_fallback_entities", lambda _text: ["George"])

    result = tagger_step.tagger(item, {})

    assert result["entities"] == ["George"]
    assert result["entity_details"] == [
        {"label": "George", "score": 12.5, "sources": ["fallback", "ner"], "type": "PERSON"}
    ]


def test_tagger_rejects_god_bless_and_justin_case_artifacts(monkeypatch):
    item = {
        "transcript": "God bless! Devil you! You're a backup. You're a second line. A Justin Case. George arrives.",
    }

    def fake_extract(_text, _cfg):
        return (
            ["God", "Justin Case", "George"],
            [
                {"name": "God", "type": "PER", "source_step": "tagger", "source_modality": "text"},
                {"name": "Justin Case", "type": "PER", "source_step": "tagger", "source_modality": "text"},
                {"name": "George", "type": "PERSON", "source_step": "tagger", "source_modality": "text"},
            ],
        )

    monkeypatch.setattr(tagger_step, "_extract_entities_transformers", fake_extract)
    monkeypatch.setattr(tagger_step, "_fallback_entities", lambda _text: ["George"])

    result = tagger_step.tagger(item, {})

    assert result["entities"] == ["George"]
    assert result["entity_details"] == [
        {"label": "George", "score": 12.5, "sources": ["fallback", "ner"], "type": "PERSON"}
    ]


def test_tagger_rejects_batman_and_case_common_noun_artifacts(monkeypatch):
    item = {
        "transcript": "It's not like Batman. We are going to crack this case. Case closed. Sony is here.",
    }

    def fake_extract(_text, _cfg):
        return (
            ["Batman", "Case", "Sony"],
            [
                {"name": "Batman", "type": "PER", "source_step": "tagger", "source_modality": "text"},
                {"name": "Case", "type": "PER", "source_step": "tagger", "source_modality": "text"},
                {"name": "Sony", "type": "ORG", "source_step": "tagger", "source_modality": "text"},
            ],
        )

    monkeypatch.setattr(tagger_step, "_extract_entities_transformers", fake_extract)
    monkeypatch.setattr(tagger_step, "_fallback_entities", lambda _text: ["Sony"])

    result = tagger_step.tagger(item, {})

    assert result["entities"] == ["Sony"]
    assert result["entity_details"] == [
        {"label": "Sony", "score": 10.5, "sources": ["fallback", "ner"], "type": "ORG"}
    ]


def test_tagger_boosts_repeated_names_over_one_off_entities(monkeypatch):
    item = {
        "transcript": "George arrives. George sits down. Bill waves once.",
    }

    def fake_extract(_text, _cfg):
        return (
            ["George", "Bill"],
            [
                {"name": "George", "type": "PERSON", "source_step": "tagger", "source_modality": "text"},
                {"name": "Bill", "type": "PERSON", "source_step": "tagger", "source_modality": "text"},
            ],
        )

    monkeypatch.setattr(tagger_step, "_extract_entities_transformers", fake_extract)
    monkeypatch.setattr(tagger_step, "_fallback_entities", lambda _text: ["George", "Bill"])

    result = tagger_step.tagger(item, {})

    assert result["entities"][:2] == ["George", "Bill"]
    assert result["entity_details"][0]["label"] == "George"
    assert result["entity_details"][0]["score"] > result["entity_details"][1]["score"]


def test_tagger_collapses_unstable_compound_person_alias_to_head_name(monkeypatch):
    item = {
        "transcript": "And I'm Jerry Cougar, Mellon Camp. Anyway, we have a problem here.",
    }

    def fake_extract(_text, _cfg):
        return (
            ["Jerry Cougar", "Mellon Camp"],
            [
                {"name": "Jerry Cougar", "type": "PER", "source_step": "tagger", "source_modality": "text"},
                {"name": "Mellon Camp", "type": "ORG", "source_step": "tagger", "source_modality": "text"},
            ],
        )

    monkeypatch.setattr(tagger_step, "_extract_entities_transformers", fake_extract)
    monkeypatch.setattr(tagger_step, "_fallback_entities", lambda _text: ["Jerry Cougar"])

    result = tagger_step.tagger(item, {})

    assert "Jerry Cougar" not in result["entities"]
    assert "Jerry" in result["entities"]
    assert "Mellon" not in result["entities"]
    assert [entry["name"] for entry in result["ner_entities"]] == ["Jerry", "Mellon Camp"]


def test_tagger_collapses_three_word_alias_to_stable_head_name(monkeypatch):
    item = {
        "transcript": "Oh, really? Elaine Marie Venice. What? No, it's not a big deal.",
    }

    def fake_extract(_text, _cfg):
        return (
            ["Elaine Marie Venice"],
            [
                {"name": "Elaine Marie Venice", "type": "PER", "source_step": "tagger", "source_modality": "text"},
            ],
        )

    monkeypatch.setattr(tagger_step, "_extract_entities_transformers", fake_extract)
    monkeypatch.setattr(tagger_step, "_fallback_entities", lambda _text: ["Elaine Marie Venice"])

    result = tagger_step.tagger(item, {})

    assert result["entities"] == ["Elaine"]
    assert result["ner_entities"] == [
        {"name": "Elaine", "type": "PER", "source_step": "tagger", "source_modality": "text"}
    ]


def test_tagger_preserves_repeated_compound_person_name_with_recurrence(monkeypatch):
    item = {
        "transcript": "George Costanza walks in. George Costanza sits down. Jerry listens.",
    }

    def fake_extract(_text, _cfg):
        return (
            ["George Costanza", "Jerry"],
            [
                {"name": "George Costanza", "type": "PER", "source_step": "tagger", "source_modality": "text"},
                {"name": "Jerry", "type": "PER", "source_step": "tagger", "source_modality": "text"},
            ],
        )

    monkeypatch.setattr(tagger_step, "_extract_entities_transformers", fake_extract)
    monkeypatch.setattr(tagger_step, "_fallback_entities", lambda _text: ["George Costanza", "Jerry"])

    result = tagger_step.tagger(item, {})

    assert "George Costanza" in result["entities"]
    assert "George" not in [entry["name"] for entry in result["ner_entities"]]
    assert result["ner_entities"][0]["name"] == "George Costanza"
