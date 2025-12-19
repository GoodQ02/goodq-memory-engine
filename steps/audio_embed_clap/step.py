from __future__ import annotations
# GPU Configuration - Auto-configured on import
from steps.common.gpu_config import configure_gpu, get_device, clear_cache, print_memory_stats
from steps.common.qdrant_client import build_qdrant_client


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
        
        # GPU Isolation - Phase 2
        os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
        
        device = "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
        
        # Set memory fraction for this process (20% of GPU)
        if device == "cuda":
            torch.cuda.set_per_process_memory_fraction(0.2, 0)
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True
        
        # Prefer local caches; processor prepares input_features for audio
        proc = AutoProcessor.from_pretrained("laion/clap-htsat-unfused", local_files_only=True)
        model = ClapModel.from_pretrained("laion/clap-htsat-unfused", local_files_only=True).to(device).eval()
        _CLAP.update({"model": model, "proc": proc, "device": device})
        print(f"[INFO] CLAP model loaded on {device} with memory fraction 0.2")
    except Exception as e:
        print(f"[ERROR] Failed to load CLAP model: {str(e)}")
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
        except Exception as e:
            print(f'[ERROR] Exception in step.py line 46: {str(e)}')
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
        from steps.text_embed.step import _content_fingerprint
        
        # VAD Preprocessing - filter silence before embedding
        vad_enabled = cfg.get("vad_enabled", True)
        audio_path_to_use = path
        
        if vad_enabled:
            try:
                from steps.common.vad_preprocessor import preprocess_audio_with_vad
                print(f"[AUDIO_CLAP] Running VAD preprocessing on {path}")
                
                vad_path, vad_segments = preprocess_audio_with_vad(
                    path,
                    threshold=0.5,
                    min_speech_duration_ms=400,
                    min_silence_duration_ms=200,
                    extract_to_file=True
                )
                
                if vad_path and vad_segments:
                    audio_path_to_use = vad_path
                    print(f"[AUDIO_CLAP] Using VAD-filtered audio ({len(vad_segments)} segments)")
                else:
                    print(f"[AUDIO_CLAP] VAD found no speech, using original audio")
            except Exception as vad_exc:
                print(f"[AUDIO_CLAP] VAD failed: {vad_exc}, using original audio")
        
        # resample to 48kHz mono as expected
        wave, sr = librosa.load(audio_path_to_use, sr=48000, mono=True)
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
            try:
                from steps.common.memory_commit_events import MemoryCommitEvent, emit_memory_commit_event, utc_now_iso

                scene_id = item.get("scene_id") or item.get("scene_index")
                if scene_id is not None and not isinstance(scene_id, str):
                    scene_id = f"scene_{int(scene_id):04d}"
                elif scene_id is not None:
                    scene_id = str(scene_id)
                emit_memory_commit_event(
                    cfg,
                    MemoryCommitEvent(
                        ts_utc=utc_now_iso(),
                        scene_id=scene_id,
                        video_id=str(item.get("video_id")) if item.get("video_id") is not None else None,
                        modality=str(item.get("modality") or "audio") or "audio",
                        model="laion/clap-htsat-unfused",
                        embedding_id=None,
                        component="audio_embed_clap",
                        attempted=False,
                        committed=False,
                        reason="no_index_path",
                        targets={"faiss": {"attempted": False, "committed": False, "ref": None, "reason": "no_index_path"}},
                        details={"source_path": path},
                    ),
                )
            except Exception:
                pass
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
        except Exception as e:
            index.add(feats.astype("float32"))
            # best-effort: last ID is ntotal-1 but only valid for flat add
            faiss_id = getattr(index, 'ntotal', 0) - 1
        faiss.write_index(index, index_path)
        faiss_ok = True

        # Optional Qdrant dual-write
        qdrant_attempted = False
        qdrant_ok = False
        qdrant_reason = None
        qdrant_collection = None
        try:
            q_client = build_qdrant_client(cfg, dim=feats.shape[1], key="audio")
            if q_client:
                qdrant_collection = getattr(getattr(q_client, "cfg", None), "collection", None)
                qdrant_attempted = True
                qdrant_ok = bool(q_client.upsert([{
                    "id": h,
                    "vector": feats[0].tolist(),
                    "payload": {
                        "source_path": path,
                        "modality": "audio",
                        "faiss_id": faiss_id,
                    }
                }]))
                if not qdrant_ok:
                    qdrant_reason = "upsert_failed"
        except Exception as e:
            qdrant_attempted = True
            qdrant_ok = False
            qdrant_reason = f"exception:{type(e).__name__}"
            pass
        # Map FAISS ID -> fingerprint/source in dedicated SQLite
        map_db = (cfg.get("paths", {}) or {}).get("clap_id_map_db")
        map_ok = False
        map_reason = None
        if map_db:
            try:
                _ensure_clap_map(map_db)
                con = sqlite3.connect(map_db, check_same_thread=False)
                with con:
                    con.execute(
                        "INSERT OR REPLACE INTO clap_id_map(faiss_id, hash, source_path, created_at) VALUES (?,?,?,?)",
                        (faiss_id, h, path, datetime.utcnow().isoformat()),
                    )
                map_ok = True
            except Exception as e:
                map_reason = f"exception:{type(e).__name__}"
                print(f'[ERROR] Exception in step.py line 111: {str(e)}')
                pass
            finally:
                try:
                    con.close()  # type: ignore
                except Exception as e:
                    print(f'[ERROR] Exception in step.py line 117: {str(e)}')
                    pass
        # Upsert generic embedding metadata for recall
        embedding_ok = False
        embedding_reason = None
        try:
            from steps.common.memory import upsert_embedding
            scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            upsert_embedding(cfg, h, faiss_id, path, item.get("modality", "audio") or "audio", scene_id=scene_id)
            embedding_ok = True
        except Exception as e:
            embedding_reason = f"exception:{type(e).__name__}"
            print(f'[ERROR] Exception in step.py line 124: {str(e)}')
            pass

        try:
            from steps.common.memory_commit_events import MemoryCommitEvent, emit_memory_commit_event, utc_now_iso

            scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            elif scene_id is not None:
                scene_id = str(scene_id)
            emit_memory_commit_event(
                cfg,
                MemoryCommitEvent(
                    ts_utc=utc_now_iso(),
                    scene_id=scene_id,
                    video_id=str(item.get("video_id")) if item.get("video_id") is not None else None,
                    modality=str(item.get("modality") or "audio") or "audio",
                    model="laion/clap-htsat-unfused",
                    embedding_id=h,
                    component="audio_embed_clap",
                    targets={
                        "faiss": {"attempted": True, "committed": bool(faiss_ok), "ref": index_path, "reason": None if faiss_ok else "write_failed"},
                        "qdrant": {"attempted": bool(qdrant_attempted), "committed": bool(qdrant_ok), "ref": qdrant_collection, "reason": qdrant_reason},
                        "sqlite_map": {"attempted": bool(map_db), "committed": bool(map_ok), "ref": map_db, "reason": map_reason},
                        "sqlite_embeddings": {
                            "attempted": True,
                            "committed": bool(embedding_ok),
                            "ref": (cfg.get("paths", {}) or {}).get("db_path"),
                            "reason": embedding_reason,
                        },
                    },
                    details={"faiss_id": faiss_id, "source_path": path},
                ),
            )
        except Exception:
            pass
        return {"clap_meta": {"status": "ok", "index_path": index_path, "faiss_id": faiss_id}}
    except Exception as e:
        return {"clap_meta": {"status": "error", "error": str(e)}}
