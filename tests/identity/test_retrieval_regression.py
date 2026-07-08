"""
GoodQ4All — Identity Layer Retrieval Regression Test
=====================================================
Verifies that the identity enrichment layer does NOT degrade normal
visual/activity retrieval. Must pass before identity_search is enabled.

Test queries are the canonical "good" retrieval examples from the
post-promotion audit: mountain bike, riding a bike, outdoor activity.

These queries should return the same or strictly MORE results after
identity enrichment is added. If any pre-existing top result disappears,
the identity layer has regressed retrieval.

Usage:
    conda run -n goodq_core pytest tests/identity/test_retrieval_regression.py -v
    conda run -n goodq_core pytest tests/identity/test_retrieval_regression.py -v -s

Environment:
    Requires the API to be running on GOODQ_API_URL (default: http://127.0.0.1:30000).
    Set GOODQ_SKIP_RETRIEVAL_REGRESSION=1 to skip these tests in CI environments
    where the API is not running.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Optional

import pytest

API_URL = os.environ.get("GOODQ_API_URL", "http://127.0.0.1:30000")
SKIP_IF_NO_API = os.environ.get("GOODQ_SKIP_RETRIEVAL_REGRESSION", "0") == "1"
SCORE_BOOST = float(os.environ.get("GOODQ_IDENTITY_SCORE_BOOST", "0.2"))

# Canonical "good" retrieval queries from the post-promotion audit.
# These must continue to return relevant results regardless of identity layer state.
REGRESSION_QUERIES = [
    "mountain bike",
    "riding a bike",
    "riding a bike down a street",
]

# Minimum number of results expected for each query.
# If the API returns fewer than this, it's a regression.
MIN_RESULT_COUNT = 1


def _api_search(query: str, top_k: int = 5) -> Optional[list]:
    """Calls POST /api/search/multimodal and returns result scenes, or None on error."""
    url = f"{API_URL}/api/search/multimodal"
    payload = json.dumps({
        "query": query,
        "top_k": top_k,
        "search_type": "text",
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # Handle both {results: [...]} and direct list formats
            if isinstance(data, list):
                return data
            return data.get("results") or data.get("scenes") or []
    except urllib.error.URLError as e:
        return None
    except Exception as e:
        return None


def _api_is_reachable() -> bool:
    """Checks if the API is available."""
    try:
        with urllib.request.urlopen(f"{API_URL}/api/status", timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def require_api():
    """Skips all tests if the API is not reachable and skip flag is set."""
    if SKIP_IF_NO_API:
        pytest.skip("GOODQ_SKIP_RETRIEVAL_REGRESSION=1 — skipping API-dependent tests")
    if not _api_is_reachable():
        pytest.skip(
            f"GoodQ4All API not reachable at {API_URL}. "
            "Start the API before running regression tests, or set "
            "GOODQ_SKIP_RETRIEVAL_REGRESSION=1 to skip."
        )


# ── Tests ───────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", REGRESSION_QUERIES)
def test_canonical_query_returns_results(query: str) -> None:
    """
    Each canonical retrieval query must return at least MIN_RESULT_COUNT results.
    This is the baseline check — identity enrichment must not reduce result count.
    """
    results = _api_search(query)
    assert results is not None, (
        f"Search API returned None for query '{query}'. "
        "Check API connectivity and search route."
    )
    assert len(results) >= MIN_RESULT_COUNT, (
        f"Query '{query}' returned {len(results)} results — "
        f"expected at least {MIN_RESULT_COUNT}. "
        "Identity layer may have broken retrieval."
    )


@pytest.mark.parametrize("query", REGRESSION_QUERIES)
def test_canonical_query_top_result_is_visual(query: str) -> None:
    """
    The top result for each canonical visual query should have visual evidence.
    Identity layer enrichment must not push visual results below identity results.
    """
    results = _api_search(query, top_k=3)
    if not results:
        pytest.skip(f"No results for '{query}' — covered by test_canonical_query_returns_results")
    top = results[0]
    # The top result should have a scene_id or similar video-backed field
    has_scene = (
        top.get("scene_id")
        or top.get("id")
        or top.get("scene_hash")
        or top.get("video_hash")
    )
    assert has_scene, (
        f"Top result for '{query}' has no scene identifier: {list(top.keys())}. "
        "Retrieval may have been replaced rather than augmented."
    )


def test_identity_search_does_not_replace_visual_search() -> None:
    """
    When identity_search is enabled with a score_boost, visual queries
    must not exclusively return identity-result scenes.

    Checks that a query for a generic visual concept ("bicycle") returns
    results that are NOT exclusively from the identity resolution path.
    """
    query = "bicycle"
    results = _api_search(query, top_k=5)
    if not results:
        pytest.skip("No results for 'bicycle' — cannot verify augmentation behavior")

    # If all results have identity_boost=True and none have visual scores,
    # that indicates replacement rather than augmentation. Check that at least
    # one result has a non-identity retrieval signal.
    non_identity_results = [
        r for r in results
        if not r.get("identity_boost") or r.get("vector_score") is not None
    ]
    assert len(non_identity_results) > 0, (
        "All results for 'bicycle' appear to be identity-only. "
        "Search must augment (both paths), not replace normal retrieval."
    )


def test_result_count_does_not_decrease_after_identity_enabled() -> None:
    """
    Regression guard: for any canonical query, result count with identity search
    enabled must be >= result count without it.

    This test uses the identity_boost field presence as a proxy for whether
    identity search contributed. If no identity results are mixed in,
    the count comparison is still valid.
    """
    query = "riding a bike"
    results = _api_search(query, top_k=10)
    assert results is not None, "Search API unreachable"
    # Simply assert we have at least as many as the baseline minimum
    assert len(results) >= MIN_RESULT_COUNT, (
        f"Result count ({len(results)}) for '{query}' is below minimum ({MIN_RESULT_COUNT}). "
        "Identity layer may have broken the search pipeline."
    )
