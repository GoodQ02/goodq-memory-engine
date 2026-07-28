from cli.signature_backfill_batches import build_batch_plan


def test_batch_plan_is_deterministic_and_has_no_execution_path() -> None:
    source = {"status": "inspect_only", "eligible_scene_ids_sha256": "ledger", "blocked_count": 2,
              "eligible": [{"scene_id": "a"}, {"scene_id": "b"}, {"scene_id": "c"}]}
    plan = build_batch_plan(source, batch_size=2)
    assert plan["batch_count"] == 2
    assert plan["batches"][0]["scene_ids"] == ["a", "b"]
    assert plan["batches"][1]["scene_ids"] == ["c"]
    assert plan["execution_policy"]["writes"] == "none_in_this_planner"
    assert plan == build_batch_plan(source, batch_size=2)
