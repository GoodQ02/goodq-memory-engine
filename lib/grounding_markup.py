"""Remove vision-language grounding markup from user-facing text.

Some caption models emit ``<ref>phrase</ref><box><x1><y1><x2><y2></box>``
grounding tokens. The phrase is kept; tags and box coordinates are removed.
Box patterns accept only coordinate characters, so they never cross a JSON
string boundary when applied to serialized responses.
"""
import re

_BOX = re.compile(r"<(box|quad)>(?:[\s\d,.\[\]()\-]|<[\s\d,.\-]*>)*</\1>")
_REF = re.compile(r"</?ref>")
_UNCLOSED_TAIL = re.compile(
    r"(?:<(?:box|quad)\b(?:>(?:[\s\d,.\[\]()\-]|<[\s\d,.\-]*>?)*(?:</(?:box|bo|b|quad|qua|qu|q)?>?)?)?|<ref\b>?|</(?:ref\b>?|re|r))\s*$"
)
_UNCLOSED_JSON_TAIL = re.compile(
    r'[ \t]*(?:<(?:box|quad)\b(?:>(?:[ \t\d,.\[\]()\-]|<[ \t\d,.\-]*>?)*(?:</(?:box|bo|b|quad|qua|qu|q)?>?)?)?|<ref\b>?|</(?:ref\b>?|re|r))(?=(?<!\\)")'
)
_MARKER_RE = re.compile(r"<(?:/?ref|box|quad)\b")
_JSON_MARKERS = (b"<ref", b"</ref", b"<box", b"<quad")


def has_grounding_markup(text):
    return isinstance(text, str) and bool(_MARKER_RE.search(text))


def strip_grounding_markup(text):
    """Return text without grounding tags; non-strings are returned unchanged."""
    if not has_grounding_markup(text):
        return text
    cleaned = _REF.sub("", _BOX.sub("", text))
    cleaned = _UNCLOSED_TAIL.sub("", cleaned)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def strip_grounding_markup_json(body):
    """Strip tags inside serialized JSON bytes without reformatting the document."""
    if not any(marker in body for marker in _JSON_MARKERS):
        return body
    text = body.decode("utf-8")
    cleaned = _REF.sub("", _BOX.sub("", text))
    cleaned = _UNCLOSED_JSON_TAIL.sub("", cleaned)
    return cleaned.encode("utf-8")
