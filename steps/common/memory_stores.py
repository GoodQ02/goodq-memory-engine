from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict, List, Optional

from steps.common.memory import to_faiss_id
from steps.common.faiss_utils import add_with_required_ids, create_hnsw_id_index, FaissLock
from steps.common.memory_store import MemoryStore
from steps.common.qdrant_client import QdrantClient, build_qdrant_client
from steps.common.retrieval_events import (
    RetrievalEvent,
    emit_retrieval_events,
    normalize_retrieval_context,
    retrieval_events_enabled,
    utc_now_iso,
)
from steps.common import sqlite_read_authority

logger = logging.getLogger(__name__)


class EphemeralMemory(MemoryStore):
    """In-memory TTL cache for short-term embeddings, used as the tier-0 ephemeral store."""

    def __init__(
        self,
        dim: int,
        ttl_seconds: int = 900,
        max_items: int = 512,
        *,
        db_path: Optional[str] = None,
        log_dir: Optional[str] = None,
        log_retrieval_events: bool = True,
    ):
        self.dim = dim
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self.db_path = db_path
        self.log_dir = log_dir
        self.log_retrieval_events = log_retrieval_events
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
        try:
            context = normalize_retrieval_context(os.environ.get("GOODQ_RETRIEVAL_CONTEXT"))
            ts = utc_now_iso()
            events: List[RetrievalEvent] = []
            for h in results:
                if not isinstance(h, dict):
                    continue
                payload = h.get("payload") if isinstance(h.get("payload"), dict) else {}
                scene_id = payload.get("scene_id") if payload else None
                modality = payload.get("modality") if payload else None
                model = payload.get("model") if payload else None
                if modality is None and isinstance(payload.get("model"), str):
                    modality = payload.get("model")
                embedding_id = h.get("id")
                embedding_id_s = str(embedding_id) if embedding_id is not None else None
                events.append(
                    RetrievalEvent(
                        ts_utc=ts,
                        store="ephemeral",
                        retrieval_context=context,
                        embedding_id=embedding_id_s,
                        scene_id=str(scene_id) if scene_id is not None else None,
                        modality=str(modality) if modality is not None else None,
                        model=str(model) if model is not None else None,
                        score=h.get("score") if isinstance(h.get("score"), (int, float)) else None,
                        details={
                            "store_type": "ephemeral_cache",
                            "store_ref": "ephemeral_memory",
                            "ttl_seconds": self.ttl_seconds,
                        },
                    )
                )
            emit_retrieval_events(self.db_path, events, enabled=self.log_retrieval_events, log_dir=self.log_dir)
        except Exception as e:
            logger.warning(
                "memory_stores operation failed store=%s operation=%s exc_type=%s exc=%s",
                "ephemeral",
                "emit_retrieval_events",
                type(e).__name__,
                e,
            )
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


ChromaMemory = EphemeralMemory


class FaissMemory(MemoryStore):
    def __init__(
        self,
        index_path: str,
        dim: int,
        db_path: Optional[str] = None,
        *,
        log_dir: Optional[str] = None,
        log_retrieval_events: bool = True,
        cfg: Optional[Dict[str, Any]] = None,
    ):
        self.index_path = index_path
        self.dim = dim
        self.db_path = db_path
        self.log_dir = log_dir
        self.log_retrieval_events = log_retrieval_events
        self.cfg = cfg

    def _load_index(self):
        import faiss  # type: ignore
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        if os.path.isfile(self.index_path):
            return faiss.read_index(self.index_path), faiss
        index = create_hnsw_id_index(faiss, self.dim)
        faiss.write_index(index, self.index_path)
        return index, faiss

    def insert(self, vectors: List[Dict[str, Any]]) -> bool:
        if not self.index_path:
            return False
        try:
            with FaissLock(self.index_path):
                index, faiss = self._load_index()
                import numpy as np  # type: ignore
                vecs = []
                ids = []
                missing_id_count = 0
                for v in vectors:
                    vec = v.get("vector")
                    vid = v.get("id")
                    if not isinstance(vec, list) or len(vec) != self.dim:
                        continue
                    vecs.append(vec)
                    if vid is not None:
                        ids.append(to_faiss_id(vid))
                    else:
                        missing_id_count += 1
                if not vecs:
                    return False
                if missing_id_count or len(ids) != len(vecs):
                    logger.warning(
                        "memory_stores operation failed store=%s operation=%s index_path=%s reason=%s vector_count=%s id_count=%s missing_id_count=%s",
                        "faiss",
                        "insert",
                        self.index_path,
                        "explicit_ids_required",
                        len(vecs),
                        len(ids),
                        missing_id_count,
                    )
                    return False
                np_vecs = np.array(vecs, dtype="float32")
                np_ids = np.array(ids, dtype="int64")
                add_with_required_ids(index, np_vecs, np_ids)
                faiss.write_index(index, self.index_path)
                return True
        except Exception as e:
            logger.warning(
                "memory_stores operation failed store=%s operation=%s index_path=%s exc_type=%s exc=%s",
                "faiss",
                "insert",
                self.index_path,
                type(e).__name__,
                e,
            )
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
            except Exception as e:
                logger.warning(
                    "memory_stores operation failed store=%s operation=%s index_path=%s exc_type=%s exc=%s",
                    "faiss",
                    "attach_provenance",
                    self.index_path,
                    type(e).__name__,
                    e,
                )

            # Shadow-Mode scoring comparison
            if self.db_path and os.path.isfile(self.db_path) and len(out) > 0:
                try:
                    quant_routing = (self.cfg or {}).get("memory", {}).get("routing", {}) if self.cfg else {}
                    shadow_mode = bool(quant_routing.get("quantization_shadow_mode", True))
                    if shadow_mode:
                        valid_ids = [h["id"] for h in out if h["id"] is not None]
                        if valid_ids:
                            conn = sqlite_read_authority.open_sqlite_read_connection(
                                self.db_path
                            )
                            try:
                                placeholders = ",".join("?" for _ in valid_ids)
                                cursor = conn.execute(
                                    f"""
                                    SELECT faiss_id, tq_indices, tq_norm, tq_qjl_sign, tq_norm_residual
                                    FROM embeddings
                                    WHERE faiss_id IN ({placeholders})
                                    """,
                                    valid_ids
                                )
                                rows = cursor.fetchall()
                            finally:
                                conn.close()

                            sidecars = {}
                            for r_id, tq_idx_b, tq_norm_val, tq_sign_b, tq_res_val in rows:
                                if (tq_idx_b is not None and tq_norm_val is not None 
                                        and tq_sign_b is not None and tq_res_val is not None):
                                    sidecars[r_id] = {
                                        "tq_indices": np.frombuffer(tq_idx_b, dtype=np.uint8),
                                        "tq_norm": tq_norm_val,
                                        "tq_qjl_sign": np.frombuffer(tq_sign_b, dtype=np.int8),
                                        "tq_norm_residual": tq_res_val
                                    }

                            if sidecars:
                                from steps.common.quantization import TurboQuantEncoder
                                encoder = TurboQuantEncoder()
                                q_arr = np.array(query_vector, dtype=np.float32)
                                norm_q_sq = float(np.linalg.norm(q_arr) ** 2)

                                quant_scores = []
                                for h in out:
                                    fid = h["id"]
                                    if fid in sidecars:
                                        sc = sidecars[fid]
                                        try:
                                            est_ip = encoder.estimate_inner_product(
                                                q_arr,
                                                sc["tq_indices"],
                                                sc["tq_norm"],
                                                sc["tq_qjl_sign"],
                                                sc["tq_norm_residual"]
                                            )
                                            tq_norm_sq = float(sc["tq_norm"] ** 2)
                                            # FAISS index is L2 metric (IndexHNSWFlat): distance squared
                                            est_score = norm_q_sq + tq_norm_sq - 2.0 * est_ip
                                            quant_scores.append((fid, h["score"], est_score))
                                        except Exception as est_exc:
                                            logger.debug("Failed to estimate inner product: %s", est_exc)

                                if len(quant_scores) >= 2:
                                    # Sort both by score ascending (smaller L2 distance is better)
                                    baseline_sorted = sorted(quant_scores, key=lambda x: x[1])
                                    quant_sorted = sorted(quant_scores, key=lambda x: x[2])

                                    # Rank Overlap (Precision at K)
                                    K = min(len(quant_scores), 5)
                                    baseline_top_k = {item[0] for item in baseline_sorted[:K]}
                                    quant_top_k = {item[0] for item in quant_sorted[:K]}
                                    rank_overlap = len(baseline_top_k.intersection(quant_top_k)) / K

                                    # Score Drift: Mean Absolute Difference (MAD)
                                    differences = [abs(orig - est) for _, orig, est in quant_scores]
                                    score_drift = float(np.mean(differences)) if differences else 0.0

                                    # Spearman's Rank Correlation (rho_s)
                                    baseline_ranks = {item[0]: idx for idx, item in enumerate(baseline_sorted)}
                                    quant_ranks = {item[0]: idx for idx, item in enumerate(quant_sorted)}

                                    n = len(quant_scores)
                                    d_squared_sum = sum((baseline_ranks[fid] - quant_ranks[fid]) ** 2 for fid in baseline_ranks)
                                    spearman_rho = 1.0 - (6.0 * d_squared_sum) / (n * (n**2 - 1)) if n > 1 else 1.0

                                    logger.info(
                                        "TurboQuant shadow mode query metrics: rank_overlap=%.4f score_drift=%.4f spearman_rho=%.4f candidates=%d",
                                        rank_overlap,
                                        score_drift,
                                        spearman_rho,
                                        len(quant_scores)
                                    )
                except Exception as shadow_exc:
                    logger.warning(
                        "memory_stores operation failed store=%s operation=%s exc_type=%s exc=%s",
                        "faiss",
                        "shadow_mode_evaluation",
                        type(shadow_exc).__name__,
                        shadow_exc,
                    )
            try:
                from steps.common.retrieval_events import (
                    RetrievalEvent,
                    emit_retrieval_events,
                    normalize_retrieval_context,
                    utc_now_iso,
                )

                context = normalize_retrieval_context(os.environ.get("GOODQ_RETRIEVAL_CONTEXT"))
                ts = utc_now_iso()
                events: List[RetrievalEvent] = []
                for h in out:
                    if not isinstance(h, dict):
                        continue
                    score = h.get("score")
                    try:
                        score_f = float(score) if score is not None else None
                    except Exception as e:
                        logger.warning(
                            "memory_stores operation failed store=%s operation=%s index_path=%s exc_type=%s exc=%s",
                            "faiss",
                            "query.score_parse",
                            self.index_path,
                            type(e).__name__,
                            e,
                        )
                        score_f = None
                    payload = h.get("payload") if isinstance(h.get("payload"), dict) else {}
                    prov = h.get("provenance") if isinstance(h.get("provenance"), dict) else {}
                    scene_id = payload.get("scene_id") if payload else None
                    modality = payload.get("modality") if payload else None
                    model = payload.get("model") if payload else None
                    if scene_id is None and prov:
                        scene_id = prov.get("scene_id")
                    if modality is None and prov:
                        modality = prov.get("modality")
                    if model is None and prov:
                        model = prov.get("model")
                    if modality is None and isinstance(payload.get("model"), str):
                        modality = payload.get("model")
                    embedding_id = h.get("id")
                    embedding_id_s = str(embedding_id) if embedding_id is not None else None
                    events.append(
                        RetrievalEvent(
                            ts_utc=ts,
                            store="faiss",
                            retrieval_context=context,
                            embedding_id=embedding_id_s,
                            scene_id=str(scene_id) if scene_id is not None else None,
                            modality=str(modality) if modality is not None else None,
                            model=str(model) if model is not None else None,
                            score=score_f,
                            details={
                                "store_type": "faiss",
                                "store_ref": os.path.basename(self.index_path) if self.index_path else None,
                                "index_path": self.index_path,
                            },
                        )
                    )
                emit_retrieval_events(self.db_path, events, enabled=self.log_retrieval_events, log_dir=self.log_dir)
            except Exception as e:
                logger.warning(
                    "memory_stores operation failed store=%s operation=%s index_path=%s exc_type=%s exc=%s",
                    "faiss",
                    "emit_retrieval_events",
                    self.index_path,
                    type(e).__name__,
                    e,
                )
            return out
        except Exception as e:
            logger.warning(
                "memory_stores operation failed store=%s operation=%s index_path=%s exc_type=%s exc=%s",
                "faiss",
                "query",
                self.index_path,
                type(e).__name__,
                e,
            )
            return []

    def stats(self) -> Dict[str, Any]:
        try:
            import faiss  # type: ignore
            if os.path.isfile(self.index_path):
                idx = faiss.read_index(self.index_path)
                return {"available": True, "vectors": int(getattr(idx, "ntotal", 0)), "dim": self.dim}
        except Exception as e:
            logger.warning(
                "memory_stores operation failed store=%s operation=%s index_path=%s exc_type=%s exc=%s",
                "faiss",
                "stats",
                self.index_path,
                type(e).__name__,
                e,
            )
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
    log_retrieval = True
    try:
        log_retrieval = retrieval_events_enabled(cfg, default=True)
    except Exception as e:
        logger.warning(
            "memory_stores operation failed store=%s operation=%s exc_type=%s exc=%s",
            "build_text_stores",
            "retrieval_events_enabled",
            type(e).__name__,
            e,
        )
        log_retrieval = True
    stores["ephemeral"] = EphemeralMemory(
        text_dim,
        ttl_seconds=ttl_seconds,
        max_items=max_ephemeral,
        db_path=paths.get("db_path"),
        log_dir=paths.get("log_dir"),
        log_retrieval_events=log_retrieval,
    )
    faiss_path = paths.get("faiss_index_path") or ""
    if faiss_path:
        stores["faiss"] = FaissMemory(
            faiss_path,
            text_dim,
            db_path=paths.get("db_path"),
            log_dir=paths.get("log_dir"),
            log_retrieval_events=log_retrieval,
            cfg=cfg,
        )
    q_client = None
    try:
        q_client = build_qdrant_client(cfg, dim=text_dim, key="text")
    except Exception as e:
        logger.warning(
            "memory_stores operation failed store=%s operation=%s exc_type=%s exc=%s",
            "build_text_stores",
            "build_qdrant_client",
            type(e).__name__,
            e,
        )
        q_client = None
    if q_client:
        stores["qdrant"] = QdrantMemory(q_client)
    # The tier-0 ephemeral cache remains intentionally local and in-memory.
    return stores
