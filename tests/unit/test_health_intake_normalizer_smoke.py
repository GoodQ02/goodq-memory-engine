#!/usr/bin/env python3
"""
Health Intake Normalizer (HIN v1) smoke tests.

Safety / integrity:
- Read-only: no DB writes, no network calls
- Drift-tolerant: must not crash on schema changes
- Privacy-preserving: emits derived summaries only (no raw per-record values)
"""

from steps.health_auto_export.normalizer import normalize_health_payload


def _assert_che_minimal(che: dict):
    for key in ("schema_version", "event_id", "source", "timestamp_utc", "category", "measurement_type", "value_ref"):
        assert key in che, f"missing required CHE field: {key}"
    assert che["schema_version"] == 1
    assert isinstance(che["event_id"], str) and che["event_id"]
    assert isinstance(che["timestamp_utc"], str) and che["timestamp_utc"].endswith("Z")
    assert isinstance(che["measurement_type"], str) and che["measurement_type"]
    assert isinstance(che["value_ref"], str) and che["value_ref"].startswith("vaultref:")


def test_empty_input_returns_no_events():
    out = normalize_health_payload({}, source_id="health-auto-export", received_at_utc="2025-12-22T12:00:00Z")
    assert out == []


def test_known_payload_emits_events_with_fingerprints():
    raw = {
        "data": {
            "metrics": [
                {
                    "name": "Heart Rate",
                    "data": [
                        {"date": "2025-12-22T10:00:00Z", "value": 60, "unit": "bpm"},
                        {"date": "2025-12-22T11:00:00Z", "value": 70, "unit": "bpm"},
                    ],
                }
            ]
        }
    }
    out = normalize_health_payload(raw, source_id="health-auto-export", received_at_utc="2025-12-23T00:00:00Z")
    assert len(out) >= 1
    for che in out:
        _assert_che_minimal(che)
        assert "schema_fingerprint" in che
        assert "source_fingerprint" in che
        assert "summary_stats" in che
        assert isinstance(che.get("data_quality", []), list)


def test_renamed_fields_do_not_break_normalization():
    raw = {
        "payload": {
            "series": [
                {
                    "title": "Steps",
                    "values": [
                        {"timestamp": "2025-12-22T00:00:00Z", "qty": "123"},
                        {"timestamp": "2025-12-22T01:00:00Z", "qty": "456"},
                    ],
                }
            ]
        }
    }
    out = normalize_health_payload(raw, source_id="unknown-source", received_at_utc="2025-12-22T12:00:00Z")
    assert len(out) >= 1
    for che in out:
        _assert_che_minimal(che)


def test_date_grouped_records_are_handled_without_raw_timestamps():
    raw = {
        "measurements_by_day": {
            "2025-12-22": [{"value": 1}, {"value": 2}],
            "2025-12-23": [{"value": 3}],
        }
    }
    out = normalize_health_payload(raw, source_id="health-auto-export", received_at_utc="2025-12-24T12:00:00Z")
    assert len(out) >= 1
    for che in out:
        _assert_che_minimal(che)
        assert che.get("time_range", {}).get("start_day_utc")
        assert che.get("time_range", {}).get("end_day_utc")


def test_additional_unknown_fields_do_not_crash():
    raw = {
        "data": {
            "metrics": [
                {
                    "name": "Heart Rate",
                    "data": [
                        {
                            "date": "2025-12-22T10:00:00Z",
                            "value": 60,
                            "nested": {"opaque": ["a", "b", {"c": 1}]},
                        }
                    ],
                }
            ]
        },
        "new_top_level": {"unexpected": [{"x": 1, "y": 2}]},
    }
    out = normalize_health_payload(raw, source_id="health-auto-export", received_at_utc="2025-12-22T12:00:00Z")
    assert len(out) >= 1
    for che in out:
        _assert_che_minimal(che)


if __name__ == "__main__":
    test_empty_input_returns_no_events()
    test_known_payload_emits_events_with_fingerprints()
    test_renamed_fields_do_not_break_normalization()
    test_date_grouped_records_are_handled_without_raw_timestamps()
    test_additional_unknown_fields_do_not_crash()
    print("OK: health_intake_normalizer smoke tests passed")

