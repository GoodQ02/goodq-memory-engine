from __future__ import annotations

import io
import sys

from scripts import bootstrap_install


class _Cp1252Stdout(io.StringIO):
    encoding = "cp1252"

    def write(self, s: str) -> int:  # type: ignore[override]
        s.encode(self.encoding)
        return super().write(s)


def test_bootstrap_print_falls_back_for_cp1252_console(monkeypatch):
    fake_stdout = _Cp1252Stdout()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    bootstrap_install._print("prefetch progress \u2014 \U0001f525")

    written = fake_stdout.getvalue()
    assert "prefetch progress" in written
