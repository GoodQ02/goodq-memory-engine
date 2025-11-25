from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import requests


@dataclass
class QdrantConfig:
    host: str
    collection: str
    dim: int
    distance: str = "Cosine"
    enabled: bool = True


class QdrantClient:
    def __init__(self, cfg: QdrantConfig):
        self.cfg = cfg
        self.session = requests.Session()
        self._collection_ready = False
        self._points_cached: Optional[int] = None

    def ensure_collection(self) -> bool:
        if self._collection_ready:
            return True
        if not self.cfg.enabled:
            return False
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
            return self._collection_ready
        except Exception:
            return False

    def upsert(self, points: List[Dict[str, Any]]) -> bool:
        if not self.cfg.enabled:
            return False
        if not self.ensure_collection():
            return False
        try:
            r = self.session.put(
                f"{self.cfg.host}/collections/{self.cfg.collection}/points",
                json={"points": points},
                timeout=5,
            )
            return r.status_code == 200
        except Exception:
            return False

    def query(self, vector: List[float], top_k: int = 5, payload_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self.cfg.enabled:
            return []
        if not self.ensure_collection():
            return []
        try:
            body: Dict[str, Any] = {"vector": vector, "limit": top_k}
            if payload_filter:
                body["filter"] = payload_filter
            r = self.session.post(
                f"{self.cfg.host}/collections/{self.cfg.collection}/points/search",
                json=body,
                timeout=5,
            )
            if r.status_code != 200:
                return []
            res = r.json().get("result", []) or []
            return [
                {
                    "id": hit.get("id"),
                    "score": hit.get("score"),
                    "payload": hit.get("payload", {}),
                }
                for hit in res
            ]
        except Exception:
            return []

    def stats(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {"collection": self.cfg.collection, "host": self.cfg.host, "enabled": self.cfg.enabled}
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
        except Exception:
            pass
        info["available"] = False
        if self._points_cached is not None:
            info["vectors"] = self._points_cached
        return info


def build_qdrant_client(cfg: Dict[str, Any], dim: int, key: str) -> Optional[QdrantClient]:
    qcfg = (cfg.get("qdrant") or {}) if cfg else {}
    if not qcfg.get("enabled", False):
        return None
    host = qcfg.get("host", "http://localhost:36335")
    collections = qcfg.get("collections", {}) or {}
    collection = collections.get(key, f"goodq_{key}")
    return QdrantClient(QdrantConfig(host=host, collection=collection, dim=dim, enabled=True))
