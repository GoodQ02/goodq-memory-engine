from __future__ import annotations


def test_probe_wsl_audio_runtime_allows_abi_degraded_transcription(monkeypatch):
    from scripts import wsl_audio_preflight

    def _fake_run_wsl_probe(distro, script, *, timeout):
        if "test -f" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        if "import faster_whisper, torch" in script:
            return type(
                "Probe",
                (),
                {"returncode": 0, "stdout": "transcription_ready\ngpu_ready\n", "stderr": ""},
            )()
        if "spec_from_file_location('goodq_process_audio'" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "process_import_ready\n", "stderr": ""})()
        if "from torchvision.ops import nms" in script:
            return type(
                "Probe",
                (),
                {
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "RuntimeError: operator torchvision::nms does not exist",
                },
            )()
        if "from pyannote.audio import Pipeline" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "diarization_ready\n", "stderr": ""})()
        raise AssertionError(f"unexpected probe script: {script}")

    monkeypatch.setattr(wsl_audio_preflight, "_run_wsl_probe", _fake_run_wsl_probe)
    monkeypatch.setattr(
        wsl_audio_preflight,
        "_probe_package_version",
        lambda distro, workspace, package_name: {
            "torch": "2.5.1",
            "torchvision": "0.20.1+cu121",
            "torchaudio": "2.5.1+cu121",
            "pyannote.audio": "3.3.2",
            "faster-whisper": "1.2.1",
        }.get(package_name),
    )

    result = wsl_audio_preflight.probe_wsl_audio_runtime("Ubuntu-22.04", "/home/goodq/goodq_audio")

    assert result["workspace_ready"] is True
    assert result["transcription_ready"] is True
    assert result["process_import_ready"] is True
    assert result["diarization_ready"] is True
    assert result["runtime_ready"] is True
    assert result["abi_ready"] is False
    assert result["ready"] is True
    assert "process_audio import ready" in result["detail"]
    assert result["detected_versions"]["torchvision"] == "0.20.1+cu121"
