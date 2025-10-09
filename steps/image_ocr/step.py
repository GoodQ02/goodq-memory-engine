from __future__ import annotations
from typing import Any, Dict, Optional

from GoodQ_4_All.steps.common.tool_paths import resolve_tesseract


def image_ocr(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Tesseract OCR if available, else placeholder.

    This keeps behavior safe if pytesseract/Pillow are not installed.
    """
    text: Optional[str] = None
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        tess = resolve_tesseract(cfg)
        if tess:
            pytesseract.pytesseract.tesseract_cmd = tess
        img_path = item.get("source_path")
        if isinstance(img_path, str):
            text = pytesseract.image_to_string(Image.open(img_path)) or None
    except Exception:
        text = None
    return {"ocr_text": text}
