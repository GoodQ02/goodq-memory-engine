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
