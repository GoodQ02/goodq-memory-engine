from __future__ import annotations
from typing import Any, Dict, Optional
from contextlib import nullcontext
import sqlite3
from datetime import datetime

import os


_CLAP = {"model": None, "proc": None, "device": "cpu"}


def _load() -> None:
    if _CLAP["model"] is not None:
        return
    try:
        import torch  # type: ignore
        from transformers import ClapModel, AutoProcessor  # type: ignore
        device = "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
        # Prefer local caches; processor prepares input_features for audio
        proc = AutoProcessor.from_pretrained("laion/clap-htsat-unfused", local_files_only=True)
        model = ClapModel.from_pretrained("laion/clap-htsat-unfused", local_files_only=True).to(device).eval()
        _CLAP.update({"model": model, "proc": proc, "device": device})
    except Exception:
        _CLAP.update({"model": None, "proc": None})


def _ensure_clap_map(db_path: str) -> None:
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        con = sqlite3.connect(db_path, check_same_thread=False)
        with con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS clap_id_map (
                    faiss_id INTEGER PRIMARY KEY,
                    hash TEXT,
                    source_path TEXT,
                    created_at TEXT
                )
                """
            )
    finally:
        try:
            con.close()  # type: ignore
        except Exception:
            pass


def audio_embed_clap(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"clap_meta": {"status": "no_file"}}
    _load()
    if _CLAP["model"] is None:
        return {"clap_meta": {"status": "unavailable"}}
    try:
        import torch  # type: ignore
        import librosa  # type: ignore
        import numpy as np  # type: ignore
        import faiss  # type: ignore
        from GoodQ_4_All.steps.text_embed.step import _content_fingerprint
        # resample to 48kHz mono as expected
        wave, sr = librosa.load(path, sr=48000, mono=True)
        # Prepare CLAP audio input features; ClapModel expects input_features for audio
        batch = _CLAP["proc"](audios=wave, sampling_rate=48000, return_tensors="pt")
        input_features = batch.get("input_features")
        if input_features is None:
            raise RuntimeError("CLAP processor did not return input_features for audio")
        input_features = input_features.to(_CLAP["device"])  # type: ignore[attr-defined]
        if _CLAP["device"] == "cuda":
            with torch.cuda.amp.autocast():
                out = _CLAP["model"].get_audio_features(input_features=input_features)
        else:
            out = _CLAP["model"].get_audio_features(input_features=input_features)
        feats = out.detach().cpu().numpy().astype("float32")
        index_path = (cfg.get("paths", {}) or {}).get("faiss_audio_path")
        if not index_path:
            return {"clap_meta": {"status": "no_index_path"}}
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        if os.path.isfile(index_path):
            index = faiss.read_index(index_path)
        else:
            index = faiss.IndexHNSWFlat(feats.shape[1], 32)
            index.hnsw.efConstruction = 200
            index.hnsw.efSearch = 50

        # Stable 64-bit ID derived from content fingerprint
        h = _content_fingerprint(item)
        try:
            uid = np.array([int(h[:16], 16) % (2**63 - 1)], dtype='int64')
            index.add_with_ids(feats.astype("float32"), uid)
            faiss_id = int(uid[0])
        except Exception:
            index.add(feats.astype("float32"))
            # best-effort: last ID is ntotal-1 but only valid for flat add
            faiss_id = getattr(index, 'ntotal', 0) - 1
        faiss.write_index(index, index_path)
        # Map FAISS ID -> fingerprint/source in dedicated SQLite
        map_db = (cfg.get("paths", {}) or {}).get("clap_id_map_db")
        if map_db:
            try:
                _ensure_clap_map(map_db)
                con = sqlite3.connect(map_db, check_same_thread=False)
                with con:
                    con.execute(
                        "INSERT OR REPLACE INTO clap_id_map(faiss_id, hash, source_path, created_at) VALUES (?,?,?,?)",
                        (faiss_id, h, path, datetime.utcnow().isoformat()),
                    )
            except Exception:
                pass
            finally:
                try:
                    con.close()  # type: ignore
                except Exception:
                    pass
        # Upsert generic embedding metadata for recall
        try:
            from GoodQ_4_All.steps.common.memory import upsert_embedding
            upsert_embedding(cfg, h, faiss_id, path, item.get("modality", "audio") or "audio")
        except Exception:
            pass
        return {"clap_meta": {"status": "ok", "index_path": index_path, "faiss_id": faiss_id}}
    except Exception as e:
        return {"clap_meta": {"status": "error", "error": str(e)}}
