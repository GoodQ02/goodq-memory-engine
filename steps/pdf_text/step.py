from __future__ import annotations
from typing import Any, Dict, Optional

import os
import subprocess


def _pdftotext(pdf_path: str, poppler_bin: Optional[str]) -> Optional[str]:
    exe = "pdftotext"
    env = os.environ.copy()
    if poppler_bin and os.path.isdir(poppler_bin):
        env["PATH"] = poppler_bin + os.pathsep + env.get("PATH", "")
        candidate = os.path.join(poppler_bin, "pdftotext.exe")
        if os.path.isfile(candidate):
            exe = candidate
    try:
        # Output to stdout with '-' to avoid temp files
        proc = subprocess.run(
            [exe, "-layout", "-enc", "UTF-8", pdf_path, "-"],
            capture_output=True,
            text=True,
            timeout=45,
            env=env,
        )
        if proc.returncode == 0:
            return proc.stdout
    except Exception:
        return None
    return None


def pdf_to_text(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not path.lower().endswith(".pdf"):
        return {"pdf_text": None}
    poppler_bin = (
        cfg.get("config", {})
        .get("tools", {})
        .get("poppler_bin")
    )
    text = _pdftotext(path, poppler_bin)
    return {"pdf_text": text}
