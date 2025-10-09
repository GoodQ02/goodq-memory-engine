from __future__ import annotations
import argparse
import hashlib
import json
import os
from typing import Any, Dict, List, Tuple


def _load_cfg() -> Dict[str, Any]:
    from GoodQ_4_All.steps.common.config_loader import load_configs
    return load_configs({})


def _embed_query(text: str) -> Tuple[Any, Any]:
    from sentence_transformers import SentenceTransformer  # type: ignore
    import numpy as np  # type: ignore
    import torch  # type: ignore

    device = "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
    model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
    vec = model.encode([text], normalize_embeddings=True).astype("float32")
    return vec, np


def _search_faiss(index_path: str, vec) -> Tuple[List[int], List[float]]:
    import faiss  # type: ignore
    idx = faiss.read_index(index_path)
    D, I = idx.search(vec, k=10)
    ids = [int(i) for i in (I[0] if len(I) else [])]
    scores = [float(d) for d in (D[0] if len(D) else [])]
    return ids, scores


def _results_from_db(ids: List[int], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    import sqlite3

    db_path = (cfg.get("paths", {}) or {}).get("db_path") or ""
    out: List[Dict[str, Any]] = []
    if not db_path or not os.path.isfile(db_path) or not ids:
        return out
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    qmarks = ",".join(["?"] * len(ids))
    cur.execute(f"SELECT hash, faiss_id, source_path, modality FROM embeddings WHERE faiss_id IN ({qmarks})", ids)
    rows = cur.fetchall()
    con.close()
    for h, fid, sp, mod in rows:
        out.append({"hash": h, "faiss_id": fid, "source_path": sp, "modality": mod})
    return out


def _scene_for_frame(frame_path: str, cfg: Dict[str, Any]) -> Dict[str, Any] | None:
    import sqlite3

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
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT parent_hash FROM links WHERE child_hash=? AND relation='keyframe_of' LIMIT 1", (fh,))
    r = cur.fetchone()
    if not r:
        con.close()
        return None
    scene_id = r[0]
    cur.execute("SELECT video_hash, start, end, meta FROM scenes WHERE id=?", (scene_id,))
    r2 = cur.fetchone()
    con.close()
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

    vec, np = _embed_query(args.text)
    ids, scores = _search_faiss(index_path, vec)
    rows = _results_from_db(ids[: args.topk], cfg)
    out = []
    for r, sc in zip(rows, scores):
        scene_info = _scene_for_frame(r.get("source_path") or "", cfg) if (r.get("modality") == "frame_text") else None
        out.append({
            "source_path": r.get("source_path"),
            "modality": r.get("modality"),
            "score": sc,
            "scene": scene_info,
        })
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
    index_path = paths.get("faiss_index_path") or ""
    if not index_path or not os.path.isfile(index_path):
        return {"matches": []}
    vec, _np = _embed_query(text)
    ids, scores = _search_faiss(index_path, vec)
    rows = _results_from_db(ids[: topk], cfg)
    out: List[Dict[str, Any]] = []
    for r, sc in zip(rows, scores):
        scene_info = _scene_for_frame(r.get("source_path") or "", cfg) if (r.get("modality") == "frame_text") else None
        out.append({
            "source_path": r.get("source_path"),
            "modality": r.get("modality"),
            "score": sc,
            "scene": scene_info,
        })
    return {"matches": out}
