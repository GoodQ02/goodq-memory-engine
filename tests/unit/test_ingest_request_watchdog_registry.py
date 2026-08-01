from __future__ import annotations

import logging

from api.utils.ingest_requests import load_watchdog_registry


def test_unreadable_watchdog_registry_warns_and_preserves_safe_empty_fallback(
    tmp_path, caplog
) -> None:
    registry_path = tmp_path / "watchdog_registry.json"
    registry_path.write_text("{not-json", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="api.utils.ingest_requests"):
        result = load_watchdog_registry(registry_path)

    assert result == {}
    assert "Watchdog registry could not be read" in caplog.text
