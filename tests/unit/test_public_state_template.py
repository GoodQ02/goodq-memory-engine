"""Public placeholders cannot be mistaken for observed runtime evidence."""
import copy

import pytest

from scripts.docs import build_current_state as state


def template():
    epoch = "epoch_public_unconfigured"
    value = {
        "schema_version": 1,
        "evidence_kind": "unconfigured_template",
        "captured_at_utc": "2026-09-16T00:00:00Z",
        "authority": {
            "epoch_id": epoch, "profile": "PUBLIC_RELEASE_UNCONFIGURED",
            "config_source": "public_unconfigured_template",
            "collections": {m: f"goodq_{m}_{epoch}" for m in state.MODALITIES},
        },
        "completion": {"context_frames": 0, "promotion_status": {}},
        "persistence": {"memory": {"scenes": 0}, "qdrant": {
            "state": "not_probed", "collections": {m: {
                "name": f"goodq_{m}_{epoch}", "status": "not_probed",
                "points_count": 0, "dimensions": 0,
            } for m in state.MODALITIES},
        }},
        "configured_runtime": {s: {"endpoint": f"http://127.0.0.1:{p}", "loopback_only": True}
                               for s, p in (("api", 30000), ("qdrant", 6333))},
        "observed_services": {"qdrant": {"state": "not_probed"}},
        "historical_evidence": [],
    }
    return seal(value)


def seal(value):
    value = copy.deepcopy(value)
    value["evidence_id"] = state._expected_evidence_id(value)
    return value


def test_public_template_is_explicit_in_all_projections():
    value = template()
    for rendered in (state.render_current_state_markdown(value), state.render_rag_context_pack(value)):
        assert "UNCONFIGURED PUBLIC TEMPLATE" in rendered
        assert "No runtime or corpus was observed" in rendered
        assert "DOC_BADGE: CANONICAL" not in rendered
        assert value["authority"]["epoch_id"] in rendered
    projection = state.project_current_state_json(value)
    assert projection["evidence_kind"] == "unconfigured_template"
    assert not projection["lifecycle"]["complete_and_fully_promoted"]


@pytest.mark.parametrize("path,new", [
    (("completion", "context_frames"), 1),
    (("persistence", "memory", "scenes"), 1),
    (("persistence", "qdrant", "state"), "running_loopback"),
    (("persistence", "qdrant", "collections", "text", "status"), "green"),
    (("observed_services", "qdrant", "state"), "running_loopback"),
    (("authority", "profile"), "GPU_ENHANCED"),
    (("historical_evidence",), [{"path": "private-receipt.json"}]),
])
def test_template_rejects_observed_or_private_evidence(path, new):
    value = template()
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = new
    with pytest.raises(ValueError):
        state.validate_evidence(seal(value))


def test_unmarked_unobserved_capture_still_fails_closed():
    value = template()
    del value["evidence_kind"]
    with pytest.raises(ValueError, match="reachable loopback Qdrant"):
        state.validate_evidence(seal(value))
