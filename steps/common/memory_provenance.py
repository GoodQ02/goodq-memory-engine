from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from datetime import datetime, timezone
import json
import math
import os
import sqlite3
import uuid


def _vector_debug_enabled() -> bool:
    val = os.environ.get("GOODQ_VECTOR_DEBUG", "")
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def _id_key(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    try:
        return str(value)
    except Exception:
        return None


def _normalize_qdrant_point_id(raw_id: Any) -> Any:
    # Mirror steps.common.qdrant_client.QdrantClient._normalize_point_id for provenance matching.
    if raw_id is None:
        return None
    if isinstance(raw_id, int):
        return raw_id
    if isinstance(raw_id, str):
        s = raw_id.strip()
        if not s:
            return None
        try:
            return str(uuid.UUID(s))
        except Exception:
            pass
        try:
            if s.isdigit():
                return int(s)
        except Exception:
            pass
        # Deterministic UUID for arbitrary strings (stable across runs).
        namespace = uuid.UUID("2058b732-6666-5424-a820-5cf54ef071c4")
        return str(uuid.uuid5(namespace, s))
    try:
        namespace = uuid.UUID("2058b732-6666-5424-a820-5cf54ef071c4")
        return str(uuid.uuid5(namespace, str(raw_id)))
    except Exception:
        return None


def _scene_id_candidates(scene_id: Any) -> List[str]:
    if scene_id is None:
        return []
    out: List[str] = []
    if isinstance(scene_id, int):
        out.append(str(scene_id))
        out.append(f"scene_{scene_id:04d}")
        return out
    if isinstance(scene_id, str):
        s = scene_id.strip()
        if not s:
            return []
        out.append(s)
        # Best-effort: normalize "scene_0001" <-> "1"
        if s.lower().startswith("scene_"):
            try:
                n = int(s.split("_", 1)[1])
                out.append(str(n))
                out.append(f"scene_{n:04d}")
            except Exception:
                pass
        elif s.isdigit():
            try:
                n = int(s)
                out.append(str(n))
                out.append(f"scene_{n:04d}")
            except Exception:
                pass
    else:
        try:
            out.append(str(scene_id))
        except Exception:
            return []
    # Deduplicate preserving order
    seen = set()
    deduped: List[str] = []
    for v in out:
        if v in seen:
            continue
        seen.add(v)
        deduped.append(v)
    return deduped


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    try:
        cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,))
        return cur.fetchone() is not None
    except Exception:
        return False


def default_confidence_payload() -> Dict[str, Any]:
    return {
        "intrinsic": None,
        "source": None,
        "temporal": None,
        "consistency": None,
        "overall": None,
    }


def _normalize_confidence(confidence: Any) -> Dict[str, Any]:
    defaults = default_confidence_payload()
    if isinstance(confidence, dict):
        for k in defaults.keys():
            if k in confidence:
                defaults[k] = confidence.get(k)
    return defaults


def _parse_ts_utc(ts_utc: Any) -> Optional[datetime]:
    if not isinstance(ts_utc, str) or not ts_utc.strip():
        return None
    s = ts_utc.strip()
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _temporal_confidence(ts_utc: Any, *, now_utc: datetime) -> Tuple[Optional[float], Optional[str]]:
    commit_ts = _parse_ts_utc(ts_utc)
    if commit_ts is None:
        return None, None
    try:
        age_seconds = max(0.0, (now_utc - commit_ts).total_seconds())
        half_life_days = 30.0
        half_life_seconds = half_life_days * 86400.0
        # Smooth exponential decay (no thresholds; never gates behavior).
        value = math.exp(-math.log(2.0) * age_seconds / max(1.0, half_life_seconds))
        value = float(f"{value:.4f}")
        age_days = age_seconds / 86400.0
        explanation = (
            f"exp_decay(ts_utc_age_days={age_days:.1f}, half_life_days={half_life_days:g}, source=provenance.ts_utc)"
        )
        return value, explanation
    except Exception:
        return None, None


def _row_to_provenance(row: sqlite3.Row) -> Dict[str, Any]:
    targets: Any = {}
    try:
        raw = row["targets_json"]
        if isinstance(raw, str) and raw.strip():
            targets = json.loads(raw)
    except Exception:
        targets = {}
    confidence: Any = None
    try:
        raw = row["confidence_json"]
        if isinstance(raw, str) and raw.strip():
            confidence = json.loads(raw)
    except Exception:
        confidence = None
    return {
        "provenance_version": 1,
        "ts_utc": row["ts_utc"],
        "scene_id": row["scene_id"],
        "video_id": row["video_id"],
        "modality": row["modality"],
        "model": row["model"],
        "component": row["component"],
        "attempted": bool(row["attempted"]),
        "committed": bool(row["committed"]),
        "reason": row["reason"],
        "targets": targets if isinstance(targets, dict) else {},
        "confidence": _normalize_confidence(confidence),
    }


def _best_event(existing: Optional[Dict[str, Any]], candidate: Dict[str, Any]) -> Dict[str, Any]:
    if existing is None:
        return candidate
    ex_c = 1 if existing.get("committed") else 0
    ex_a = 1 if existing.get("attempted") else 0
    ex_ts = str(existing.get("ts_utc") or "")
    ca_c = 1 if candidate.get("committed") else 0
    ca_a = 1 if candidate.get("attempted") else 0
    ca_ts = str(candidate.get("ts_utc") or "")
    if (ca_c, ca_a, ca_ts) > (ex_c, ex_a, ex_ts):
        return candidate
    return existing


def attach_provenance_to_hits(db_path: Optional[str], hits: List[Dict[str, Any]]) -> None:
    """
    Best-effort: annotate retrieval hits with a `provenance` field derived from memory_commit_events.
    Never raises; never changes ranking/scoring.
    """
    if not hits:
        return
    if not isinstance(db_path, str) or not db_path.strip():
        return
    if not os.path.isfile(db_path):
        return

    debug = _vector_debug_enabled()

    # Pre-scan hits for IDs and scene hints.
    hit_id_keys: Dict[int, str] = {}
    scene_candidates: List[str] = []
    modality_candidates: List[str] = []
    faiss_ids: List[int] = []
    for idx, hit in enumerate(hits):
        if not isinstance(hit, dict):
            continue
        hit.setdefault("confidence", default_confidence_payload())
        if "provenance" in hit:
            continue
        norm = _normalize_qdrant_point_id(hit.get("id"))
        key = _id_key(norm if norm is not None else hit.get("id"))
        if key:
            hit_id_keys[idx] = key

        payload = hit.get("payload") if isinstance(hit.get("payload"), dict) else {}
        if payload:
            for sid in _scene_id_candidates(payload.get("scene_id")):
                scene_candidates.append(sid)
            mod = payload.get("modality") or payload.get("model")
            if isinstance(mod, str) and mod.strip():
                modality_candidates.append(mod.strip())
        else:
            try:
                if isinstance(hit.get("id"), int):
                    faiss_ids.append(int(hit["id"]))
                elif isinstance(hit.get("id"), str) and hit["id"].strip().isdigit():
                    faiss_ids.append(int(hit["id"].strip()))
            except Exception:
                pass

    if not hit_id_keys and not faiss_ids:
        return

    # Deduplicate with stable order.
    def _uniq(seq: Sequence[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for s in seq:
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    scene_candidates = _uniq(scene_candidates)
    modality_candidates = _uniq(modality_candidates)

    try:
        conn = sqlite3.connect(db_path, timeout=0.2, check_same_thread=False)
        conn.row_factory = sqlite3.Row
    except Exception:
        return

    try:
        if not _table_exists(conn, "memory_commit_events"):
            return
        try:
            cur = conn.execute("PRAGMA table_info('memory_commit_events')")
            mce_cols = {row[1] for row in cur.fetchall()}
        except Exception:
            mce_cols = set()
        mce_select = (
            "ts_utc, scene_id, video_id, modality, model, embedding_id, component, attempted, committed, reason, targets_json, confidence_json"
            if "confidence_json" in mce_cols
            else "ts_utc, scene_id, video_id, modality, model, embedding_id, component, attempted, committed, reason, targets_json"
        )

        # 1) Fast path: resolve by embedding_id (normalized to Qdrant point ID) from recent/candidate events.
        norm_to_event: Dict[str, Dict[str, Any]] = {}

        # Prefer scene-filtered scan when possible (stable + bounded).
        scanned = 0
        try:
            rows: Iterable[sqlite3.Row]
            if scene_candidates:
                placeholders = ",".join("?" for _ in scene_candidates)
                rows = conn.execute(
                    f"""
                    SELECT {mce_select}
                    FROM memory_commit_events
                    WHERE scene_id IN ({placeholders})
                    ORDER BY ts_utc DESC
                    LIMIT 2000
                    """,
                    tuple(scene_candidates),
                )
            elif modality_candidates:
                placeholders = ",".join("?" for _ in modality_candidates)
                rows = conn.execute(
                    f"""
                    SELECT {mce_select}
                    FROM memory_commit_events
                    WHERE modality IN ({placeholders})
                    ORDER BY ts_utc DESC
                    LIMIT 2000
                    """,
                    tuple(modality_candidates),
                )
            else:
                rows = conn.execute(
                    f"""
                    SELECT {mce_select}
                    FROM memory_commit_events
                    ORDER BY ts_utc DESC
                    LIMIT 2000
                    """
                )

            wanted = set(hit_id_keys.values())
            for row in rows:
                scanned += 1
                emb = row["embedding_id"]
                norm = _normalize_qdrant_point_id(emb)
                key = _id_key(norm)
                if not key or key not in wanted:
                    continue
                prov = _row_to_provenance(row)
                norm_to_event[key] = _best_event(norm_to_event.get(key), prov)
        except Exception:
            norm_to_event = {}

        # Attach by normalized embedding_id match.
        attached = 0
        for idx, key in hit_id_keys.items():
            ev = norm_to_event.get(key)
            if not ev:
                continue
            hit = hits[idx]
            if isinstance(hit, dict) and "provenance" not in hit:
                hit["provenance"] = ev
                hit["confidence"] = ev.get("confidence") or hit.get("confidence")
                attached += 1

        # 2) FAISS fallback: map faiss_id -> embeddings.hash -> commit event by embedding_id.
        if faiss_ids and _table_exists(conn, "embeddings"):
            try:
                placeholders = ",".join("?" for _ in faiss_ids)
                cur = conn.execute(
                    f"SELECT hash, faiss_id, modality, scene_id FROM embeddings WHERE faiss_id IN ({placeholders})",
                    tuple(faiss_ids),
                )
                faiss_map: Dict[int, Dict[str, Any]] = {}
                for row in cur.fetchall():
                    try:
                        fid = int(row["faiss_id"])
                    except Exception:
                        continue
                    faiss_map[fid] = {
                        "hash": row["hash"],
                        "modality": row["modality"],
                        "scene_id": row["scene_id"],
                    }
                ev_cache: Dict[str, Dict[str, Any]] = {}
                for hit in hits:
                    if not isinstance(hit, dict) or "provenance" in hit:
                        continue
                    hid = hit.get("id")
                    if not isinstance(hid, int):
                        continue
                    meta = faiss_map.get(hid)
                    if not meta:
                        continue
                    h = meta.get("hash")
                    if not isinstance(h, str) or not h:
                        continue
                    ev = ev_cache.get(h)
                    if ev is None:
                        try:
                            row = conn.execute(
                                f"""
                                SELECT {mce_select}
                                FROM memory_commit_events
                                WHERE embedding_id = ?
                                ORDER BY ts_utc DESC
                                LIMIT 1
                                """,
                                (h,),
                            ).fetchone()
                            ev = _row_to_provenance(row) if row else {}
                        except Exception:
                            ev = {}
                        ev_cache[h] = ev
                    if ev:
                        hit["provenance"] = ev
                        hit["confidence"] = ev.get("confidence") or hit.get("confidence")
            except Exception:
                pass

        # 3) Fallback: scene_id + modality + model (best-effort)
        try:
            fallback_cache: Dict[Tuple[str, str, Optional[str]], Optional[Dict[str, Any]]] = {}
            for hit in hits:
                if not isinstance(hit, dict) or "provenance" in hit:
                    continue
                payload = hit.get("payload") if isinstance(hit.get("payload"), dict) else {}
                if not payload:
                    continue
                modality = payload.get("modality") or payload.get("model")
                if not isinstance(modality, str) or not modality.strip():
                    continue
                modality = modality.strip()
                model = payload.get("model")
                model_s = model.strip() if isinstance(model, str) and model.strip() else None
                for sid in _scene_id_candidates(payload.get("scene_id")):
                    cache_key = (sid, modality, model_s)
                    if cache_key in fallback_cache:
                        ev = fallback_cache[cache_key]
                    else:
                        ev = None
                        try:
                            if model_s:
                                row = conn.execute(
                                    f"""
                                    SELECT {mce_select}
                                    FROM memory_commit_events
                                    WHERE scene_id = ? AND modality = ? AND model = ?
                                    ORDER BY ts_utc DESC
                                    LIMIT 1
                                    """,
                                    (sid, modality, model_s),
                                ).fetchone()
                                if row:
                                    ev = _row_to_provenance(row)
                            if ev is None:
                                row = conn.execute(
                                    f"""
                                    SELECT {mce_select}
                                    FROM memory_commit_events
                                    WHERE scene_id = ? AND modality = ?
                                    ORDER BY ts_utc DESC
                                    LIMIT 1
                                    """,
                                    (sid, modality),
                                ).fetchone()
                                if row:
                                    ev = _row_to_provenance(row)
                        except Exception:
                            ev = None
                        fallback_cache[cache_key] = ev
                    if ev:
                        hit["provenance"] = ev
                        hit["confidence"] = ev.get("confidence") or hit.get("confidence")
                        break
        except Exception:
            pass

        # 4) Read-time temporal confidence (best-effort; no persistence; no ranking impact)
        try:
            now_utc = datetime.now(timezone.utc)
            for hit in hits:
                if not isinstance(hit, dict):
                    continue
                confidence = hit.get("confidence")
                if not isinstance(confidence, dict):
                    continue
                if confidence.get("temporal") is not None:
                    continue
                prov = hit.get("provenance")
                if not isinstance(prov, dict):
                    continue
                temporal, explanation = _temporal_confidence(prov.get("ts_utc"), now_utc=now_utc)
                if temporal is None:
                    continue
                confidence["temporal"] = temporal
                if isinstance(explanation, str) and explanation.strip():
                    confidence.setdefault("temporal_explanation", explanation)
        except Exception:
            pass

        if debug:
            try:
                print(
                    f"[VECTOR_DEBUG] provenance.annotate hits={len(hits)} attached={sum(1 for h in hits if isinstance(h, dict) and 'provenance' in h)}"
                    f" scanned_events={scanned}"
                )
            except Exception:
                pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
