from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_vllm_installer_keeps_local_path_out_of_the_served_model_contract() -> None:
    source = (REPO_ROOT / "scripts" / "wsl" / "install_vllm_service.sh").read_text(
        encoding="utf-8"
    )

    assert 'SERVED_MODEL_NAME="${GOODQ_VLLM_SERVED_MODEL_NAME:-goodq-qwen-speed}"' in source
    assert "--served-model-name ${SERVED_MODEL_NAME}" in source
    assert "SERVED_MODEL_NAME=${MODEL_PATH}" not in source
