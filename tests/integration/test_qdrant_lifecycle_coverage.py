"""Integration test: assert the invariant that every Qdrant point in epoch
collections has ``ucf_promotion_status`` set after ingestion + promotion.

This prevents silent regression if a new embedding step is added later without
lifecycle metadata.
"""

import os
import json
import pytest
import requests

from tests.runtime_profile import (
    expected_epoch_collections,
    require_live_profile,
    require_runtime_evidence,
    selected_runtime_epoch,
)


QDRANT_HOST = os.environ.get("GOODQ_QDRANT_HOST", "http://127.0.0.1:6333")


def _get_collection_names(profile):
    """Return the read-only Qdrant collection inventory."""
    try:
        resp = requests.get(f"{QDRANT_HOST}/collections", timeout=5)
        require_runtime_evidence(
            profile,
            resp.status_code == 200,
            f"Qdrant collection inventory returned HTTP {resp.status_code}",
        )
        colls = resp.json().get("result", {}).get("collections", [])
    except requests.RequestException as exc:
        require_runtime_evidence(profile, False, f"Qdrant request failed: {type(exc).__name__}")
        return []
    return [c["name"] for c in colls if c.get("name")]


def _scroll_all_points(collection_name):
    """Scroll all points in a collection, return list of dicts."""
    all_points = []
    offset = None
    while True:
        body = {"limit": 100, "with_payload": True, "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        resp = requests.post(
            f"{QDRANT_HOST}/collections/{collection_name}/points/scroll",
            json=body, timeout=10,
        )
        if resp.status_code != 200:
            pytest.fail(
                f"Qdrant scroll failed for {collection_name}: HTTP {resp.status_code}",
                pytrace=False,
            )
        result = resp.json().get("result", {})
        points = result.get("points", [])
        all_points.extend(points)
        next_offset = result.get("next_page_offset")
        if not next_offset or not points:
            break
        offset = next_offset
    return all_points


@pytest.fixture(scope="module")
def qdrant_epoch_snapshot(goodq_test_profile):
    """Read the exact selected-epoch collections once for all lifecycle checks."""
    require_live_profile(goodq_test_profile, "Qdrant lifecycle witness")
    epoch_id = selected_runtime_epoch(goodq_test_profile)
    expected = expected_epoch_collections(goodq_test_profile, epoch_id)
    expected_names = set(expected.values())
    inventory = _get_collection_names(goodq_test_profile)
    selected_names = {
        name
        for name in inventory
        if name.startswith("goodq_") and name.endswith(epoch_id)
    }
    require_runtime_evidence(
        goodq_test_profile,
        selected_names == expected_names,
        (
            "selected-epoch Qdrant collections do not match the exact authority: "
            f"expected={sorted(expected_names)!r}, actual={sorted(selected_names)!r}"
        ),
    )

    snapshot = {name: _scroll_all_points(name) for name in sorted(expected_names)}
    empty = [name for name, points in snapshot.items() if not points]
    require_runtime_evidence(
        goodq_test_profile,
        not empty,
        f"required Qdrant collections contain no points: {empty!r}",
    )
    return snapshot


@pytest.mark.live_runtime
def test_no_lifecycle_anonymous_qdrant_points(qdrant_epoch_snapshot):
    """After ingest + promote, every Qdrant point in epoch collections
    must have ucf_promotion_status set. Zero anonymous points allowed."""
    anonymous_report = {}
    for coll_name, points in qdrant_epoch_snapshot.items():
        missing = [
            pt["id"] for pt in points
            if "ucf_promotion_status" not in (pt.get("payload") or {})
        ]
        if missing:
            anonymous_report[coll_name] = {
                "total": len(points),
                "missing": len(missing),
                "example_ids": missing[:5],
            }

    assert not anonymous_report, (
        f"Lifecycle-anonymous Qdrant points found in {len(anonymous_report)} collections:\n"
        + json.dumps(anonymous_report, indent=2)
    )


@pytest.mark.live_runtime
def test_qdrant_status_distribution_consistent(qdrant_epoch_snapshot):
    """After full lifecycle, Qdrant status distribution should contain
    only valid lifecycle states."""
    valid_states = {"staged", "validated", "promoted", "rejected", "superseded"}
    for coll_name, points in qdrant_epoch_snapshot.items():
        for pt in points:
            status = (pt.get("payload") or {}).get("ucf_promotion_status")
            assert status in valid_states, (
                f"Point {pt['id']} in {coll_name} has invalid status: {status!r}"
            )
