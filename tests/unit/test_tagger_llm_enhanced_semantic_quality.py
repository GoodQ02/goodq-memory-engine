from __future__ import annotations

from steps.tagger import step_llm_enhanced as llm_tagger


def test_llm_enhanced_fallback_rejects_sentence_start_scaffolding():
    text = "Do you know why we're here? To be out. Can he go? Hold on."

    entities = llm_tagger._fallback_entities(text)

    assert entities == []


def test_llm_enhanced_sanitizes_llm_placeholder_entities_and_tags():
    parsed = {
        "tags": ["Well", "Apartment", "Apartment"],
        "entities": ["SPEAKER_00", "George", "George"],
        "themes": ["social gathering", "OK"],
        "keywords": ["FACE_1", "coffee", "coffee"],
    }

    assert llm_tagger._sanitize_llm_values(parsed["tags"], kind="tag", limit=5) == ["Apartment"]
    assert llm_tagger._sanitize_llm_values(parsed["entities"], kind="entity", limit=20) == ["George"]
    assert llm_tagger._sanitize_llm_values(parsed["themes"], kind="tag", limit=10) == ["social gathering"]
    assert llm_tagger._sanitize_llm_values(parsed["keywords"], kind="tag", limit=15) == ["coffee"]
