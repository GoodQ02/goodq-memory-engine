from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
import logging
import os
import uuid
import string
import requests
import time
from urllib.parse import urlparse

from steps.common.retrieval_events import (
    RetrievalEventPolicy,
    resolve_retrieval_event_policy,
)

logger = logging.getLogger(__name__)


# NOTE: This namespace is part of GoodQ's storage identity for Qdrant point IDs.
# Changing it will change derived UUIDs and can create duplicates for the same raw IDs.
GOODQ_POINT_ID_NAMESPACE = uuid.UUID("2058b732-6666-5424-a820-5cf54ef071c4")


def build_qdrant_session(host: str) -> requests.Session:
    """Create a transport session that never proxies canonical loopback Qdrant.

    Workstation shells may legitimately export a proxy for external traffic.
    Qdrant is a local-only authority, so routing its loopback endpoint through
    that proxy makes a healthy service look unavailable.  Non-loopback hosts
    retain the caller environment unchanged.
    """
    session = requests.Session()
    hostname = (urlparse(str(host)).hostname or "").lower()
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        session.trust_env = False
    return session


def _truncate_http_body(body: Optional[str], max_len: int = 300) -> str:
    text = (body or "").strip().replace("\n", " ")
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


@dataclass
class QdrantConfig:
    host: str
    collection: str
    dim: int
    distance: str = "Cosine"
    enabled: bool = True
    db_path: Optional[str] = None
    retrieval_event_policy: RetrievalEventPolicy = field(
        default_factory=RetrievalEventPolicy
    )


class QdrantClient:
    def __init__(self, cfg: QdrantConfig):
        self.cfg = cfg
        self.session = build_qdrant_session(cfg.host)
        self._collection_ready = False
        self._points_cached: Optional[int] = None
        self._upsert_metrics: Dict[str, int] = {
            "upsert_calls": 0,
            "points_input": 0,
            "points_dropped": 0,
            "points_normalized": 0,
            "points_written": 0,
        }

    def _debug_enabled(self) -> bool:
        val = os.environ.get("GOODQ_VECTOR_DEBUG", "")
        return val.strip().lower() in ("1", "true", "yes", "y", "on")

    def _normalize_point_id(self, raw_id: Any) -> Any:
        # Qdrant point IDs must be int or UUID (not arbitrary strings).
        if raw_id is None:
            return None
        if isinstance(raw_id, int):
            return raw_id
        if isinstance(raw_id, str):
            s = raw_id.strip()
            if not s:
                return None
            # If already a UUID (or 32-hex UUID form), normalize it.
            hex_candidate = s.replace("-", "")
            if len(hex_candidate) == 32 and all(ch in string.hexdigits for ch in hex_candidate):
                return str(uuid.UUID(hex_candidate))
            # If numeric string, allow as int.
            if s.isdigit():
                return int(s)
            # Deterministic UUID for arbitrary strings (stable across runs).
            return str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, s))
        # Best-effort: coerce other types to deterministic UUID.
        try:
            return str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, str(raw_id)))
        except Exception as e:
            logger.warning(
                "qdrant operation failed operation=%s collection=%s exc_type=%s exc=%s",
                "normalize_point_id.uuid5",
                self.cfg.collection,
                type(e).__name__,
                e,
            )
            return None

    def ensure_collection(self) -> bool:
        if self._collection_ready:
            return True
        if not self.cfg.enabled:
            return False
        for attempt in range(2):
            try:
                # Check if collection exists
                r = self.session.get(f"{self.cfg.host}/collections/{self.cfg.collection}", timeout=3)
                if r.status_code == 200:
                    self._collection_ready = True
                    return True
                # Create if missing
                payload = {
                    "vectors": {
                        "size": self.cfg.dim,
                        "distance": self.cfg.distance
                    }
                }
                r = self.session.put(
                    f"{self.cfg.host}/collections/{self.cfg.collection}",
                    json=payload,
                    timeout=5,
                )
                self._collection_ready = r.status_code == 200
                if not self._collection_ready:
                    body = _truncate_http_body(getattr(r, "text", None))
                    logger.warning(
                        "qdrant operation failed operation=%s collection=%s status_code=%s body=%s attempt=%s",
                        "ensure_collection.create",
                        self.cfg.collection,
                        getattr(r, "status_code", None),
                        body,
                        attempt + 1,
                    )
                else:
                    return True
            except Exception as e:
                logger.warning(
                    "qdrant operation failed operation=%s collection=%s exc_type=%s exc=%s attempt=%s",
                    "ensure_collection",
                    self.cfg.collection,
                    type(e).__name__,
                    e,
                    attempt + 1,
                )
            if attempt == 0:
                time.sleep(0.5)
        return False

    def collection_exists(self) -> bool:
        """Inspect collection availability without creating it."""
        if self._collection_ready:
            return True
        if not self.cfg.enabled:
            return False
        for attempt in range(2):
            try:
                response = self.session.get(
                    f"{self.cfg.host}/collections/{self.cfg.collection}",
                    timeout=3,
                )
                if response.status_code == 200:
                    self._collection_ready = True
                    return True
                body = _truncate_http_body(getattr(response, "text", None))
                logger.warning(
                    "qdrant operation failed operation=%s collection=%s status_code=%s body=%s attempt=%s",
                    "collection_exists",
                    self.cfg.collection,
                    getattr(response, "status_code", None),
                    body,
                    attempt + 1,
                )
                if response.status_code == 404:
                    return False
            except Exception as e:
                logger.warning(
                    "qdrant operation failed operation=%s collection=%s exc_type=%s exc=%s attempt=%s",
                    "collection_exists",
                    self.cfg.collection,
                    type(e).__name__,
                    e,
                    attempt + 1,
                )
            if attempt == 0:
                time.sleep(0.5)
        return False

    def upsert(self, points: List[Dict[str, Any]]) -> bool:
        if not self.cfg.enabled:
            return False
        if not self.ensure_collection():
            return False
        try:
            points_in = len(points or [])
            self._upsert_metrics["upsert_calls"] += 1
            self._upsert_metrics["points_input"] += points_in

            normalized: List[Dict[str, Any]] = []
            ids_normalized = 0
            for p in points or []:
                if not isinstance(p, dict):
                    continue
                pid = self._normalize_point_id(p.get("id"))
                if pid is None:
                    continue
                out = p
                if pid != p.get("id"):
                    out = dict(p)
                    out["id"] = pid
                    ids_normalized += 1
                normalized.append(out)

            points_dropped = max(0, points_in - len(normalized))
            self._upsert_metrics["points_dropped"] += points_dropped
            self._upsert_metrics["points_normalized"] += ids_normalized

            if not normalized:
                if self._debug_enabled():
                    print(
                        f"[VECTOR_DEBUG] qdrant.upsert skipped (no valid points) collection={self.cfg.collection}"
                        f" points_in={points_in} dropped={points_dropped} normalized={ids_normalized}"
                    )
                return False

            if self._debug_enabled():
                modalities: Dict[str, int] = {}
                scenes = set()
                for p in normalized:
                    payload = p.get("payload") if isinstance(p.get("payload"), dict) else {}
                    mod = payload.get("modality") or payload.get("model") or "unknown"
                    modalities[str(mod)] = modalities.get(str(mod), 0) + 1
                    sid = payload.get("scene_id")
                    if sid is not None:
                        scenes.add(str(sid))
                scene_note = f" scenes={len(scenes)}" if scenes else ""
                print(
                    f"[VECTOR_DEBUG] qdrant.upsert collection={self.cfg.collection} points={len(normalized)}"
                    f" points_in={points_in} dropped={points_dropped} ids_normalized={ids_normalized}"
                    f" modalities={modalities}{scene_note}"
                )
            for attempt in range(2):
                try:
                    r = self.session.put(
                        f"{self.cfg.host}/collections/{self.cfg.collection}/points?wait=true",
                        json={"points": normalized},
                        timeout=5,
                    )
                    ok = r.status_code in (200, 202)
                    if ok:
                        self._upsert_metrics["points_written"] += len(normalized)
                        return True
                    else:
                        body = _truncate_http_body(getattr(r, "text", None))
                        logger.warning(
                            "qdrant operation failed operation=%s collection=%s status_code=%s body=%s attempt=%s",
                            "upsert",
                            self.cfg.collection,
                            getattr(r, "status_code", None),
                            body,
                            attempt + 1,
                        )
                        if self._debug_enabled():
                            print(f"[VECTOR_DEBUG] qdrant.upsert failed status={r.status_code} collection={self.cfg.collection} body={body}")
                        self._collection_ready = False
                except Exception as e:
                    logger.warning(
                        "qdrant operation failed operation=%s collection=%s exc_type=%s exc=%s attempt=%s",
                        "upsert",
                        self.cfg.collection,
                        type(e).__name__,
                        e,
                        attempt + 1,
                    )
                    self._collection_ready = False
                if attempt == 0:
                    time.sleep(0.5)
                    if not self.ensure_collection():
                        return False
            return False
        except Exception as e:
            logger.warning(
                "qdrant operation failed operation=%s collection=%s exc_type=%s exc=%s",
                "upsert",
                self.cfg.collection,
                type(e).__name__,
                e,
            )
            return False

    def set_payload(
        self,
        points: List[str],
        payload: Dict[str, Any],
        timeout: int = 10,
    ) -> bool:
        """
        Update payload fields for existing Qdrant points without touching vectors.
        Idempotent: safe to call multiple times with the same value.
        Returns True on success, False on any failure. Never raises.
        """
        if not self.cfg.enabled:
            return False
        if not points:
            return True
            
        try:
            normalized_points = []
            for p in points:
                np = self._normalize_point_id(p)
                if np is not None:
                    normalized_points.append(np)
            if not normalized_points:
                return False

            body = {"payload": payload, "points": normalized_points}
            
            # Use PUT instead of POST as per ORIGINAL_REQUEST.md
            for attempt in range(2):
                try:
                    r = self.session.put(
                        f"{self.cfg.host}/collections/{self.cfg.collection}/points/payload?wait=true",
                        json=body,
                        timeout=timeout,
                    )
                    if r.status_code in (200, 202):
                        return True
                    else:
                        body_text = _truncate_http_body(getattr(r, "text", None))
                        logger.warning(
                            "qdrant operation failed operation=%s collection=%s status_code=%s body=%s attempt=%s",
                            "set_payload",
                            self.cfg.collection,
                            getattr(r, "status_code", None),
                            body_text,
                            attempt + 1,
                        )
                        self._collection_ready = False
                except Exception as e:
                    logger.warning(
                        "qdrant operation failed operation=%s collection=%s exc_type=%s exc=%s attempt=%s",
                        "set_payload",
                        self.cfg.collection,
                        type(e).__name__,
                        e,
                        attempt + 1,
                    )
                    self._collection_ready = False
                if attempt == 0:
                    time.sleep(0.5)
                    if not self.ensure_collection():
                        return False
            return False
        except Exception as e:
            logger.warning(
                "qdrant operation failed operation=%s collection=%s exc_type=%s exc=%s",
                "set_payload",
                self.cfg.collection,
                type(e).__name__,
                e,
            )
            return False

    def query(
        self,
        vector: List[float],
        top_k: int = 5,
        payload_filter: Optional[Dict[str, Any]] = None,
        *,
        retrieval_context: str,
    ) -> List[Dict[str, Any]]:
        if not self.cfg.enabled:
            return []
        if not self.collection_exists():
            return []
        try:
            body: Dict[str, Any] = {
                "vector": vector,
                "limit": top_k,
                "with_payload": True,
                "with_vector": False,
            }
            if payload_filter:
                body["filter"] = payload_filter
            res = None
            for attempt in range(2):
                try:
                    r = self.session.post(
                        f"{self.cfg.host}/collections/{self.cfg.collection}/points/search",
                        json=body,
                        timeout=5,
                    )
                    if r.status_code == 200:
                        res = r.json().get("result", []) or []
                        break
                    else:
                        body_text = _truncate_http_body(getattr(r, "text", None))
                        logger.warning(
                            "qdrant operation failed operation=%s collection=%s status_code=%s body=%s attempt=%s",
                            "query",
                            self.cfg.collection,
                            getattr(r, "status_code", None),
                            body_text,
                            attempt + 1,
                        )
                        self._collection_ready = False
                except Exception as e:
                    logger.warning(
                        "qdrant operation failed operation=%s collection=%s exc_type=%s exc=%s attempt=%s",
                        "query",
                        self.cfg.collection,
                        type(e).__name__,
                        e,
                        attempt + 1,
                    )
                    self._collection_ready = False
                if attempt == 0:
                    time.sleep(0.5)
                    if not self.collection_exists():
                        return []
            if res is None:
                return []
            hits = [
                {
                    "id": hit.get("id"),
                    "score": hit.get("score"),
                    "payload": hit.get("payload", {}),
                }
                for hit in res
            ]
            try:
                from steps.common.memory_provenance import attach_provenance_to_hits

                attach_provenance_to_hits(getattr(self.cfg, "db_path", None), hits)
            except Exception as e:
                logger.warning(
                    "qdrant operation failed operation=%s collection=%s exc_type=%s exc=%s",
                    "query.attach_provenance",
                    self.cfg.collection,
                    type(e).__name__,
                    e,
                )
            try:
                from steps.common.retrieval_events import (
                    RetrievalEvent,
                    emit_retrieval_events,
                    normalize_retrieval_context,
                    utc_now_iso,
                )

                context = normalize_retrieval_context(retrieval_context)
                ts = utc_now_iso()
                events: List[RetrievalEvent] = []
                for h in hits:
                    if not isinstance(h, dict):
                        continue
                    score = h.get("score")
                    if score is None:
                        score_f = None
                    elif isinstance(score, (int, float)):
                        score_f = float(score)
                    else:
                        try:
                            score_f = float(score)
                        except Exception as e:
                            logger.warning(
                                "qdrant operation failed operation=%s collection=%s exc_type=%s exc=%s",
                                "query.score_parse",
                                self.cfg.collection,
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
                            store="qdrant",
                            retrieval_context=context,
                            embedding_id=embedding_id_s,
                            scene_id=str(scene_id) if scene_id is not None else None,
                            modality=str(modality) if modality is not None else None,
                            model=str(model) if model is not None else None,
                            score=score_f,
                            details={
                                "store_type": "qdrant",
                                "store_ref": self.cfg.collection,
                                "collection": self.cfg.collection,
                            },
                        )
                    )
                emit_retrieval_events(
                    getattr(self.cfg, "db_path", None),
                    events,
                    policy=self.cfg.retrieval_event_policy,
                )
            except Exception as e:
                logger.warning(
                    "qdrant operation failed operation=%s collection=%s exc_type=%s exc=%s",
                    "query.emit_retrieval_events",
                    self.cfg.collection,
                    type(e).__name__,
                    e,
                )
            return hits
        except Exception as e:
            logger.warning(
                "qdrant operation failed operation=%s collection=%s exc_type=%s exc=%s",
                "query",
                self.cfg.collection,
                type(e).__name__,
                e,
            )
            return []

    def stats(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {"collection": self.cfg.collection, "host": self.cfg.host, "enabled": self.cfg.enabled}
        info["upsert_metrics"] = dict(self._upsert_metrics)
        if not self.cfg.enabled:
            info["available"] = False
            return info
        try:
            if self.ensure_collection():
                r = self.session.get(f"{self.cfg.host}/collections/{self.cfg.collection}", timeout=3)
                if r.status_code == 200:
                    res = r.json().get("result", {}) or {}
                    points = res.get("points_count") or res.get("vectors_count") or 0
                    self._points_cached = points
                    info.update({"available": True, "vectors": points, "dim": self.cfg.dim, "distance": self.cfg.distance})
                    return info
        except Exception as e:
            logger.warning(
                "qdrant operation failed operation=%s collection=%s exc_type=%s exc=%s",
                "stats",
                self.cfg.collection,
                type(e).__name__,
                e,
            )
        info["available"] = False
        if self._points_cached is not None:
            info["vectors"] = self._points_cached
        return info


def build_qdrant_client(
    cfg: Dict[str, Any],
    dim: int,
    key: str,
    *,
    retrieval_event_policy: Optional[RetrievalEventPolicy] = None,
) -> Optional[QdrantClient]:
    qcfg = (cfg.get("qdrant") or {}) if cfg else {}
    if not qcfg.get("enabled", False):
        val = os.environ.get("GOODQ_VECTOR_DEBUG", "")
        if val.strip().lower() in ("1", "true", "yes", "y", "on"):
            print(f"[VECTOR_DEBUG] qdrant.disabled key={key}")
        return None
    host = qcfg.get("host", "http://localhost:6333")
    collections = qcfg.get("collections", {}) or {}
    collection = collections.get(key, f"goodq_{key}")
    paths = (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}
    db_path = paths.get("db_path")
    policy = (
        retrieval_event_policy
        if retrieval_event_policy is not None
        else resolve_retrieval_event_policy(cfg)
    )
    return QdrantClient(
        QdrantConfig(
            host=host,
            collection=collection,
            dim=dim,
            enabled=True,
            db_path=db_path,
            retrieval_event_policy=policy,
        )
    )
