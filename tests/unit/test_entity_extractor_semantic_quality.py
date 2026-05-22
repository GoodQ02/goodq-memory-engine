import logging

from steps.video.entity_extractor import extract_entities_from_scene


def _entity_map(result):
    return {(entry["name"], entry["entity_type"]) for entry in result["entities"]}


def test_entity_extractor_prefers_typed_entities_and_filters_placeholders():
    result = extract_entities_from_scene(
        scene_data={
            "audio": {
                "transcript": "Jerry meets George in New York.",
                "ner_entities": [
                    {"name": "Jerry", "type": "PER", "source_step": "tagger"},
                    {"name": "New York", "type": "LOC", "source_step": "tagger"},
                ],
                "entity_details": [
                    {"label": "Jerry", "type": "PER", "score": 12.5, "sources": ["ner", "fallback"]},
                    {"label": "New York", "type": "LOC", "score": 11.5, "sources": ["ner"]},
                    {"label": "Can", "type": None, "score": 2.5, "sources": ["fallback"]},
                    {"label": "U", "type": "PER", "score": 11.0, "sources": ["ner"]},
                ],
                "speakers": ["SPEAKER_00"],
            },
            "keyframe": {
                "objects": [{"label": "bottle", "score": 0.95}],
                "tags": ["bottle", "Apartment"],
                "tag_details": [
                    {"label": "bottle", "score": 5.0, "sources": ["object"], "type": None},
                    {"label": "Apartment", "score": 4.5, "sources": ["place"], "type": None},
                ],
                "faces": [{"embedding": [0.1, 0.2, 0.3]}],
            },
            "start_time": 42.0,
        },
        scene_id="scene_0007",
        video_id="video_123",
    )

    entities = _entity_map(result)

    assert ("Jerry", "person") in entities
    assert ("New York", "location") in entities
    assert ("bottle", "object") in entities
    assert ("Apartment", "location") in entities
    assert ("SPEAKER_00", "person") not in entities
    assert ("FACE_0", "person") not in entities
    assert ("Can", "concept") not in entities
    assert ("U", "person") not in entities
    assert sum(1 for entry in result["entities"] if entry["name"] == "bottle") == 1


def test_entity_extractor_keeps_real_face_or_speaker_identity_when_present():
    result = extract_entities_from_scene(
        scene_data={
            "audio": {
                "speakers": [{"name": "Jerry"}],
            },
            "keyframe": {
                "faces": [{"identity": "Elaine"}],
            },
            "start_time": 0.0,
        },
        scene_id="scene_0001",
        video_id="video_123",
    )

    entities = _entity_map(result)

    assert ("Jerry", "person") in entities
    assert ("Elaine", "person") in entities


def test_entity_extractor_preserves_family_name_text_matching_without_ner():
    result = extract_entities_from_scene(
        scene_data={
            "audio": {
                "transcript": "Donna and Joey are heading out tonight.",
                "entity_details": [
                    {"label": "He", "type": None, "score": 2.5, "sources": ["fallback"]},
                ],
                "speakers": ["SPEAKER_00"],
            }
        },
        scene_id="scene_0009",
        video_id="video_123",
    )

    entities = _entity_map(result)

    assert ("Donna", "person") in entities
    assert ("Joey", "person") in entities
    assert ("SPEAKER_00", "person") not in entities
    assert ("He", "concept") not in entities


def test_entity_extractor_adds_safe_vision_place_inference():
    result = extract_entities_from_scene(
        scene_data={
            "keyframe": {
                "caption": "Jerry stands in the apartment kitchen.",
                "objects": [
                    {"label": "refrigerator", "score": 0.97},
                    {"label": "dining table", "score": 0.91},
                    {"label": "chair", "score": 0.88},
                ],
            },
            "start_time": 5.0,
        },
        scene_id="scene_0011",
        video_id="video_123",
    )

    entities = _entity_map(result)

    assert ("Apartment", "location") in entities
    assert ("Kitchen", "location") in entities
    assert ("Dining Room", "location") in entities


def test_entity_extractor_labels_no_input_pass_without_warning(caplog):
    caplog.set_level(logging.INFO, logger="steps.video.entity_extractor")

    result = extract_entities_from_scene(
        scene_data={},
        scene_id="scene_early_frame_pass",
        video_id="video_123",
    )

    assert result["entities"] == []
    assert "No entity-bearing inputs available yet" in caplog.text
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]
