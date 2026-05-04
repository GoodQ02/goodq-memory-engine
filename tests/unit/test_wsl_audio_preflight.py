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
            return type(
                "Probe",
                (),
                {
                    "returncode": 0,
                    "stdout": "diarization_ready\n",
                    "stderr": "UserWarning: torchcodec decoder is not available",
                },
            )()
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
    monkeypatch.setattr(
        wsl_audio_preflight,
        "_probe_wsl_audio_black_box",
        lambda distro, workspace: {
            "package_versions": {
                "torch": "2.5.1+cu121",
                "torchvision": "0.20.1+cu121",
                "torchaudio": "2.5.1+cu121",
                "torchcodec": None,
            },
            "torchcodec": {"ready": True},
        },
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
    monkeypatch.setattr(
        wsl_audio_preflight,
        "_probe_wsl_audio_black_box",
        lambda distro, workspace: {
            "package_versions": {
                "torch": "2.5.1+cu121",
                "torchvision": "0.20.1+cu121",
                "torchaudio": "2.5.1+cu121",
            },
            "torchcodec": {"ready": True},
        },
    )

    result = wsl_audio_preflight.probe_wsl_audio_runtime("Ubuntu-22.04", "/home/goodq/goodq_audio")

    assert result["workspace_ready"] is True
    assert result["runtime_ready"] is True
    assert result["abi_ready"] is True
    assert result["diarization_ready"] is False
    assert "cache miss" in result["diarization_detail"]
    assert "diarization unavailable" in result["detail"]


def test_probe_wsl_audio_runtime_records_torch_lane_and_torchcodec_warning(monkeypatch):
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
                    "stdout": "diarization_ready\n",
                    "stderr": "UserWarning: torchcodec decoder is not available",
                },
            )()
        raise AssertionError(f"unexpected probe script: {script}")

    monkeypatch.setattr(wsl_audio_preflight, "_run_wsl_probe", _fake_run_wsl_probe)
    monkeypatch.setattr(
        wsl_audio_preflight,
        "_probe_package_version",
        lambda distro, workspace, package_name: {
            "torch": "2.8.0+cu128",
            "torchvision": "0.23.0+cu128",
            "torchaudio": "2.8.0+cu128",
            "pyannote.audio": "4.0.4",
            "faster-whisper": "1.2.1",
        }.get(package_name),
    )
    monkeypatch.setattr(
        wsl_audio_preflight,
        "_probe_wsl_audio_black_box",
        lambda distro, workspace: {
            "package_versions": {
                "torch": "2.8.0+cu128",
                "torchvision": "0.23.0+cu128",
                "torchaudio": "2.8.0+cu128",
                "torchcodec": "0.10.0",
            },
            "torchcodec": {
                "ready": False,
                "error_tail": (
                    "libavutil.so.59 missing; undefined symbol; "
                    "PyTorch version is not compatible with this version of TorchCodec"
                ),
            },
        },
    )

    result = wsl_audio_preflight.probe_wsl_audio_runtime("Ubuntu-22.04", "/home/goodq/goodq_audio")

    assert result["ready"] is True
    assert result["torch_lane_status"] == "differs_from_expected"
    assert result["torchcodec_ready"] is False
    assert "torchcodec_decoder_unavailable" in result["runtime_warnings"]
    assert "torch_lane_differs_from_expected" in result["runtime_warnings"]
    assert "pyannote_warned_torchcodec_decoder_unavailable" in result["runtime_warnings"]
    assert "ffmpeg_shared_library_unavailable" in result["torchcodec_detail"]
    assert "torch_abi_symbol_mismatch" in result["torchcodec_detail"]


def test_main_emits_json_preflight_payload(monkeypatch, capsys):
    import json

    from scripts import wsl_audio_preflight

    monkeypatch.setattr(
        wsl_audio_preflight,
        "probe_wsl_audio_runtime",
        lambda distro, workspace: {
            "ready": True,
            "distro": distro,
            "workspace": workspace,
            "runtime_warnings": ["torchcodec_decoder_unavailable"],
        },
    )

    exit_code = wsl_audio_preflight.main(
        ["--distro", "Ubuntu-22.04", "--workspace", "/home/goodq/goodq_audio", "--compact"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["distro"] == "Ubuntu-22.04"
    assert payload["workspace"] == "/home/goodq/goodq_audio"
    assert payload["runtime_warnings"] == ["torchcodec_decoder_unavailable"]
