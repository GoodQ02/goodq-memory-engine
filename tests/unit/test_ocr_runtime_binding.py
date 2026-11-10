"""OCR must not inherit an unrelated or stale shared interpreter."""

from pathlib import Path

from configs.python_paths import PythonPathConfig
from scripts.config_schema import ImageOCRConfig
import pytest


def test_missing_local_ocr_runtime_does_not_fall_back_to_conda(monkeypatch):
    config = PythonPathConfig()
    config.is_sandboxed = False
    monkeypatch.setattr(Path, "is_file", lambda _path: False)
    config._env_pythons["goodq_ocr"] = Path("stale-conda/python.exe")
    assert config.get_env_python("goodq_ocr") is None


def test_missing_packaged_ocr_runtime_does_not_use_shared_python(monkeypatch):
    config = PythonPathConfig()
    config.is_sandboxed = True
    monkeypatch.setattr(Path, "is_file", lambda _path: False)
    assert config.get_env_python("goodq_ocr") is None


def test_cpu_is_portable_default_and_unqualified_devices_are_rejected():
    assert ImageOCRConfig().device == "cpu"
    assert ImageOCRConfig(device="cuda:0").device == "cuda:0"
    with pytest.raises(ValueError):
        ImageOCRConfig(device="cuda:1")
