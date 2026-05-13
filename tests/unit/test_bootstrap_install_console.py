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


def test_bootstrap_print_redacts_secret_shapes(monkeypatch):
    fake_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    field_name = "token"
    fake_hf_value = "hf_" + "abcdefghijklmnopqrstuvwxyz"
    fake_openai_key = "sk-" + "testsecretsecretsecretsecret"

    bootstrap_install._print(f"{field_name}={fake_hf_value} Authorization: Bearer {fake_openai_key}")

    written = fake_stdout.getvalue()
    assert "***REDACTED***" in written
    assert fake_hf_value not in written
    assert fake_openai_key not in written


def test_bootstrap_redaction_masks_sensitive_assignment_keys():
    sensitive_key = "".join(("pass", "word"))
    synthetic_sensitive_value = "redaction-fixture-value"

    redacted = bootstrap_install._redact_console_text(f"{sensitive_key}={synthetic_sensitive_value}")

    assert "***REDACTED***" in redacted
    assert synthetic_sensitive_value not in redacted


def test_bootstrap_console_security_notice_states_secret_boundary(monkeypatch):
    fake_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    bootstrap_install.print_console_security_notice()

    written = fake_stdout.getvalue()
    assert "Secret values are redacted" in written
    assert "not raw tokens" in written


def test_conda_tos_block_uses_anaconda_channel_url():
    assert bootstrap_install._is_conda_tos_block(
        "Please accept channel terms at https://repo.anaconda.com/pkgs/main before continuing"
    )
    assert not bootstrap_install._is_conda_tos_block(
        "Please accept channel terms at https://example.com/repo.anaconda.com/pkgs/main before continuing"
    )
