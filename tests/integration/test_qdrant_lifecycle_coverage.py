"""Integration test: assert the invariant that every Qdrant point in epoch
collections has ``ucf_promotion_status`` set after ingestion + promotion.

This prevents silent regression if a new embedding step is added later without
lifecycle metadata.
"""

import os
import json
import pytest
import requests


QDRANT_HOST = os.environ.get("GOODQ_QDRANT_HOST", "http://127.0.0.1:6333")
EPOCH_SUBSTR = os.environ.get("GOODQ_TEST_EPOCH", "")


def _get_epoch_collections():
    """Return list of Qdrant collection names that contain 'epoch' in name."""
    try:
        resp = requests.get(f"{QDRANT_HOST}/collections", timeout=5)
        if resp.status_code != 200:
            pytest.skip(f"Qdrant unavailable: {resp.status_code}")
        colls = resp.json().get("result", {}).get("collections", [])
    except requests.exceptions.ConnectionError:
        pytest.skip("Qdrant not running")
    epoch_colls = [
        c["name"] for c in colls
        if "epoch" in c.get("name", "") and (not EPOCH_SUBSTR or EPOCH_SUBSTR in c.get("name", ""))
    ]
    return epoch_colls


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
            break
        result = resp.json().get("result", {})
        points = result.get("points", [])
        all_points.extend(points)
        next_offset = result.get("next_page_offset")
        if not next_offset or not points:
            break
        offset = next_offset
    return all_points


@pytest.mark.skipif(not EPOCH_SUBSTR, reason="GOODQ_TEST_EPOCH not set")
def test_no_lifecycle_anonymous_qdrant_points():
    """After ingest + promote, every Qdrant point in epoch collections
    must have ucf_promotion_status set. Zero anonymous points allowed."""
    epoch_colls = _get_epoch_collections()
    assert epoch_colls, f"No epoch collections found matching '{EPOCH_SUBSTR}'"

    anonymous_report = {}
    for coll_name in epoch_colls:
        points = _scroll_all_points(coll_name)
        if not points:
            continue
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


@pytest.mark.skipif(not EPOCH_SUBSTR, reason="GOODQ_TEST_EPOCH not set")
def test_qdrant_status_distribution_consistent():
    """After full lifecycle, Qdrant status distribution should contain
    only valid lifecycle states."""
    valid_states = {"staged", "validated", "promoted", "rejected", "superseded"}
    epoch_colls = _get_epoch_collections()
    assert epoch_colls

    for coll_name in epoch_colls:
        points = _scroll_all_points(coll_name)
        if not points:
            continue
        for pt in points:
            status = (pt.get("payload") or {}).get("ucf_promotion_status")
            assert status in valid_states, (
                f"Point {pt['id']} in {coll_name} has invalid status: {status!r}"
            )
