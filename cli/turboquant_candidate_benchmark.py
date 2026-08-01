"""Read-only, candidate-only TurboQuant query-pack authority."""

from __future__ import annotations

import math
import copy
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from steps.common import sqlite_read_authority
from steps.common.memory_stores import FaissMemory
from steps.common.retrieval_events import RetrievalEventPolicy


class BenchmarkAuthorityError(RuntimeError):
    """Raised when a benchmark would escape its sealed candidate root."""


def _contained_database(root: Path, database: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved_database = database.resolve(strict=True)
    try:
        resolved_database.relative_to(resolved_root)
    except ValueError as exc:
        raise BenchmarkAuthorityError("candidate database escapes witness root") from exc
    if not resolved_database.is_file():
        raise BenchmarkAuthorityError("candidate database is not a file")
    return resolved_database


def build_fixed_query_pack(root: Path, database: Path) -> list[dict[str, Any]]:
    """Build deterministic self/cross queries from candidate vectors in memory only."""
    resolved_database = _contained_database(root, database)
    connection = sqlite_read_authority.open_sqlite_read_connection(resolved_database)
    try:
        rows = connection.execute(
            "SELECT faiss_id, modality, vector FROM embeddings WHERE faiss_id IS NOT NULL AND vector IS NOT NULL ORDER BY modality, faiss_id"
        ).fetchall()
    finally:
        connection.close()

    grouped: dict[tuple[str, int], list[tuple[int, np.ndarray]]] = {}
    for faiss_id, modality, vector_blob in rows:
        vector = np.frombuffer(vector_blob, dtype=np.float32)
        if vector.ndim != 1 or vector.size == 0:
            continue
        key = (str(modality), int(vector.size))
        grouped.setdefault(key, []).append((int(faiss_id), vector.copy()))

    query_pack: list[dict[str, Any]] = []
    for (modality, dimension), vectors in grouped.items():
        for faiss_id, vector in vectors:
            query_pack.append(
                {
                    "kind": "self",
                    "modality": modality,
                    "dimension": dimension,
                    "source_faiss_id": faiss_id,
                    "vector": vector,
                }
            )
        if len(vectors) >= 2:
            first_id, first_vector = vectors[0]
            second_id, second_vector = vectors[1]
            query_pack.append(
                {
                    "kind": "cross",
                    "modality": modality,
                    "dimension": dimension,
                    "source_faiss_id": first_id,
                    "paired_faiss_id": second_id,
                    "vector": (first_vector + second_vector) / 2.0,
                }
            )
    return query_pack


def receipt_query_summary(query_pack: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return aggregate-safe query metadata; vectors never enter receipts."""
    return [
        {
            "kind": item["kind"],
            "modality": item["modality"],
            "dimension": item["dimension"],
        }
        for item in query_pack
    ]


def _same_hits(baseline: list[dict[str, Any]], active: list[dict[str, Any]]) -> bool:
    if len(baseline) != len(active):
        return False
    for left, right in zip(baseline, active):
        if left.get("id") != right.get("id"):
            return False
        try:
            if not math.isclose(
                float(left.get("score")),
                float(right.get("score")),
                rel_tol=1e-6,
                abs_tol=1e-6,
            ):
                return False
        except (TypeError, ValueError):
            return False
    return True


def compare_query_pack(
    query_pack: list[dict[str, Any]],
    *,
    baseline_query: Any,
    active_query: Any,
) -> dict[str, Any]:
    """Compare in-memory vector queries and return an aggregate-safe receipt."""
    baseline_latencies: list[float] = []
    active_latencies: list[float] = []
    exact_match_count = 0
    fallback_count = 0
    for item in query_pack:
        started = perf_counter()
        baseline_hits = baseline_query(item)
        baseline_latencies.append(perf_counter() - started)
        started = perf_counter()
        active_hits = active_query(item)
        active_latencies.append(perf_counter() - started)
        if _same_hits(baseline_hits, active_hits):
            exact_match_count += 1
        if any(hit.get("_retrieval_route") != "turboquant_candidate_exact_rerank" for hit in active_hits):
            fallback_count += 1
    query_count = len(query_pack)
    baseline_median = float(np.median(baseline_latencies)) if baseline_latencies else 0.0
    active_median = float(np.median(active_latencies)) if active_latencies else 0.0
    passed = (
        query_count > 0
        and exact_match_count == query_count
        and fallback_count == 0
        and active_median <= baseline_median
    )
    return {
        "status": "pass" if passed else "fail",
        "query_count": query_count,
        "query_summary": receipt_query_summary(query_pack),
        "exact_match_count": exact_match_count,
        "fallback_count": fallback_count,
        "baseline_median_seconds": baseline_median,
        "active_median_seconds": active_median,
    }


def write_benchmark_receipt(root: Path, receipt: dict[str, Any]) -> Path:
    """Write one aggregate-only receipt below an existing candidate root."""
    resolved_root = root.resolve(strict=True)
    path = resolved_root / "turboquant-ab-receipt.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


_INDEX_PATHS = {
    "audio": "faiss_audio_path",
    "clip": "faiss_clip_path",
    "dino": "faiss_dino_path",
    "text": "faiss_index_path",
    "audio_transcript": "faiss_index_path",
    "frame_text": "faiss_index_path",
}


def run_benchmark_from_snapshot(snapshot_path: Path, *, top_k: int = 5) -> Path:
    """Run a candidate-only A/B comparison over one sealed witness snapshot."""
    snapshot = Path(snapshot_path).resolve(strict=True)
    config = json.loads(snapshot.read_text(encoding="utf-8"))
    witness = config.get("witness") or {}
    paths = config.get("paths") or {}
    root = Path(witness["artifact_root"]).resolve(strict=True)
    database = Path(paths["db_path"]).resolve(strict=True)
    _contained_database(root, database)
    if config.get("ingestion_isolation") is not True or witness.get("promotion_enabled") is not False:
        raise BenchmarkAuthorityError("snapshot is not a non-promoting isolated candidate")

    active_cfg = copy.deepcopy(config)
    active_cfg.setdefault("witness", {})["allow_turboquant_active_retrieval"] = True
    baseline_cfg = copy.deepcopy(config)
    baseline_cfg.setdefault("witness", {}).pop("allow_turboquant_active_retrieval", None)
    stores: dict[tuple[str, int, str], tuple[FaissMemory, FaissMemory]] = {}

    def query_with(cfg: dict[str, Any], item: dict[str, Any], *, active: bool) -> list[dict[str, Any]]:
        modality = str(item["modality"])
        index_key = _INDEX_PATHS.get(modality)
        if index_key is None:
            raise BenchmarkAuthorityError(f"unsupported candidate modality: {modality}")
        index_path = str(paths.get(index_key) or "")
        if not index_path:
            raise BenchmarkAuthorityError(f"snapshot lacks index path for modality: {modality}")
        key = (modality, int(item["dimension"]), index_path)
        if key not in stores:
            stores[key] = (
                FaissMemory(index_path, key[1], db_path=str(database), cfg=baseline_cfg, retrieval_event_policy=RetrievalEventPolicy(enabled=False)),
                FaissMemory(index_path, key[1], db_path=str(database), cfg=active_cfg, retrieval_event_policy=RetrievalEventPolicy(enabled=False)),
            )
        baseline_store, active_store = stores[key]
        store = active_store if active else baseline_store
        return store.query(item["vector"].tolist(), top_k=top_k, retrieval_context="system.healthcheck")

    query_pack = build_fixed_query_pack(root, database)
    receipt = compare_query_pack(
        query_pack,
        baseline_query=lambda item: query_with(baseline_cfg, item, active=False),
        active_query=lambda item: query_with(active_cfg, item, active=True),
    )
    receipt["candidate_root"] = str(root)
    receipt["top_k"] = top_k
    return write_benchmark_receipt(root, receipt)
