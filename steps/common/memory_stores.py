from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from steps.common.memory_store import MemoryStore
from steps.common.qdrant_client import QdrantClient, build_qdrant_client


class ChromaMemory(MemoryStore):
    """Lightweight in-memory store for short-term embeddings."""

    def __init__(self, dim: int, ttl_seconds: int = 900, max_items: int = 512):
        self.dim = dim
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self._items: List[Dict[str, Any]] = []
        self._hits = 0
        self._misses = 0
        self._evicted = 0

    def _purge_expired(self) -> None:
        now = time.time()
        before = len(self._items)
        self._items = [it for it in self._items if now - it.get("ts", now) <= self.ttl_seconds]
        self._evicted += max(0, before - len(self._items))
        if len(self._items) > self.max_items:
            # drop oldest
            drop = len(self._items) - self.max_items
            self._items = self._items[drop:]
            self._evicted += drop

    def insert(self, vectors: List[Dict[str, Any]]) -> bool:
        if not vectors:
            return False
        self._purge_expired()
        now = time.time()
        for v in vectors:
            vec = v.get("vector")
            if not isinstance(vec, list) or len(vec) != self.dim:
                continue
            item = dict(v)
            item["ts"] = now
            item["hits"] = 0
            self._items.append(item)
        self._purge_expired()
        return True

    def query(self, query_vector: List[float], top_k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        import numpy as np  # type: ignore

        self._purge_expired()
        if not query_vector or len(query_vector) != self.dim or not self._items:
            self._misses += 1
            return []
        q = np.array(query_vector, dtype="float32")
        scores = []
        for item in self._items:
            vec = np.array(item["vector"], dtype="float32")
            denom = (np.linalg.norm(q) * np.linalg.norm(vec)) or 1e-9
            sim = float(np.dot(q, vec) / denom)
            scores.append(sim)
        order = np.argsort(scores)[::-1][:top_k]
        results: List[Dict[str, Any]] = []
        for idx in order:
            item = self._items[int(idx)]
            # basic filter support on payload keys
            if filter and isinstance(filter, dict):
                payload = item.get("payload") or {}
                ok = all(payload.get(k) == v for k, v in filter.items())
                if not ok:
                    continue
            item["hits"] = item.get("hits", 0) + 1
            results.append(
                {
                    "id": item.get("id"),
                    "score": float(scores[int(idx)]),
                    "payload": item.get("payload") or {},
                }
            )
        if results:
            self._hits += 1
        else:
            self._misses += 1
        return results

    def stats(self) -> Dict[str, Any]:
        self._purge_expired()
        return {
            "available": True,
            "vectors": len(self._items),
            "dim": self.dim,
            "hits": self._hits,
            "misses": self._misses,
            "evicted": self._evicted,
            "ttl_seconds": self.ttl_seconds,
            "max_items": self.max_items,
        }


class FaissMemory(MemoryStore):
    def __init__(self, index_path: str, dim: int, db_path: Optional[str] = None):
        self.index_path = index_path
        self.dim = dim
        self.db_path = db_path

    def _load_index(self):
        import faiss  # type: ignore
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        if os.path.isfile(self.index_path):
            return faiss.read_index(self.index_path), faiss
        index = faiss.IndexHNSWFlat(self.dim, 32)
        index.hnsw.efConstruction = 200
        index.hnsw.efSearch = 50
        faiss.write_index(index, self.index_path)
        return index, faiss

    def insert(self, vectors: List[Dict[str, Any]]) -> bool:
        if not self.index_path:
            return False
        try:
            index, faiss = self._load_index()
            import numpy as np  # type: ignore
            vecs = []
            ids = []
            for v in vectors:
                vec = v.get("vector")
                vid = v.get("id")
                if not isinstance(vec, list) or len(vec) != self.dim:
                    continue
                vecs.append(vec)
                if vid is not None:
                    ids.append(int(vid) % (2**63 - 1))
            if not vecs:
                return False
            np_vecs = np.array(vecs, dtype="float32")
            if ids:
                np_ids = np.array(ids, dtype="int64")
                index.add_with_ids(np_vecs, np_ids)
            else:
                index.add(np_vecs)
            faiss.write_index(index, self.index_path)
            return True
        except Exception:
            return False

    def query(self, query_vector: List[float], top_k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self.index_path or not os.path.isfile(self.index_path):
            return []
        if not query_vector or len(query_vector) != self.dim:
            return []
        try:
            import faiss  # type: ignore
            import numpy as np  # type: ignore
            index = faiss.read_index(self.index_path)
            D, I = index.search(np.array([query_vector], dtype="float32"), k=top_k)
            ids = I[0] if len(I) else []
            scores = D[0] if len(D) else []
            out = []
            for i, s in zip(ids, scores):
                out.append({"id": int(i), "score": float(s), "payload": {}})
            try:
                from steps.common.memory_provenance import attach_provenance_to_hits

                attach_provenance_to_hits(self.db_path, out)
            except Exception:
                pass
            return out
        except Exception:
            return []

    def stats(self) -> Dict[str, Any]:
        try:
            import faiss  # type: ignore
            if os.path.isfile(self.index_path):
                idx = faiss.read_index(self.index_path)
                return {"available": True, "vectors": int(getattr(idx, "ntotal", 0)), "dim": self.dim}
        except Exception:
            pass
        return {"available": False, "vectors": 0, "dim": self.dim}


class QdrantMemory(MemoryStore):
    def __init__(self, client: QdrantClient):
        self.client = client
        self.dim = getattr(client.cfg, "dim", None)

    def insert(self, vectors: List[Dict[str, Any]]) -> bool:
        return self.client.upsert(vectors)

    def query(self, query_vector: List[float], top_k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return self.client.query(query_vector, top_k=top_k, payload_filter=filter)

    def stats(self) -> Dict[str, Any]:
        return {"available": True, "collection": getattr(self.client, "cfg", None).collection if getattr(self.client, "cfg", None) else None}


def build_text_stores(cfg: Dict[str, Any]) -> Dict[str, MemoryStore]:
    stores: Dict[str, MemoryStore] = {}
    paths = (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}
    memory_cfg = (cfg.get("memory") or {}) if isinstance(cfg, dict) else {}
    dims_cfg = (memory_cfg.get("dims") or {})
    ttl_seconds = memory_cfg.get("ttl_seconds", 900)
    max_ephemeral = memory_cfg.get("max_ephemeral_items", 512)
    text_dim = dims_cfg.get("text", 384)
    stores["chroma"] = ChromaMemory(text_dim, ttl_seconds=ttl_seconds, max_items=max_ephemeral)
    faiss_path = paths.get("faiss_index_path") or ""
    if faiss_path:
        stores["faiss"] = FaissMemory(faiss_path, text_dim, db_path=paths.get("db_path"))
    q_client = None
    try:
        q_client = build_qdrant_client(cfg, dim=text_dim, key="text")
    except Exception:
        q_client = None
    if q_client:
        stores["qdrant"] = QdrantMemory(q_client)
    # Chroma placeholder (not implemented)
    return stores
