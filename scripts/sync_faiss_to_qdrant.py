#!/usr/bin/env python3
"""
One-time helper to push FAISS vectors into Qdrant for long-term storage.

Assumptions:
- Uses text embedding dimensionality from config.memory.dims.text (default 384).
- Reads FAISS index at paths.faiss_index_path.
- Writes to Qdrant collection for "text" (config.qdrant.collections.text) on the configured host.

Usage:
  python scripts/sync_faiss_to_qdrant.py --batch 500
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Dict

from steps.common.config_loader import load_configs
from steps.common.qdrant_client import build_qdrant_client


def load_faiss_vectors(index_path: str, batch: int) -> List[List[float]]:
    import faiss  # type: ignore
    import numpy as np  # type: ignore

    idx = faiss.read_index(index_path)
    total = int(getattr(idx, "ntotal", 0))
    vectors: List[List[float]] = []
    cursor = 0
    while cursor < total:
        n = min(batch, total - cursor)
        arr = faiss.vector_float_to_array(idx.reconstruct_n(cursor, n))
        dim = int(len(arr) / n) if n else 0
        if dim <= 0:
            break
        mat = np.array(arr, dtype="float32").reshape(n, dim)
        vectors.extend(mat.tolist())
        cursor += n
    return vectors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=500, help="Batch size for Qdrant upserts")
    args = parser.parse_args()

    cfg = load_configs({})
    paths = (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}
    memory_cfg = (cfg.get("memory") or {}) if isinstance(cfg, dict) else {}
    dims_cfg = memory_cfg.get("dims", {}) or {}
    text_dim = int(dims_cfg.get("text", 384))
    index_path = paths.get("faiss_index_path")
    if not index_path:
        print("[ERROR] faiss_index_path missing in paths config.", file=sys.stderr)
        sys.exit(1)

    q_client = build_qdrant_client(cfg, dim=text_dim, key="text")
    if not q_client:
        print("[ERROR] Qdrant client not available/enabled.", file=sys.stderr)
        sys.exit(1)
    if not q_client.ensure_collection():
        print("[ERROR] Unable to ensure Qdrant collection exists.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Loading FAISS vectors from {index_path} ...")
    vectors = load_faiss_vectors(index_path, args.batch)
    if not vectors:
        print("[WARN] No vectors found in FAISS index.")
        return

    print(f"[INFO] Upserting {len(vectors)} vectors into Qdrant (batch={args.batch}) ...")
    success = 0
    for i in range(0, len(vectors), args.batch):
        chunk = vectors[i : i + args.batch]
        points: List[Dict[str, object]] = [
            {"id": i + j, "vector": vec, "payload": {"modality": "text", "source": "faiss_sync"}}
            for j, vec in enumerate(chunk)
        ]
        if q_client.upsert(points):
            success += len(chunk)
    print(f"[INFO] Completed. Upserted {success}/{len(vectors)} vectors.")


if __name__ == "__main__":
    main()
