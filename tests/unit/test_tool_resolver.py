import sys
import os
import shutil
from pathlib import Path
from unittest.mock import patch
from steps.common.tool_resolver import ToolResolver

def test_tool_resolver_ffmpeg(tmp_path):
    # Mock shutil.which
    with patch("shutil.which", return_value=str(tmp_path / "ffmpeg")):
        res = ToolResolver.resolve_tool("ffmpeg")
        assert res["found"] is True
        assert "ffmpeg" in res["path"]
        assert res["severity"] == "error"

def test_tool_resolver_not_found():
    with patch("shutil.which", return_value=None), patch("pathlib.Path.exists", return_value=False):
        res = ToolResolver.resolve_tool("tesseract")
        assert res["found"] is False
        assert res["path"] is None
        assert res["severity"] == "warning"
        assert any(pkg in res["install_hint"].lower() for pkg in ["brew install", "apt install", "winget install", "apt-get"])


def test_windows_pdftotext_fallback_does_not_satisfy_ffmpeg(monkeypatch, tmp_path):
    program_files = tmp_path / "Program Files"
    pdftotext = program_files / "Git" / "mingw64" / "bin" / "pdftotext.exe"
    pdftotext.parent.mkdir(parents=True)
    pdftotext.write_text("stub", encoding="utf-8")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("ProgramFiles", str(program_files))
    monkeypatch.setattr(shutil, "which", lambda _: None)

    result = ToolResolver.resolve_tool("ffmpeg")

    assert result["found"] is False
    assert result["path"] is None
