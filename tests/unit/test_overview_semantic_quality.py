from __future__ import annotations

import importlib
import sys
import types


def test_overview_filters_semantic_noise_from_tags_and_entities(tmp_path):
    diagnostics_module = types.ModuleType("lib.memory_management.diagnostics")
    diagnostics_module.run_all_diagnostics = lambda _paths: {"status": "ok"}
    memory_management_module = types.ModuleType("lib.memory_management")
    memory_management_module.diagnostics = diagnostics_module
    sys.modules["lib.memory_management"] = memory_management_module
    sys.modules["lib.memory_management.diagnostics"] = diagnostics_module
    overview_module = importlib.import_module("steps.overview.step")

    cfg = {
        "paths": {
            "db_path": str(tmp_path / "memory.db"),
            "log_dir": str(tmp_path / "logs"),
        }
    }
    results = [
        {
            "modality": "frame",
            "tag_details": [
                {"label": "Apartment", "score": 4.5},
                {"label": "coffee", "score": 5.0},
            ],
            "tags": ["Well", "Apartment"],
            "ner_entities": [
                {"name": "Jerry", "type": "PERSON"},
                {"name": "Vermont", "type": "LOCATION"},
            ],
            "entities": ["I'm", "Jerry"],
        }
    ]

    report = overview_module.overview(results, {"video_summaries": []}, cfg)

    assert report["top_tags"] == [
        {"label": "Apartment", "count": 1},
        {"label": "coffee", "count": 1},
    ]
    assert report["top_entities"] == [
        {"label": "Jerry", "count": 1},
        {"label": "Vermont", "count": 1},
    ]
