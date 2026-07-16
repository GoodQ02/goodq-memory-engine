"""Read-only required-service witness for explicit live/golden test profiles."""

import os

import pytest
import requests

from tests.runtime_profile import (
    require_live_profile,
    require_runtime_evidence,
    selected_runtime_epoch,
)


@pytest.mark.live_runtime
def test_goodq_api_status_matches_selected_epoch(goodq_test_profile):
    require_live_profile(goodq_test_profile, "GoodQ API status witness")
    epoch_id = selected_runtime_epoch(goodq_test_profile)
    api_url = os.environ.get("GOODQ_API_URL", "http://127.0.0.1:30000").rstrip("/")

    try:
        response = requests.get(f"{api_url}/api/status", timeout=5)
    except requests.RequestException as exc:
        require_runtime_evidence(
            goodq_test_profile,
            False,
            f"GoodQ API request failed: {type(exc).__name__}",
        )
        return

    require_runtime_evidence(
        goodq_test_profile,
        response.status_code == 200,
        f"GoodQ API status returned HTTP {response.status_code}",
    )
    try:
        payload = response.json()
    except ValueError:
        require_runtime_evidence(
            goodq_test_profile,
            False,
            "GoodQ API status did not return JSON",
        )
        return

    require_runtime_evidence(
        goodq_test_profile,
        isinstance(payload, dict),
        "GoodQ API status payload is not an object",
    )
    database = payload.get("database") if isinstance(payload.get("database"), dict) else {}
    checks = {
        "status is active": payload.get("status") == "active",
        "API component is running": payload.get("components", {}).get("api") == "running",
        "database exists": database.get("exists") is True,
        "database epoch matches selected authority": database.get("epoch") == epoch_id,
    }
    missing = [name for name, passed in checks.items() if not passed]
    require_runtime_evidence(
        goodq_test_profile,
        not missing,
        f"GoodQ API status evidence failed: {missing!r}",
    )
