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


def test_vhs_date_candidate_recovers_noisy_dec_prefix() -> None:
    from steps.image_ocr.step import _extract_vhs_date_candidates, _select_vhs_ocr_candidate

    texts = [
        "EC 16 2002",
        "DEC 18 2002",
    ]

    assert _extract_vhs_date_candidates(texts)[0] == "DEC 16 2002"
    assert _select_vhs_ocr_candidate(texts) == "DEC 16 2002"


def test_image_ocr_uses_vhs_timestamp_fallback(monkeypatch, tmp_path: Path) -> None:
    from PIL import Image

    from steps.image_ocr.step import image_ocr

    image_path = tmp_path / "scene.jpg"
    Image.new("RGB", (720, 376), "white").save(image_path)

    calls = {"count": 0}

    def _fake_image_to_string(_image, config=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return "   "
        return "EC 16 2002"

    pytesseract_mod = types.SimpleNamespace(
        pytesseract=types.SimpleNamespace(tesseract_cmd=None),
        image_to_string=_fake_image_to_string,
    )
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract_mod)

    result = image_ocr({"source_path": str(image_path)}, {"config": {}})

    assert result["ocr_text"] == "DEC 16 2002"
    assert result["ocr_meta"]["status"] == "ok"
    assert result["ocr_meta"]["strategy"] == "vhs_timestamp_fallback"
    assert "DEC 16 2002" in result["ocr_meta"]["date_candidates"]
    assert result["time_hints"]["explicit_dates"] == ["2002-12-16"]
    assert result["time_hints"]["months"] == ["december"]
