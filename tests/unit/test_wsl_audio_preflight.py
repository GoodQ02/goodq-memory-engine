from __future__ import annotations

import pytest


@pytest.mark.parametrize('strict,missing,ready', [(True, [], True), (False, [], False), (True, ['classifier.weight'], False)])
def test_emotion_probe_checks_the_workers_strict_trained_loader(monkeypatch, capsys, strict, missing, ready):
    import sys
    from types import SimpleNamespace
    from scripts.wsl_audio_preflight import _build_wav2vec_enrichment_probe_script

    calls = []
    class Extractor:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            return object()

    def load(repo, **kwargs):
        calls.append((repo, kwargs))
        return object(), {'strict': strict, 'missing_inference_keys': missing}

    monkeypatch.setitem(sys.modules, 'process_audio', SimpleNamespace(
        _load_trained_wav2vec=load, _resolve_hf_cache_dir=lambda: '/offline/cache',
        Wav2Vec2FeatureExtractor=Extractor))
    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(
        Wav2Vec2ForSequenceClassification=Extractor, Wav2Vec2FeatureExtractor=Extractor,
        Wav2Vec2Model=Extractor))
    script = _build_wav2vec_enrichment_probe_script('/test/worker')
    code = script.split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    original_path = sys.path[:]
    try:
        exec(compile(code, '<emotion-preflight>', 'exec'), {})
    finally:
        sys.path[:] = original_path
    lines = capsys.readouterr().out.splitlines()
    assert ('wav2vec_enrichment_ready' in lines) is ready
    assert calls == [('ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition',
                      {'cache_dir': '/offline/cache', 'is_offline': True, 'emotion': True})]


@pytest.mark.parametrize('decode_ready,pyannote,expected', [
    (True, '3.3.2', 'not_required_for_active_lane'),
    (False, '3.3.2', 'unknown'),
    (True, '4.0.0', 'unknown'),
])
def test_missing_torchcodec_is_not_a_degradation_for_verified_active_decoder(monkeypatch, decode_ready, pyannote, expected):
    from types import SimpleNamespace
    from scripts import wsl_audio_preflight as preflight

    def probe(distro, script, **kwargs):
        # Return independent successful markers for the required probes.
        return SimpleNamespace(returncode=0, stderr='', stdout='\n'.join([
            'transcription_ready', 'gpu_ready', 'process_import_ready', 'abi_ready',
            'diarization_ready', 'speaker_signature_ready', 'wav2vec_enrichment_ready']))
    monkeypatch.setattr(preflight, '_run_wsl_probe', probe)
    monkeypatch.setattr(preflight, '_probe_wsl_audio_black_box', lambda *args: {
        'package_versions': {**preflight._EXPECTED_TORCH_LANE, 'pyannote.audio': pyannote},
        'audio_decode': {'ready': decode_ready, 'backend': 'torchaudio.load'},
        'torchcodec': {'ready': False, 'error_tail': "No module named 'torchcodec'"}})
    result = preflight.probe_wsl_audio_runtime('Ubuntu', '/test/worker')
    assert result['torchcodec_ready'] is False
    assert result['torchcodec_applicability'] == expected
    assert ('torchcodec_decoder_unavailable' in result['runtime_warnings']) is (expected == 'unknown')
    assert ('active_audio_decoder_unavailable' in result['runtime_warnings']) is (not decode_ready)


@pytest.mark.parametrize('model_name', ['pyannote/speaker-diarization-3.1', '/isolated/models/community-1'])
@pytest.mark.parametrize('loader_fails', [False, True])
def test_diarization_probe_loads_the_configured_model_through_worker(monkeypatch, capsys, model_name, loader_fails):
    import sys
    from types import SimpleNamespace
    from scripts.wsl_audio_preflight import _build_diarization_probe_script

    calls, caches = [], []
    def load(factory, model, token, **kwargs):
        calls.append((model, kwargs))
        if loader_fails:
            raise OSError('missing model asset')
        return object()
    monkeypatch.setenv('HF_HUB_OFFLINE', '1')
    monkeypatch.setitem(sys.modules, 'process_audio', SimpleNamespace(
        _load_runtime_config=lambda: {'models': {'diarization': model_name}},
        _load_pyannote_pipeline=load, _resolve_hf_cache_dir=lambda: '/offline/cache'))
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(snapshot_download=lambda **kw: caches.append(kw)))
    monkeypatch.setitem(sys.modules, 'pyannote.audio', SimpleNamespace(Pipeline=object))
    code = _build_diarization_probe_script('/test/worker').split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    original_path = sys.path[:]
    try:
        exec(compile(code, '<diarization-preflight>', 'exec'), {})
    finally:
        sys.path[:] = original_path
    assert calls == [(model_name, {'cache_dir': '/offline/cache', 'is_offline': True})]
    assert all(call['local_files_only'] for call in caches)
    if model_name.startswith('/isolated'):
        assert not any(call['repo_id'].startswith('pyannote/') for call in caches)
    assert ('diarization_ready' in capsys.readouterr().out.splitlines()) is not loader_fails


def test_build_diarization_probe_uses_pinned_offline_revisions():
    from scripts.wsl_audio_preflight import WSL_DIARIZATION_MODEL_REPOS, _build_diarization_probe_script

    script = _build_diarization_probe_script("/home/goodq/goodq_audio")

    assert "pinned_revisions" in script
    assert "revision" in script
    for repo_id in WSL_DIARIZATION_MODEL_REPOS:
        assert repo_id in script


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


@pytest.mark.parametrize("ecapa_ready", [True, False])
def test_probe_wsl_audio_runtime_reports_separate_enrichment_readiness(monkeypatch, ecapa_ready):
    from scripts import wsl_audio_preflight

    def _fake_run_wsl_probe(distro, script, *, timeout):
        if "from speaker_signature import load_encoder" in script:
            return type("Probe", (), {"returncode": 0 if ecapa_ready else 1,
                "stdout": "speaker_signature_ready\n" if ecapa_ready else "",
                "stderr": "" if ecapa_ready else "ECAPA assets unavailable"})()
        if "test -f" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        if "import faster_whisper, torch" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "transcription_ready\ngpu_ready\n", "stderr": ""})()
        if "spec_from_file_location('goodq_process_audio'" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "process_import_ready\n", "stderr": ""})()
        if "from torchvision.ops import nms" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "abi_ready\n", "stderr": ""})()
        if "snapshot_download" in script and "speaker-diarization-3.1" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "diarization_ready\n", "stderr": ""})()
        if "_load_trained_wav2vec" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "wav2vec_enrichment_ready\n", "stderr": ""})()
        raise AssertionError(f"unexpected probe script: {script}")

    monkeypatch.setattr(wsl_audio_preflight, "_run_wsl_probe", _fake_run_wsl_probe)
    monkeypatch.setattr(
        wsl_audio_preflight,
        "_probe_package_version",
        lambda distro, workspace, package_name: {
            "torch": "2.5.1+cu121",
            "torchvision": "0.20.1+cu121",
            "torchaudio": "2.5.1+cu121",
            "pyannote.audio": "3.3.2",
            "faster-whisper": "1.2.1",
            "transformers": "4.43.3",
            "tokenizers": "0.19.1",
            "safetensors": "0.7.0",
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
                "transformers": "4.43.3",
                "tokenizers": "0.19.1",
                "safetensors": "0.7.0",
            },
            "torchcodec": {"ready": True},
        },
    )

    result = wsl_audio_preflight.probe_wsl_audio_runtime("Ubuntu-22.04", "/home/goodq/goodq_audio")

    assert result["ready"] is True
    assert result["wav2vec_enrichment_ready"] is True
    assert result["speaker_signature_ready"] is ecapa_ready
    assert ("speaker_signature_unavailable" in result["runtime_warnings"]) is not ecapa_ready
    assert result["clap_handoff_ready"] is True
    assert result["clap_handoff"]["required_step"] == "audio_embed_clap"
    assert result["clap_handoff"]["reason"] == "canonical_clap_required"
    assert result["detected_versions"]["transformers"] == "4.43.3"


def test_probe_wsl_audio_runtime_exposes_a_failed_clap_handoff_contract(monkeypatch):
    from scripts import wsl_audio_preflight

    monkeypatch.setattr(
        wsl_audio_preflight,
        "_probe_clap_handoff_contract",
        lambda: {
            "ready": False,
            "required_step": "audio_embed_clap",
            "reason": "canonical_clap_contract_unavailable",
        },
    )
    monkeypatch.setattr(
        wsl_audio_preflight,
        "_run_wsl_probe",
        lambda _distro, script, timeout: type(
            "Probe",
            (),
            {
                "returncode": 0,
                "stdout": (
                    "transcription_ready\ngpu_ready\n"
                    if "import faster_whisper, torch" in script
                    else "process_import_ready\n"
                    if "spec_from_file_location('goodq_process_audio'" in script
                    else "abi_ready\n"
                    if "from torchvision.ops import nms" in script
                    else "diarization_ready\n"
                    if "snapshot_download" in script
                    else "wav2vec_enrichment_ready\n"
                    if "_load_trained_wav2vec" in script
                    else ""
                ),
                "stderr": "",
            },
        )(),
    )
    monkeypatch.setattr(wsl_audio_preflight, "_probe_package_version", lambda *args: None)
    monkeypatch.setattr(
        wsl_audio_preflight,
        "_probe_wsl_audio_black_box",
        lambda *args: {"package_versions": {}, "torchcodec": {"ready": True}},
    )

    result = wsl_audio_preflight.probe_wsl_audio_runtime(
        "Ubuntu-22.04", "/home/goodq/goodq_audio"
    )

    assert result["clap_handoff_ready"] is False
    assert result["clap_handoff"]["reason"] == "canonical_clap_contract_unavailable"
    assert "clap_handoff_unavailable" in result["runtime_warnings"]


def test_probe_wsl_audio_runtime_uses_env_probe_timeouts(monkeypatch):
    from scripts import wsl_audio_preflight

    monkeypatch.setenv("GOODQ_WSL_WORKSPACE_PROBE_TIMEOUT_SEC", "31")
    monkeypatch.setenv("GOODQ_WSL_TRANSCRIPTION_PROBE_TIMEOUT_SEC", "61")
    monkeypatch.setenv("GOODQ_WSL_PROCESS_IMPORT_PROBE_TIMEOUT_SEC", "62")
    monkeypatch.setenv("GOODQ_WSL_ABI_PROBE_TIMEOUT_SEC", "46")
    monkeypatch.setenv("GOODQ_WSL_DIARIZATION_PROBE_TIMEOUT_SEC", "91")
    monkeypatch.setenv("GOODQ_WSL_WAV2VEC_PROBE_TIMEOUT_SEC", "92")
    observed = {}

    def _fake_run_wsl_probe(distro, script, *, timeout):
        if "test -f" in script:
            observed["workspace"] = timeout
            return type("Probe", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        if "import faster_whisper, torch" in script:
            observed["transcription"] = timeout
            return type("Probe", (), {"returncode": 0, "stdout": "transcription_ready\ngpu_ready\n", "stderr": ""})()
        if "spec_from_file_location('goodq_process_audio'" in script:
            observed["process_import"] = timeout
            return type("Probe", (), {"returncode": 0, "stdout": "process_import_ready\n", "stderr": ""})()
        if "from torchvision.ops import nms" in script:
            observed["abi"] = timeout
            return type("Probe", (), {"returncode": 0, "stdout": "abi_ready\n", "stderr": ""})()
        if "snapshot_download" in script and "speaker-diarization-3.1" in script:
            observed["diarization"] = timeout
            return type("Probe", (), {"returncode": 0, "stdout": "diarization_ready\n", "stderr": ""})()
        if "_load_trained_wav2vec" in script:
            observed["wav2vec"] = timeout
            return type("Probe", (), {"returncode": 0, "stdout": "wav2vec_enrichment_ready\n", "stderr": ""})()
        raise AssertionError(f"unexpected probe script: {script}")

    monkeypatch.setattr(wsl_audio_preflight, "_run_wsl_probe", _fake_run_wsl_probe)
    monkeypatch.setattr(wsl_audio_preflight, "_probe_package_version", lambda *args: None)
    monkeypatch.setattr(wsl_audio_preflight, "_probe_wsl_audio_black_box", lambda *args: {"package_versions": {}})

    result = wsl_audio_preflight.probe_wsl_audio_runtime("Ubuntu-22.04", "/home/goodq/goodq_audio")

    assert result["ready"] is True
    assert observed == {
        "workspace": 31,
        "transcription": 61,
        "process_import": 62,
        "abi": 46,
        "diarization": 91,
        "wav2vec": 92,
    }


def test_probe_wsl_audio_runtime_keeps_base_ready_when_wav2vec_enrichment_missing(monkeypatch):
    from scripts import wsl_audio_preflight

    def _fake_run_wsl_probe(distro, script, *, timeout):
        if "test -f" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        if "import faster_whisper, torch" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "transcription_ready\ngpu_ready\n", "stderr": ""})()
        if "spec_from_file_location('goodq_process_audio'" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "process_import_ready\n", "stderr": ""})()
        if "from torchvision.ops import nms" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "abi_ready\n", "stderr": ""})()
        if "snapshot_download" in script and "speaker-diarization-3.1" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "diarization_ready\n", "stderr": ""})()
        if "_load_trained_wav2vec" in script:
            return type(
                "Probe",
                (),
                {"returncode": 0, "stdout": "wav2vec_enrichment_unavailable\ntransformers import failed\n", "stderr": ""},
            )()
        raise AssertionError(f"unexpected probe script: {script}")

    monkeypatch.setattr(wsl_audio_preflight, "_run_wsl_probe", _fake_run_wsl_probe)
    monkeypatch.setattr(wsl_audio_preflight, "_probe_package_version", lambda *args: None)
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

    assert result["ready"] is True
    assert result["wav2vec_enrichment_ready"] is False
    assert "wav2vec_enrichment_unavailable" in result["runtime_warnings"]


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
