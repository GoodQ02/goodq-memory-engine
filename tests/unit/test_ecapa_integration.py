import json
import sqlite3
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.kg_realtime_integration import update_kg_for_scene
from wsl2_audio import speaker_signature as contract


def signature(label="SPEAKER_00", tagged=True):
    return {"speaker": label, "embedding": [1.0] + [0.0] * 191,
            "embedding_dim": 192, "voiced_seconds": 4.4, "segment_count": 2,
            **(contract.metadata() if tagged else {})}


def ingest(db, scene, signatures):
    return update_kg_for_scene(
        {"speaker_ids": [s["speaker"] for s in signatures],
         "speaker_voice_signatures": signatures}, scene, "video", "retained.wav",
        cfg={"paths": {"knowledge_graph_db": str(db)}})


@pytest.mark.parametrize("provenance", ["present", "missing", "empty"])
def test_ecapa_space_survives_caller_reload_and_consumer_without_legacy_overwrite(tmp_path, provenance):
    from api.routes import system
    db = tmp_path / "kg.db"
    def observed_signature(tagged=True):
        value = signature(tagged=tagged)
        if provenance != "missing":
            value["selected_segments"] = ([
                {"speaker": value["speaker"], "start": 0.0, "end": 2.0},
                {"speaker": value["speaker"], "start": 3.0, "end": 5.4},
            ] if provenance == "present" else [])
        return value

    ingest(db, "same_scene", [observed_signature(tagged=False)])
    with sqlite3.connect(db) as conn:
        legacy = conn.execute("SELECT id,name,properties FROM nodes WHERE node_type='speaker_pattern'").fetchone()
    ingest(db, "same_scene", [observed_signature()])
    ingest(db, "other_scene", [observed_signature()])
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT id,name,properties FROM nodes WHERE id=?", (legacy[0],)).fetchone() == legacy
        patterns = conn.execute("SELECT properties FROM nodes WHERE node_type='speaker_pattern'").fetchall()
        assert len(patterns) == 2
        new = next(json.loads(p[0]) for p in patterns if json.loads(p[0]).get("embedding_space"))
        assert new["embedding_space"] == contract.SPACE
        assert new["signature_count"] == 2
        evidence = [json.loads(row[0]) for row in conn.execute(
            "SELECT properties FROM edges WHERE edge_type='voice_pattern_match'")]
        assert len(evidence) == 3
        assert all(e["selected_segments"] == observed_signature().get("selected_segments") for e in evidence)
    app = FastAPI()
    app.include_router(system.router)
    with patch.object(system, "_get_kg_db_path", return_value=db), TestClient(app) as client:
        response = client.get("/api/system/identity/unstitched")
        assert response.status_code == 200
        rows = sorted(response.json(), key=lambda row: row["scene_count"])
        assert [row["scene_count"] for row in rows] == [1, 2]
        expected = {"present": [2, 4], "missing": [None, None], "empty": [0, 0]}
        assert [row["segment_count"] for row in rows] == expected[provenance]
        assert {e["embedding_space"] for e in rows[0]["signature_evidence"]} == {"legacy_untagged"}
        assert {e["embedding_space"] for e in rows[1]["signature_evidence"]} == {contract.SPACE}


def test_ecapa_same_scene_guard_records_false_split_limit(tmp_path):
    db = tmp_path / "kg.db"
    ingest(db, "scene", [signature(), signature("SPEAKER_01")])
    with sqlite3.connect(db) as conn:
        patterns = conn.execute("SELECT properties FROM nodes WHERE node_type='speaker_pattern'").fetchall()
        assert len(patterns) == 2  # Same vector is deliberately not identity proof.
        assert all("false_splits" in json.loads(p[0])["separation_policy"] for p in patterns)


def test_ecapa_cutoff_is_separate_from_legacy_and_rejects_negative(tmp_path):
    db = tmp_path / "kg.db"
    ingest(db, "first", [signature()])
    positive = signature()
    positive["embedding"] = [0.4, (1 - 0.4 ** 2) ** 0.5] + [0.0] * 190
    ingest(db, "positive", [positive])  # Above ECAPA cutoff, below legacy cutoff.
    negative = signature()
    negative["embedding"] = [-1.0] + [0.0] * 191
    ingest(db, "negative", [negative])
    with sqlite3.connect(db) as conn:
        patterns = conn.execute("SELECT properties FROM nodes WHERE node_type='speaker_pattern'").fetchall()
        assert sorted(json.loads(p[0])["signature_count"] for p in patterns) == [1, 2]


def test_ecapa_registry_pin_and_profile():
    from pathlib import Path
    from scripts.bootstrap_models import build_wanted_models, load_registry
    registry = load_registry(Path(__file__).resolve().parents[2])
    entry = registry["huggingface_models"]["ecapa_speaker"]
    assert entry["revision"] == contract.REVISION
    assert contract.MODEL_ID in build_wanted_models(registry, "audio_standard")
    assert contract.MODEL_ID not in build_wanted_models(registry, "baseline")


@pytest.mark.parametrize("change", [
    {"embedding_space": "unknown"}, {"model_revision": "other"},
    {"embedding_dim": 768}, {"embedding": [float("nan")] * 192},
])
def test_invalid_tagged_signature_fails_visibly(tmp_path, change):
    value = signature()
    value.update(change)
    with pytest.raises(ValueError):
        ingest(tmp_path / "kg.db", "scene", [value])


def test_ecapa_offline_assets_do_not_fall_back_or_download(tmp_path, monkeypatch):
    monkeypatch.setenv("GOODQ_ECAPA_MODEL_DIR", str(tmp_path))
    with pytest.raises(OSError, match="hash mismatch"):
        contract.resolve_model()


def test_bridge_preserves_embedding_contract(monkeypatch):
    from steps.audio import audio_wsl2_bridge as bridge
    # Check the supported composite adapter, not a dictionary-copy helper.
    result = {"status": "success", "transcription": "words", "diarization": [],
              "speaker_voice_signatures": [signature()], "speaker_voice_signature_meta": {"status": "ok"},
              "embeddings_status": "retired", "embeddings_note": "whole_scene_vector_retired"}
    monkeypatch.setattr(bridge, "WSL2AudioBridge", lambda: type("Runner", (), {
        "process_audio": lambda self, *args, **kwargs: result})())
    output = bridge.audio_unified_wsl2("fixture.wav", duration=5.0)
    assert output["speaker_voice_signatures"] == result["speaker_voice_signatures"]
    assert output["speaker_voice_signature_meta"]["status"] == "ok"


def test_bootstrap_and_readiness_include_ecapa_separately():
    from scripts.bootstrap_models import build_wanted_models
    from scripts.wsl_audio_preflight import _build_speaker_signature_probe_script, _build_wav2vec_enrichment_probe_script
    assert contract.MODEL_ID in build_wanted_models(None, "audio_standard")
    assert "load_encoder" in _build_speaker_signature_probe_script("/worker")
    assert "facebook/wav2vec2-base-960h" not in _build_wav2vec_enrichment_probe_script("/worker")

@pytest.mark.parametrize('compatible', [True, False])
def test_possible_split_survives_bridge_kg_reload_and_api(tmp_path, monkeypatch, compatible):
    from steps.audio import audio_wsl2_bridge as bridge
    from lib.identity_ledger import _flatten_scene_payload
    from api.routes import system
    db = tmp_path / 'kg.db'
    first = signature()
    second = signature('SPEAKER_01')
    first.update(selected_segments=[{'start': 2, 'end': 7}],
                 excluded_segments=[{'start': 0, 'end': 1, 'reason': 'overlapping_speaker_turn'}],
                 admission_policy='exclude_overlapping_turns_v1')
    if not compatible:
        second['embedding'] = [-1.0] + [0.0] * 191
    result = {'status': 'success', 'diarization': [
        {'speaker': s['speaker'], 'start': i * 6, 'end': i * 6 + 5} for i, s in enumerate([first, second])],
        'speaker_voice_signatures': [first, second]}
    runner = type('Runner', (), {'process_audio': lambda self, *a, **kw: result})()
    monkeypatch.setattr(bridge, 'WSL2AudioBridge', lambda: runner)
    payload = _flatten_scene_payload({'audio': bridge.audio_unified_wsl2('fixture.wav', duration=12)})
    update_kg_for_scene(payload, 'scene', 'video', 'fixture.wav', cfg={'paths': {'knowledge_graph_db': str(db)}})
    with sqlite3.connect(db) as conn:
        patterns = [json.loads(row[0]) for row in conn.execute("SELECT properties FROM nodes WHERE node_type='speaker_pattern'")]
        assert len(patterns) == 2
        assert all(p['signature_count'] == 1 for p in patterns)
        assert sorted(p['embedding'][0] for p in patterns) == ([1, 1] if compatible else [-1, 1])
        assert conn.execute("SELECT count(*) FROM edges WHERE edge_type='identity_evidence'").fetchone()[0] == 0
    app = FastAPI(); app.include_router(system.router)
    with patch.object(system, '_get_kg_db_path', return_value=db), TestClient(app) as client:
        response = client.get('/api/system/identity/unstitched')
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 2
        assert all(len(p['possible_same_speaker_patterns']) == int(compatible) for p in rows)
        evidence = [e for p in rows for e in p['signature_evidence'] if e['admission_policy']]
        assert evidence[0]['selected_segments'] == first['selected_segments']
        assert evidence[0]['excluded_segments'] == first['excluded_segments']
