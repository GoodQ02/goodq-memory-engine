from __future__ import annotations

import importlib
from pathlib import Path


def test_step_runner_surfaces_ocr_dependency_missing() -> None:
    from cli.step_runner import _derive_step_log_outcome

    status, error, extra = _derive_step_log_outcome(
        "image_ocr",
        {"ocr_meta": {"status": "dependency_missing", "reason": "pytesseract"}},
        verbose=False,
    )

    assert status == "skipped"
    assert error is None
    assert extra is not None
    assert extra["reason"] == "image_ocr_pytesseract"
    assert extra["result_meta"]["ocr_meta"]["status"] == "dependency_missing"


def test_step_runner_surfaces_direct_dino_clip_no_index_path() -> None:
    from cli.step_runner import _derive_step_log_outcome

    for step_name, meta_key in (
        ("image_embed_dino", "dino_meta"),
        ("image_embed_clip", "clip_meta"),
    ):
        status, error, extra = _derive_step_log_outcome(
            step_name,
            {meta_key: {"status": "no_index_path", "reason": "direct_faiss_index_unconfigured"}},
            verbose=False,
        )

        assert status == "skipped"
        assert error is None
        assert extra is not None
        assert extra["reason"] == f"{step_name}_direct_faiss_index_unconfigured"
        assert extra["embedding_emitted"] is False
        assert extra["result_meta"][meta_key]["status"] == "no_index_path"


def test_image_embed_dino_no_index_path_skips_model_load(monkeypatch, tmp_path: Path) -> None:
    module = importlib.import_module("steps.image_embed_dino.step")
    image_path = tmp_path / "scene.jpg"
    image_path.write_bytes(b"fake-image")

    monkeypatch.setattr(
        module,
        "_load",
        lambda: (_ for _ in ()).throw(AssertionError("DINO model load should not run")),
    )

    result = module.image_embed_dino({"source_path": str(image_path)}, {"paths": {}})

    assert result["dino_meta"]["status"] == "no_index_path"
    assert result["dino_meta"]["reason"] == "direct_faiss_index_unconfigured"


def test_image_embed_clip_no_index_path_skips_model_load_and_debug_log(monkeypatch, tmp_path: Path) -> None:
    module = importlib.import_module("steps.image_embed_clip.step")
    image_path = tmp_path / "scene.jpg"
    image_path.write_bytes(b"fake-image")

    monkeypatch.setattr(
        module,
        "_load",
        lambda: (_ for _ in ()).throw(AssertionError("CLIP model load should not run")),
    )
    monkeypatch.setattr(
        module,
        "_debug_env",
        lambda: (_ for _ in ()).throw(AssertionError("CLIP debug log should not run")),
    )

    result = module.image_embed_clip({"source_path": str(image_path)}, {"paths": {}})

    assert result["clip_meta"]["status"] == "no_index_path"
    assert result["clip_meta"]["reason"] == "direct_faiss_index_unconfigured"
