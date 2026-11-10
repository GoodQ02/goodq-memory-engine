from types import SimpleNamespace

import pytest


def _black_box():
    packages = {'torch': '2.14.1+cu126', 'torchvision': '0.29.1+cu126',
                'torchaudio': '2.11.1+cpu', 'torchcodec': '0.17.0+cpu'}
    return {'package_versions': packages, 'python_version': '3.12.16',
            'torch': {'cuda_compiled': '12.6'},
            'audio_decode': {'ready': True}, 'transcription_decode': {'ready': True}, 'torchcodec': {'ready': True},
            'runtime_manifest': {'sha256': 'receipt', 'manifest': {
                'schema_version': 1, 'candidate_id': 'test', 'python_version': '3.12.16',
                'torch_cuda': '12.6', 'expected_packages': dict(packages),
                'requires_torchcodec': True}}}


@pytest.mark.parametrize('fault', [None, 'package', 'python', 'cuda', 'schema', 'unreadable', 'config', 'missing_file'])
def test_manifest_does_not_accept_runtime_drift(fault):
    from scripts.wsl_audio_preflight import _check_runtime_manifest
    payload = _black_box()
    payload['runtime_manifest']['manifest']['expected_files'] = {'config.json': 'a'*64}
    payload['runtime_manifest']['files'] = {'config.json': 'a'*64}
    if fault == 'config': payload['runtime_manifest']['files']['config.json'] = 'b'*64
    if fault == 'missing_file': payload['runtime_manifest']['files'] = {}
    if fault == 'package': payload['package_versions']['torch'] = '2.5.1+cu121'
    if fault == 'python': payload['python_version'] = '3.10.12'
    if fault == 'cuda': payload['torch']['cuda_compiled'] = '13.2'
    if fault == 'schema': payload['runtime_manifest']['manifest']['schema_version'] = 0
    if fault == 'unreadable': payload['runtime_manifest'] = {'error': 'JSONDecodeError'}
    result = _check_runtime_manifest(payload)
    assert (result['status'] == 'matched') is (fault is None)
    assert _check_runtime_manifest({}) == {'status': 'not_declared'}


@pytest.mark.parametrize('fault', [None, 'package', 'decoder', 'transcription_decoder', 'torchcodec'])
def test_production_preflight_requires_declared_runtime_and_decoder(monkeypatch, fault):
    from scripts import wsl_audio_preflight as mod
    payload = _black_box()
    if fault == 'package': payload['package_versions']['torchcodec'] = None
    if fault == 'decoder': payload['audio_decode']['ready'] = False
    if fault == 'transcription_decoder': payload['transcription_decode']['ready'] = False
    if fault == 'torchcodec': payload['torchcodec']['ready'] = False
    monkeypatch.setattr(mod, '_probe_wsl_audio_black_box', lambda *a: payload)
    monkeypatch.setattr(mod, '_run_wsl_probe', lambda *a, **kw: SimpleNamespace(
        returncode=0, stderr='', stdout='\n'.join(['transcription_ready', 'gpu_ready',
            'process_import_ready', 'abi_ready', 'diarization_ready',
            'speaker_signature_ready', 'wav2vec_enrichment_ready'])))
    result = mod.probe_wsl_audio_runtime('Ubuntu', '/isolated')
    assert result['runtime_ready'] is (fault is None)
    assert result['ready'] is (fault is None)
    assert result['torchcodec_applicability'] == 'required_by_runtime_manifest'
    assert result['recommended_install_command'] is None


def test_compact_bridge_receipt_keeps_manifest_identity():
    from scripts.wsl2_audio_bridge import _compact_runtime_probe
    manifest = {'status': 'matched', 'sha256': 'manifest-hash'}
    assert _compact_runtime_probe({'runtime_manifest': manifest})['runtime_manifest'] == manifest


def test_declared_manifest_cannot_disappear_on_black_box_failure(monkeypatch):
    from scripts import wsl_audio_preflight as mod
    monkeypatch.setattr(mod, '_probe_wsl_audio_black_box', lambda *a: {'probe_error_type':'TimeoutError'})
    monkeypatch.setattr(mod, '_probe_package_version', lambda *a: None)
    monkeypatch.setattr(mod, '_run_wsl_probe', lambda *a, **kw: SimpleNamespace(
        returncode=0, stderr='', stdout='\n'.join(['runtime_manifest_declared', 'transcription_ready',
            'gpu_ready', 'process_import_ready', 'abi_ready', 'diarization_ready',
            'speaker_signature_ready', 'wav2vec_enrichment_ready'])))
    result = mod.probe_wsl_audio_runtime('Ubuntu','/isolated')
    assert result['runtime_manifest']['reason'] == 'runtime_manifest_probe_unavailable'
    assert result['runtime_ready'] is False and result['ready'] is False
