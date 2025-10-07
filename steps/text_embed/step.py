from __future__ import annotations
from typing import Any, Dict, Optional

import os
import hashlib
import json

from zenml_project.steps.common.memory import upsert_embedding


_ST = None  # sentence-transformers model
_FAISS = None


def _load_st() -> Any:
    global _ST
    if _ST is not None:
        return _ST
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        import torch  # type: ignore

        device = "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
        _ST = SentenceTransformer("all-MiniLM-L6-v2", device=device)
    except Exception:
        _ST = None
    return _ST


def _open_faiss(path: str):
    global _FAISS
    try:
        import faiss  # type: ignore
    except Exception:
        return None, None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    index = None
    if os.path.isfile(path):
        try:
            index = faiss.read_index(path)
        except Exception:
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
        except Exception:
            h.update((src or "").encode("utf-8", errors="ignore"))
    else:
        h.update(repr(item).encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _gather_text(item: Dict[str, Any]) -> Optional[str]:
    # Pull text from known fields in priority order
    for k in ("frame_text", "transcript", "ocr_text", "caption"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return None


def text_embed(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    text = _gather_text(item)
    if not text:
        return {"embedding_meta": {"status": "no_text"}}

    model = _load_st()
    if model is None:
        return {"embedding_meta": {"status": "unavailable", "engine": "sentence-transformers"}}

    index_path = (cfg.get("paths", {}) or {}).get("faiss_index_path") or ""
    if not index_path:
        return {"embedding_meta": {"status": "no_index_path"}}

    try:
        vec = model.encode([text], normalize_embeddings=True)
        index, faiss = _open_faiss(index_path)
        if index is None or faiss is None:
            return {"embedding_meta": {"status": "faiss_unavailable"}}
        ids = None
        try:
            # Some faiss builds support add_with_ids; if not, fallback
            import numpy as np  # type: ignore
            uid_int = int(_content_fingerprint(item)[:16], 16) % (2**63 - 1)
            index.add_with_ids(vec.astype("float32"), np.array([uid_int], dtype="int64"))
            ids = [uid_int]
        except Exception:
            index.add(vec.astype("float32"))
        faiss.write_index(index, index_path)
        # persist mapping for recall/linking
        try:
            upsert_embedding(cfg, _content_fingerprint(item), (ids or [None])[0], item.get("source_path", ""), item.get("modality", ""))
        except Exception:
            pass
        return {"embedding_meta": {"status": "ok", "engine": "all-MiniLM-L6-v2", "index_path": index_path, "ids": ids}}
    except Exception as e:
        return {"embedding_meta": {"status": "error", "error": str(e)}}
