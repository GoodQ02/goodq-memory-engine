from __future__ import annotations

from typing import Dict

from steps.common.memory_router import MemoryRouter
from steps.common.memory_store import MemoryConfig, MemoryDims
from steps.common.memory_stores import build_text_stores


def build_memory_router(cfg: Dict) -> MemoryRouter:
    """Construct the active memory router with an ephemeral cache, optional FAISS parity, and canonical Qdrant retrieval."""
    memory_cfg = (cfg.get("memory") or {}) if isinstance(cfg, dict) else {}
    dims_cfg = memory_cfg.get("dims", {})
    read_priority = memory_cfg.get("routing", {}).get("read_priority", ["qdrant", "faiss", "chroma"])
    write_targets = memory_cfg.get("routing", {}).get("write_targets", ["faiss", "qdrant"])
    ttl_seconds = memory_cfg.get("ttl_seconds", 900)
    max_ephemeral = memory_cfg.get("max_ephemeral_items", 512)

    dims = MemoryDims(
        text=dims_cfg.get("text", 384),
        image=dims_cfg.get("image", 512),
        audio=dims_cfg.get("audio", 512),
    )
    config = MemoryConfig(
        read_priority=read_priority,
        write_targets=write_targets,
        dims=dims,
        ttl_seconds=ttl_seconds,
        max_ephemeral_items=max_ephemeral,
    )
    stores = build_text_stores(cfg)
    return MemoryRouter(stores, config=config)
