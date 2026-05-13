from __future__ import annotations

import builtins
import importlib
from types import SimpleNamespace


def test_console_print_falls_back_on_unicode_encode_error(monkeypatch) -> None:
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")
    monkeypatch.delenv("GOODQ_REQUIRE_GPU", raising=False)

    gpu_config = importlib.reload(importlib.import_module("steps.common.gpu_config"))
    monkeypatch.setattr(gpu_config.sys, "stdout", SimpleNamespace(encoding="cp1252"))

    calls: list[str] = []

    def fake_print(value: str) -> None:
        calls.append(value)
        if any(ch in value for ch in ("╔", "═", "╗")):
            raise UnicodeEncodeError("charmap", value, 0, len(value), "cannot encode")

    monkeypatch.setattr(builtins, "print", fake_print)

    gpu_config._console_print("╔══╗")

    assert calls[0] == "╔══╗"
    assert calls[-1] != calls[0]
    assert all(ord(ch) < 128 for ch in calls[-1])
