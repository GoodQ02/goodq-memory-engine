#!/usr/bin/env python3
"""
Epistemic Diff Engine v1 smoke tests.

Integrity-only:
- No scoring/ranking
- No correctness inference
- Structural diffs only
"""

from steps.common.epistemic_diff import compute_epistemic_diff


def _bundle(envelope, decisions=None, *, source="example", loaded_at="2025-12-21T00:00:00Z"):
    return {
        "envelope": envelope,
        "nonActionDecisions": decisions or [],
        "sourceLabel": source,
        "loaded_at_utc": loaded_at,
    }


def _identity_exact():
    return {"type": "question_text_exact", "details": {}}


def test_no_differences():
    env = {
        "read_model_version": 1,
        "question": {"text": "Is there music in scene 0007?"},
        "retrieval_context": "human.ui.search",
        "outcome": "answer",
        "candidates": [
            {
                "candidate_id": "a1",
                "state": "supported",
                "evidence": [
                    {
                        "role": "support",
                        "store": "qdrant",
                        "store_ref": "goodq_audio",
                        "embedding_id": "e1",
                        "payload": {"video_id": "v1", "scene_id": "0007", "model": "clap", "transcript": "[REDACTED]"},
                        "provenance": {"provenance_version": 1, "ts_utc": "2025-12-20T00:00:00Z"},
                        "limits": [],
                    }
                ],
                "limits": [],
                "next_steps": [],
            }
        ],
    }
    diff = compute_epistemic_diff(_bundle(env), _bundle(env), _identity_exact())
    assert diff["diff_total"] == 0
    assert diff["diffs"] == []

    # Absence handling: categories are always present in summaries.
    cats = {c["category"]: c for c in diff["category_summaries"]}
    for expected in (
        "identity_basis",
        "outcome",
        "candidates",
        "non_action_decisions",
        "evidence",
        "limits_aggregated",
        "limits_dont_know",
        "next_steps",
    ):
        assert expected in cats
    assert cats["limits_aggregated"]["presence"] == "absent_both"
    assert cats["limits_dont_know"]["presence"] == "absent_both"
    assert cats["next_steps"]["presence"] == "absent_both"


def test_outcome_change():
    a = {
        "read_model_version": 1,
        "question": {"text": "Q"},
        "retrieval_context": "human.ui.search",
        "outcome": "answer",
        "candidates": [],
    }
    b = {
        "read_model_version": 1,
        "question": {"text": "Q"},
        "retrieval_context": "human.ui.search",
        "outcome": "dont_know",
        "candidates": [],
        "dont_know": {"state": "unknown", "explanation": "no evidence", "evidence": [], "limits": [], "next_steps": []},
    }
    diff = compute_epistemic_diff(_bundle(a), _bundle(b), _identity_exact())
    assert diff["diff_codes"][0] == "outcome_changed"
    assert any(d["diff_code"] == "outcome_changed" for d in diff["diffs"])


def test_candidate_add_remove():
    a = {
        "read_model_version": 1,
        "question": {"text": "Q"},
        "retrieval_context": "human.ui.search",
        "outcome": "answer",
        "candidates": [{"candidate_id": "a1", "state": "supported", "evidence": [], "limits": [], "next_steps": []}],
    }
    b = {
        "read_model_version": 1,
        "question": {"text": "Q"},
        "retrieval_context": "human.ui.search",
        "outcome": "answer",
        "candidates": [{"candidate_id": "a2", "state": "supported", "evidence": [], "limits": [], "next_steps": []}],
    }
    diff = compute_epistemic_diff(_bundle(a), _bundle(b), _identity_exact())
    codes = [d["diff_code"] for d in diff["diffs"]]
    assert "candidate_removed" in codes
    assert "candidate_added" in codes
    # Stable order: removals (A order) before additions (B order)
    assert codes.index("candidate_removed") < codes.index("candidate_added")


def test_evidence_removed():
    a = {
        "read_model_version": 1,
        "question": {"text": "Q"},
        "retrieval_context": "human.ui.search",
        "outcome": "answer",
        "candidates": [
            {
                "candidate_id": "a1",
                "state": "supported",
                "evidence": [{"role": "support", "store": "qdrant", "store_ref": "goodq_clip", "embedding_id": "e1"}],
                "limits": [],
                "next_steps": [],
            }
        ],
    }
    b = {
        "read_model_version": 1,
        "question": {"text": "Q"},
        "retrieval_context": "human.ui.search",
        "outcome": "answer",
        "candidates": [{"candidate_id": "a1", "state": "supported", "evidence": [], "limits": [], "next_steps": []}],
    }
    diff = compute_epistemic_diff(_bundle(a), _bundle(b), _identity_exact())
    assert any(d["diff_code"] == "evidence_removed" for d in diff["diffs"])


def test_non_action_remove_add_when_required_response_changes():
    env = {"read_model_version": 1, "question": {"text": "Q"}, "retrieval_context": "human.ui.search", "outcome": "answer", "candidates": []}
    a_dec = [{"contract_version": 1, "domain": "act", "condition": "x", "required_response": "defer", "rationale": {}}]
    b_dec = [{"contract_version": 1, "domain": "act", "condition": "x", "required_response": "refuse", "rationale": {}}]
    diff = compute_epistemic_diff(_bundle(env, a_dec), _bundle(env, b_dec), _identity_exact())
    codes = [d["diff_code"] for d in diff["diffs"]]
    assert "decision_removed" in codes
    assert "decision_added" in codes


def test_identity_basis_mismatch():
    a = {"read_model_version": 1, "question": {"text": "A"}, "retrieval_context": "human.ui.search", "outcome": "answer", "candidates": []}
    b = {"read_model_version": 1, "question": {"text": "B"}, "retrieval_context": "human.ui.search", "outcome": "answer", "candidates": []}
    diff = compute_epistemic_diff(_bundle(a), _bundle(b), _identity_exact())
    assert diff["identity_basis"]["matches"] is False
    assert any(d["diff_code"] == "identity_basis_mismatch" for d in diff["diffs"])


if __name__ == "__main__":
    test_no_differences()
    test_outcome_change()
    test_candidate_add_remove()
    test_evidence_removed()
    test_non_action_remove_add_when_required_response_changes()
    test_identity_basis_mismatch()
    print("OK: epistemic_diff smoke tests passed")

