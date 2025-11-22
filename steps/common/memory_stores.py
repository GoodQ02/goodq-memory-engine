from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from steps.common.memory_store import MemoryStore
from steps.common.qdrant_client import QdrantClient, build_qdrant_client


class FaissMemory(MemoryStore):
    def __init__(self, index_path: str, dim: int):
        self.index_path = index_path
        self.dim = dim

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
    text_dim = dims_cfg.get("text", 384)
    faiss_path = paths.get("faiss_index_path") or ""
    if faiss_path:
        stores["faiss"] = FaissMemory(faiss_path, text_dim)
    q_client = None
    try:
        q_client = build_qdrant_client(cfg, dim=text_dim, key="text")
    except Exception:
        q_client = None
    if q_client:
        stores["qdrant"] = QdrantMemory(q_client)
    # Chroma placeholder (not implemented)
    return stores
