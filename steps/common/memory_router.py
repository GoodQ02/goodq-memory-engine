from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from steps.common.memory_store import (
    MemoryStore,
    MemoryConfig,
    MemoryDims,
    normalize_memory_tier_list,
    normalize_memory_tier_name,
)

logger = logging.getLogger(__name__)


class MemoryRouter:
    """
    Tiered vector memory router for canonical Qdrant retrieval, optional FAISS parity,
    and a legacy-named in-memory cache tier.
    """

    def __init__(self, stores: Dict[str, MemoryStore], config: Optional[MemoryConfig] = None):
        self.stores = stores
        self.config = config or MemoryConfig(
            read_priority=["qdrant", "faiss", "ephemeral"],
            write_targets=["faiss", "qdrant"],
            dims=MemoryDims(),
        )
        self.config.read_priority = normalize_memory_tier_list(self.config.read_priority)
        self.config.write_targets = normalize_memory_tier_list(self.config.write_targets)
        self._hits: Dict[str, int] = {k: 0 for k in stores.keys()}
        self._misses: Dict[str, int] = {k: 0 for k in stores.keys()}
        self._promotions: int = 0
        self._evictions: int = 0

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
        debug = os.environ.get("GOODQ_VECTOR_DEBUG", "").strip().lower() in ("1", "true", "yes", "y", "on")
        results: Dict[str, bool] = {}
        if debug:
            try:
                modalities: Dict[str, int] = {}
                for v in vectors or []:
                    if not isinstance(v, dict):
                        continue
                    mod = v.get("modality") or (v.get("payload") or {}).get("modality") or (v.get("payload") or {}).get("model") or "unknown"
                    modalities[str(mod)] = modalities.get(str(mod), 0) + 1
                print(
                    f"[VECTOR_DEBUG] router.insert vectors={len(vectors or [])} targets={self.config.write_targets}"
                    f" stores={list(self.stores.keys())} modalities={modalities}"
                )
            except Exception as e:
                logger.warning(
                    "memory_router operation failed operation=%s target=%s exc_type=%s exc=%s",
                    "insert.debug_summary",
                    "n/a",
                    type(e).__name__,
                    e,
                )
        for target in self.config.write_targets:
            canonical_target = normalize_memory_tier_name(target) or target
            store = self.stores.get(canonical_target)
            if not store:
                results[canonical_target] = False
                logger.warning(
                    "memory_router store unavailable operation=%s target=%s",
                    "insert",
                    canonical_target,
                )
                print("[STAGE10_16_DEBUG] memory_router_target:", canonical_target)
                print("[STAGE10_16_DEBUG] memory_router_vector_len:", 0)
                print("[STAGE10_16_DEBUG] memory_router_upsert_return:", results[canonical_target])
                if debug:
                    print(f"[VECTOR_DEBUG] router.target missing target={canonical_target}")
                continue
            try:
                payload = self._filter_vectors_for_store(vectors, store)
                vector_len = 0
                if payload:
                    first = payload[0] if isinstance(payload[0], dict) else {}
                    first_vec = first.get("vector") if isinstance(first, dict) else None
                    if isinstance(first_vec, list):
                        vector_len = len(first_vec)
                print("[STAGE10_16_DEBUG] memory_router_target:", canonical_target)
                print("[STAGE10_16_DEBUG] memory_router_vector_len:", vector_len)
                if debug:
                    print(
                        f"[VECTOR_DEBUG] router.target target={canonical_target} store={store.__class__.__name__}"
                        f" dim={getattr(store, 'dim', None)} filtered={len(payload)}"
                    )
                results[canonical_target] = store.insert(payload) if payload else False
                print("[STAGE10_16_DEBUG] memory_router_upsert_return:", results[canonical_target])
                if debug:
                    print(f"[VECTOR_DEBUG] router.target result target={canonical_target} ok={results[canonical_target]}")
            except Exception as e:
                logger.warning(
                    "memory_router operation failed operation=%s target=%s exc_type=%s exc=%s",
                    "insert",
                    canonical_target,
                    type(e).__name__,
                    e,
                )
                results[canonical_target] = False
                print("[STAGE10_16_DEBUG] memory_router_target:", canonical_target)
                print("[STAGE10_16_DEBUG] memory_router_vector_len:", 0)
                print("[STAGE10_16_DEBUG] memory_router_upsert_return:", results[canonical_target])
                if debug:
                    print(f"[VECTOR_DEBUG] router.target exception target={canonical_target}")
        return results

    def query(self, query_vector: List[float], top_k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        # Iterate by read priority; return first non-empty result
        for tier in self.config.read_priority:
            canonical_tier = normalize_memory_tier_name(tier) or tier
            store = self.stores.get(canonical_tier)
            if not store:
                continue
            try:
                store_dim = getattr(store, "dim", None)
                if store_dim and query_vector and len(query_vector) != store_dim:
                    continue
                hits = store.query(query_vector, top_k=top_k, filter=filter)
                if hits:
                    self._hits[canonical_tier] = self._hits.get(canonical_tier, 0) + 1
                    # Promotion: if we hit tier-0, push to higher tiers
                    if canonical_tier == "ephemeral":
                        promote_targets = [t for t in self.config.write_targets if t != "ephemeral"]
                        if promote_targets:
                            promote_vectors = [{"vector": h.get("vector", query_vector), "payload": h.get("payload", {})} for h in hits]
                            promoted_any = False
                            for promote_target in promote_targets:
                                promote_store = self.stores.get(promote_target)
                                if not promote_store:
                                    continue
                                payload = self._filter_vectors_for_store(promote_vectors, promote_store)
                                if payload and promote_store.insert(payload):
                                    promoted_any = True
                            if promoted_any:
                                self._promotions += 1
                    return hits
            except Exception as e:
                logger.warning(
                    "memory_router operation failed operation=%s target=%s exc_type=%s exc=%s",
                    "query",
                    canonical_tier,
                    type(e).__name__,
                    e,
                )
            self._misses[canonical_tier] = self._misses.get(canonical_tier, 0) + 1
        return []

    def stats(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"tiers": {}}
        for name, store in self.stores.items():
            try:
                out["tiers"][name] = store.stats()
            except Exception as e:
                logger.warning(
                    "memory_router operation failed operation=%s target=%s exc_type=%s exc=%s",
                    "stats",
                    name,
                    type(e).__name__,
                    e,
                )
                out["tiers"][name] = {"available": False}
        out["routing"] = {
            "read_priority": self.config.read_priority,
            "write_targets": self.config.write_targets,
            "hits": self._hits,
            "misses": self._misses,
            "promotions": self._promotions,
            "evictions": self._evictions,
        }
        return out
