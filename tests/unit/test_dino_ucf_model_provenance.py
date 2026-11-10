from __future__ import annotations

import json
import sqlite3
import sys
import types
from contextlib import nullcontext

import numpy as np
import pytest


@pytest.mark.parametrize("source_kind", [None, "image"])
def test_dino_worker_and_ucf_caller_agree_with_provisioned_model(monkeypatch, tmp_path, source_kind):
    from cli import run_ingestion
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    from steps.common import config_loader, memory, model_provisioner, qdrant_client
    from steps.image_embed_dino import step

    model_tag = "facebook/dinov2-large"
    provision_calls = []
    points = []

    class Tensor:
        def __getitem__(self, _key):
            return self

        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return np.ones((1, 1024), dtype="float32")

    class Model:
        def to(self, _device):
            return self

        def eval(self):
            return self

        def __call__(self, **_kwargs):
            return types.SimpleNamespace(last_hidden_state=Tensor())

    class Batch(dict):
        def to(self, _device):
            return self

    class Processor:
        def __call__(self, **_kwargs):
            return Batch(pixel_values=types.SimpleNamespace(shape=(1, 3, 224, 224)))

    def provision(key, **kwargs):
        provision_calls.append((key, kwargs))
        return types.SimpleNamespace(
            status="cached", repo_id=model_tag, local_path=str(tmp_path / "model"), revision="fixture",
        )

    torch = types.ModuleType("torch")
    torch.inference_mode = nullcontext
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    transformers = types.ModuleType("transformers")
    transformers.AutoModel = types.SimpleNamespace(from_pretrained=lambda *_args, **_kwargs: Model())
    transformers.AutoProcessor = types.SimpleNamespace(from_pretrained=lambda *_args, **_kwargs: Processor())
    pil = types.ModuleType("PIL")
    pil.Image = types.SimpleNamespace(open=lambda _: types.SimpleNamespace(
        convert=lambda _: types.SimpleNamespace(size=(640, 428)),
    ))
    text_embed = types.ModuleType("steps.text_embed.step")
    text_embed._content_fingerprint = lambda _: "a" * 64
    for name, module in (
        ("torch", torch), ("transformers", transformers), ("PIL", pil),
        ("faiss", types.ModuleType("faiss")), ("steps.text_embed.step", text_embed),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(step, "_DINO", {"model": None, "proc": None, "device": "cpu"})
    monkeypatch.setattr(step, "setup_step_gpu", lambda _: {"device": "cpu"})
    monkeypatch.setattr(config_loader, "load_configs", lambda _: {"verification": {"offline_mode": True}})
    monkeypatch.setattr(model_provisioner, "ensure_model_cached", provision)
    monkeypatch.setattr(step, "FaissLock", lambda _: nullcontext())
    monkeypatch.setattr(step, "create_hnsw_id_index", lambda *_: object())
    monkeypatch.setattr(step, "add_with_required_ids", lambda *_: None)
    monkeypatch.setattr(step, "write_index_atomically", lambda *_: None)
    monkeypatch.setattr(memory, "embedding_persistence_allowed", lambda _: False)
    qclient = types.SimpleNamespace(
        cfg=types.SimpleNamespace(collection="test_dino"),
        upsert=lambda batch: points.extend(batch) or True,
    )
    monkeypatch.setattr(qdrant_client, "build_qdrant_client", lambda *_args, **_kwargs: qclient)

    frames = tmp_path / "frames"
    frames.mkdir()
    image = frames / "frame.jpg"
    image.write_bytes(b"fixture; model and image decoder are replaced")
    epoch = tmp_path / "epoch_fixture"
    (epoch / "ucf").mkdir(parents=True)
    db = epoch / "ucf" / "ucf_ledger.db"
    client = UCFLedgerClient(str(db))
    client.init_schema()
    client.register_media("video-1", str(image), 20.0, 30.0, 640, 428)
    client.close()
    cfg = {
        "ingestion_isolation": True,
        "paths": {
            "db_dir": str(epoch), "faiss_dino_path": str(tmp_path / "dino.index"),
            "dino_id_map_db": str(tmp_path / "dino-map.sqlite"),
        },
        "qdrant": {"enabled": False, "embedding_dims": {"dino": 1024}},
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    identity = {"source_kind": source_kind} if source_kind else {}
    result = step.image_embed_dino({
        "source_path": str(image), "scene_id": "scene-1", "video_hash": "video-1",
        **identity,
    }, cfg)
    assert result["dino_meta"]["status"] == "ok"
    run_ingestion._log_visual_to_ucf_ledger(
        cfg_path, "video-1", "scene-1", {"start": 0, "duration": 0 if source_kind else 20}, frames, {**result, **identity},
    )

    with sqlite3.connect(db) as con:
        ucf = con.execute("SELECT model_tag, vector_model_tag, vector_dim FROM context_frames").fetchone()
        ucf_modality = con.execute("SELECT modality FROM context_frames").fetchone()[0]
    with sqlite3.connect(cfg["paths"]["dino_id_map_db"]) as con:
        map_tag = con.execute("SELECT vector_model_tag FROM dino_id_map").fetchone()[0]
        map_modality = con.execute("SELECT modality FROM dino_id_map").fetchone()[0]
    raw = json.loads((frames / "scene-1_raw_dino.json").read_text(encoding="utf-8"))
    assert provision_calls == [("dinov2", {"offline": True})]
    assert ucf == (model_tag, model_tag, 1024)
    assert result["dino_meta"]["model"] == raw["model"] == map_tag == model_tag
    assert points[0]["payload"]["vector_model_tag"] == model_tag
    expected_modality = "multimodal" if source_kind else "video"
    assert points[0]["payload"]["modality"] == ucf_modality == map_modality == expected_modality
    if source_kind:
        assert points[0]["payload"]["source_kind"] == source_kind


def test_standalone_clip_worker_matches_ucf_and_sidecar_modality(monkeypatch, tmp_path):
    from steps.image_embed_clip import step
    from cli import run_ingestion
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    from PIL import Image

    points = []
    class Tensor:
        def to(self, _): return self
        def detach(self): return self
        def cpu(self): return self
        def numpy(self): return np.ones((1, 512), dtype="float32")
    torch = types.ModuleType("torch")
    torch.no_grad = nullcontext
    torch.is_tensor = lambda value: isinstance(value, Tensor)
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "faiss", types.ModuleType("faiss"))
    monkeypatch.setattr(step, "_CLIP", {"device": "cpu", "model_tag": "fixture-clip",
        "model": types.SimpleNamespace(get_image_features=lambda **_: Tensor()),
        "proc": lambda **_: {"pixel_values": Tensor()}})
    monkeypatch.setattr(step, "_debug_env", lambda: None)
    monkeypatch.setattr(step, "_load", lambda: None)
    monkeypatch.setattr(step, "FaissLock", lambda _: nullcontext())
    monkeypatch.setattr(step, "create_hnsw_id_index", lambda *_: object())
    monkeypatch.setattr(step, "add_with_required_ids", lambda *_: None)
    monkeypatch.setattr(step, "write_index_atomically", lambda *_: None)
    monkeypatch.setattr(step, "build_qdrant_client", lambda *_a, **_kw: types.SimpleNamespace(
        cfg=types.SimpleNamespace(collection="test_clip"), upsert=lambda batch: points.extend(batch) or True))
    image = tmp_path / "image.png"
    Image.new("RGB", (8, 8)).save(image)
    epoch = tmp_path / "epoch"
    (epoch / "ucf").mkdir(parents=True)
    ledger_path = epoch / "ucf/ucf_ledger.db"
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.init_schema()
    ledger.register_media("source-hash", str(image), 0, 0, 8, 8)
    ledger.close()
    cfg = {"ingestion_isolation": True, "paths": {"db_dir": str(epoch),
        "faiss_clip_path": str(tmp_path / "clip.index"), "clip_id_map_db": str(tmp_path / "clip.sqlite")},
        "qdrant": {"enabled": False}}
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    item = {"source_path": str(image), "source_kind": "image", "video_hash": "source-hash", "scene_id": "scene-1"}
    result = step.image_embed_clip(item, cfg)
    assert result["clip_meta"]["status"] == "ok"
    run_ingestion._log_visual_to_ucf_ledger(cfg_path, "source-hash", "scene-1", {"start": 0, "duration": 0},
                                          tmp_path, {**item, **result}, strict=True)
    with sqlite3.connect(ledger_path) as db:
        modality = db.execute("SELECT modality FROM context_frames").fetchone()[0]
    with sqlite3.connect(cfg["paths"]["clip_id_map_db"]) as db:
        map_modality = db.execute("SELECT modality FROM clip_id_map").fetchone()[0]
    assert points[0]["payload"]["modality"] == modality == map_modality == "multimodal"
    assert points[0]["payload"]["source_kind"] == "image"
