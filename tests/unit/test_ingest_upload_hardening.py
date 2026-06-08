from __future__ import annotations

import pytest
from pathlib import Path
from fastapi import HTTPException
import sys
import importlib.util

def _load_route_module(module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    module_path = repo_root / "api" / "routes" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"tests.{module_name}_route", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ingest_module = _load_route_module("ingest")

def test_safe_upload_name_valid():
    res = ingest_module.safe_upload_name("test_video.mp4")
    assert len(res) == 32 + 4  # 32 chars hex UUID + 4 chars extension
    assert res.endswith(".mp4")

def test_safe_upload_name_missing():
    with pytest.raises(HTTPException) as exc:
        ingest_module.safe_upload_name("")
    assert exc.value.status_code == 400
    assert "Filename is missing" in exc.value.detail

def test_safe_upload_name_path_traversal():
    bad_names = [
        "../test.mp4",
        "..\\test.mp4",
        "folder/test.mp4",
        "folder\\test.mp4",
        "C:\\test.mp4",
        "/absolute/path.mp4",
        "test.mp4/../evil.mp4",
        "test.mp4\\..\\evil.mp4",
        ".",
        "..",
    ]
    for bad in bad_names:
        with pytest.raises(HTTPException) as exc:
            ingest_module.safe_upload_name(bad)
        assert exc.value.status_code == 400

def test_safe_upload_name_null_byte():
    with pytest.raises(HTTPException) as exc:
        ingest_module.safe_upload_name("test.mp4\x00.evil")
    assert exc.value.status_code == 400

def test_safe_upload_name_unsupported_extension():
    with pytest.raises(HTTPException) as exc:
        ingest_module.safe_upload_name("test.exe")
    assert exc.value.status_code == 400
    assert "Unsupported ingest file type" in exc.value.detail

def test_get_allowed_import_roots(tmp_path):
    runtime_paths = {
        "import_inbox": tmp_path / "inbox",
        "processing": tmp_path / "processing",
    }
    roots = ingest_module.get_allowed_import_roots(runtime_paths)
    # Roots should contain inbox, inbox's parent (tmp_path), processing, processing's parent
    assert tmp_path.resolve() in roots
    assert (tmp_path / "inbox").resolve() in roots

def test_require_allowed_source_valid(tmp_path):
    allowed = [tmp_path]
    target = tmp_path / "subdir" / "file.mp4"
    res = ingest_module.require_allowed_source(target, allowed)
    assert res == target.resolve()

def test_require_allowed_source_invalid(tmp_path):
    allowed = [tmp_path / "inbox"]
    target = tmp_path / "outside.mp4"
    with pytest.raises(HTTPException) as exc:
        ingest_module.require_allowed_source(target, allowed)
    assert exc.value.status_code == 403
    assert "Source path is outside allowed import roots" in exc.value.detail
