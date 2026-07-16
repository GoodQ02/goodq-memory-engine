from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from retrieval.multimodal_search import MultimodalSearchEngine


_INSPECTOR_MODULE = "steps.common.model_cache_inspector"
_PROVISIONER_MODULE = "steps.common.model_provisioner"
_CLIP_REPO = "openai/clip-vit-large-patch14"
_CLIP_REVISION = "32bd64288804d66eefd0ccbe215aa642df71cc41"
_TEXT_REPO = "sentence-transformers/all-MiniLM-L6-v2"
_TEXT_REVISION = "8b3219a92973c328a8e22fadcfa821b5dc75636a"


def _inspector():
    return importlib.import_module(_INSPECTOR_MODULE)


def _engine(models_root: Path) -> MultimodalSearchEngine:
    return MultimodalSearchEngine(
        {
            "qdrant": {
                "host": "http://127.0.0.1:6333",
                "collections": {
                    "text": "goodq_text",
                    "clip": "goodq_clip_scenes",
                    "audio": "goodq_audio",
                },
            },
            "paths": {
                "data_root": str(models_root.parent / "data"),
                "models_cache": str(models_root),
            },
        }
    )


def _snapshot_path(models_root: Path, repo_id: str, revision: str) -> Path:
    return (
        models_root
        / "hub"
        / f"models--{repo_id.replace('/', '--')}"
        / "snapshots"
        / revision
    )


def _seed_snapshot(
    models_root: Path,
    repo_id: str,
    revision: str,
    filenames: tuple[str, ...],
) -> Path:
    snapshot = _snapshot_path(models_root, repo_id, revision)
    snapshot.mkdir(parents=True)
    for index, filename in enumerate(filenames):
        target = snapshot / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"fixture-{index}".encode("utf-8"))
    return snapshot.resolve()


def _create_directory_redirect(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except OSError as exc:
        if os.name != "nt":
            pytest.skip(f"directory symlink unavailable: {exc}")

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"directory junction unavailable: {result.stderr or result.stdout}")


def _tree_state(root: Path) -> dict[str, tuple[str, int, int, bytes | None]]:
    paths = [root, *sorted(root.rglob("*"), key=lambda item: item.as_posix())]
    state: dict[str, tuple[str, int, int, bytes | None]] = {}
    for path in paths:
        stat = path.stat()
        relative = "." if path == root else path.relative_to(root).as_posix()
        state[relative] = (
            "file" if path.is_file() else "dir",
            stat.st_size,
            stat.st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
    return state


def _install_fake_model_libraries(
    monkeypatch: pytest.MonkeyPatch,
    calls: list[tuple[str, str, dict[str, object]]],
) -> None:
    class _FakeSentenceTransformer:
        def __init__(self, model_source: str, **kwargs: object) -> None:
            calls.append(("sentence", str(model_source), dict(kwargs)))

    class _FakeProcessor:
        @classmethod
        def from_pretrained(cls, model_source: str, **kwargs: object):
            calls.append(("clip_processor", str(model_source), dict(kwargs)))
            return cls()

    class _FakeModel:
        @classmethod
        def from_pretrained(cls, model_source: str, **kwargs: object):
            calls.append(("clip_model", str(model_source), dict(kwargs)))
            return cls()

        def eval(self):
            return self

    sentence_transformers = types.ModuleType("sentence_transformers")
    sentence_transformers.SentenceTransformer = _FakeSentenceTransformer
    transformers = types.ModuleType("transformers")
    transformers.CLIPModel = _FakeModel
    transformers.CLIPProcessor = _FakeProcessor
    torch = types.ModuleType("torch")

    monkeypatch.setitem(sys.modules, "sentence_transformers", sentence_transformers)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "torch", torch)


def test_model_cache_inspector_fresh_import_is_process_pure() -> None:
    script = f"""
import json
import os
import sys

path_before = list(sys.path)
env_before = dict(os.environ)
modules_before = set(sys.modules)
import {_INSPECTOR_MODULE} as imported
new_modules = set(sys.modules) - modules_before
forbidden_roots = {{
    "filelock",
    "huggingface_hub",
    "sentence_transformers",
    "transformers",
}}
print(json.dumps({{
    "module": imported.__name__,
    "path_unchanged": sys.path == path_before,
    "env_unchanged": dict(os.environ) == env_before,
    "provisioner_imported": "{_PROVISIONER_MODULE}" in sys.modules,
    "forbidden_imports": sorted(
        name for name in new_modules if name.split(".", 1)[0] in forbidden_roots
    ),
}}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        check=True,
        capture_output=True,
        text=True,
    )
    evidence = json.loads(result.stdout)

    assert evidence == {
        "module": _INSPECTOR_MODULE,
        "path_unchanged": True,
        "env_unchanged": True,
        "provisioner_imported": False,
        "forbidden_imports": [],
    }


def test_exact_snapshot_resolver_does_not_create_missing_root(tmp_path: Path) -> None:
    models_root = tmp_path / "absent-models"
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
huggingface_models:
  fixture_model:
    repo_id: fixture/model
    revision: pinned-revision
""".lstrip(),
        encoding="utf-8",
    )

    resolved = _inspector().resolve_pinned_model_snapshot(
        models_root,
        "fixture_model",
        registry_path=registry_path,
        required_files=("modules.json",),
    )

    assert resolved is None
    assert not models_root.exists()


def test_exact_snapshot_resolver_rejects_unpinned_snapshot(tmp_path: Path) -> None:
    models_root = tmp_path / "models"
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
huggingface_models:
  fixture_model:
    repo_id: fixture/model
    revision: pinned-revision
""".lstrip(),
        encoding="utf-8",
    )
    wrong_snapshot = _seed_snapshot(
        models_root,
        "fixture/model",
        "newer-but-unpinned",
        ("config.json", "modules.json", "model.safetensors"),
    )
    ref = wrong_snapshot.parents[1] / "refs" / "main"
    ref.parent.mkdir(parents=True)
    ref.write_text("newer-but-unpinned", encoding="utf-8")
    state_before = _tree_state(models_root)

    resolved = _inspector().resolve_pinned_model_snapshot(
        models_root,
        "fixture_model",
        registry_path=registry_path,
        required_files=("modules.json",),
    )

    assert resolved is None
    assert _tree_state(models_root) == state_before


def test_exact_snapshot_resolver_rejects_incomplete_pinned_snapshot(tmp_path: Path) -> None:
    models_root = tmp_path / "models"
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
huggingface_models:
  fixture_model:
    repo_id: fixture/model
    revision: pinned-revision
""".lstrip(),
        encoding="utf-8",
    )
    _seed_snapshot(
        models_root,
        "fixture/model",
        "pinned-revision",
        ("config.json", "model.safetensors"),
    )
    state_before = _tree_state(models_root)

    resolved = _inspector().resolve_pinned_model_snapshot(
        models_root,
        "fixture_model",
        registry_path=registry_path,
        required_files=("modules.json",),
    )

    assert resolved is None
    assert _tree_state(models_root) == state_before


def test_exact_snapshot_resolver_rejects_redirected_pinned_directory(tmp_path: Path) -> None:
    models_root = tmp_path / "models"
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
huggingface_models:
  fixture_model:
    repo_id: fixture/model
    revision: pinned-revision
""".lstrip(),
        encoding="utf-8",
    )
    arbitrary_target = models_root / "arbitrary-snapshot"
    arbitrary_target.mkdir(parents=True)
    for filename in ("config.json", "modules.json", "model.safetensors"):
        (arbitrary_target / filename).write_text("fixture", encoding="utf-8")
    pinned_path = _snapshot_path(
        models_root,
        "fixture/model",
        "pinned-revision",
    )
    pinned_path.parent.mkdir(parents=True)
    _create_directory_redirect(pinned_path, arbitrary_target)

    resolved = _inspector().resolve_pinned_model_snapshot(
        models_root,
        "fixture_model",
        registry_path=registry_path,
        required_files=("modules.json",),
    )

    assert resolved is None
    assert (arbitrary_target / "model.safetensors").read_text(encoding="utf-8") == "fixture"


def test_retrieval_loaders_do_not_call_libraries_or_create_absent_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    models_root = tmp_path / "absent-models"
    calls: list[tuple[str, str, dict[str, object]]] = []
    _install_fake_model_libraries(monkeypatch, calls)
    engine = _engine(models_root)

    engine._load_text_model()
    engine._load_clip_model()

    assert calls == []
    assert engine._text_model is None
    assert engine._clip_model is None
    assert np.array_equal(engine.encode_text_query("fixture"), np.zeros(384))
    assert np.array_equal(engine.encode_text_for_visual_search("fixture"), np.zeros(512))
    assert calls == []
    assert not models_root.exists()


def test_retrieval_loaders_use_exact_pinned_snapshots_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    models_root = tmp_path / "models"
    text_snapshot = _seed_snapshot(
        models_root,
        _TEXT_REPO,
        _TEXT_REVISION,
        ("config.json", "modules.json", "model.safetensors"),
    )
    clip_snapshot = _seed_snapshot(
        models_root,
        _CLIP_REPO,
        _CLIP_REVISION,
        ("config.json", "preprocessor_config.json", "model.safetensors"),
    )
    state_before = _tree_state(models_root)
    calls: list[tuple[str, str, dict[str, object]]] = []
    _install_fake_model_libraries(monkeypatch, calls)
    engine = _engine(models_root)

    engine._load_text_model()
    engine._load_clip_model()

    assert calls == [
        ("sentence", str(text_snapshot), {"local_files_only": True}),
        ("clip_processor", str(clip_snapshot), {"local_files_only": True}),
        (
            "clip_model",
            str(clip_snapshot),
            {"use_safetensors": True, "local_files_only": True},
        ),
    ]
    assert engine._text_model is not None
    assert engine._clip_model is not None
    assert _tree_state(models_root) == state_before
