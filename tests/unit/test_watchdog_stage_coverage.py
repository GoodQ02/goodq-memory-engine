from __future__ import annotations

from cli.watchdog import ProcessedRegistry


def test_same_content_with_missing_or_failed_stage_requires_recovery(tmp_path) -> None:
    registry = ProcessedRegistry(tmp_path / "watchdog_state.json")
    registry.mark_processed(
        "same-content",
        "clip.mp4",
        stage_coverage={
            "audio": {"status": "failed", "provenance": "wsl-unified-v1"},
            "vision": {"status": "success", "provenance": "vision-v1"},
        },
    )

    assert registry.coverage_decision("same-content", {"audio": "wsl-unified-v1"}) == "recover"
    assert registry.coverage_decision("same-content", {"new_stage": "v1"}) == "recover"


def test_proven_current_stage_skips_and_provenance_change_recovers(tmp_path) -> None:
    registry = ProcessedRegistry(tmp_path / "watchdog_state.json")
    registry.mark_processed(
        "same-content",
        "clip.mp4",
        stage_coverage={"audio": {"status": "success", "provenance": "wsl-unified-v2"}},
    )

    assert registry.coverage_decision("same-content", {"audio": "wsl-unified-v2"}) == "skip"
    assert registry.coverage_decision("same-content", {"audio": "wsl-unified-v3"}) == "recover"


def test_legacy_success_record_is_not_evidence_for_requested_stage(tmp_path) -> None:
    registry = ProcessedRegistry(tmp_path / "watchdog_state.json")
    registry.mark_processed("legacy-content", "clip.mp4")

    assert registry.coverage_decision("legacy-content", {"audio": "wsl-unified-v2"}) == "recover"
