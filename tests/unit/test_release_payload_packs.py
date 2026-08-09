from scripts.install.release_payload_packs import DEFAULT_MAX_PACK_BYTES


def test_default_pack_boundary_accepts_largest_sealed_gpu_shard() -> None:
    """Public GPU packages must accommodate the pinned DeepSeek 14B source shard."""
    largest_sealed_gpu_shard_bytes = 8_714_116_464

    assert DEFAULT_MAX_PACK_BYTES >= largest_sealed_gpu_shard_bytes
