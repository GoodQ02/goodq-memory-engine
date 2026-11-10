from __future__ import annotations
import argparse
import hashlib
import json
import os
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Tuple

from steps.common.sqlite_read_authority import open_sqlite_read_connection

def _load_cfg() -> Dict[str, Any]:
    from steps.common.config_loader import load_configs
    return load_configs({})


def _embed_query(text: str) -> Tuple[Any, Any]:
    from sentence_transformers import SentenceTransformer  # type: ignore
    import numpy as np  # type: ignore
    import torch  # type: ignore

    device = "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
    model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
    vec = model.encode([text], normalize_embeddings=True).astype("float32")
    return vec, np


def _search_qdrant(text: str, topk: int, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Qdrant-first search; falls through if disabled/unavailable."""
    try:
        from steps.common.qdrant_client import build_qdrant_client
    except Exception:
        return []

    q_client = build_qdrant_client(cfg, dim=384, key="text")
    if not q_client:
        return []
    vec, _np = _embed_query(text)
    if vec is None:
        return []
    hits = q_client.query(
        vec[0].tolist(),
        top_k=topk,
        payload_filter={"must": [
            {"key": "ucf_promotion_status", "match": {"value": "promoted"}},
            *([{"key": "epoch_id", "match": {
                "value": Path(cfg["paths"]["db_dir"]).name
            }}] if (cfg.get("paths") or {}).get("db_dir") else []),
        ]},
        retrieval_context="human.cli.retrieve",
    )
    results = []
    for h in hits:
        payload = h.get("payload") or {}
        results.append({
            "source_path": payload.get("source_path"),
            "modality": payload.get("modality") or "text",
            "score": h.get("score"),
            "scene_id": payload.get("scene_id"),
            "video_hash": payload.get("video_hash"),
            "faiss_id": payload.get("faiss_id"),
        })
    return results


def _search_faiss(index_path: str, vec, cfg: Dict[str, Any], topk: int) -> List[Dict[str, Any]]:
    import faiss  # type: ignore
    if topk <= 0:
        return []
    idx = faiss.read_index(index_path)
    if not idx.ntotal:
        return []
    limit = min(idx.ntotal, max(10, topk))
    while True:
        distances, indices = idx.search(vec, k=limit)
        ranked = [(int(fid), float(score)) for fid, score in zip(indices[0], distances[0]) if fid >= 0]
        rows = _results_from_db([fid for fid, _ in ranked], cfg)
        by_id: Dict[int, List[Dict[str, Any]]] = {}
        for row in rows:
            by_id.setdefault(row["faiss_id"], []).append(row)
        matches = []
        for fid, score in ranked:
            seen_scenes = set()
            # Promotion can add a text alias for an audio_transcript row. Keep
            # one hit per vector/scene, preferring its preserved source path.
            for row in sorted(by_id.get(fid, []), key=lambda item: not bool(item.get("source_path"))):
                identity = row.get("scene_id") or row.get("source_path") or row["hash"]
                if identity not in seen_scenes:
                    matches.append(_match(row, score, cfg))
                    seen_scenes.add(identity)
        if len(matches) >= topk or limit == idx.ntotal:
            return matches[:topk]
        # Unmapped or unpromoted candidates must not consume the result quota.
        limit = min(idx.ntotal, limit * 2)


def _results_from_db(ids: List[int], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    db_path = (cfg.get("paths", {}) or {}).get("db_path") or ""
    out: List[Dict[str, Any]] = []
    if not ids:
        return out
    if not db_path or not os.path.isfile(db_path):
        raise FileNotFoundError("configured memory database is unavailable")
    with closing(open_sqlite_read_connection(db_path)) as con:
        columns = {col[0] for col in con.execute("SELECT * FROM embeddings LIMIT 0").description}
        scene_column = "scene_id" if "scene_id" in columns else "NULL AS scene_id"
        for offset in range(0, len(ids), 400):
            batch = ids[offset:offset + 400]
            qmarks = ",".join("?" for _ in batch)
            cursor = con.execute(
                f"SELECT hash, faiss_id, source_path, modality, {scene_column} "
                f"FROM embeddings WHERE faiss_id IN ({qmarks})", batch
            )
            names = [col[0] for col in cursor.description]
            out.extend(dict(zip(names, row)) for row in cursor)
        return _promoted_rows(out, cfg, con, columns)


def _promoted_rows(rows, cfg, memory, columns):
    """Check exact embedding membership against the configured epoch ledger."""
    paths = cfg.get("paths") or {}
    db_dir = paths.get("db_dir")
    ledger_path = Path(db_dir or Path(paths["db_path"]).parent) / "ucf" / "ucf_ledger.db"
    has_provenance = False
    if "ucf_provenance" in columns:
        has_provenance = memory.execute(
            "SELECT 1 FROM embeddings WHERE ucf_provenance IS NOT NULL "
            "AND ucf_provenance NOT IN ('', '[]') LIMIT 1"
        ).fetchone() is not None
    if memory.execute("SELECT 1 FROM sqlite_master WHERE name='ucf_provenance_mapping'").fetchone():
        has_provenance |= memory.execute("SELECT 1 FROM ucf_provenance_mapping LIMIT 1").fetchone() is not None
    if not ledger_path.is_file():
        if db_dir or cfg.get("ingestion_isolation") or has_provenance:
            raise FileNotFoundError("configured UCF ledger is unavailable")
        # Pre-UCF, non-isolated stores retain their existing read contract.
        return rows
    if not db_dir:
        raise RuntimeError("UCF ledger retrieval requires configured paths.db_dir")
    epoch_id = Path(db_dir).name
    membership = {}
    keys = list({row["hash"] for row in rows})
    with closing(open_sqlite_read_connection(ledger_path)) as ledger:
        for offset in range(0, len(keys), 400):
            batch = keys[offset:offset + 400]
            qmarks = ",".join("?" for _ in batch)
            frames = ledger.execute(
                "SELECT vector_key, json_extract(payload, '$.embedding_id'), "
                "source_artifact_id, video_hash FROM context_frames "
                "WHERE epoch_id=? AND promotion_status='promoted' "
                f"AND (vector_key IN ({qmarks}) OR json_extract(payload, '$.embedding_id') IN ({qmarks}))",
                [epoch_id, *batch, *batch],
            )
            for vector_key, embedding_id, scene_id, video_hash in frames:
                for key in (vector_key, embedding_id):
                    if key is not None:
                        membership.setdefault(key, set()).add((scene_id, video_hash))
        # Grouped document passages retain one source frame, with explicit
        # per-vector membership. A promoted sibling never admits another key.
        from steps.common.embedding_references import expand_embedding_references
        cursor = ledger.execute(
            "SELECT * FROM context_frames WHERE epoch_id=? AND promotion_status='promoted' "
            "AND json_type(payload, '$.embedding_chunks')='array'", (epoch_id,),
        )
        names = [column[0] for column in cursor.description]
        requested = set(keys)
        for row in cursor:
            frame = dict(zip(names, row))
            for ref in expand_embedding_references(frame):
                key = ref["vector_key"]
                if key in requested:
                    membership.setdefault(key, set()).add((ref["source_artifact_id"], ref["video_hash"]))
    result = []
    for row in rows:
        evidence = membership.get(row["hash"], set())
        if row.get("scene_id"):
            evidence = {item for item in evidence if item[0] == row["scene_id"]}
        if len(evidence) == 1:
            scene_id, video_hash = next(iter(evidence))
            result.append({**row, "scene_id": scene_id, "video_hash": video_hash})
    return result


def _match(row: Dict[str, Any], score: float, cfg: Dict[str, Any]) -> Dict[str, Any]:
    scene = None
    if row.get("scene_id"):
        db_path = (cfg.get("paths") or {}).get("db_path")
        if db_path and os.path.isfile(db_path):
            with closing(open_sqlite_read_connection(db_path)) as con:
                found = con.execute("SELECT video_hash, start, end, meta FROM scenes WHERE id=?",
                                    (row["scene_id"],)).fetchone()
            if found and (not row.get("video_hash") or row["video_hash"] == found[0]):
                try:
                    meta = json.loads(found[3]) if found[3] else None
                except (TypeError, ValueError):
                    meta = None
                scene = {"scene_id": row["scene_id"], "video_hash": found[0],
                         "start": found[1], "end": found[2], "meta": meta}
    elif row.get("modality") == "frame_text":
        scene = _scene_for_frame(row.get("source_path") or "", cfg)
    return {"source_path": row.get("source_path"), "modality": row.get("modality"),
            "score": score, "scene": scene}


def _scene_for_frame(frame_path: str, cfg: Dict[str, Any]) -> Dict[str, Any] | None:
    try:
        h = hashlib.sha256()
        with open(frame_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        fh = h.hexdigest()
    except Exception:
        return None
    db_path = (cfg.get("paths", {}) or {}).get("db_path") or ""
    if not db_path or not os.path.isfile(db_path):
        return None
    with closing(open_sqlite_read_connection(db_path)) as con:
        r = con.execute("SELECT parent_hash FROM links WHERE child_hash=? AND relation='keyframe_of' LIMIT 1", (fh,)).fetchone()
        if not r:
            return None
        scene_id = r[0]
        r2 = con.execute("SELECT video_hash, start, end, meta FROM scenes WHERE id=?", (scene_id,)).fetchone()
    if r2:
        meta = None
        try:
            meta = json.loads(r2[3]) if r2[3] else None
        except Exception:
            meta = None
        return {"scene_id": scene_id, "video_hash": r2[0], "start": r2[1], "end": r2[2], "meta": meta}
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--csv", help="Write matches to CSV path", required=False)
    ap.add_argument("--print-paths", action="store_true", help="Print only source paths for thumbnails", required=False)
    args = ap.parse_args()

    cfg = _load_cfg()
    paths = cfg.get("paths", {}) or {}
    index_path = paths.get("faiss_index_path") or ""
    if not index_path or not os.path.isfile(index_path):
        print(json.dumps({"error": "text index not found"}))
        return

    vec, _np = _embed_query(args.text)
    out = _search_faiss(index_path, vec, cfg, args.topk)
    if args.print_paths:
        for m in out:
            p = m.get("source_path") or ""
            if p:
                print(p)
        return
    if args.csv:
        import csv
        with open(args.csv, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["source_path","modality","score","scene_start","scene_end"])  # header
            for m in out:
                scn = m.get("scene") or {}
                w.writerow([m.get("source_path"), m.get("modality"), m.get("score"), (scn.get("start") if scn else None), (scn.get("end") if scn else None)])
        print(json.dumps({"matches": len(out), "csv": args.csv}))
        return
    print(json.dumps({"matches": out}, ensure_ascii=False))


if __name__ == "__main__":
    main()


def search_text_index(text: str, topk: int = 50) -> Dict[str, Any]:
    """Programmatic API: search text index and return matches with scene info.

    Returns a dict {"matches": [{source_path, modality, score, scene?}, ...]}
    """
    cfg = _load_cfg()
    paths = cfg.get("paths", {}) or {}
    # Try Qdrant first if enabled
    q_matches = _search_qdrant(text, topk, cfg)
    if q_matches:
        return {"matches": [_match(m, m.get("score"), cfg) for m in q_matches]}

    index_path = paths.get("faiss_index_path") or ""
    if not index_path or not os.path.isfile(index_path):
        return {"matches": []}
    vec, _np = _embed_query(text)
    return {"matches": _search_faiss(index_path, vec, cfg, topk)}
