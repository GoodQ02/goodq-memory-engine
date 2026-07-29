from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


def _load_run_ingestion_module():
    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    try:
        importlib.import_module("typer")
    except ModuleNotFoundError:
        typer = types.ModuleType("typer")

        class _DummyTyper:
            def __init__(self, *args, **kwargs):
                pass

            def command(self, *args, **kwargs):
                def _decorator(fn):
                    return fn

                return _decorator

        typer.Typer = _DummyTyper
        typer.Option = lambda default=None, *args, **kwargs: default
        typer.echo = lambda *args, **kwargs: None
        typer.BadParameter = Exception
        sys.modules["typer"] = typer

    return importlib.import_module("cli.run_ingestion")


def test_aggregate_modality_status_defaults_to_not_attempted():
    run_ingestion = _load_run_ingestion_module()

    status = run_ingestion._aggregate_modality_status([])

    assert status == {
        "vision_clip": "not_attempted",
        "vision_dino": "not_attempted",
        "text_embed": "not_attempted",
        "audio_embed": "not_attempted",
    }


def test_aggregate_modality_status_marks_available_and_unavailable_from_scene_payloads():
    run_ingestion = _load_run_ingestion_module()

    scene_outputs = [
        {
            "keyframe": {
                "clip_embedding": [0.1, 0.2],
                "dino_embedding": [0.3, 0.4],
                "frame_text_embed_meta": {"status": "unavailable"},
            },
            "audio": {
                "clap_meta": {"status": "unavailable"},
                "audio_text_embed_meta": {"status": "unavailable"},
            },
        }
    ]

    status = run_ingestion._aggregate_modality_status(scene_outputs)

    assert status == {
        "vision_clip": "available",
        "vision_dino": "available",
        "text_embed": "unavailable",
        "audio_embed": "unavailable",
    }


def test_aggregate_modality_status_uses_phase6_attempts_for_vision_unavailable():
    run_ingestion = _load_run_ingestion_module()

    phase6_embeddings_result = {
        "clip_embeddings": 3,
        "dino_embeddings": 2,
        "clip_committed": False,
        "dino_committed": False,
        "scene_clip_vectors_written": 0,
        "scene_dino_vectors_written": 0,
    }

    status = run_ingestion._aggregate_modality_status(
        [],
        phase6_embeddings_result=phase6_embeddings_result,
    )

    assert status["vision_clip"] == "unavailable"
    assert status["vision_dino"] == "unavailable"
    assert status["text_embed"] == "not_attempted"
    assert status["audio_embed"] == "not_attempted"


def test_aggregate_modality_status_prefers_available_when_any_scene_succeeds():
    run_ingestion = _load_run_ingestion_module()

    scene_outputs = [
        {"audio": {"audio_text_embed_meta": {"status": "unavailable"}}},
        {"audio": {"audio_text_embed_meta": {"status": "ok"}}},
    ]

    status = run_ingestion._aggregate_modality_status(scene_outputs)

    assert status["text_embed"] == "available"


def test_wsl_wav2vec_embeddings_do_not_count_as_persisted_clap():
    run_ingestion = _load_run_ingestion_module()

    audio_payload = {
        "wsl2_unified": True,
        "audio_backend_effective": "wsl",
        "embeddings": [0.1, 0.2, 0.3],
        "embedding_dim": 768,
        "embeddings_status": "success",
        "clap_meta": {"status": "skipped", "reason": "wsl_unified_embeddings_present"},
    }

    assert run_ingestion._has_wsl_unified_audio_embeddings(audio_payload) is False

    status = run_ingestion._aggregate_modality_status([{"audio": audio_payload}])

    assert status["audio_embed"] == "not_attempted"
