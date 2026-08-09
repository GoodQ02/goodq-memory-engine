from scripts.install.release_payload_packs import DEFAULT_MAX_PACK_BYTES


def test_default_pack_boundary_accepts_largest_sealed_gpu_model_member() -> None:
    """Public GPU packages must accommodate every pinned monolithic model member."""
    deepseek_14b_shard_bytes = 8_714_116_464
    gemma_4_12b_model_bytes = 23_919_549_408

    assert DEFAULT_MAX_PACK_BYTES >= deepseek_14b_shard_bytes
    assert DEFAULT_MAX_PACK_BYTES >= gemma_4_12b_model_bytes
