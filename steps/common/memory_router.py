from __future__ import annotations

from typing import Any, Dict, List, Optional

from steps.common.memory_store import MemoryStore, MemoryConfig, MemoryDims


class MemoryRouter:
    """
    Simple router placeholder for tiered memory.
    Intent-aware routing to be filled in alongside read/write paths.
    """

    def __init__(self, stores: Dict[str, MemoryStore], config: Optional[MemoryConfig] = None):
        self.stores = stores
        self.config = config or MemoryConfig(
            read_priority=["qdrant", "faiss", "chroma"],
            write_targets=["faiss", "qdrant"],
            dims=MemoryDims(),
        )

    def _filter_vectors_for_store(self, vectors: List[Dict[str, Any]], store: MemoryStore) -> List[Dict[str, Any]]:
        """Drop vectors that don't match the expected dimension for the store/modality."""
        if not vectors:
            return []
        store_dim = getattr(store, "dim", None)
        filtered: List[Dict[str, Any]] = []
        for v in vectors:
            vec = v.get("vector")
            if not isinstance(vec, list):
                continue
            expected = store_dim
            if expected is None:
                modality = v.get("modality") or (v.get("payload") or {}).get("modality")
                expected = self.config.expected_dim_for_modality(modality)
            if expected and len(vec) != expected:
                # Skip vectors with mismatched dimension
                continue
            filtered.append(v)
        return filtered

    def insert(self, vectors: List[Dict[str, Any]]) -> Dict[str, bool]:
        results: Dict[str, bool] = {}
        for target in self.config.write_targets:
            store = self.stores.get(target)
            if not store:
                results[target] = False
                continue
            try:
                payload = self._filter_vectors_for_store(vectors, store)
                results[target] = store.insert(payload) if payload else False
            except Exception:
                results[target] = False
        return results

    def query(self, query_vector: List[float], top_k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        # Iterate by read priority; return first non-empty result
        for tier in self.config.read_priority:
            store = self.stores.get(tier)
            if not store:
                continue
            try:
                store_dim = getattr(store, "dim", None)
                if store_dim and query_vector and len(query_vector) != store_dim:
                    continue
                hits = store.query(query_vector, top_k=top_k, filter=filter)
                if hits:
                    return hits
            except Exception:
                continue
        return []

    def stats(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"tiers": {}}
        for name, store in self.stores.items():
            try:
                out["tiers"][name] = store.stats()
            except Exception:
                out["tiers"][name] = {"available": False}
        out["routing"] = {
            "read_priority": self.config.read_priority,
            "write_targets": self.config.write_targets,
        }
        return out
