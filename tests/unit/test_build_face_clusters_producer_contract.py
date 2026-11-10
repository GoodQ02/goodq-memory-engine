"""Face identity must survive the production visual writer and rebuild CLI."""
from contextlib import closing
import base64
import asyncio
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import sys

import numpy as np
from PIL import Image
import pytest


def controlled_faces(engine="opencv-yunet-sface", dimension=128):
    """Controlled compute output, never a claim about a real person's identity."""
    return [{"bbox": [10 + index * 60, 10, 50 + index * 60, 90],
             "encoding": [1.0] + [0.0] * (dimension - 1),
             "engine": engine, "embedding_dimension": dimension} for index in range(2)]


@pytest.fixture
def face_pipeline(tmp_path, monkeypatch):
    for key, child in {
        "GOODQ_DATA_ROOT": "data", "GOODQ_LOGS_ROOT": "logs", "GOODQ_TEMP_ROOT": "temp",
        "GOODQ_CACHE_ROOT": "cache", "TEMP": "temp", "TMP": "temp",
    }.items():
        target = tmp_path / child
        target.mkdir(exist_ok=True)
        monkeypatch.setenv(key, str(target))
    monkeypatch.setenv("GOODQ_PROFILE", "BASELINE")
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "0")
    monkeypatch.setenv("GOODQ_REQUIRE_WSL_AUDIO", "0")
    monkeypatch.delenv("GOODQ_WITNESS_CONFIG", raising=False)
    import requests
    monkeypatch.setattr(requests.Session, "send", lambda *_a, **_k: pytest.fail("network forbidden"))
    from cli.run_ingestion import _log_visual_to_ucf_ledger
    from scripts.identity import build_face_clusters as builder
    from scripts.ucf.ucf_ledger import UCFLedgerClient

    epoch = tmp_path / "epochs" / "epoch-contract"
    frames = epoch / "processing" / "controlled-source" / "video" / "frames"
    frames.mkdir(parents=True)
    (epoch / "ucf").mkdir()
    ledger_path = epoch / "ucf/ucf_ledger.db"
    video_hash = hashlib.sha256(b"controlled source").hexdigest()
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.init_schema()
    ledger.register_media(video_hash, "controlled-test-source", 30, 25, 128, 100)
    ledger.close()
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"paths": {"db_dir": str(epoch)}}), encoding="utf-8")
    manifest = {"video_hash": video_hash, "scenes": []}
    observations = []
    manifest_path = frames.parent / "scene_manifest.json"

    def persist(faces, *, index=0, engine="opencv-yunet-sface", source_kind=None, sampled=False):
        start = index * 10.0
        duration = 0.0 if source_kind == "image" else 10.0
        sid = hashlib.sha256(f"scene{video_hash}|{start:.3f}|{start + duration:.3f}|".encode()).hexdigest()
        image = frames / f"scene_{index:04d}.jpg"
        pixels = np.zeros((100, 128, 3), dtype=np.uint8)
        pixels[:, :60] = (255, 0, 0)
        pixels[:, 60:] = (0, 255, 0)
        Image.fromarray(pixels).save(image)
        row = {"scene_id": sid, "start": start, "end": start + duration, "duration": duration,
               "keyframe": {"path": str(image), "timestamp": start + duration / 2}}
        manifest["scenes"].append(row)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        item = {"path": str(image), "faces": faces, "faces_meta": {"engine": engine}}
        if sampled:
            item.update(_face_observation_index=0, source_path=str(image), timestamp=start + duration / 2)
        if source_kind:
            item["source_kind"] = source_kind
        _log_visual_to_ucf_ledger(config, video_hash, sid, row, frames, item, strict=True)
        with closing(sqlite3.connect(ledger_path)) as db, db:
            records = db.execute("SELECT frame_id,payload,raw_ref FROM context_frames WHERE worker_name='face_embed' AND source_artifact_id=? ORDER BY frame_id", (sid,)).fetchall()
            db.execute("UPDATE context_frames SET promotion_status='promoted' WHERE source_artifact_id=?", (sid,))
        return row, image, [(fid, json.loads(payload), raw) for fid, payload, raw in records]

    real_compute = builder.run_dbscan

    def compute(detections, *_args):
        observations.extend(copy.deepcopy(detections))
        return np.zeros(len(detections), dtype=int)

    monkeypatch.setattr(builder, "run_dbscan", compute)
    output = tmp_path / "identity-output"

    def command():
        return [str(Path(builder.__file__).resolve()), "--epoch-id", epoch.name,
                "--epoch-root", str(epoch.parent), "--data-path", str(output), "--min-samples", "1"]

    def run():
        monkeypatch.setattr(sys, "argv", command())
        builder.main()
        return json.loads((output / "face_clusters.json").read_text()), (output / "reports/face_cluster_sheet.html").read_text(encoding="utf-8")

    return {"persist": persist, "run": run, "command": command, "ledger": ledger_path,
            "observed": observations, "builder": builder, "manifest": manifest,
            "manifest_path": manifest_path, "epoch": epoch, "output": output,
            "video_hash": video_hash, "real_compute": real_compute, "config": config,
            "frames": frames}


@pytest.mark.parametrize('failed_sample', [False, True])
@pytest.mark.parametrize('engine_status', [('opencv-yunet-sface', 'ok'), ('face_recognition', 'degraded')])
def test_async_video_faces_retain_nonmidpoint_images_through_builder_and_review(face_pipeline, monkeypatch, failed_sample, engine_status):
    from cli import run_ingestion as runner
    from api.utils.identity_read_projection import project_face_cluster_images
    f = face_pipeline
    scene = {"index": 0, "start": 0.0, "end": 10.001, "duration": 10.001}
    scene_id = "sampled-scene"
    calls = []

    def extract(_ffmpeg, _video, selected, directory, **kwargs):
        stamp = kwargs.get('sample_timestamp', selected["start"] + selected["duration"] / 2)
        path = directory / f"scene_{selected['index']:04d}{kwargs.get('sample_suffix', '')}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (128, 100), "red" if stamp < 1 else "green").save(path)
        return path

    async def step(_env, name, item, _cfg):
        if name == "image_caption":
            return {"status": "ok", "outputs": {"samples": [{} for _ in item['samples']]}}
        if name != "face_embed":
            return {"status": "ok", "outputs": {}}
        calls.append(item.copy())
        if failed_sample and item['timestamp'] > 9:
            return {'status': 'error', 'errors': 'sample decoder unavailable'}
        faces = controlled_faces(engine_status[0]) if item["timestamp"] < 1 or item["timestamp"] > 7 else []
        return {"status": "ok", "outputs": {"faces": faces, "faces_meta": {"status": engine_status[1], "engine": engine_status[0]}}}

    monkeypatch.setattr(runner, "_extract_keyframe", extract)
    monkeypatch.setattr(runner, "_run_step_async", step)
    monkeypatch.setattr(runner, "_persist_frame_semantic_entities", lambda *_a, **_k: None)
    output = asyncio.run(runner._process_frame_async(
        f["config"], "ffmpeg", Path("controlled-video"), scene, f["frames"],
        f["video_hash"], scene_id, asyncio.Lock(), asyncio.Lock()))
    assert any(call["timestamp"] < 1 for call in calls), "midpoint-only sampling misses known positive"
    assert all(0 <= call["timestamp"] < 10 for call in calls)
    assert bool(output['errors']) is failed_sample
    assert bool(output['data']['face_sampling_warnings']) is (engine_status[1] == 'degraded')
    f["manifest"]["scenes"].append({**scene, "scene_id": scene_id,
        "keyframe": {**output["data"], "path": output["path"], "timestamp": output["timestamp"]}})
    f["manifest_path"].write_text(json.dumps(f["manifest"]))
    with closing(sqlite3.connect(f["ledger"])) as db, db:
        db.execute("UPDATE context_frames SET promotion_status='promoted'")
    clusters, _ = f["run"]()
    assert len(f["observed"]) == (4 if failed_sample else 6)
    assert all(row["t_start"] != 5 for row in f["observed"])
    assert all(Path(row["image_path"]) != Path(output["path"]) for row in f["observed"])
    projected = project_face_cluster_images(clusters,
        {"paths": {"db_path": str(f["epoch"] / "memory.db")}}, {"ready": True})
    evidence = projected["clusters"][0]["representative_frames"][0]
    assert Path(f["observed"][0]["image_path"]).name in evidence["frame_url"]
    assert evidence["timestamp"] == f["observed"][0]["t_start"]
    # A retired sample must not fall back to the unrelated temporal thumbnail.
    (f['frames'].parent.parent / 'temporal_index.json').write_text(json.dumps({'segments': [
        {'start': 0, 'end': 10, 'representative_frame': output['path']}]}))
    with closing(sqlite3.connect(f['ledger'])) as db, db:
        db.execute("UPDATE context_frames SET promotion_status='superseded' WHERE frame_id=?", (f['observed'][0]['frame_id'],))
    retired = project_face_cluster_images(clusters,
        {'paths': {'db_path': str(f['epoch'] / 'memory.db')}}, {'ready': True})
    assert 'representative_frames' not in retired['clusters'][0]
    with closing(sqlite3.connect(f['ledger'])) as db, db:
        db.execute("UPDATE context_frames SET promotion_status='promoted'")
    # An altered image cannot inherit the old observation's identity authority.
    Image.new('RGB', (128, 100), 'blue').save(f['observed'][0]['image_path'])
    with pytest.raises(ValueError, match='image hash'):
        f['run']()
    refused = project_face_cluster_images(clusters,
        {'paths': {'db_path': str(f['epoch'] / 'memory.db')}}, {'ready': True})
    assert 'representative_frames' not in refused['clusters'][0]


def test_empty_producer_faces_do_not_claim_positive_identity(face_pipeline):
    f = face_pipeline
    f["persist"]([])
    with pytest.raises(SystemExit) as error:
        f["run"]()
    assert error.value.code == 1
    assert not f["observed"]


def test_saved_face_members_reach_api_without_changing_labels_or_manifest(face_pipeline, monkeypatch):
    from fastapi.testclient import TestClient
    from api.main import app
    from api.routes import identity

    f = face_pipeline
    rows = f['persist'](controlled_faces(), index=0, sampled=True)[2]
    rows += f['persist'](controlled_faces(), index=1, sampled=True)[2]
    expected = {f'{fid}_{payload["face_index"]}': payload for fid, payload, _ in rows}
    clusters, _ = f['run']()
    clusters['clusters'][0]['label'] = 'Reviewer supplied name'
    clusters['clusters'][0]['operator_note'] = 'Keep my review note'
    path = f['output'] / 'face_clusters.json'
    path.write_text(json.dumps(clusters), encoding='utf-8')
    before = path.read_bytes()
    monkeypatch.setattr(identity, '_CFG', {
        'epoch_id': f['epoch'].name, 'paths': {'db_path': str(f['epoch'] / 'memory.db')},
        'identity_search': {'roster_path': str(f['output'] / 'family_roster.yaml')},
    })
    reads = []
    read_text = Path.read_text

    def tracked_read(path, *args, **kwargs):
        if path.name == 'scene_manifest.json':
            reads.append(path)
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', tracked_read)
    with TestClient(app, client=('127.0.0.1', 50000)) as client:
        response = client.get('/api/identity/face-clusters')
        assert len(reads) == 1
        assert client.get('/api/identity/face-clusters').json() == response.json()
        assert len(reads) == 2  # Fresh per request; never a stale global cache.
    assert response.status_code == 200
    cluster = response.json()['clusters'][0]
    assert len(cluster['members']) == cluster['members_available'] == 4
    assert cluster['members_unavailable'] == 0
    assert [m['target_face_id'] for m in cluster['members']] == cluster['face_ids']
    assert cluster['label'] == 'Reviewer supplied name'
    assert cluster['operator_note'] == 'Keep my review note'
    assert not cluster['confirmed'] and cluster['status'] == 'candidate'
    assert path.read_bytes() == before
    for member in cluster['members']:
        payload = expected[member['target_face_id']]
        assert member['evidence_status'] == 'available'
        assert member['image_width'] == 128 and member['image_height'] == 100
        assert member['crop_bbox'] == controlled_faces()[payload['face_index']]['bbox']
        assert member['target_face_index'] == payload['face_index']
        assert member['source_face_count'] == 2
        assert member['timestamp'] == payload['observation_timestamp']


@pytest.mark.parametrize('defect', ['retired', 'wrong_index', 'altered_box'])
def test_member_review_never_substitutes_another_face_or_hides_missing_member(face_pipeline, defect):
    from api.utils.identity_read_projection import project_face_cluster_images

    f = face_pipeline
    _scene, _image, rows = f['persist'](controlled_faces(), sampled=True)
    clusters, _ = f['run']()
    if defect == 'retired':
        with closing(sqlite3.connect(f['ledger'])) as db, db:
            db.execute("UPDATE context_frames SET promotion_status='superseded' WHERE frame_id=?", (rows[0][0],))
    elif defect == 'wrong_index':
        clusters['clusters'][0]['face_ids'][0] = f'{rows[0][0]}_1'
    else:
        raw = Path(rows[0][2])
        faces = json.loads(raw.read_text())
        faces[0]['bbox'] = faces[1]['bbox']
        raw.write_text(json.dumps(faces))
    cluster = project_face_cluster_images(clusters,
        {'paths': {'db_path': str(f['epoch'] / 'memory.db')}}, {'ready': True})['clusters'][0]
    assert len(cluster['members']) == 2
    assert cluster['members_unavailable'] == 1 and cluster['members_available'] == 1
    assert cluster['members'][0]['evidence_status'] == 'unavailable'
    assert 'frame_url' not in cluster['members'][0]
    assert cluster['members'][1]['evidence_status'] == 'available'
    assert 'representative_frames' not in cluster


def test_build_cli_preserves_each_production_face_ledger_id(face_pipeline):
    f = face_pipeline
    _, _, records = f["persist"](controlled_faces())
    manifest, _ = f["run"]()
    assert manifest["clusters"][0]["face_ids"] == [f"{fid}_{payload['face_index']}" for fid, payload, _ in records]


def test_build_cli_does_not_include_unpromoted_sibling_face(face_pipeline):
    f = face_pipeline
    _, _, records = f["persist"](controlled_faces())
    with closing(sqlite3.connect(f["ledger"])) as db, db:
        db.execute("UPDATE context_frames SET promotion_status='staged' WHERE frame_id=?", (records[1][0],))
    manifest, _ = f["run"]()
    assert manifest["clusters"][0]["face_ids"] == [f"{records[0][0]}_0"]


def test_reordered_raw_faces_cannot_reassign_promoted_authority_to_staged_sibling(face_pipeline):
    f = face_pipeline
    faces = controlled_faces()
    _, _, records = f["persist"](faces)
    with closing(sqlite3.connect(f["ledger"])) as db, db:
        db.execute("UPDATE context_frames SET promotion_status='staged' WHERE frame_id=?", (records[1][0],))
    Path(records[0][2]).write_text(json.dumps(list(reversed(faces))), encoding="utf-8")
    with pytest.raises(ValueError, match="bbox"):
        f["run"]()
    assert not f["observed"]


def test_manifest_cannot_borrow_a_neighbor_source_image(face_pipeline):
    f = face_pipeline
    row, image, _ = f["persist"](controlled_faces())
    neighbor = f["epoch"] / "processing" / "other-source" / "frame.jpg"
    neighbor.parent.mkdir()
    shutil.copy2(image, neighbor)
    row["keyframe"]["path"] = str(neighbor)
    f["manifest_path"].write_text(json.dumps(f["manifest"]), encoding="utf-8")
    with pytest.raises(ValueError, match="media directory"):
        f["run"]()
    assert not f["observed"]


def test_build_cli_uses_manifest_keyframe_for_review(face_pipeline):
    f = face_pipeline
    _, image, _ = f["persist"](controlled_faces())
    _, html = f["run"]()
    assert all(Path(item["image_path"]) == image for item in f["observed"])
    assert html.count("data:image/jpeg;base64,") == 2


def test_build_cli_accepts_producer_list_bbox_for_review(face_pipeline):
    f = face_pipeline
    row, image, _ = f["persist"](controlled_faces())
    # Diagnostic compatibility alias isolates bbox handling from path resolution.
    shutil.copy2(image, image.parent / (row["scene_id"] + ".jpg"))
    _, html = f["run"]()
    assert html.count("data:image/jpeg;base64,") == 2


def test_build_cli_rejects_equal_dimension_different_engines(face_pipeline):
    f = face_pipeline
    f["persist"](controlled_faces(), index=0)
    f["persist"](controlled_faces("face_recognition"), index=1, engine="face_recognition")
    with pytest.raises(RuntimeError, match="mixed"):
        f["run"]()
    assert not f["observed"]


def replace_payload(ledger, frame_id, payload, *, model_tag=None):
    encoded = json.dumps(payload)
    hashed = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with closing(sqlite3.connect(ledger)) as db, db:
        db.execute("UPDATE context_frames SET payload=?,payload_hash=? WHERE frame_id=?", (encoded, hashed, frame_id))
        if model_tag is not None:
            db.execute("UPDATE context_frames SET model_tag=? WHERE frame_id=?", (model_tag, frame_id))


@pytest.mark.parametrize("case", ["missing", "duplicate", "bool", "out_of_range", "aggregate_video"])
def test_build_cli_refuses_ambiguous_face_authority(face_pipeline, case):
    f = face_pipeline
    _, _, records = f["persist"](controlled_faces())
    fid, payload, _ = records[0]
    if case in {"missing", "aggregate_video"}:
        payload.pop("face_index")
        if case == "aggregate_video":
            payload["face_count"] = 2
    else:
        payload["face_index"] = {"duplicate": 1, "bool": True, "out_of_range": 2}[case]
    replace_payload(f["ledger"], fid, payload)
    with pytest.raises(ValueError, match="face_index"):
        f["run"]()
    assert not f["observed"]
    assert not (f["output"] / "face_clusters.json").exists()


def test_static_image_aggregate_authorizes_its_exact_raw_faces(face_pipeline):
    f = face_pipeline
    row, image, records = f["persist"](controlled_faces(), source_kind="image")
    assert len(records) == 1 and records[0][1]["face_count"] == 2
    retained = image.parent.parent.parent / "retained-original.jpg"
    shutil.copy2(image, retained)
    row["keyframe"]["path"] = str(retained)
    f["manifest_path"].write_text(json.dumps(f["manifest"]), encoding="utf-8")
    manifest, html = f["run"]()
    assert manifest["clusters"][0]["face_ids"] == [f"{records[0][0]}_0", f"{records[0][0]}_1"]
    assert html.count("data:image/jpeg;base64,") == 2


def test_static_image_aggregate_count_must_match_raw_artifact(face_pipeline):
    f = face_pipeline
    _, _, records = f["persist"](controlled_faces(), source_kind="image")
    records[0][1]["face_count"] = 1
    replace_payload(f["ledger"], records[0][0], records[0][1])
    with pytest.raises(ValueError, match="face_count"):
        f["run"]()


def test_unambiguous_legacy_single_face_and_dict_box_remain_usable(face_pipeline):
    f = face_pipeline
    faces = controlled_faces()[:1]
    row, image, records = f["persist"](faces)
    faces[0].pop("engine")
    faces[0].pop("embedding_dimension")
    faces[0]["bbox"] = dict(zip(("left", "top", "right", "bottom"), faces[0]["bbox"]))
    Path(records[0][2]).write_text(json.dumps(faces), encoding="utf-8")
    payload = records[0][1]
    payload.pop("face_index")
    payload.pop("engine")
    replace_payload(f["ledger"], records[0][0], payload, model_tag="unknown")
    # The historical matching-basename image remains supported without a manifest.
    shutil.copy2(image, image.parent / (row["scene_id"] + ".jpg"))
    f["manifest_path"].unlink()
    manifest, html = f["run"]()
    assert manifest["clusters"][0]["face_ids"] == [f"{records[0][0]}_0"]
    assert f["observed"][0]["engine"] == "legacy_unsealed"
    assert html.count("data:image/jpeg;base64,") == 1


def test_capture_time_comes_from_keyframe_not_row_uniqueness_offset(face_pipeline):
    f = face_pipeline
    row, _, _ = f["persist"](controlled_faces())
    manifest, _ = f["run"]()
    assert [item["t_start"] for item in f["observed"]] == [row["keyframe"]["timestamp"]] * 2
    assert manifest["clusters"][0]["timestamp_range"] == [5.0, 5.0]


@pytest.mark.parametrize("case", ["video", "epoch", "missing_scene", "duplicate_scene", "image_escape", "outside_processing", "time", "time_disagrees"])
def test_manifest_authority_and_containment_fail_before_clustering(face_pipeline, case):
    f = face_pipeline
    row, _, _ = f["persist"](controlled_faces())
    if case == "video":
        f["manifest"]["video_hash"] = "other-video"
    elif case == "epoch":
        f["manifest"]["epoch_id"] = "other-epoch"
    elif case == "missing_scene":
        row["scene_id"] = "other-scene"
    elif case == "duplicate_scene":
        f["manifest"]["scenes"].append(copy.deepcopy(row))
    elif case == "image_escape":
        row["keyframe"]["path"] = str(f["epoch"].parent / "outside.jpg")
    elif case == "outside_processing":
        row["keyframe"]["path"] = str(f["epoch"] / "outside-processing.jpg")
    elif case == "time_disagrees":
        row["keyframe"]["timestamp"] = 3.0
    else:
        row["keyframe"]["timestamp"] = 999.0
    f["manifest_path"].write_text(json.dumps(f["manifest"]), encoding="utf-8")
    with pytest.raises(ValueError):
        f["run"]()
    assert not f["observed"]


@pytest.mark.parametrize("legacy", [True, False])
def test_missing_capture_time_remains_explicitly_unknown(face_pipeline, legacy):
    f = face_pipeline
    row, image, records = f["persist"](controlled_faces())
    with closing(sqlite3.connect(f["ledger"])) as db, db:
        db.execute("UPDATE context_frames SET promotion_status='staged' WHERE frame_id=?", (records[0][0],))
    if legacy:
        f["manifest_path"].unlink()
        shutil.copy2(image, image.parent / (row["scene_id"] + ".jpg"))
    else:
        row["keyframe"].pop("timestamp")
        f["manifest_path"].write_text(json.dumps(f["manifest"]), encoding="utf-8")
    manifest, html = f["run"]()
    assert manifest["clusters"][0]["timestamp_range"] == []
    assert "t=unknown" in html
    assert html.count("data:image/jpeg;base64,") == 1


@pytest.mark.parametrize("key", ["video_hash", "source_artifact_id"])
def test_legacy_raw_reference_cannot_collapse_conflicting_sources(face_pipeline, key):
    f = face_pipeline
    _, _, records = f["persist"](controlled_faces())
    f["manifest_path"].unlink()
    with closing(sqlite3.connect(f["ledger"])) as db, db:
        db.execute(f"UPDATE context_frames SET {key}='other-source' WHERE frame_id=?", (records[1][0],))
    with pytest.raises(ValueError, match="conflicting source"):
        f["run"]()


@pytest.mark.parametrize("case", ["model", "raw_engine", "dimension", "nan", "zero"])
def test_raw_embedding_must_match_promoted_model_contract(face_pipeline, case):
    f = face_pipeline
    faces = controlled_faces()
    _, _, records = f["persist"](faces)
    if case == "model":
        replace_payload(f["ledger"], records[0][0], records[0][1], model_tag="other-model")
    else:
        if case == "raw_engine":
            faces[0]["engine"] = "other-engine"
        elif case == "dimension":
            faces[0]["embedding_dimension"] = 64
        elif case == "nan":
            faces[0]["encoding"][0] = float("nan")
        else:
            faces[0]["encoding"] = [0.0] * 128
        Path(records[0][2]).write_text(json.dumps(faces), encoding="utf-8")
    with pytest.raises(ValueError):
        f["run"]()
    assert not f["observed"]


def test_selected_epoch_and_payload_integrity_are_read_authority(face_pipeline):
    f = face_pipeline
    _, _, records = f["persist"](controlled_faces())
    with closing(sqlite3.connect(f["ledger"])) as db, db:
        db.execute("UPDATE context_frames SET epoch_id='other-epoch' WHERE frame_id=?", (records[1][0],))
    manifest, _ = f["run"]()
    assert manifest["clusters"][0]["face_ids"] == [f"{records[0][0]}_0"]


def test_corrupt_payload_is_not_used_as_face_authority(face_pipeline):
    f = face_pipeline
    f["persist"](controlled_faces())
    with closing(sqlite3.connect(f["ledger"])) as db, db:
        db.execute("UPDATE context_frames SET payload_hash='incorrect'")
    with pytest.raises(ValueError, match="payload hash"):
        f["run"]()


def test_builder_opens_ledger_read_only_and_does_not_create_missing_ledger(face_pipeline, monkeypatch):
    f = face_pipeline
    f["persist"](controlled_faces())
    original = sqlite3.connect
    reads = []

    def readonly_connect(path, **kwargs):
        conn = original(path, **kwargs)
        assert kwargs.get("uri") and str(path).endswith("?mode=ro")
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("UPDATE context_frames SET promotion_status='staged'")
        reads.append(path)
        return conn

    before = f["ledger"].read_bytes()
    monkeypatch.setattr(f["builder"].sqlite3, "connect", readonly_connect)
    f["run"]()
    assert reads and f["ledger"].read_bytes() == before
    missing = f["epoch"] / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        f["builder"].load_face_ucf_provenance(missing)
    assert not missing.exists()


@pytest.mark.parametrize("bbox", [[50, 0, 10, 20], [float("nan"), 0, 10, 20], [0, 1], {}])
def test_invalid_box_never_becomes_a_whole_image_face(face_pipeline, bbox):
    f = face_pipeline
    _, image, _ = f["persist"](controlled_faces())
    assert f["builder"]._crop_face_b64(str(image), bbox) is None


def test_real_api_launches_real_builder_and_preserves_face_authority(face_pipeline, monkeypatch):
    from api.main import app
    from api.routes import identity
    from fastapi.testclient import TestClient

    f = face_pipeline
    faces = controlled_faces()
    faces.append(copy.deepcopy(faces[0]))
    _, _, records = f["persist"](faces)
    with closing(sqlite3.connect(f["ledger"])) as db, db:
        db.execute("UPDATE context_frames SET promotion_status='staged' WHERE frame_id=?", (records[2][0],))
    monkeypatch.setattr(identity, "_CFG", {
        "epoch_id": f["epoch"].name,
        "paths": {"db_path": str(f["epoch"] / "memory.db")},
        "identity_search": {"roster_path": str(f["output"] / "family_roster.yaml")},
    })
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        prepared = client.post("/api/identity/rebuild-face-clusters", json={"eps": 0.4})
        assert prepared.status_code == 403, prepared.text
        token = prepared.json()["result"]["confirmation_token"]
        response = client.post("/api/identity/rebuild-face-clusters", json={"eps": 0.4, "confirmation_token": token})
    assert response.status_code == 200, response.text
    manifest = json.loads((f["output"] / "face_clusters.json").read_text())
    cluster = manifest["clusters"][0]
    assert cluster["face_ids"] == [f"{records[0][0]}_0", f"{records[1][0]}_1"]
    assert cluster["timestamp_range"] == [5.0, 5.0]
    assert cluster["status"] == "candidate" and cluster["confirmed"] is False
    html = (f["output"] / "reports/face_cluster_sheet.html").read_text(encoding="utf-8")
    assert html.count("data:image/jpeg;base64,") == 2
    import re
    for encoded, expected_channel in zip(re.findall(r"base64,([^\"]+)", html), (0, 1)):
        with Image.open(io.BytesIO(base64.b64decode(encoded))) as crop:
            assert crop.size == (80, 80)
            assert crop.getpixel((40, 40))[expected_channel] > 220
    jobs = [json.loads(path.read_text()) for path in (f["output"] / "process_jobs").glob("job_*.json")]
    assert len(jobs) == 1 and jobs[0]["state"] == "succeeded"
    assert jobs[0]["child_pid"] > 0 and jobs[0]["child_start_token"]
    assert not f["observed"], "subprocess must use real installed DBSCAN, not the parent test stub"
