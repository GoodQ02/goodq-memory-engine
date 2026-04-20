from __future__ import annotations


def test_build_diarization_probe_uses_current_pyannote_token_kwarg():
    from scripts.wsl_audio_preflight import _build_diarization_probe_script

    script = _build_diarization_probe_script("/home/goodq/goodq_audio")

    assert "use_auth_token" not in script
    assert "Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', token=token)" in script


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
        if "snapshot_download" in script and "speaker-diarization-3.1" in script:
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


def test_probe_wsl_audio_runtime_reports_cache_missing_diarization(monkeypatch):
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
            return type("Probe", (), {"returncode": 0, "stdout": "abi_ready\n", "stderr": ""})()
        if "snapshot_download" in script and "speaker-diarization-3.1" in script:
            return type(
                "Probe",
                (),
                {
                    "returncode": 0,
                    "stdout": (
                        "diarization_cache_missing\n"
                        "pyannote/speaker-diarization-3.1: LocalEntryNotFoundError: cache miss\n"
                    ),
                    "stderr": "",
                },
            )()
        raise AssertionError(f"unexpected probe script: {script}")

    monkeypatch.setattr(wsl_audio_preflight, "_run_wsl_probe", _fake_run_wsl_probe)
    monkeypatch.setattr(
        wsl_audio_preflight,
        "_probe_package_version",
        lambda distro, workspace, package_name: None,
    )

    result = wsl_audio_preflight.probe_wsl_audio_runtime("Ubuntu-22.04", "/home/goodq/goodq_audio")

    assert result["workspace_ready"] is True
    assert result["runtime_ready"] is True
    assert result["abi_ready"] is True
    assert result["diarization_ready"] is False
    assert "cache miss" in result["diarization_detail"]
    assert "diarization unavailable" in result["detail"]
