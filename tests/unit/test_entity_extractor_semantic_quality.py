import logging

import pytest

from steps.video.entity_extractor import extract_entities_from_scene


@pytest.mark.parametrize("text,names", [
    ("A quiet moment; predominantly green surroundings.", set()),
    ("Arturo talks about the camera.", set()),
    ("Art, look at Avery's camera.", {"Art", "Avery"}),
    ("ART and Avery are outside.", {"Art", "Avery"}),
])
def test_family_name_matching_requires_complete_words(text, names):
    result = extract_entities_from_scene(
        scene_data={"audio": {"transcript": text}},
        scene_id="names",
        video_id="source",
        config={"family_names": ["art", "avery"]},
    )
    assert {e["name"] for e in result["entities"] if e["entity_type"] == "person"} == names


@pytest.mark.parametrize("detection,expected", [
    ({"score": 0.3857478201389313}, 0.3857478201389313),
    ({"score": 0.0}, 0.0),
    ({"confidence": 0.72}, 0.72),
    ({"score": 0.38, "confidence": 0.5}, 0.38),
])
def test_object_detector_score_survives_scene_entity_extraction(detection, expected):
    result = extract_entities_from_scene(
        scene_data={"keyframe": {"objects": [{"label": "elephant", **detection}]}},
        scene_id="object-score-scene", video_id="object-score-video",
    )
    entity = next(row for row in result["entities"] if row["name"] == "elephant")
    assert entity["confidence"] == expected
    assert entity["properties"]["detection"] == {"label": "elephant", **detection}


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
                "transcript": "Avery and Casey are heading out tonight.",
                "entity_details": [
                    {"label": "He", "type": None, "score": 2.5, "sources": ["fallback"]},
                ],
                "speakers": ["SPEAKER_00"],
            }
        },
        scene_id="scene_0009",
        video_id="video_123",
        config={"family_names": ["avery", "casey"]},
    )

    entities = _entity_map(result)

    assert ("Avery", "person") in entities
    assert ("Casey", "person") in entities
    assert ("SPEAKER_00", "person") not in entities
    assert ("He", "concept") not in entities


def test_entity_extractor_filters_ambiguous_person_labels_from_structured_ner():
    result = extract_entities_from_scene(
        scene_data={
            "audio": {
                "transcript": "Mercury appears in the narration as an object, not a person.",
                "ner_entities": [
                    {"name": "Mercury", "type": "MISC", "source_step": "tagger"},
                    {"name": "Mercury", "type": "PER", "source_step": "tagger"},
                ],
                "entity_details": [
                    {"label": "Mercury", "type": "MISC", "score": 8.0, "sources": ["ner"]},
                    {"label": "Mercury", "type": "PER", "score": 7.5, "sources": ["ner"]},
                ],
            }
        },
        scene_id="scene_0010",
        video_id="video_123",
    )

    entities = _entity_map(result)

    assert ("Mercury", "concept") in entities
    assert ("Mercury", "person") not in entities


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


def test_entity_extractor_preserves_good_and_bad_object_fixtures_as_unconfirmed_candidates():
    # Scene 37 good fixture: low-confidence valid detections with multiple bounding boxes
    result37 = extract_entities_from_scene(
        scene_data={
            "keyframe": {
                "caption": "a man and a woman sitting at a table in a restaurant",
                "objects": [
                    {"label": "cup", "score": 0.4713, "bbox": [100, 120, 140, 180], "timestamp": 12.5},
                    {"label": "cup", "score": 0.4016, "bbox": [210, 130, 245, 185], "timestamp": 12.5},
                    {"label": "bottle", "score": 0.4169, "bbox": [310, 90, 340, 190], "timestamp": 12.5},
                    {"label": "bottle", "score": 0.3889, "bbox": [360, 95, 390, 192], "timestamp": 12.5},
                    {"label": "dining table", "score": 0.5094, "bbox": [20, 160, 620, 350], "timestamp": 12.5},
                    {"label": "dining table", "score": 0.4304, "bbox": [30, 165, 610, 355], "timestamp": 12.5},
                ],
            },
            "start_time": 10.0,
        },
        scene_id="scene_0037",
        video_id="video_123",
    )
    entities37 = {(entry["name"], entry["entity_type"]): entry for entry in result37["entities"]}
    cup = entities37[("cup", "object")]
    assert cup["confidence"] == 0.4713
    assert cup["occurrences"] == 2
    assert cup["timestamps"] == [12.5]
    assert cup["properties"]["score_status"] == "observed"
    assert cup["properties"]["verification_status"] == "candidate_unconfirmed"
    assert cup["properties"]["establishes_visible_presence"] is False
    assert len(cup["properties"]["bboxes"]) == 2
    assert len(cup["properties"]["detections"]) == 2

    bottle = entities37[("bottle", "object")]
    assert bottle["confidence"] == 0.4169
    assert bottle["occurrences"] == 2
    assert bottle["properties"]["verification_status"] == "candidate_unconfirmed"

    # Scene 36 & 39 bad fixtures + missing detector score
    result_bad = extract_entities_from_scene(
        scene_data={
            "keyframe": {
                "caption": "a man and a woman sitting at a table",
                "objects": [
                    {"label": "sandwich", "score": 0.377349, "bbox": [10, 20, 50, 60]},
                    {"label": "dog", "score": 0.370045, "bbox": [70, 80, 110, 150]},
                    {"label": "chair"},
                ],
            },
            "start_time": 20.0,
        },
        scene_id="scene_0036",
        video_id="video_123",
    )
    entities_bad = {(entry["name"], entry["entity_type"]): entry for entry in result_bad["entities"]}
    sandwich = entities_bad[("sandwich", "object")]
    assert sandwich["confidence"] == 0.377349
    assert sandwich["properties"]["score_status"] == "observed"
    assert sandwich["properties"]["verification_status"] == "candidate_unconfirmed"
    assert sandwich["properties"]["establishes_visible_presence"] is False

    dog = entities_bad[("dog", "object")]
    assert dog["confidence"] == 0.370045
    assert dog["properties"]["verification_status"] == "candidate_unconfirmed"

    chair = entities_bad[("chair", "object")]
    assert chair["confidence"] is None
    assert chair["properties"]["score_status"] == "unknown"
    assert chair["properties"]["verification_status"] == "candidate_unconfirmed"


def test_entity_extractor_distinguishes_spoken_object_mention_from_visible_presence():
    result = extract_entities_from_scene(
        scene_data={
            "keyframe": {
                "caption": "two men talking in a hallway",
                "objects": [{"label": "person", "score": 0.99}],
            },
            "audio": {
                "transcript": "Did you leave the sandwich in the taxi?",
                "ner_entities": [
                    {"name": "sandwich", "type": "OBJECT", "confidence": 0.85, "source_step": "tagger"},
                ],
            },
            "start_time": 30.0,
        },
        scene_id="scene_spoken_obj",
        video_id="video_123",
    )
    entities = {(entry["name"], entry["entity_type"]): entry for entry in result["entities"]}
    sandwich = entities[("sandwich", "object")]
    assert "audio" in sandwich["source_modalities"]
    assert "vision" not in sandwich["source_modalities"]
    assert sandwich["properties"]["mention_scope"] == "spoken_mention"
    assert sandwich["properties"]["verification_status"] == "mentioned_not_visibly_confirmed"
    assert sandwich["properties"]["establishes_visible_presence"] is False


def test_entity_extractor_mixed_modality_keeps_detector_score_separate_from_spoken_mention_confidence():
    result = extract_entities_from_scene(
        scene_data={
            "keyframe": {
                "caption": "a man and a woman sitting at a table",
                "objects": [
                    {"label": "sandwich", "score": 0.377349, "bbox": [10, 20, 50, 60], "timestamp": 22.5},
                    {"label": "cup", "bbox": [100, 120, 140, 180], "timestamp": 23.0},
                ],
            },
            "audio": {
                "start_time": 20.0,
                "transcript": "Pass the sandwich and the cup.",
                "ner_entities": [
                    {
                        "name": "sandwich",
                        "type": "OBJECT",
                        "confidence": 0.92,
                        "source_step": "tagger",
                    },
                    {
                        "name": "cup",
                        "type": "OBJECT",
                        "confidence": 0.92,
                        "source_step": "tagger",
                    },
                ],
            },
            "start_time": 20.0,
        },
        scene_id="scene_mixed_modality",
        video_id="video_123",
    )
    entities = {(entry["name"], entry["entity_type"]): entry for entry in result["entities"]}

    sandwich = entities[("sandwich", "object")]
    assert sandwich["confidence"] == 0.377349
    assert sandwich["properties"]["detector_score"] == 0.377349
    assert sandwich["properties"]["raw_score"] == 0.377349
    assert sandwich["properties"]["score_status"] == "observed"
    assert sandwich["properties"]["mention_confidence"] == 0.92
    assert sandwich["properties"]["verification_status"] == "candidate_unconfirmed"
    assert sandwich["properties"]["establishes_visible_presence"] is False
    assert sandwich["properties"]["bboxes"] == [[10, 20, 50, 60]]
    assert sandwich["properties"]["detections"] == [
        {"label": "sandwich", "score": 0.377349, "bbox": [10, 20, 50, 60], "timestamp": 22.5}
    ]
    assert sandwich["properties"]["detector_timestamps"] == [22.5]
    assert sandwich["properties"]["mention_timestamps"] == [20.0]
    assert sandwich["timestamps"] == [20.0, 22.5]
    assert "audio" in sandwich["source_modalities"]
    assert "vision" in sandwich["source_modalities"]

    cup = entities[("cup", "object")]
    assert cup["confidence"] is None
    assert cup["properties"]["detector_score"] is None
    assert cup["properties"]["raw_score"] is None
    assert cup["properties"]["score_status"] == "unknown"
    assert cup["properties"]["mention_confidence"] == 0.92
    assert cup["properties"]["verification_status"] == "candidate_unconfirmed"
    assert cup["properties"]["establishes_visible_presence"] is False
    assert cup["properties"]["bboxes"] == [[100, 120, 140, 180]]
    assert cup["properties"]["detections"] == [
        {"label": "cup", "bbox": [100, 120, 140, 180], "timestamp": 23.0}
    ]
    assert cup["properties"]["detector_timestamps"] == [23.0]
    assert cup["properties"]["mention_timestamps"] == [20.0]
    assert cup["timestamps"] == [20.0, 23.0]
    assert "audio" in cup["source_modalities"]
    assert "vision" in cup["source_modalities"]


def test_entity_extractor_ignores_hedged_caption_place_clauses_while_preserving_unhedged_places():
    hedged = extract_entities_from_scene(
        scene_data={
            "keyframe": {
                "caption": (
                    "Two men stand indoors in a warmly lit room. "
                    "The setting appears to be a cozy indoor environment, possibly a home office or living room."
                ),
                "objects": [{"label": "person", "score": 0.95}],
            },
            "start_time": 0.0,
        },
        scene_id="scene_hedged_place",
        video_id="video_123",
    )
    hedged_locations = {
        entry["name"]
        for entry in hedged["entities"]
        if entry["entity_type"] == "location"
    }
    assert "Office" not in hedged_locations
    assert "Living Room" not in hedged_locations

    unhedged = extract_entities_from_scene(
        scene_data={
            "keyframe": {
                "caption": "A man is sitting indoors in a bathroom setting with a sink visible.",
                "objects": [{"label": "person", "score": 0.95}, {"label": "sink", "score": 0.88}],
            },
            "start_time": 4.0,
        },
        scene_id="scene_unhedged_place",
        video_id="video_123",
    )
    unhedged_locations = {
        entry["name"]
        for entry in unhedged["entities"]
        if entry["entity_type"] == "location"
    }
    assert "Bathroom" in unhedged_locations

