"""Remove vision-language grounding markup from user-facing text.

Some caption models emit ``<ref>phrase</ref><box><x1><y1><x2><y2></box>``
grounding tokens. The phrase is kept; tags and box coordinates are removed.
Box patterns accept only coordinate characters, so they never cross a JSON
string boundary when applied to serialized responses.
"""
import re

_BOX = re.compile(r"<(box|quad)>(?:[\s\d,.()\-]|<[\s\d,.\-]*>)*</\1>")
_REF = re.compile(r"</?ref>")
_MARKERS = ("<ref>", "</ref>", "<box>", "<quad>")


def has_grounding_markup(text):
    return isinstance(text, str) and any(marker in text for marker in _MARKERS)


def strip_grounding_markup(text):
    """Return text without grounding tags; non-strings are returned unchanged."""
    if not has_grounding_markup(text):
        return text
    cleaned = _REF.sub("", _BOX.sub("", text))
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def strip_grounding_markup_json(body):
    """Strip tags inside serialized JSON bytes without reformatting the document."""
    if not any(marker.encode() in body for marker in _MARKERS):
        return body
    text = body.decode("utf-8")
    return _REF.sub("", _BOX.sub("", text)).encode("utf-8")
