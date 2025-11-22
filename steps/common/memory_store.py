from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class MemoryStore(Protocol):
    """Minimal interface for tiered memory backends."""

    def insert(self, vectors: List[Dict[str, Any]]) -> bool:
        ...

    def query(self, query_vector: List[float], top_k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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
