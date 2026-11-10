from __future__ import annotations
from typing import Any, Dict, Optional

import os
import subprocess
from pathlib import Path

from steps.common.tool_resolver import ToolResolver


def _pdftotext(pdf_path: str, poppler_bin: Optional[str]) -> Dict[str, Any]:
    exe = None
    resolution = "tool_resolver"
    env = os.environ.copy()
    if poppler_bin and os.path.isdir(poppler_bin):
        env["PATH"] = poppler_bin + os.pathsep + env.get("PATH", "")
        candidate = os.path.join(poppler_bin, "pdftotext.exe" if os.name == "nt" else "pdftotext")
        if os.path.isfile(candidate):
            exe = candidate
            resolution = "configured_poppler_bin"
    if exe is None:
        tool = ToolResolver.resolve_tool("pdftotext")
        if tool.get("found") and tool.get("path"):
            exe = str(tool["path"])
    meta = {"engine": "pdftotext", "tool_path": exe, "tool_resolution": resolution}
    if exe is None:
        return {"pdf_text": None, "document_meta": {**meta, "status": "unavailable", "reason": "pdftotext_unavailable"}}
    parser_path = os.path.abspath(pdf_path)
    if os.name == "nt" and len(parser_path) >= 260 and not parser_path.startswith("\\\\?\\"):
        parser_path = ("\\\\?\\UNC\\" + parser_path[2:]) if parser_path.startswith("\\\\") else "\\\\?\\" + parser_path
    try:
        # Keep source stream order without layout column interleaving or word joins.
        proc = subprocess.run(
            [exe, "-raw", "-enc", "UTF-8", parser_path, "-"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=45,
            env=env,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as error:
        return {"pdf_text": None, "document_meta": {
            **meta, "status": "error", "reason": "parser_invocation_failed",
            "error_type": type(error).__name__, "error": str(error),
        }}
    meta.update({"returncode": proc.returncode, "stderr": proc.stderr})
    if proc.returncode != 0:
        return {"pdf_text": None, "document_meta": {**meta, "status": "error", "reason": "parser_failed"}}
    if not proc.stdout.strip():
        return {"pdf_text": proc.stdout, "document_meta": {**meta, "status": "error", "reason": "no_extractable_text"}}
    return {"pdf_text": proc.stdout, "document_meta": {**meta, "status": "ok"}}


def pdf_to_text(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not path.lower().endswith(".pdf"):
        return {"pdf_text": None, "document_meta": {"engine": "pdftotext", "status": "no_file", "reason": "invalid_pdf_path"}}
    if not Path(path).is_file():
        return {"pdf_text": None, "document_meta": {"engine": "pdftotext", "status": "no_file", "reason": "pdf_not_found"}}
    poppler_bin = (
        cfg.get("config", {})
        .get("tools", {})
        .get("poppler_bin")
    )
    return _pdftotext(path, poppler_bin)
