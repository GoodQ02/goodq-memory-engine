from __future__ import annotations

from cli import run_ingestion


class _FakeKG:
    def __init__(self) -> None:
        self.nodes = []
        self.links = []
        self.edges = []

    def add_node(self, node_type, name, props, timestamp):
        node_id = len(self.nodes) + 1
        self.nodes.append(
            {
                "id": node_id,
                "node_type": node_type,
                "name": name,
                "props": props,
                "timestamp": timestamp,
            }
        )
        return node_id

    def link_node_to_media(self, node_id, media_id, confidence, props=None):
        self.links.append(
            {
                "node_id": node_id,
                "media_id": media_id,
                "confidence": confidence,
                "props": props or {},
            }
        )

    def add_edge(self, source_id, target_id, edge_type, weight=1.0, properties=None):
        self.edges.append(
            {
                "source_id": source_id,
                "target_id": target_id,
                "edge_type": edge_type,
                "weight": weight,
                "properties": properties or {},
            }
        )


def test_process_audio_entities_preserves_structural_speakers_without_fake_people():
    kg = _FakeKG()
    audio = {
        "scene_id": "scene_alpha",
        "speaker_transcript": [
            {"speaker": "SPEAKER_00", "text": "hello there", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_01", "text": "general kenobi", "start": 1.0, "end": 2.0},
        ]
    }

    run_ingestion._process_audio_entities(kg, audio, media_id=7, timestamp=10.0)

    assert [(node["node_type"], node["name"]) for node in kg.nodes] == [
        ("speaker", "scene_alpha__speaker_00"),
        ("speaker", "scene_alpha__speaker_01"),
    ]
    assert all(node["props"].get("speaker_label", "").startswith("SPEAKER_") for node in kg.nodes)


def test_process_audio_entities_uses_real_speaker_identity_when_available():
    kg = _FakeKG()
    audio = {
        "speakers": [
            {"speaker": "SPEAKER_00", "name": "Jerry"},
            {"speaker": "SPEAKER_01"},
        ]
    }

    run_ingestion._process_audio_entities(kg, audio, media_id=7, timestamp=10.0)

    assert ("person", "Jerry") in [(node["node_type"], node["name"]) for node in kg.nodes]
    assert ("speaker", "Jerry") in [(node["node_type"], node["name"]) for node in kg.nodes]
    assert ("speaker", "media_7__speaker_01") in [(node["node_type"], node["name"]) for node in kg.nodes]
    assert ("person", "SPEAKER_01") not in [(node["node_type"], node["name"]) for node in kg.nodes]
    assert any(edge["edge_type"] == "identity_evidence" for edge in kg.edges)


def test_process_keyframe_entities_keeps_faces_structural_and_links_named_identity():
    kg = _FakeKG()
    keyframe = {
        "faces": [
            {"identity": "Jerry", "bbox": [0, 0, 10, 10], "confidence": 0.95},
            {"bbox": [10, 10, 20, 20], "confidence": 0.88},
        ]
    }

    run_ingestion._process_keyframe_entities(kg, keyframe, media_id=7, timestamp=10.0)

    node_pairs = [(node["node_type"], node["name"]) for node in kg.nodes]
    assert ("face", "media_7_face_0") in node_pairs
    assert ("face", "media_7_face_1") in node_pairs
    assert ("person", "Jerry") in node_pairs
    assert not any(node_type == "person" and name.startswith("face_") for node_type, name in node_pairs)
    assert any(edge["edge_type"] == "identity_evidence" for edge in kg.edges)


def test_build_kg_scene_data_exposes_speaker_voice_signatures_for_realtime_stitching():
    scene = {"index": 3, "start": 10.0, "end": 20.0}
    audio = {
        "transcript": "George is talking here",
        "speakers": ["SPEAKER_00"],
        "speaker_transcript": [{"speaker": "SPEAKER_00", "text": "George is talking here"}],
        "speaker_voice_signatures": [
            {
                "speaker": "SPEAKER_00",
                "embedding": [0.1, 0.2, 0.3],
                "voiced_seconds": 6.2,
                "segment_count": 2,
            }
        ],
        "speaker_voice_signature_meta": {"status": "ok", "emitted": 1},
    }

    payload = run_ingestion._build_kg_scene_data(
        scene,
        scene_id="scene_gamma",
        video_id="video_alpha",
        frame_data={},
        audio_data=audio,
    )

    assert payload["scene_id"] == "scene_gamma"
    assert payload["video_id"] == "video_alpha"
    assert payload["speaker_ids"] == ["SPEAKER_00"]
    assert payload["speaker_voice_signatures"] == audio["speaker_voice_signatures"]
    assert payload["speaker_voice_signature_meta"] == {"status": "ok", "emitted": 1}


def test_build_kg_scene_data_carries_entity_details_into_realtime_kg_payload():
    scene = {"index": 4, "start": 20.0, "end": 30.0}
    audio = {
        "entity_details": [
            {"label": "Avery", "type": "PERSON", "score": 9.5, "sources": ["ner"]},
        ],
    }
    frame = {
        "entity_details": [
            {"label": "Backyard", "type": "LOCATION", "score": 7.0, "sources": ["vision_semantic"]},
        ],
    }

    payload = run_ingestion._build_kg_scene_data(
        scene,
        scene_id="scene_delta",
        video_id="video_alpha",
        frame_data=frame,
        audio_data=audio,
    )

    assert payload["entities"] == [
        {"label": "Backyard", "type": "LOCATION", "score": 7.0, "sources": ["vision_semantic"]},
        {"label": "Avery", "type": "PERSON", "score": 9.5, "sources": ["ner"]},
    ]


def test_persist_frame_semantic_entities_promotes_non_object_vision_signal():
    item = {
        "caption": "Jerry stands in the apartment kitchen.",
        "objects": [
            {"label": "refrigerator", "score": 0.97},
            {"label": "dining table", "score": 0.91},
            {"label": "chair", "score": 0.88},
        ],
        "tags": ["dining table", "chair"],
        "entities": [],
        "entity_details": [],
        "timestamp": 5.0,
    }

    run_ingestion._persist_frame_semantic_entities(
        item,
        scene_id="scene_0011",
        video_id="video_123",
    )

    assert "Kitchen" in item["entities"]
    assert "Apartment" in item["entities"]
    assert "Dining Room" in item["entities"]
    assert "refrigerator" not in item["entities"]
    assert item["location"] in {"Apartment", "Kitchen"}
    assert item["locations"] == ["Apartment", "Kitchen", "Dining Room"]
    assert item["vision_semantic_meta"] == {"status": "ok", "entity_count": 3, "location_count": 3}
    assert {detail["label"] for detail in item["vision_semantic_entities"]} == {
        "Apartment",
        "Kitchen",
        "Dining Room",
    }


def test_persist_frame_semantic_entities_preserves_existing_named_entities():
    item = {
        "caption": "Jerry stands in the apartment kitchen.",
        "objects": [{"label": "refrigerator", "score": 0.97}],
        "entities": ["Jerry"],
        "entity_details": [{"label": "Jerry", "type": "PERSON", "score": 12.0, "sources": ["tagger"]}],
        "timestamp": 5.0,
    }

    run_ingestion._persist_frame_semantic_entities(
        item,
        scene_id="scene_0012",
        video_id="video_123",
    )

    assert item["entities"][0] == "Jerry"
    assert "Kitchen" in item["entities"]
    assert len([detail for detail in item["entity_details"] if detail["label"] == "Jerry"]) == 1
