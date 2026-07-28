"""Static contract checks for the isolated WSL signature worker."""

import ast
from pathlib import Path


def test_signature_only_worker_cannot_enter_full_audio_processing() -> None:
    source_path = Path("wsl2_audio/signature_only.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "audio_worker"
    }

    assert "_build_speaker_voice_signatures" in calls
    assert "process_audio" not in calls
    assert "diarize" not in calls
    assert "transcribe" not in calls


def test_bootstrap_syncs_signature_only_worker_for_future_managed_runs() -> None:
    source = Path("scripts/bootstrap_install.py").read_text(encoding="utf-8")
    assert '"wsl2_audio/signature_only.py"' in source
