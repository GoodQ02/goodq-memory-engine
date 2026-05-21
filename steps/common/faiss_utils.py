from __future__ import annotations

from typing import Any


def create_hnsw_id_index(faiss_module: Any, dim: int, links: int = 32) -> Any:
    """Create a HNSW FAISS index that can accept stable explicit IDs."""
    if not hasattr(faiss_module, "IndexIDMap2"):
        raise RuntimeError("faiss_index_id_map_unavailable")
    base_index = faiss_module.IndexHNSWFlat(dim, links)
    base_index.hnsw.efConstruction = 200
    base_index.hnsw.efSearch = 50
    return faiss_module.IndexIDMap2(base_index)


def add_with_required_ids(index: Any, vectors: Any, ids: Any) -> None:
    """Add vectors to FAISS only when explicit stable IDs are supported."""
    add_with_ids = getattr(index, "add_with_ids", None)
    if not callable(add_with_ids):
        raise RuntimeError("faiss_index_lacks_add_with_ids")
    try:
        add_with_ids(vectors, ids)
    except Exception as exc:
        raise RuntimeError("faiss_add_with_ids_failed") from exc
