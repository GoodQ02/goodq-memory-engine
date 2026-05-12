from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


REDACTION_MARKER = "***REDACTED***"

_SENSITIVE_KEYS = {
    "token",
    "api_key",
    "apikey",
    "secret",
    "password",
    "passwd",
    "authorization",
    "credential",
    "credentials",
    "use_auth_token",
    "bearer",
    "cookie",
    "session",
    "client_secret",
    "private_key",
}

_JWT_LIKE_RE = re.compile(r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$")
_BEARER_RE = re.compile(r"^Bearer\s+\S+", re.IGNORECASE)
_OPENAI_KEY_RE = re.compile(r"^sk-(?:proj-)?[A-Za-z0-9_-]{20,}$")
_HF_TOKEN_RE = re.compile(r"^hf_[A-Za-z0-9]{20,}$")
_GITHUB_PAT_RE = re.compile(r"^github_pat_[A-Za-z0-9_]{20,}$")
_PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")


def redact_config(
    value: Any,
    *,
    include_local_values: bool = False,
    repo_root: str | os.PathLike[str] | None = None,
    data_root: str | os.PathLike[str] | None = None,
    user_root: str | os.PathLike[str] | None = None,
) -> Any:
    """
    Return a JSON-safe, operator-display copy of a config-like object.

    Runtime consumers should continue to use the raw config returned by
    load_configs(). This helper is only for display, logs, snapshots, and other
    operator surfaces.
    """
    roots = _display_roots(repo_root=repo_root, data_root=data_root, user_root=user_root)
    return _redact_value(value, key_hint=None, include_local_values=include_local_values, roots=roots)


def is_sensitive_key(key: str) -> bool:
    normalized = _normalize_key(key)
    if not normalized:
        return False
    if normalized in _SENSITIVE_KEYS:
        return True
    return (
        normalized.endswith("_token")
        or normalized.endswith("_secret")
        or normalized.endswith("_password")
        or normalized.endswith("_api_key")
        or normalized.endswith("_credential")
        or normalized.endswith("_credentials")
        or normalized.endswith("_cookie")
        or normalized.endswith("_session")
        or normalized.endswith("_private_key")
    )


def _redact_value(
    value: Any,
    *,
    key_hint: str | None,
    include_local_values: bool,
    roots: tuple[tuple[str, str], ...],
) -> Any:
    if key_hint and is_sensitive_key(key_hint):
        return REDACTION_MARKER

    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            redacted[key_text] = _redact_value(
                item,
                key_hint=key_text,
                include_local_values=include_local_values,
                roots=roots,
            )
        return redacted

    if isinstance(value, (list, tuple, set)):
        return [
            _redact_value(
                item,
                key_hint=key_hint,
                include_local_values=include_local_values,
                roots=roots,
            )
            for item in value
        ]

    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, Path):
        text = str(value)
    elif isinstance(value, str):
        text = value
    else:
        text = str(value)

    if _looks_like_secret_value(text):
        return REDACTION_MARKER
    if include_local_values:
        return text
    return _tokenize_local_path(text, roots)


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_")


def _looks_like_secret_value(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    return bool(
        _JWT_LIKE_RE.fullmatch(text)
        or _BEARER_RE.match(text)
        or _OPENAI_KEY_RE.fullmatch(text)
        or _HF_TOKEN_RE.fullmatch(text)
        or _GITHUB_PAT_RE.fullmatch(text)
        or _PRIVATE_KEY_RE.search(text)
    )


def _display_roots(
    *,
    repo_root: str | os.PathLike[str] | None,
    data_root: str | os.PathLike[str] | None,
    user_root: str | os.PathLike[str] | None,
) -> tuple[tuple[str, str], ...]:
    candidates: list[tuple[str, str]] = []
    for raw, placeholder in (
        (repo_root, "<PROJECT_ROOT>"),
        (data_root, "<GOODQ_DATA_ROOT>"),
        (user_root, "<USER_ROOT>"),
    ):
        normalized = _normalize_path(raw)
        if normalized:
            candidates.append((normalized, placeholder))
    candidates.sort(key=lambda item: len(item[0]), reverse=True)
    return tuple(candidates)


def _normalize_path(value: str | os.PathLike[str] | None) -> str:
    if value is None:
        return ""
    text = str(value).strip().strip("\"'")
    if not text:
        return ""
    return text.replace("\\", "/").rstrip("/")


def _tokenize_local_path(text: str, roots: Iterable[tuple[str, str]]) -> str:
    normalized_text = text.replace("\\", "/")
    lowered = normalized_text.lower()
    for root, placeholder in roots:
        root_lower = root.lower()
        if lowered == root_lower:
            return placeholder
        if lowered.startswith(root_lower + "/"):
            return placeholder + normalized_text[len(root) :]
    return normalized_text
