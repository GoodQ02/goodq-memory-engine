from __future__ import annotations

import json
import sys

import pytest

from steps.common.config_redaction import REDACTION_MARKER


def test_print_config_emits_valid_sanitized_json(monkeypatch, capsys) -> None:
    from cli import print_config

    sentinel = "SENTINEL_PRINT_CONFIG_VALUE"

    def fake_load_configs(_overrides=None):
        print("loader noise with SENTINEL_PRINT_CONFIG_VALUE")
        return {
            "host": {"profile": "BASELINE"},
            "home_assistant": {"token": sentinel},
            "paths": {"db_path": "Y:/DATA_ROOT/GoodQ_Data/epochs/demo/memory.db"},
        }

    monkeypatch.setattr(print_config, "load_configs", fake_load_configs)
    monkeypatch.setattr(sys, "argv", ["print_config"])

    print_config.main()
    captured = capsys.readouterr()

    payload = json.loads(captured.out)
    assert payload["home_assistant"]["token"] == REDACTION_MARKER
    assert sentinel not in captured.out
    assert sentinel not in captured.err
    assert REDACTION_MARKER in captured.out
    assert "<GOODQ_DATA_ROOT>" in captured.out


def test_print_config_can_include_local_values_without_exposing_secrets(monkeypatch, capsys) -> None:
    from cli import print_config

    sentinel = "SENTINEL_PRINT_CONFIG_VALUE"

    monkeypatch.setattr(
        print_config,
        "load_configs",
        lambda _overrides=None: {
            "home_assistant": {"HA_TOKEN": sentinel},
            "paths": {"db_path": "Y:/DATA_ROOT/GoodQ_Data/epochs/demo/memory.db"},
        },
    )
    monkeypatch.setattr(sys, "argv", ["print_config", "--include-local-values"])

    print_config.main()
    captured = capsys.readouterr()

    payload = json.loads(captured.out)
    assert payload["home_assistant"]["HA_TOKEN"] == REDACTION_MARKER
    assert payload["paths"]["db_path"] == "Y:/DATA_ROOT/GoodQ_Data/epochs/demo/memory.db"
    assert sentinel not in captured.out


def test_print_config_has_no_raw_secret_flag(monkeypatch, capsys) -> None:
    from cli import print_config

    monkeypatch.setattr(print_config, "load_configs", lambda _overrides=None: {})
    monkeypatch.setattr(sys, "argv", ["print_config", "--show-secrets"])

    with pytest.raises(SystemExit) as exc:
        print_config.main()

    captured = capsys.readouterr()
    assert exc.value.code != 0
    assert "show-secrets" in captured.err
