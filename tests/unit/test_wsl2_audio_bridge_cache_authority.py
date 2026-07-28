from scripts.wsl2_audio_bridge import WindowsWSL2AudioRunner
import pytest


def test_managed_bridge_exports_one_canonical_cache_to_wsl(monkeypatch) -> None:
    monkeypatch.setenv("GOODQ_WSL_USER", "goodq")
    runner = WindowsWSL2AudioRunner()
    runner._config = {"paths": {"models_cache": r"L:\\_DATA\\models"}}

    exports = runner._wsl_model_cache_exports()

    assert exports["GOODQ_MODEL_CACHE_ROOT"] == "/mnt/l/_DATA/models"
    assert exports["HF_HOME"] == "/mnt/l/_DATA/models"
    assert exports["HUGGINGFACE_HUB_CACHE"] == "/mnt/l/_DATA/models/hub"
    assert exports["HF_HUB_CACHE"] == "/mnt/l/_DATA/models/hub"
    assert exports["PYANNOTE_CACHE"] == "/mnt/l/_DATA/models/hub"


def test_required_wsl_audio_refuses_unconfigured_user_cache(monkeypatch) -> None:
    monkeypatch.setenv("GOODQ_REQUIRE_WSL_AUDIO", "1")
    monkeypatch.setenv("GOODQ_WSL_USER", "goodq")
    monkeypatch.delenv("GOODQ_MODEL_CACHE_ROOT", raising=False)
    monkeypatch.delenv("HF_HOME", raising=False)
    runner = WindowsWSL2AudioRunner()
    runner._config = {"paths": {}}

    with pytest.raises(RuntimeError, match="canonical models_cache"):
        runner._wsl_model_cache_exports()
