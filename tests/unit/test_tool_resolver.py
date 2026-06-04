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
