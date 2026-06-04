import sys
import os
from pathlib import Path
from unittest.mock import patch
from steps.common.platform_config import PlatformHelper

def test_platform_helper_os_checks():
    helper = PlatformHelper()
    with patch("sys.platform", "win32"):
        assert helper.is_windows is True
        assert helper.is_mac is False
        assert helper.is_linux is False
        assert helper.get_binary_name("qdrant") == "qdrant.exe"

    with patch("sys.platform", "darwin"):
        assert helper.is_windows is False
        assert helper.is_mac is True
        assert helper.is_linux is False
        assert helper.get_binary_name("qdrant") == "qdrant"

    with patch("sys.platform", "linux"):
        assert helper.is_windows is False
        assert helper.is_mac is False
        assert helper.is_linux is True
        assert helper.get_binary_name("qdrant") == "qdrant"

def test_platform_helper_data_roots(tmp_path):
    helper = PlatformHelper()
    
    # Overrides
    with patch.dict(os.environ, {"GOODQ_DATA_ROOT": str(tmp_path)}):
        assert helper.get_data_root() == tmp_path

    # Windows convention
    with patch("sys.platform", "win32"), patch.dict(os.environ, {"PROGRAMDATA": str(tmp_path)}, clear=True):
        assert helper.get_data_root() == tmp_path / "GoodQ4All"

    # Mac convention
    with patch("sys.platform", "darwin"), patch("pathlib.Path.home", return_value=tmp_path), patch.dict(os.environ, {}, clear=True):
        assert helper.get_data_root() == tmp_path / "Library/Application Support/GoodQ4All"

    # Linux convention
    with patch("sys.platform", "linux"), patch("pathlib.Path.home", return_value=tmp_path):
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}, clear=True):
            assert helper.get_data_root() == tmp_path / "goodq4all"
        with patch.dict(os.environ, {}, clear=True):
            assert helper.get_data_root() == tmp_path / ".local/share/goodq4all"

