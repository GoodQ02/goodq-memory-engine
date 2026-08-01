from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from cli import turboquant_candidate_benchmark


def _seed_candidate_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE embeddings (faiss_id INTEGER, modality TEXT, vector BLOB)"
        )
        for faiss_id, modality, vector in (
            (1, "text", [1.0, 0.0]),
            (2, "text", [0.0, 1.0]),
            (3, "audio", [0.5, 0.5]),
        ):
            connection.execute(
                "INSERT INTO embeddings VALUES (?, ?, ?)",
                (faiss_id, modality, np.asarray(vector, dtype=np.float32).tobytes()),
            )


def test_fixed_query_pack_uses_candidate_vectors_without_persisting_them(
    tmp_path: Path,
) -> None:
    root = tmp_path / "witness"
    database = root / "data" / "memory.db"
    database.parent.mkdir(parents=True)
    _seed_candidate_database(database)

    query_pack = turboquant_candidate_benchmark.build_fixed_query_pack(root, database)

    assert len(query_pack) == 4
    assert {item["kind"] for item in query_pack} == {"self", "cross"}
    assert all(isinstance(item["vector"], np.ndarray) for item in query_pack)
    assert all("raw_query" not in item for item in query_pack)
    assert all("vector" not in item for item in turboquant_candidate_benchmark.receipt_query_summary(query_pack))


def test_fixed_query_pack_rejects_database_outside_candidate_root(tmp_path: Path) -> None:
    root = tmp_path / "witness"
    root.mkdir()
    database = tmp_path / "canonical" / "memory.db"
    database.parent.mkdir()
    _seed_candidate_database(database)

    with pytest.raises(turboquant_candidate_benchmark.BenchmarkAuthorityError):
        turboquant_candidate_benchmark.build_fixed_query_pack(root, database)


def test_compare_query_pack_records_only_aggregate_agreement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query_pack = [
        {
            "kind": "self",
            "modality": "text",
            "dimension": 2,
            "source_faiss_id": 1,
            "vector": np.asarray([1.0, 0.0], dtype=np.float32),
        }
    ]

    clock = iter((0.0, 1.0, 2.0, 2.5))
    monkeypatch.setattr(turboquant_candidate_benchmark, "perf_counter", lambda: next(clock))

    receipt = turboquant_candidate_benchmark.compare_query_pack(
        query_pack,
        baseline_query=lambda _item: [{"id": 1, "score": 0.0}],
        active_query=lambda _item: [
            {
                "id": 1,
                "score": 0.0,
                "_retrieval_route": "turboquant_candidate_exact_rerank",
            }
        ],
    )

    assert receipt["status"] == "pass"
    assert receipt["query_count"] == 1
    assert receipt["exact_match_count"] == 1
    assert receipt["fallback_count"] == 0
    assert "vector" not in str(receipt)


def test_write_benchmark_receipt_stays_under_candidate_root(tmp_path: Path) -> None:
    root = tmp_path / "witness"
    root.mkdir()
    receipt = {"status": "pass", "query_count": 1}

    path = turboquant_candidate_benchmark.write_benchmark_receipt(root, receipt)

    assert path == root / "turboquant-ab-receipt.json"
    assert path.is_file()
    assert "vector" not in path.read_text(encoding="utf-8")
