from __future__ import annotations
from typing import Any, Dict
from contextlib import nullcontext
import sqlite3
from datetime import datetime
import os
import logging
import sys

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
        
        proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")
        model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16").to(device).eval()
        _CLIP.update({"model": model, "proc": proc, "device": device})
        logger.info(f"[OK] CLIP model loaded on {device} (GPU config: {gpu_config['memory_fraction']:.1%} memory)")
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
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        if os.path.isfile(index_path):
            index = faiss.read_index(index_path)
        else:
            index = faiss.IndexHNSWFlat(feats.shape[1], 32)
            index.hnsw.efConstruction = 200
            index.hnsw.efSearch = 50
        # stable ID from content fingerprint
        h = _content_fingerprint(item)
        try:
            import numpy as np  # type: ignore
            uid = np.array([int(h[:16], 16) % (2**63 - 1)], dtype='int64')
            index.add_with_ids(feats.astype("float32"), uid)
            faiss_id = int(uid[0])
        except Exception as e:
            index.add(feats.astype("float32"))
            faiss_id = getattr(index, 'ntotal', 0) - 1
        faiss.write_index(index, index_path)

        # Optional Qdrant dual-write
        try:
            q_client = build_qdrant_client(cfg, dim=feats.shape[1], key="image")
            if q_client:
                q_client.upsert([{
                    "id": h,
                    "vector": feats[0].tolist(),
                    "payload": {
                        "source_path": path,
                        "modality": "image",
                        "faiss_id": faiss_id,
                    }
                }])
        except Exception:
            pass
        # map table
        map_db = (cfg.get("paths", {}) or {}).get("clip_id_map_db")
        if map_db:
            try:
                os.makedirs(os.path.dirname(map_db), exist_ok=True)
                con = sqlite3.connect(map_db, check_same_thread=False)
                with con:
                    con.execute(
                        "CREATE TABLE IF NOT EXISTS clip_id_map (faiss_id INTEGER PRIMARY KEY, hash TEXT, source_path TEXT, created_at TEXT)"
                    )
                    con.execute(
                        "INSERT OR REPLACE INTO clip_id_map(faiss_id, hash, source_path, created_at) VALUES (?,?,?,?)",
                        (faiss_id, h, path, datetime.utcnow().isoformat()),
                    )
            except Exception as e:
                print(f'[ERROR] Exception in step.py line 83: {str(e)}')
                pass
            finally:
                try:
                    con.close()  # type: ignore
                except Exception as e:
                    print(f'[ERROR] Exception in step.py line 89: {str(e)}')
                    pass
        # Upsert generic embedding metadata for recall
        # NOTE: CLIP uses modality="image" (not "clip") by design.
        # This allows CLIP and DINO embeddings to be queried together as visual content.
        # To distinguish: check clip_id_map.sqlite or the specific FAISS index used.
        # See docs/ARCHITECTURE_REFERENCE.md for full explanation.
        try:
            from steps.common.memory import upsert_embedding
            scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            upsert_embedding(cfg, h, faiss_id, path, item.get("modality", "image") or "image", scene_id=scene_id)
        except Exception as e:
            print(f'[ERROR] Exception in step.py line 96: {str(e)}')
            pass
        return {"clip_meta": {"status": "ok", "index_path": index_path, "faiss_id": faiss_id}}
    except Exception as e:
        print(f"[ERROR] CLIP embedding failed: {str(e)}")
        return {"clip_meta": {"status": "error", "error": str(e)}}
