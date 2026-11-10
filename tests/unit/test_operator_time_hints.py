"""Time-hint rendering through the real scene inspector, without inference."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


def render(hints):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the Operator renderer regression")
    scenes = [dict(scene_id=str(i), start=30, end=60, **hint) for i, hint in enumerate(hints)]
    result = subprocess.run(
        [node, str(Path(__file__).with_name("operator_time_hints_render.cjs"))],
        input=json.dumps(scenes), text=True, encoding="utf-8", capture_output=True, check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("hints", [None, {}, {"explicit_dates": [], "ambiguous_dates": [], "times": [], "weekdays": [], "months": [], "relative_phrases": []}])
def test_empty_hint_values_are_not_present(hints):
    row = render([{"time_hints": hints}])[0]
    assert row["temporal"] == "Temporal hints\n0 time hints\nOff"
    assert "0 time hints" in row["summary"]
    assert "No time hints exposed" in row["detail"]


def test_offsets_are_metadata_and_selection_clears_old_evidence():
    positive, empty = render([
        {"time_hints": {"relative_phrases": ["tomorrow"], "first_seen_ts": {"tomorrow": 15.76}}},
        {},
    ])
    assert positive["temporal"] == "Temporal hints\n1 time hint\nOn"
    assert "1 time hint" in positive["summary"]
    assert "relative_phrases: tomorrow" in positive["detail"]
    assert "First-seen offsets (scene-relative)\ntomorrow: 15.76s" in positive["detail"]
    assert "[object Object]" not in positive["detail"]
    assert empty["temporal"] == "Temporal hints\n0 time hints\nOff"
    assert "tomorrow" not in empty["detail"]


def test_timestamp_only_zero_and_invalid_offsets_do_not_invent_hints():
    row = render([{"time_hints": {"first_seen_ts": {"tomorrow": 0, "today": 30.720000000000002, "bad": None, "negative": -1, "blank": "", "object": {}}}}])[0]
    assert row["temporal"] == "Temporal hints\n0 time hints\nOff"
    assert "tomorrow: 0s" in row["detail"]
    assert "today: 30.72s" in row["detail"]
    assert "bad:" not in row["detail"]
    assert "negative:" not in row["detail"]
    assert "blank:" not in row["detail"]
    assert "[object Object]" not in row["detail"]


def test_count_is_values_not_categories_and_ignores_empty_or_structured_values():
    row = render([{"time_hints": {"weekdays": ["Monday", "Tuesday", "", None, {}], "months": "May", "relative_phrases": [], "unknown": {"a": 1}}}])[0]
    assert row["temporal"] == "Temporal hints\n3 time hints\nOn"
    assert "3 time hints" in row["summary"]
    assert "[object Object]" not in row["detail"]
