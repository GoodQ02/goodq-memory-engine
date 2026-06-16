from __future__ import annotations
from typing import Any, Dict
from contextlib import nullcontext
import sqlite3
from datetime import datetime
import os
import logging
import sys
from steps.common.faiss_utils import add_with_required_ids, create_hnsw_id_index, FaissLock

logger = logging.getLogger(__name__)

# Import GPU manager for centralized GPU configuration
try:
    from scripts.gpu_config import setup_step_gpu, GPUManager
except ImportError as exc:
    logger.warning("[WARN] scripts.gpu_config unavailable; using CPU fallback: %s", exc)

    def setup_step_gpu(step_name):
        return {"device": "cpu", "step_name": step_name}

    class GPUManager:
        @staticmethod
        def clear_cache():
            pass

from steps.text_embed.step import _content_fingerprint
from steps.common.qdrant_client import build_qdrant_client


_CLIP = {"model": None, "proc": None, "device": "cpu"}


def _debug_env() -> None:
    """
    Lightweight one-shot debug writer to capture interpreter/path for import issues.
    """
    try:
        lines = [
            "=== DEBUG: image_embed_clip start ===",
            f"PID: {os.getpid()}",
            f"sys.executable: {sys.executable}",
            "sys.path (first 10):",
        ]
        lines.extend(f"  {p}" for p in sys.path[:10])
        try:
            import steps  # noqa: F401
            lines.append(f"steps module: {getattr(steps, '__file__', 'NO __file__')}")
        except Exception as e:  # pragma: no cover - diagnostics only
            lines.append(f"FAILED to import steps: {repr(e)}")
        log_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "logs", "debug_image_embed_clip_env.log"))
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n\n")
    except Exception:
        pass


def _load() -> None:
    if _CLIP["model"] is not None:
        return
    
    # Configure GPU using centralized manager (Phase 3)
    gpu_config = setup_step_gpu("image_embed_clip")
    device = gpu_config["device"]
    
    try:
        import torch  # type: ignore
        from transformers import CLIPModel, CLIPProcessor  # type: ignore
        from pathlib import Path
        import yaml
        
        # Resolve repo_id and revision from registry
        repo_root = Path(__file__).resolve().parents[2]
        registry_path = repo_root / "configs" / "model_registry.yaml"
        repo_id = "openai/clip-vit-large-patch14"  # Default fallback
        revision = None
        if registry_path.exists():
            try:
                with open(registry_path, "r", encoding="utf-8") as f:
                    registry = yaml.safe_load(f) or {}
                repo_id = registry.get("huggingface_models", {}).get("clip_vit", {}).get("repo_id") or repo_id
                revision = registry.get("huggingface_models", {}).get("clip_vit", {}).get("revision") or revision
            except Exception:
                pass
        
        kwargs = {}
        if revision is not None:
            kwargs["revision"] = revision
        proc = CLIPProcessor.from_pretrained(repo_id, **kwargs)
        model = CLIPModel.from_pretrained(repo_id, **kwargs).to(device).eval()
        _CLIP.update({"model": model, "proc": proc, "device": device})
        logger.info(f"[OK] CLIP model ({repo_id}) loaded on {device} (revision: {revision})")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load CLIP model: {str(e)}")
        logger.info("[WARN]  Falling back to CPU mode")
        _CLIP.update({"model": None, "proc": None, "device": "cpu"})
        GPUManager.clear_cache()


def image_embed_clip(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"clip_meta": {"status": "no_file"}}
    index_path = (cfg.get("paths", {}) or {}).get("faiss_clip_path")
    if not index_path:
        return {"clip_meta": {"status": "no_index_path", "reason": "direct_faiss_index_unconfigured"}}
    _debug_env()
    _load()
    if _CLIP["model"] is None:
        return {"clip_meta": {"status": "unavailable"}}
    try:
        import torch  # type: ignore
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
        import faiss  # type: ignore
        img = Image.open(path).convert("RGB")
        # FIXED: Use proper CLIP processor with image input
        ipt = _CLIP["proc"](images=img, return_tensors="pt", padding=True)
        # Move inputs to device
        ipt = {k: v.to(_CLIP["device"]) for k, v in ipt.items()}
        
        # Get image embeddings with correct method
        with torch.no_grad():
            if _CLIP["device"] == "cuda":
                with torch.cuda.amp.autocast():
                    out = _CLIP["model"].get_image_features(**ipt)
            else:
                out = _CLIP["model"].get_image_features(**ipt)
        feats = out.detach().cpu().numpy().astype("float32")
        h = _content_fingerprint(item)
        import numpy as np  # type: ignore
        uid = np.array([int(h[:16], 16) % (2**63 - 1)], dtype='int64')
        faiss_id = int(uid[0])

        with FaissLock(index_path):
            if os.path.isfile(index_path):
                index = faiss.read_index(index_path)
            else:
                index = create_hnsw_id_index(faiss, feats.shape[1])
            add_with_required_ids(index, feats.astype("float32"), uid)
            faiss.write_index(index, index_path)

        # Resolve identity fields
        video_hash = item.get("video_hash") or item.get("video_id") or "unknown_video"
        epoch_id = os.path.basename((cfg.get("paths", {}) or {}).get("db_dir") or "") or "unknown_epoch"
        scene_id = item.get("scene_id") or item.get("scene_index")
        if scene_id is not None and not isinstance(scene_id, str):
            scene_id = f"scene_{int(scene_id):04d}"

        # Optional Qdrant dual-write
        qdrant_attempted = False
        qdrant_ok = False
        qdrant_reason = None
        qdrant_collection = None
        try:
            q_client = build_qdrant_client(cfg, dim=feats.shape[1], key="clip")
            if q_client:
                qdrant_attempted = True
                qdrant_collection = getattr(getattr(q_client, "cfg", None), "collection", None)
                qdrant_ok = bool(q_client.upsert([{
                    "id": h,
                    "vector": feats[0].tolist(),
                    "payload": {
                        "epoch_id": epoch_id,
                        "video_hash": video_hash,
                        "scene_id": scene_id,
                        "scene_hash": h,
                        "worker_name": "image_embed_clip",
                        "vector_model_tag": "openai/clip-vit-large-patch14",
                        "modality": "video",
                        "ucf_frame_id": None,
                        "source_path": path,
                        "faiss_id": faiss_id,
                        "ucf_promotion_status": "staged",
                    }
                }]))
                if not qdrant_ok:
                    qdrant_reason = "upsert_failed"
            else:
                qdrant_reason = "client_unavailable"
        except Exception as e:
            qdrant_attempted = True
            qdrant_ok = False
            qdrant_reason = f"exception:{type(e).__name__}"
            logger.warning(
                "image_embed_clip operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                "qdrant.upsert",
                path,
                type(e).__name__,
                e,
            )
        # map table
        map_db = (cfg.get("paths", {}) or {}).get("clip_id_map_db")
        map_ok = False
        map_reason = None
        if map_db:
            con = None
            try:
                os.makedirs(os.path.dirname(map_db), exist_ok=True)
                con = sqlite3.connect(map_db, check_same_thread=False)
                with con:
                    # Check schema and drop if outdated
                    cursor = con.execute("PRAGMA table_info(clip_id_map)")
                    info = cursor.fetchall()
                    pk_cols = [row[1] for row in info if row[5] > 0]
                    if info and set(pk_cols) != {"video_hash", "faiss_id"}:
                        con.execute("DROP TABLE clip_id_map")

                    con.execute(
                        """
                        CREATE TABLE IF NOT EXISTS clip_id_map (
                            video_hash TEXT,
                            faiss_id INTEGER,
                            hash TEXT,
                            source_path TEXT,
                            created_at TEXT,
                            epoch_id TEXT,
                            scene_id TEXT,
                            scene_hash TEXT,
                            worker_name TEXT,
                            vector_model_tag TEXT,
                            modality TEXT,
                            ucf_frame_id INTEGER,
                            PRIMARY KEY (video_hash, faiss_id)
                        )
                        """
                    )
                    con.execute(
                        """
                        INSERT OR REPLACE INTO clip_id_map(
                            faiss_id, hash, source_path, created_at,
                            epoch_id, video_hash, scene_id, scene_hash,
                            worker_name, vector_model_tag, modality, ucf_frame_id
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL)
                        """,
                        (
                            faiss_id, h, path, datetime.utcnow().isoformat(),
                            epoch_id, video_hash, scene_id, h,
                            "image_embed_clip", "openai/clip-vit-large-patch14", "video"
                        ),
                    )
                map_ok = True
            except Exception as e:
                map_reason = f"exception:{type(e).__name__}"
                logger.warning(
                    "image_embed_clip operation failed operation=%s map_db=%s exc_type=%s exc=%s",
                    "sqlite_map.upsert",
                    map_db,
                    type(e).__name__,
                    e,
                )
            finally:
                try:
                    if con is not None:
                        con.close()
                except Exception as e:
                    logger.warning(
                        "image_embed_clip operation failed operation=%s map_db=%s exc_type=%s exc=%s",
                        "sqlite_map.close",
                        map_db,
                        type(e).__name__,
                        e,
                    )
        # Upsert generic embedding metadata for recall. Keep CLIP distinct from
        # DINO so the shared keyframe hash does not collapse visual modalities.
        embedding_ok = False
        embedding_reason = None
        try:
            from steps.common.memory import upsert_embedding
            scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            upsert_embedding(cfg, h, faiss_id, path, "clip", scene_id=scene_id, vector=feats[0].tolist())
            embedding_ok = True
        except Exception as e:
            embedding_reason = f"exception:{type(e).__name__}"
            logger.warning(
                "image_embed_clip operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                "sqlite_embeddings.upsert",
                path,
                type(e).__name__,
                e,
            )
        clip_meta: Dict[str, Any] = {
            "status": "ok",
            "index_path": index_path,
            "faiss_id": faiss_id,
            "provenance_version": 1,
            "component": "image_embed_clip",
            "step": "image_embed_clip",
            "model": "openai/clip-vit-base-patch16",
            "embedding_id": h,
            "faiss_committed": True,
            "qdrant_attempted": bool(qdrant_attempted),
            "qdrant_committed": bool(qdrant_ok),
            "sqlite_map_attempted": bool(map_db),
            "sqlite_map_committed": bool(map_ok),
            "sqlite_embeddings_committed": bool(embedding_ok),
        }
        if qdrant_collection:
            clip_meta["qdrant_collection"] = qdrant_collection
        if qdrant_reason:
            clip_meta["qdrant_reason"] = qdrant_reason
        if map_reason:
            clip_meta["sqlite_map_reason"] = map_reason
        if embedding_reason:
            clip_meta["sqlite_embeddings_reason"] = embedding_reason
        return {"clip_meta": clip_meta}
    except Exception as e:
        print(f"[ERROR] CLIP embedding failed: {str(e)}")
        return {"clip_meta": {"status": "error", "error": str(e)}}
