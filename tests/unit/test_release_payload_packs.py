from pathlib import Path

from scripts.install.release_payload_packs import DEFAULT_MAX_PACK_BYTES, build


def test_default_pack_boundary_accepts_largest_sealed_gpu_model_member() -> None:
    """Public GPU packages must accommodate every pinned monolithic model member."""
    deepseek_14b_shard_bytes = 8_714_116_464
    gemma_4_12b_model_bytes = 23_919_549_408

    assert DEFAULT_MAX_PACK_BYTES >= deepseek_14b_shard_bytes
    assert DEFAULT_MAX_PACK_BYTES >= gemma_4_12b_model_bytes


def test_build_emits_per_pack_copy_and_hash_heartbeats(tmp_path: Path) -> None:
    staging = tmp_path / "staged"
    (staging / "vendor").mkdir(parents=True)
    (staging / "wheels").mkdir()
    (staging / "models").mkdir()
    (staging / "vendor" / "dependency.bin").write_bytes(b"vendor")
    (staging / "wheels" / "dependency.whl").write_bytes(b"wheel")
    (staging / "models" / "model.bin").write_bytes(b"model")
    (staging / "wheelhouse-sbom.json").write_text("{}\n", encoding="utf-8")
    events: list[str] = []

    build(
        staging_root=staging,
        output_root=tmp_path / "output",
        version="0.0.0",
        profile="PUBLIC_GPU_ENHANCED",
        max_pack_bytes=1024 * 1024,
        progress=events.append,
        heartbeat_seconds=0,
    )

    assert any("plan:" in event for event in events)
    assert any("writing pack" in event for event in events)
    assert any("copy heartbeat" in event for event in events)
    assert any("hash heartbeat" in event for event in events)
    assert any("completed pack" in event for event in events)
