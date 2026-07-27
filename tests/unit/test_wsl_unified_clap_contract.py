from __future__ import annotations

from cli.run_ingestion import _has_wsl_unified_audio_embeddings


def _wsl_item() -> dict:
    return {
        "wsl2_unified": True,
        "audio_backend_effective": "wsl",
        "embeddings": [0.1] * 768,
        "embedding_dim": 768,
        "embeddings_status": "success",
    }


def test_wsl_wav2vec2_embedding_does_not_suppress_canonical_clap() -> None:
    assert _has_wsl_unified_audio_embeddings(_wsl_item()) is False


def test_only_persisted_clap_proof_suppresses_duplicate_clap_step() -> None:
    item = _wsl_item()
    item["clap_meta"] = {
        "status": "ok",
        "component": "audio_embed_clap",
        "embedding_id": "fingerprint",
        "qdrant_committed": True,
        "qdrant_collection": "goodq_audio_epoch",
    }

    assert _has_wsl_unified_audio_embeddings(item) is True


def test_incomplete_clap_metadata_does_not_suppress_clap_step() -> None:
    item = _wsl_item()
    item["clap_meta"] = {
        "status": "ok",
        "component": "audio_embed_clap",
        "embedding_id": "fingerprint",
        "qdrant_committed": False,
        "qdrant_collection": "goodq_audio_epoch",
    }

    assert _has_wsl_unified_audio_embeddings(item) is False
