"""Room evidence must survive the frame producer and temporal consumer."""

import json

import pytest

from cli.run_ingestion import _persist_frame_semantic_entities
from steps.video.cross_modal_harmonizer import run_cross_modal_harmonization
from steps.video.entity_extractor import extract_entities_from_scene


@pytest.mark.parametrize(
    "caption,labels,expected",
    [
        ("A woman sitting on a toilet in a bathroom.", ["sink", "laptop"], ["Bathroom"]),
        ("A man standing in a bathroom.", [], ["Bathroom"]),
        ("A BATHROOM with a mirror.", ["sink"], ["Bathroom"]),
        ("A person washing their hands.", ["sink"], []),
        ("", ["sink", "bottle"], []),
        ("A bathroomware display.", ["sink"], []),
        ("", ["toilet"], []),
        ("A person in a kitchen.", ["sink"], ["Kitchen"]),
        ("", ["refrigerator"], ["Kitchen"]),
        ("", ["oven", "sink"], ["Kitchen"]),
        ("A person in a bedroom.", ["sink"], ["Bedroom"]),
        ("Two women walking down the street at night.", [], ["Street"]),
        # A split scene may legitimately contain both; don't invent a winner.
        ("A bathroom and a kitchen in split screen.", ["sink"], ["Bathroom", "Kitchen"]),
    ],
)
def test_frame_producer_keeps_supported_room_evidence(caption, labels, expected):
    item = {
        "caption": caption,
        "objects": [{"label": label, "score": 0.8} for label in labels],
        "timestamp": 12.0,
    }
    _persist_frame_semantic_entities(item, scene_id="room", video_id="rooms")

    assert sorted(item.get("locations", [])) == sorted(expected)
    assert item["vision_semantic_meta"]["location_count"] == len(expected)
    # Ambiguous objects are still retained as detector evidence.
    assert [obj["label"] for obj in item["objects"]] == labels


def test_sampled_bathroom_caption_retains_its_provenance():
    caption = "A bathroom with green tiles and a red laptop."
    result = extract_entities_from_scene(
        {"keyframe": {
            "caption": "A person with a laptop.",
            "caption_observations": [{"caption": caption}],
            "objects": [{"label": "sink", "score": 0.82}],
        }},
        scene_id="sampled-room", video_id="rooms",
    )
    locations = [row for row in result["entities"] if row["entity_type"] == "location"]
    assert len(locations) == 1
    assert locations[0]["name"] == "Bathroom"
    assert locations[0]["source_steps"] == ["image_caption"]
    assert locations[0]["properties"]["matched_text"] == caption


@pytest.mark.parametrize("detection", [
    {"score": 0.3751038908958435},
    {"confidence": 0.4},
    {"score": 0.0},
    {},
    {"score": None, "confidence": 0.99},
    {"score": True},
    {"score": float("nan")},
    {"score": float("inf")},
])
def test_weak_or_unknown_detector_evidence_cannot_assert_another_room(detection):
    obj = {"label": "refrigerator", **detection}
    frame = {"caption": "A person in a bathroom.", "objects": [obj]}
    _persist_frame_semantic_entities(frame, scene_id="weak-room", video_id="rooms")
    assert frame["locations"] == ["Bathroom"]
    assert frame["objects"] == [obj]


@pytest.mark.parametrize("labels,expected", [
    ([("refrigerator", 0.77)], []),
    ([("refrigerator", 0.78)], ["Kitchen"]),
    ([("refrigerator", 0.93)], ["Kitchen"]),
    ([("refrigerator", 0.3), ("refrigerator", 0.93)], ["Kitchen"]),
    ([("dining table", 0.95), ("chair", 0.4)], []),
    ([("dining table", 0.95), ("chair", 0.8)], ["Dining Room"]),
])
def test_object_room_inference_cannot_exceed_its_weakest_required_evidence(labels, expected):
    frame = {"objects": [{"label": label, "score": score} for label, score in labels]}
    _persist_frame_semantic_entities(frame, scene_id="object-room", video_id="rooms")
    assert frame.get("locations", []) == expected


def test_bathroom_survives_persisted_temporal_projection_without_dialogue_leak(tmp_path):
    processing = tmp_path / "processing"
    target = processing / "rooms"
    manifest = target / "video" / "scene_manifest.json"
    manifest.parent.mkdir(parents=True)
    frame = {
        "caption": "A person in a bathroom.",
        "objects": [{"label": "sink", "score": 0.81}],
        "timestamp": 3.0,
    }
    _persist_frame_semantic_entities(frame, scene_id="room", video_id="rooms")
    manifest.write_text(json.dumps({
        "video_id": "rooms", "phase5_complete": True, "phase6_complete": True,
        "scenes": [{
            "scene_id": "room", "index": 0, "start": 0.0, "end": 6.0,
            "duration": 6.0, "confidence": 0.9, "content_state": "signal",
            "keyframe": frame,
            "audio": {"transcript": "I left it in the kitchen.", "ner_entities": [
                {"name": "Kitchen", "type": "LOC", "source_step": "tagger"},
            ]},
        }],
    }), encoding="utf-8")
    run_cross_modal_harmonization(
        {"id": "rooms", "source_path": str(tmp_path / "rooms.mp4"),
         "processing_dir": str(target), "scene_manifest_path": str(manifest)},
        {"paths": {"processing": str(processing)}},
    )
    segment = json.loads((target / "temporal_index.json").read_text(encoding="utf-8"))["segments"][0]
    assert segment["scene_locations"] == [{"text": "Bathroom", "type": "LOCATION"}]
    assert {"text": "Kitchen", "type": "LOCATION"} in segment["dialogue_mentioned_entities"]
    assert {"text": "Kitchen", "type": "LOCATION"} not in segment["scene_present_entities"]
