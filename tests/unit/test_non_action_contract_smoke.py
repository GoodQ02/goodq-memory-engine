#!/usr/bin/env python3
"""
Non-Action Contract v1 smoke tests.

Integrity-only:
- No enforcement assertions (only decision generation)
- No thresholds/scoring
"""

from steps.common.non_action_contract import evaluate_non_action


def test_answer_allowed_when_supported():
    envelope = {
        "read_model_version": 1,
        "question": {"text": "what do you see?"},
        "retrieval_context": "human.ui.search",
        "outcome": "answer",
        "candidates": [
            {
                "candidate_id": "scene:v1:s1",
                "state": "supported",
                "evidence": [{"role": "support", "payload": {"video_id": "v1", "scene_id": "s1"}}],
                "next_steps": [],
            }
        ],
    }
    decisions = evaluate_non_action({"domains": ["answer"], "epistemic_envelope": envelope})
    assert decisions == []


def test_dont_know_required_when_answer_shape_invalid():
    # Envelope attempts outcome="answer" but provides no support evidence.
    envelope = {
        "read_model_version": 1,
        "question": {"text": "what is the exact camera brand?"},
        "retrieval_context": "human.ui.search",
        "outcome": "answer",
        "candidates": [{"candidate_id": "scene:v1:s1", "state": "supported", "evidence": [], "next_steps": []}],
    }
    decisions = evaluate_non_action({"domains": ["answer"], "epistemic_envelope": envelope})
    assert any(d["domain"] == "answer" and d["required_response"] == "dont_know" for d in decisions)


def test_ingestion_blocked_when_adapter_missing():
    decisions = evaluate_non_action(
        {
            "domains": ["ingest"],
            "ingest": {
                "source_kind": "health_auto_export",
                "sensitive": True,
                "adapter_present": False,
                "pipeline_registered": False,
            },
        }
    )
    assert any(d["domain"] == "ingest" and d["required_response"] == "refuse" for d in decisions)


if __name__ == "__main__":
    test_answer_allowed_when_supported()
    test_dont_know_required_when_answer_shape_invalid()
    test_ingestion_blocked_when_adapter_missing()
    print("OK: non_action_contract smoke tests passed")

