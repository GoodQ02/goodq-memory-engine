from __future__ import annotations


def test_step_runner_openmp_guard_applies_to_native_faiss_steps(monkeypatch):
    from cli.step_runner import apply_step_runtime_guards

    for key in ("KMP_DUPLICATE_LIB_OK", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        monkeypatch.delenv(key, raising=False)

    for step_name in ("image_embed_dino", "text_embed", "scene_visual_embeddings"):
        for key in ("KMP_DUPLICATE_LIB_OK", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
            monkeypatch.delenv(key, raising=False)

        apply_step_runtime_guards(step_name)

        assert "KMP_DUPLICATE_LIB_OK" in __import__("os").environ
        assert __import__("os").environ["KMP_DUPLICATE_LIB_OK"] == "TRUE"
        assert __import__("os").environ["OMP_NUM_THREADS"] == "1"
        assert __import__("os").environ["MKL_NUM_THREADS"] == "1"


def test_step_runner_openmp_guard_does_not_touch_plain_steps(monkeypatch):
    from cli.step_runner import apply_step_runtime_guards

    for key in ("KMP_DUPLICATE_LIB_OK", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        monkeypatch.delenv(key, raising=False)

    apply_step_runtime_guards("image_caption")

    assert "KMP_DUPLICATE_LIB_OK" not in __import__("os").environ
