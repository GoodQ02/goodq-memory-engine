#!/usr/bin/env python3
"""
Epistemic Read Formatter smoke tests.

These are deterministic, integrity-only checks:
- No scoring or policy assertions
- Only verifies envelope assembly + evidence-shape -> state mapping
"""

import json
import os

from steps.common.epistemic_formatter import format_epistemic_read


def _dump(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def test_supported_minimal():
    hits = [
        {
            "id": "uuid-1",
            "score": 0.1,
            "payload": {"model": "clip", "video_id": "v1", "scene_id": "s1"},
            "provenance": {"provenance_version": 1, "attempted": True, "committed": True, "targets": {"qdrant": {"ref": "goodq_clip"}}},
            "confidence": {"intrinsic": None, "source": None, "temporal": 0.9, "consistency": None, "overall": None},
        }
    ]
    out1 = format_epistemic_read(question={"text": "what do you see?"}, retrieval_context="human.ui.search", hits=hits)
    out2 = format_epistemic_read(question={"text": "what do you see?"}, retrieval_context="human.ui.search", hits=hits)
    assert _dump(out1) == _dump(out2)
    assert out1["outcome"] == "answer"
    assert out1["candidates"][0]["state"] in ("supported", "partially_supported")
    assert out1["candidates"][0]["evidence"][0]["role"] == "support"
    assert out1["candidates"][0]["source_hit_order"] == [0]


def test_conflicted_via_role_override():
    orig = os.environ.get("GOODQ_VECTOR_DEBUG")
    os.environ["GOODQ_VECTOR_DEBUG"] = "1"
    hits = [
        {
            "id": "uuid-1",
            "score": 0.1,
            "payload": {"model": "clip", "video_id": "v1", "scene_id": "s1"},
            "provenance": {"provenance_version": 1, "attempted": True, "committed": True, "targets": {"qdrant": {"ref": "goodq_clip"}}},
            "confidence": {"temporal": 0.9},
            "evidence_role": "support",
        },
        {
            "id": "uuid-2",
            "score": 0.2,
            "payload": {"model": "audio", "video_id": "v1", "scene_id": "s1"},
            "provenance": {"provenance_version": 1, "attempted": True, "committed": True, "targets": {"qdrant": {"ref": "goodq_audio"}}},
            "confidence": {"temporal": 0.9},
            "evidence_role": "contradict",
        },
    ]
    try:
        out = format_epistemic_read(question={"text": "is there music?"}, retrieval_context="human.cli.retrieve", hits=hits)
        assert out["outcome"] == "answer"
        assert out["candidates"][0]["state"] == "conflicted"
        assert out["candidates"][0]["source_hit_order"] == [0, 1]
    finally:
        if orig is None:
            os.environ.pop("GOODQ_VECTOR_DEBUG", None)
        else:
            os.environ["GOODQ_VECTOR_DEBUG"] = orig


def test_dont_know_when_no_support():
    hits = [
        {
            "id": "uuid-1",
            "score": 0.1,
            "payload": {"model": "clip", "video_id": "v1", "scene_id": "s1"},
            # No provenance => meta evidence; formatter should emit dont_know.
            "confidence": {"temporal": 0.9},
        }
    ]
    out = format_epistemic_read(question={"text": "what is the exact camera brand?"}, retrieval_context="human.ui.search", hits=hits)
    assert out["outcome"] == "dont_know"
    assert out["dont_know"]["state"] in ("unknown", "unsupported_but_related")


if __name__ == "__main__":
    test_supported_minimal()
    test_conflicted_via_role_override()
    test_dont_know_when_no_support()
    print("OK: epistemic_formatter smoke tests passed")
