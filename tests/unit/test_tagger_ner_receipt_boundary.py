from __future__ import annotations

import json
import sys
import types

import pytest


@pytest.mark.parametrize("ner_case", ["typed", "unavailable", "empty"])
def test_tagger_factory_to_harmonized_mentions_and_receipt(monkeypatch, tmp_path, ner_case):
    from cli import run_ingestion, step_runner
    from steps.common import config_loader, model_provisioner, step_logger
    from steps.tagger import step as tagger

    text = "She says Laura is in Lansing, Michigan. Claire meets George."
    cfg = {
        "ingestion_isolation": True,
        "verification": {"offline_mode": True},
        "paths": {"processing": str(tmp_path / "processing"), "log_dir": str(tmp_path / "logs")},
        "run": {"id": "ner-boundary"},
        "host": {"profile": "PERSONAL_AIR_GAP"},
        "gpu": {"clear_cache_before_step": False},
    }
    local_path = str(tmp_path / "pinned-ner")
    load_calls = []
    model, tokenizer = object(), object()

    def provision(model_id, *, offline):
        assert model_id == "dslim/bert-base-NER"
        assert offline is True
        return types.SimpleNamespace(status="cached", local_path=local_path)

    def loader(kind, result):
        def load(path, *, local_files_only):
            load_calls.append((kind, path, local_files_only))
            if ner_case == "unavailable":
                raise OSError("fixture local checkpoint unavailable")
            return result
        return types.SimpleNamespace(from_pretrained=load)

    # Match the installed task constructor boundary: load-only kwargs are not
    # token-classification pipeline parameters. Real installed-model proof is
    # separate; this regression must never load shared assets or use a GPU.
    def pipeline(task, *, model, tokenizer=None, aggregation_strategy):
        assert task == "token-classification"
        assert aggregation_strategy == "simple"
        assert tokenizer is not None
        labels = {"Laura": "PER", "Lansing": "LOC", "Michigan": "LOC", "Claire": "PER", "George": "PER"}
        return lambda _: [] if ner_case == "empty" else [
            {"word": name, "entity_group": entity_type}
            for name, entity_type in labels.items()
        ]

    transformers = types.ModuleType("transformers")
    transformers.pipeline = pipeline
    transformers.AutoTokenizer = loader("tokenizer", tokenizer)
    transformers.AutoModelForTokenClassification = loader("model", model)
    transformers.logging = types.SimpleNamespace(set_verbosity_error=lambda: None)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setattr(tagger, "_NER_PIPELINES", {})
    monkeypatch.setattr(model_provisioner, "ensure_model_cached", provision)
    # A per-run resolved offline requirement must not be replaced by ambient defaults.
    monkeypatch.setattr(config_loader, "load_configs", lambda _: {"verification": {"offline_mode": False}})
    monkeypatch.setattr(step_runner, "load_step_config", lambda *_: cfg)
    monkeypatch.setattr(step_logger, "MISSION_LOGGER_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "_CURRENT_RUN_CONTEXT", cfg["run"])
    gpu = types.ModuleType("common.gpu_manager")
    gpu.initialize_gpu_for_step = lambda **_: None
    monkeypatch.setitem(sys.modules, "common.gpu_manager", gpu)

    def dispatch(step, item):
        input_path, output_path = tmp_path / f"{step}-in.json", tmp_path / f"{step}-out.json"
        input_path.write_text(json.dumps(item), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["step_runner", "--step", step, "--in", str(input_path), "--out", str(output_path)])
        step_runner.main()
        return json.loads(output_path.read_text(encoding="utf-8"))

    result = dispatch("tagger", {"scene_id": "scene-1", "transcript": text})
    manifest_path = tmp_path / "processing" / "video-1" / "video" / "scene_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({
        "video_id": "video-1", "phase5_complete": True,
        "scenes": [{
            "scene_id": "scene-1", "start": 0, "end": 20, "duration": 20, "content_state": "signal",
            "keyframe": {"caption": "a person sitting at a table", "faces": [{}]},
            "audio": {"transcript": text, **result},
        }],
    }), encoding="utf-8")
    dispatch("cross_modal_harmonization", {"id": "video-1", "scene_manifest_path": str(manifest_path)})
    scene = json.loads(manifest_path.read_text(encoding="utf-8"))["scenes"][0]
    temporal = json.loads((manifest_path.parent.parent / "temporal_index.json").read_text(encoding="utf-8"))
    mentioned = {x["text"] for x in scene["mentioned_people"]}
    assert mentioned == ({"Laura", "Claire", "George"} if ner_case == "typed" else set())
    assert scene["visible_people"] == []
    assert scene["candidate_visible_people"] == []
    assert temporal["segments"][0]["mentioned_people"] == scene["mentioned_people"]
    assert scene["audio"]["tagger_meta"] == result["tagger_meta"]

    logged = [json.loads(line) for line in (tmp_path / "logs" / "step_runs.jsonl").read_text(encoding="utf-8").splitlines()]
    row = next(x for x in logged if x["step"] == "tagger")
    assert row["extra"]["result_meta"]["tagger_meta"] == result["tagger_meta"]
    receipt = run_ingestion._finalize_capability_receipt(
        terminal_status="completed", cfg=cfg, results=[{"scenes": [{"scene_id": "scene-1"}]}],
        output=tmp_path / "receipt" / "results.json", input_count=1, release_validation=True,
    )
    capability = receipt["capabilities_by_step"]["tagger"]
    if ner_case == "unavailable":
        assert result["entities"]  # Existing pattern evidence remains usable.
        assert result["ner_entities"] == []
        assert row["status"] == "degraded"
        assert "fixture local checkpoint unavailable" in result["tagger_meta"]["error"]
        assert capability["fallback_chain"] == ["pattern_tags"]
        assert capability["closure_status"] == "unapproved_fallback"
    else:
        assert row["status"] == "ok"
        assert capability["fallback_chain"] == []
        assert result["tagger_meta"]["typed_entity_count"] == (5 if ner_case == "typed" else 0)
        assert set(load_calls) == {("model", local_path, True), ("tokenizer", local_path, True)}
