from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

LEGACY_MEMORY_TIER_ALIASES: Dict[str, str] = {
    "chroma": "ephemeral",
}


@runtime_checkable
class MemoryStore(Protocol):
    """Minimal interface for tiered memory backends."""

    def insert(self, vectors: List[Dict[str, Any]]) -> bool:
        ...

    def query(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        *,
        retrieval_context: str,
    ) -> List[Dict[str, Any]]:
        ...

    def stats(self) -> Dict[str, Any]:
        ...


@dataclass
class MemoryDims:
    text: int = 384
    image: int = 512
    audio: int = 512


@dataclass
class MemoryConfig:
    """Shared configuration for the memory router."""

    read_priority: List[str]
    write_targets: List[str]
    dims: MemoryDims
    ttl_seconds: int = 900  # for tier-0 ephemeral cache
    promote_min_hits: int = 3  # hits before promoting from tier-0 to tier-1/2
    max_ephemeral_items: int = 512

    def expected_dim_for_modality(self, modality: Optional[str]) -> Optional[int]:
        """Map modality name to expected embedding dimension."""
        if not modality:
            return None
        mod = modality.lower()
        if mod in {"text", "frame_text", "caption", "ocr", "transcript"}:
            return self.dims.text
        if mod in {"image", "clip", "vision"}:
            return self.dims.image
        if mod in {"audio", "sound", "voice"}:
            return self.dims.audio
        return None


def normalize_memory_tier_name(name: Optional[str]) -> Optional[str]:
    """Map legacy tier labels onto the canonical memory-tier vocabulary."""
    if not isinstance(name, str):
        return None
    normalized = name.strip().lower()
    if not normalized:
        return None
    return LEGACY_MEMORY_TIER_ALIASES.get(normalized, normalized)


def normalize_memory_tier_list(names: Optional[List[str]]) -> List[str]:
    """Normalize a tier list while preserving order and removing duplicates."""
    if not isinstance(names, list):
        return []
    normalized: List[str] = []
    seen: set[str] = set()
    for name in names:
        tier = normalize_memory_tier_name(name)
        if not tier or tier in seen:
            continue
        normalized.append(tier)
        seen.add(tier)
    return normalized
