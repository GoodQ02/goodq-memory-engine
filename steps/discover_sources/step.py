from __future__ import annotations
import os
from typing import Any, Dict, List


def discover_sources(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Recursively discover inputs from `paths.input_inbox` with basic modality inference."""
    inbox = cfg.get("paths", {}).get("input_inbox", "")
    ex_audio = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"}
    ex_image = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
    ex_text = {".txt", ".md", ".json"}
    ex_pdf = {".pdf"}
    ex_video = {".mp4", ".m4v", ".mov", ".mkv", ".avi", ".wmv", ".webm"}

    items: List[Dict[str, Any]] = []
    if not inbox or not os.path.isdir(inbox):
        return items
    for root, _, files in os.walk(inbox):
        for name in files:
            path = os.path.join(root, name)
            try:
                ext = os.path.splitext(name)[1].lower()
                modality = (
                    "audio" if ext in ex_audio else
                    "image" if ext in ex_image else
                    "text" if ext in ex_text else
                    "pdf" if ext in ex_pdf else
                    "video" if ext in ex_video else
                    "unknown"
                )
                items.append({"source_path": path, "filename": name, "modality": modality})
            except Exception:
                continue
    return items
