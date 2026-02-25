from __future__ import annotations
from typing import Any, Dict, Optional
from contextlib import nullcontext
import sqlite3
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

# Import GPU manager for centralized GPU configuration
try:
    from gpu_config import setup_step_gpu, GPUManager
except ImportError:
    try:
        from gpu_config import setup_step_gpu, GPUManager
    except ImportError:
        def setup_step_gpu(step_name):
            return {"device": "cpu", "step_name": step_name}
        class GPUManager:
            @staticmethod
            def clear_cache():
                pass


_DINO = {"model": None, "proc": None, "device": "cpu"}


def _load() -> None:
    if _DINO["model"] is not None:
        return
    
    # Configure GPU using centralized manager (Phase 3)
    gpu_config = setup_step_gpu("image_embed_dino")
    device = gpu_config["device"]
    
    try:
        import torch  # type: ignore
        from transformers import AutoModel, AutoProcessor  # type: ignore
        
        proc = AutoProcessor.from_pretrained("facebook/dinov2-base")
        model = AutoModel.from_pretrained("facebook/dinov2-base").to(device).eval()
        _DINO.update({"model": model, "proc": proc, "device": device})
        logger.info(f"[OK] DINO model loaded on {device} (GPU config: {gpu_config['memory_fraction']:.1%} memory)")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load DINO model: {str(e)}")
        logger.info("[WARN]  Falling back to CPU mode")
        _DINO.update({"model": None, "proc": None, "device": "cpu"})
        GPUManager.clear_cache()


def image_embed_dino(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"dino_meta": {"status": "no_file"}}
    _load()
    if _DINO["model"] is None:
        return {"dino_meta": {"status": "unavailable"}}
    try:
        import torch  # type: ignore
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
        from steps.text_embed.step import _content_fingerprint
        import faiss  # type: ignore

        img = Image.open(path).convert("RGB")
        ipt = _DINO["proc"](images=img, return_tensors="pt").to(_DINO["device"])
        with np.errstate(all='ignore'):
            if _DINO["device"] == "cuda":
                with torch.cuda.amp.autocast():
                    out = _DINO["model"](**ipt)
            else:
                out = _DINO["model"](**ipt)
        feats = out.last_hidden_state[:, 0, :].detach().cpu().numpy().astype("float32")
        # write to faiss
        index_path = (cfg.get("paths", {}) or {}).get("faiss_dino_path")
        if not index_path:
            return {"dino_meta": {"status": "no_index_path"}}
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        if os.path.isfile(index_path):
            index = faiss.read_index(index_path)
        else:
            index = faiss.IndexHNSWFlat(feats.shape[1], 32)
            index.hnsw.efConstruction = 200
            index.hnsw.efSearch = 50

        # stable ID from content fingerprint
        from steps.text_embed.step import _content_fingerprint
        h = _content_fingerprint(item)
        try:
            import numpy as np  # type: ignore
            uid = np.array([int(h[:16], 16) % (2**63 - 1)], dtype='int64')
            index.add_with_ids(feats.astype("float32"), uid)
            faiss_id = int(uid[0])
        except Exception as e:
            logger.warning(
                "image_embed_dino operation fallback operation=%s source_path=%s exc_type=%s exc=%s",
                "faiss.add_with_ids_to_add",
                path,
                type(e).__name__,
                e,
            )
            index.add(feats.astype("float32"))
            faiss_id = getattr(index, 'ntotal', 0) - 1
        faiss.write_index(index, index_path)
        # map table
        map_db = (cfg.get("paths", {}) or {}).get("dino_id_map_db")
        if map_db:
            try:
                os.makedirs(os.path.dirname(map_db), exist_ok=True)
                con = sqlite3.connect(map_db, check_same_thread=False)
                with con:
                    con.execute(
                        "CREATE TABLE IF NOT EXISTS dino_id_map (faiss_id INTEGER PRIMARY KEY, hash TEXT, source_path TEXT, created_at TEXT)"
                    )
                    con.execute(
                        "INSERT OR REPLACE INTO dino_id_map(faiss_id, hash, source_path, created_at) VALUES (?,?,?,?)",
                        (faiss_id, h, path, datetime.utcnow().isoformat()),
                    )
            except Exception as e:
                logger.warning(
                    "image_embed_dino operation failed operation=%s map_db=%s exc_type=%s exc=%s",
                    "sqlite_map.upsert",
                    map_db,
                    type(e).__name__,
                    e,
                )
            finally:
                try:
                    con.close()  # type: ignore
                except Exception as e:
                    logger.warning(
                        "image_embed_dino operation failed operation=%s map_db=%s exc_type=%s exc=%s",
                        "sqlite_map.close",
                        map_db,
                        type(e).__name__,
                        e,
                    )
        # Upsert generic embedding metadata for recall
        # NOTE: DINO uses modality="image" (not "dino") by design.
        # This allows DINO and CLIP embeddings to be queried together as visual content.
        # To distinguish: check dino_id_map.sqlite or the specific FAISS index used.
        # See docs/ARCHITECTURE_REFERENCE.md for full explanation.
        try:
            from steps.common.memory import upsert_embedding
            scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            upsert_embedding(cfg, h, faiss_id, path, item.get("modality", "image") or "image", scene_id=scene_id)
        except Exception as e:
            logger.warning(
                "image_embed_dino operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                "sqlite_embeddings.upsert",
                path,
                type(e).__name__,
                e,
            )
        return {"dino_meta": {"status": "ok", "index_path": index_path, "faiss_id": faiss_id}}
    except Exception as e:
        return {"dino_meta": {"status": "error", "error": str(e)}}
