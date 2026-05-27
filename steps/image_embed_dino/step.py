from __future__ import annotations
from typing import Any, Dict, Optional
from contextlib import nullcontext
import sqlite3
from datetime import datetime
import os
import logging
import json
import sys
from steps.common.faiss_utils import add_with_required_ids, create_hnsw_id_index

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


_DINO = {"model": None, "proc": None, "device": "cpu"}


def _resolve_device(requested_device: str) -> str:
    if os.getenv("GOODQ_DINO_FORCE_CPU", "").strip() == "1":
        return "cpu"
    return requested_device


def _amp_enabled(device: str) -> bool:
    if device != "cuda":
        return False
    return os.getenv("GOODQ_DINO_DISABLE_AMP", "").strip() != "1"


def _gpu_memory_snapshot(torch_module) -> Dict[str, Any]:
    if not getattr(torch_module, "cuda", None):
        return {"available": False}
    try:
        if not torch_module.cuda.is_available():
            return {"available": False}
        return {
            "available": True,
            "allocated_mb": round(float(torch_module.cuda.memory_allocated()) / (1024 * 1024), 2),
            "reserved_mb": round(float(torch_module.cuda.memory_reserved()) / (1024 * 1024), 2),
            "max_allocated_mb": round(float(torch_module.cuda.max_memory_allocated()) / (1024 * 1024), 2),
        }
    except Exception as exc:
        return {"available": "unknown", "error": str(exc)}


def _shape_for_log(value: Any) -> Optional[list[int]]:
    shape = getattr(value, "shape", None)
    if shape is None:
        return None
    try:
        return [int(dim) for dim in shape]
    except Exception:
        return None


def _log_dino_diagnostics(
    stage: str,
    *,
    source_path: str,
    device: str,
    image_size: Optional[tuple[int, int]] = None,
    tensor_shape: Optional[list[int]] = None,
    model_loaded_now: Optional[bool] = None,
    amp_enabled: Optional[bool] = None,
    gpu_memory: Optional[Dict[str, Any]] = None,
) -> None:
    payload = {
        "event": "image_embed_dino_diagnostics",
        "stage": stage,
        "source_path": source_path,
        "device": device,
        "image_size": list(image_size) if image_size else None,
        "tensor_shape": tensor_shape,
        "model_loaded_now": model_loaded_now,
        "amp_enabled": amp_enabled,
        "gpu_memory": gpu_memory,
    }
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)
    logger.info("image_embed_dino diagnostics %s", payload)


def _load() -> bool:
    if _DINO["model"] is not None:
        return False
    
    # Configure GPU using centralized manager (Phase 3)
    gpu_config = setup_step_gpu("image_embed_dino")
    device = _resolve_device(gpu_config["device"])
    
    try:
        import torch  # type: ignore
        from transformers import AutoModel, AutoProcessor  # type: ignore
        from pathlib import Path
        import yaml
        
        # Resolve repo_id from registry
        repo_root = Path(__file__).resolve().parents[2]
        registry_path = repo_root / "configs" / "model_registry.yaml"
        repo_id = "facebook/dinov2-large"  # Default fallback
        if registry_path.exists():
            try:
                with open(registry_path, "r", encoding="utf-8") as f:
                    registry = yaml.safe_load(f) or {}
                repo_id = registry.get("huggingface_models", {}).get("dinov2", {}).get("repo_id") or repo_id
            except Exception:
                pass
        
        proc = AutoProcessor.from_pretrained(repo_id)
        model = AutoModel.from_pretrained(repo_id).to(device).eval()
        _DINO.update({"model": model, "proc": proc, "device": device})
        logger.info(f"[OK] DINO model ({repo_id}) loaded on {device} (GPU config: {gpu_config['memory_fraction']:.1%} memory)")
        return True
    except Exception as e:
        logger.error(f"[FAIL] Failed to load DINO model: {str(e)}")
        logger.info("[WARN]  Falling back to CPU mode")
        _DINO.update({"model": None, "proc": None, "device": "cpu"})
        GPUManager.clear_cache()
        return False


def image_embed_dino(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"dino_meta": {"status": "no_file"}}
    index_path = (cfg.get("paths", {}) or {}).get("faiss_dino_path")
    if not index_path:
        return {"dino_meta": {"status": "no_index_path", "reason": "direct_faiss_index_unconfigured"}}
    model_loaded_now = _load()
    if _DINO["model"] is None:
        return {"dino_meta": {"status": "unavailable"}}
    image_size: Optional[tuple[int, int]] = None
    tensor_shape: Optional[list[int]] = None
    gpu_memory_before: Optional[Dict[str, Any]] = None
    amp_enabled = False
    try:
        import torch  # type: ignore
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
        from steps.text_embed.step import _content_fingerprint
        import faiss  # type: ignore

        img = Image.open(path).convert("RGB")
        image_size = getattr(img, "size", None)
        ipt = _DINO["proc"](images=img, return_tensors="pt").to(_DINO["device"])
        tensor_shape = _shape_for_log(ipt.get("pixel_values"))
        gpu_memory_before = _gpu_memory_snapshot(torch)
        amp_enabled = _amp_enabled(_DINO["device"])
        _log_dino_diagnostics(
            "before_inference",
            source_path=path,
            device=_DINO["device"],
            image_size=image_size,
            tensor_shape=tensor_shape,
            model_loaded_now=model_loaded_now,
            amp_enabled=amp_enabled,
            gpu_memory=gpu_memory_before,
        )
        with np.errstate(all='ignore'):
            autocast_ctx = (
                torch.amp.autocast(device_type="cuda", dtype=torch.float16)
                if amp_enabled
                else nullcontext()
            )
            with torch.inference_mode():
                with autocast_ctx:
                    out = _DINO["model"](**ipt)
        _log_dino_diagnostics(
            "after_inference",
            source_path=path,
            device=_DINO["device"],
            image_size=image_size,
            tensor_shape=tensor_shape,
            model_loaded_now=model_loaded_now,
            amp_enabled=amp_enabled,
            gpu_memory=_gpu_memory_snapshot(torch),
        )
        feats = out.last_hidden_state[:, 0, :].detach().cpu().numpy().astype("float32")
        # write to faiss
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        if os.path.isfile(index_path):
            index = faiss.read_index(index_path)
        else:
            index = create_hnsw_id_index(faiss, feats.shape[1])

        # stable ID from content fingerprint
        from steps.text_embed.step import _content_fingerprint
        h = _content_fingerprint(item)
        import numpy as np  # type: ignore
        uid = np.array([int(h[:16], 16) % (2**63 - 1)], dtype='int64')
        add_with_required_ids(index, feats.astype("float32"), uid)
        faiss_id = int(uid[0])
        faiss.write_index(index, index_path)
        # Optional Qdrant dual-write.
        qdrant_attempted = False
        qdrant_ok = False
        qdrant_reason = None
        qdrant_collection = None
        try:
            from steps.common.qdrant_client import build_qdrant_client

            q_client = build_qdrant_client(cfg, dim=feats.shape[1], key="dino")
            if q_client:
                qdrant_attempted = True
                qdrant_collection = getattr(getattr(q_client, "cfg", None), "collection", None)
                qdrant_ok = bool(q_client.upsert([{
                    "id": h,
                    "vector": feats[0].tolist(),
                    "payload": {
                        "source_path": path,
                        "modality": "dino",
                        "model": "dino",
                        "scene_id": item.get("scene_id"),
                        "video_id": item.get("video_id") or item.get("video_hash"),
                        "faiss_id": faiss_id,
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
                "image_embed_dino operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                "qdrant.upsert",
                path,
                type(e).__name__,
                e,
            )
        # map table
        map_db = (cfg.get("paths", {}) or {}).get("dino_id_map_db")
        map_ok = False
        map_reason = None
        if map_db:
            con = None
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
                map_ok = True
            except Exception as e:
                map_reason = f"exception:{type(e).__name__}"
                logger.warning(
                    "image_embed_dino operation failed operation=%s map_db=%s exc_type=%s exc=%s",
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
                        "image_embed_dino operation failed operation=%s map_db=%s exc_type=%s exc=%s",
                        "sqlite_map.close",
                        map_db,
                        type(e).__name__,
                        e,
                    )
        # Upsert generic embedding metadata for recall. Keep DINO distinct from
        # CLIP so the shared keyframe hash does not collapse visual modalities.
        embedding_ok = False
        embedding_reason = None
        try:
            from steps.common.memory import upsert_embedding
            scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            upsert_embedding(cfg, h, faiss_id, path, "dino", scene_id=scene_id, vector=feats[0].tolist())
            embedding_ok = True
        except Exception as e:
            embedding_reason = f"exception:{type(e).__name__}"
            logger.warning(
                "image_embed_dino operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                "sqlite_embeddings.upsert",
                path,
                type(e).__name__,
                e,
            )
        dino_meta: Dict[str, Any] = {
            "status": "ok",
            "index_path": index_path,
            "faiss_id": faiss_id,
            "provenance_version": 1,
            "component": "image_embed_dino",
            "step": "image_embed_dino",
            "model": "facebook/dinov2-base",
            "embedding_id": h,
            "faiss_committed": True,
            "qdrant_attempted": bool(qdrant_attempted),
            "qdrant_committed": bool(qdrant_ok),
            "sqlite_map_attempted": bool(map_db),
            "sqlite_map_committed": bool(map_ok),
            "sqlite_embeddings_committed": bool(embedding_ok),
        }
        if qdrant_collection:
            dino_meta["qdrant_collection"] = qdrant_collection
        if qdrant_reason:
            dino_meta["qdrant_reason"] = qdrant_reason
        if map_reason:
            dino_meta["sqlite_map_reason"] = map_reason
        if embedding_reason:
            dino_meta["sqlite_embeddings_reason"] = embedding_reason
        return {"dino_meta": dino_meta}
    except Exception as e:
        logger.exception(
            "image_embed_dino operation failed source_path=%s device=%s image_size=%s tensor_shape=%s model_loaded_now=%s amp_enabled=%s gpu_memory_before=%s",
            path,
            _DINO.get("device"),
            image_size,
            tensor_shape,
            model_loaded_now,
            amp_enabled,
            gpu_memory_before,
        )
        return {
            "dino_meta": {
                "status": "error",
                "error": str(e),
                "exc_type": type(e).__name__,
                "device": _DINO.get("device"),
                "image_size": list(image_size) if image_size else None,
                "tensor_shape": tensor_shape,
                "model_loaded_now": model_loaded_now,
                "amp_enabled": amp_enabled,
                "gpu_memory_before": gpu_memory_before,
            }
        }
