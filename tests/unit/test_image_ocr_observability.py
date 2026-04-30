from __future__ import annotations

import builtins
import sys
import types
from pathlib import Path


def test_image_ocr_reports_no_source_path() -> None:
    from steps.image_ocr.step import image_ocr

    result = image_ocr({}, {"config": {}})

    assert result["ocr_text"] is None
    assert result["ocr_meta"]["status"] == "no_source_path"
    assert result["ocr_meta"]["reason"] == "source_image_missing"


def test_image_ocr_reports_missing_dependency(monkeypatch, tmp_path: Path) -> None:
    from steps.image_ocr.step import image_ocr

    image_path = tmp_path / "scene.jpg"
    image_path.write_bytes(b"fake-image")
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "pytesseract":
            raise ModuleNotFoundError("missing dependency", name="pytesseract")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    result = image_ocr({"source_path": str(image_path)}, {"config": {}})

    assert result["ocr_text"] is None
    assert result["ocr_meta"]["status"] == "dependency_missing"
    assert result["ocr_meta"]["reason"] == "pytesseract"
    assert result["ocr_meta"]["exc_type"] == "ModuleNotFoundError"


def test_image_ocr_reports_no_text(monkeypatch, tmp_path: Path) -> None:
    from steps.image_ocr.step import image_ocr

    image_path = tmp_path / "scene.jpg"
    image_path.write_bytes(b"fake-image")

    pytesseract_mod = types.SimpleNamespace(
        pytesseract=types.SimpleNamespace(tesseract_cmd=None),
        image_to_string=lambda _image: "   ",
    )
    pil_mod = types.ModuleType("PIL")
    pil_mod.Image = types.SimpleNamespace(open=lambda _path: object())
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract_mod)
    monkeypatch.setitem(sys.modules, "PIL", pil_mod)

    result = image_ocr({"source_path": str(image_path)}, {"config": {}})

    assert result["ocr_text"] is None
    assert result["ocr_meta"]["status"] == "no_text"
    assert result["ocr_meta"]["reason"] == "empty_ocr_text"


def test_image_ocr_reports_text_with_meta(monkeypatch, tmp_path: Path) -> None:
    from steps.image_ocr.step import image_ocr

    image_path = tmp_path / "scene.jpg"
    image_path.write_bytes(b"fake-image")

    pytesseract_mod = types.SimpleNamespace(
        pytesseract=types.SimpleNamespace(tesseract_cmd=None),
        image_to_string=lambda _image: " SEINFELD \n",
    )
    pil_mod = types.ModuleType("PIL")
    pil_mod.Image = types.SimpleNamespace(open=lambda _path: object())
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract_mod)
    monkeypatch.setitem(sys.modules, "PIL", pil_mod)

    result = image_ocr({"source_path": str(image_path)}, {"config": {}})

    assert result["ocr_text"] == "SEINFELD"
    assert result["ocr_meta"]["status"] == "ok"
    assert result["ocr_meta"]["engine"] == "tesseract"
    assert result["ocr_meta"]["text_length"] == len("SEINFELD")
