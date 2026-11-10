"""Retained substring-name failures through producer and API read callers."""
import copy
import json

import pytest


def test_frame_semantics_does_not_invent_dom_from_domestic():
    from cli.run_ingestion import _persist_frame_semantic_entities

    frame = {"caption": "A quiet moment in a artifact scene with a woman and a baby."}
    _persist_frame_semantic_entities(frame, scene_id="frame", video_id="source")
    assert "Mom" not in frame.get("entities", [])
    genuine = {"caption": "Mom is standing beside Dad."}
    _persist_frame_semantic_entities(genuine, scene_id="frame", video_id="source")
    assert {"Mom", "Dad"}.issubset(genuine["entities"])


@pytest.mark.parametrize("text,matched,keep", [
    ("A artifact scene.", "A artifact scene.", False),
    ("He spoke to Arturo.", "He spoke to Arturo.", False),
    ("The camera shows a long dinner scene. It is a artifact scene.", "The camera shows", False),
    ("Art's camera is new.", "Art's camera is new.", True),
    ("A artifact scene. Art is here.", "A artifact scene.", True),
    ("A artifact scene.", None, True),
])
def test_temporal_reader_reconciles_only_proven_substring_matches(tmp_path, text, matched, keep):
    from api.utils.loaders import DataLoader
    from api.routes.scenes import _build_scene_response
    from api.routes.timeline import _build_timeline_segment

    root = tmp_path / "processing"
    folder = root / "movie"
    folder.mkdir(parents=True)
    entity = {"name": "Art", "entity_type": "person", "source_steps": ["transcription"],
              "properties": {"matched_text": matched}}
    segment = {"scene_id": "s", "start": 0.0, "end": 10.0, "full_transcript": text,
               "entities": [entity], "dialogue_mentioned_entities": [{"text": "Art", "type": "PERSON"}],
               "mentioned_people": [{"text": "Art", "type": "PERSON"}]}
    path = folder / "temporal_index.json"
    raw = json.dumps({"video_id": "movie", "segments": [segment]})
    path.write_text(raw, encoding="utf-8")
    loader = DataLoader(processing_root=root)
    result = loader.load_temporal_index("movie")["segments"][0]
    assert bool(result["entities"]) is keep
    assert bool(result["dialogue_mentioned_entities"]) is keep
    assert result["full_transcript"] == text
    assert path.read_text(encoding="utf-8") == raw
    assert bool(_build_scene_response("movie", result).dialogue_mentioned_entities) is keep
    assert bool(_build_timeline_segment("movie", result).dialogue_mentioned_entities) is keep


def test_name_projection_does_not_mutate_or_remove_typed_independent_evidence():
    from api.utils.media_projection import project_legacy_name_matches
    record = {"full_transcript": "A artifact scene.", "entities": [
        {"name": "Art", "entity_type": "person", "source_steps": ["tagger"],
         "properties": {"matched_text": "A artifact scene."}},
    ]}
    before = copy.deepcopy(record)
    assert project_legacy_name_matches(record) == before
    assert record == before


def test_projection_removes_only_derived_false_name_annotations():
    from api.utils.media_projection import project_legacy_name_matches
    record = {"visual_caption": "A artifact scene.", "entities": [
        {"name": "Art", "entity_type": "person", "source_steps": ["image_caption"],
         "properties": {"matched_text": "A artifact scene."}}],
        "transcript_entity_disagreements": [{"reason": "other disagreement",
            "entity_names": ["Art", "Avery"], "mentioned_people": [{"text": "Art"}, {"text": "Avery"}]}],
        "scene_context_arbitration": {"hypotheses": [
            {"axis": "conversation_focus", "claim": "art", "evidence_family": "identity"},
            {"axis": "topic", "claim": "dinner", "evidence_family": "transcript"}]}}
    before = copy.deepcopy(record)
    result = project_legacy_name_matches(record)
    assert result["transcript_entity_disagreements"][0]["entity_names"] == ["Avery"]
    assert result["transcript_entity_disagreements"][0]["mentioned_people"] == [{"text": "Avery"}]
    assert result["scene_context_arbitration"]["hypotheses"] == before["scene_context_arbitration"]["hypotheses"][1:]
    assert record == before


def test_independent_person_evidence_survives_a_same_name_legacy_match():
    from api.utils.media_projection import project_legacy_name_matches
    record = {"visual_caption": "A artifact scene.", "entities": [
        {"name": "Art", "entity_type": "person", "source_steps": ["image_caption"],
         "properties": {"matched_text": "A artifact scene."}},
        {"name": "Art", "entity_type": "person", "source_steps": ["reviewed_identity"]}],
        "visible_people": [{"text": "Art", "type": "PERSON"}]}
    assert project_legacy_name_matches(record) == record
