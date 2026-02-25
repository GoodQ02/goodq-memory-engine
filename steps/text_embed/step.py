from __future__ import annotations
from typing import Any, Dict, Optional

import os
import hashlib
import json
import logging

from steps.common.memory import upsert_embedding
from steps.common.memory_router import MemoryRouter
from steps.common.memory_stores import build_text_stores

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


_ST = None  # sentence-transformers model
_FAISS = None


def _load_st() -> Any:
    global _ST
    if _ST is not None:
        return _ST
    
    # Configure GPU using centralized manager (Phase 3)
    gpu_config = setup_step_gpu("text_embed")
    device = gpu_config["device"]
    
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        
        _ST = SentenceTransformer("all-MiniLM-L6-v2", device=device)
        mem_fraction = gpu_config.get("memory_fraction")
        if isinstance(mem_fraction, (int, float)):
            logger.info(f"[OK] SentenceTransformer loaded on {device} (GPU config: {mem_fraction:.1%} memory)")
        else:
            logger.info(f"[OK] SentenceTransformer loaded on {device}")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load SentenceTransformer: {str(e)}")
        logger.info("[WARN]  Falling back to CPU mode")
        _ST = None
        GPUManager.clear_cache()
    return _ST


def _open_faiss(path: str):
    global _FAISS
    try:
        import faiss  # type: ignore
    except Exception as e:
        logger.warning(
            "text_embed operation failed operation=%s index_path=%s exc_type=%s exc=%s",
            "open_faiss.import",
            path,
            type(e).__name__,
            e,
        )
        return None, None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    index = None
    if os.path.isfile(path):
        try:
            index = faiss.read_index(path)
        except Exception as e:
            logger.warning(
                "text_embed operation failed operation=%s index_path=%s exc_type=%s exc=%s",
                "open_faiss.read_index",
                path,
                type(e).__name__,
                e,
            )
            index = None
    if index is None:
        # HNSW index for cosine similarity
        dim = 384  # all-MiniLM-L6-v2
        index = faiss.IndexHNSWFlat(dim, 32)
        index.hnsw.efConstruction = 200
        index.hnsw.efSearch = 50
        faiss.write_index(index, path)
    _FAISS = faiss
    return index, faiss


def _content_fingerprint(item: Dict[str, Any]) -> str:
    h = hashlib.sha256()
    # Prefer explicit frame_text/text_override to generate a unique text hash
    txt_override = item.get("frame_text") or item.get("text_override")
    if isinstance(txt_override, str) and txt_override.strip():
        h.update(txt_override.encode("utf-8", errors="ignore"))
        return h.hexdigest()
    src = item.get("source_path")
    if isinstance(src, str) and os.path.isfile(src):
        try:
            with open(src, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
        except Exception as e:
            logger.warning(
                "text_embed operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                "content_fingerprint.read_source",
                src,
                type(e).__name__,
                e,
            )
            h.update((src or "").encode("utf-8", errors="ignore"))
    else:
        h.update(repr(item).encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _gather_text(item: Dict[str, Any]) -> Optional[str]:
    # Pull text from known fields in priority order
    for k in ("frame_text", "transcript", "text", "ocr_text", "caption"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v
    print(f'[WARN] _gather_text returning None')
    return None


def text_embed(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    text = _gather_text(item)
    if not text:
        return {"embedding_meta": {"status": "no_text"}}

    model = _load_st()
    if model is None:
        return {"embedding_meta": {"status": "unavailable", "engine": "sentence-transformers"}}

    try:
        vec = model.encode([text], normalize_embeddings=True)
        vector_list = vec.astype("float32")[0].tolist()

        # Route writes via MemoryRouter (faiss + qdrant as configured)
        stores = build_text_stores(cfg)
        router = MemoryRouter(stores)
        payload = {
            "id": _content_fingerprint(item),
            "vector": vector_list,
            "payload": {
                "source_path": item.get("source_path"),
                "modality": item.get("modality", "text"),
                "scene_id": item.get("scene_id") or item.get("scene_index"),
            },
        }
        router_results = router.insert([payload])

        # Persist mapping for recall/linking (FAISS id if available is not tracked here)
        embedding_ok = False
        embedding_reason = None
        try:
            scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            upsert_embedding(cfg, payload["id"], None, item.get("source_path", ""), item.get("modality", ""), scene_id=scene_id)
            embedding_ok = True
        except Exception as e:
            embedding_reason = f"exception:{type(e).__name__}"
            logger.warning(
                "text_embed operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                "sqlite_embeddings.upsert",
                item.get("source_path"),
                type(e).__name__,
                e,
            )

        try:
            from steps.common.memory_commit_events import MemoryCommitEvent, emit_memory_commit_event, utc_now_iso

            scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            elif scene_id is not None:
                scene_id = str(scene_id)

            qdrant_ref = None
            try:
                q_store = stores.get("qdrant")
                q_client = getattr(q_store, "client", None)
                qdrant_ref = getattr(getattr(q_client, "cfg", None), "collection", None)
            except Exception as e:
                logger.warning(
                    "text_embed operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                    "resolve_qdrant_ref",
                    item.get("source_path"),
                    type(e).__name__,
                    e,
                )
                qdrant_ref = None

            faiss_ref = None
            try:
                f_store = stores.get("faiss")
                faiss_ref = getattr(f_store, "index_path", None)
            except Exception as e:
                logger.warning(
                    "text_embed operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                    "resolve_faiss_ref",
                    item.get("source_path"),
                    type(e).__name__,
                    e,
                )
                faiss_ref = None

            targets = {}
            for target, ok in (router_results or {}).items():
                present = target in (stores or {})
                ref = qdrant_ref if target == "qdrant" else faiss_ref if target == "faiss" else None
                reason = None
                if not present:
                    reason = "store_missing"
                elif not ok:
                    reason = "insert_failed_or_filtered"
                targets[str(target)] = {"attempted": bool(present), "committed": bool(ok), "ref": ref, "reason": reason, "count": 1}
            targets["sqlite_embeddings"] = {
                "attempted": True,
                "committed": bool(embedding_ok),
                "ref": (cfg.get("paths", {}) or {}).get("db_path"),
                "reason": embedding_reason,
            }
            emit_memory_commit_event(
                cfg,
                MemoryCommitEvent(
                    ts_utc=utc_now_iso(),
                    scene_id=scene_id,
                    video_id=str(item.get("video_id")) if item.get("video_id") is not None else None,
                    modality=str((payload.get("payload") or {}).get("modality") or "text") or "text",
                    model="all-MiniLM-L6-v2",
                    embedding_id=str(payload.get("id")) if payload.get("id") is not None else None,
                    component="text_embed",
                    targets=targets,
                    details={"text_len": len(text) if isinstance(text, str) else None, "source_path": item.get("source_path")},
                ),
            )
        except Exception as e:
            logger.warning(
                "text_embed operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                "emit_memory_commit_event",
                item.get("source_path"),
                type(e).__name__,
                e,
            )

        return {"embedding_meta": {"status": "ok", "engine": "all-MiniLM-L6-v2"}}
    except Exception as e:
        logger.warning(
            "text_embed operation failed operation=%s source_path=%s exc_type=%s exc=%s",
            "embed_text",
            item.get("source_path"),
            type(e).__name__,
            e,
        )
        return {"embedding_meta": {"status": "error", "error": str(e)}}
