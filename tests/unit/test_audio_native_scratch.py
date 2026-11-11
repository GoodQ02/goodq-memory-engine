"""Bounded real-decoder/caller checks; no model inference or saved media."""
from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tests.unit.test_audio_engine_recording_call import (
    Recognizer, ffmpeg, make_request, profile, verify_test_assets,
)
from wsl2_audio import native_scratch as scratch, recording_engine as engine
from wsl2_audio.evidence_contract import validate_evidence
from wsl2_audio.profile_identity import profile_identity
from wsl2_audio.recording_audio import _atomic_json, _sha_file
from wsl2_audio.scene_projection import project_audio


def test_model_locations_preserve_actual_recording_and_projection_ids_and_resume(tmp_path, ffmpeg, monkeypatch):
    req = make_request(tmp_path, ffmpeg, count=16000)
    p = profile()
    p['recognizer']['path'] = '/mnt/c/models/recognizer'
    p['speech_activity_model']['path'] = '/mnt/l/models/vad'
    model = Recognizer()
    monkeypatch.setattr(engine, 'load_recognizer', lambda *args: model)
    first = engine.analyze_recording(req, p, tmp_path/'job')
    relocated = deepcopy(p)
    relocated['recognizer']['path'] = '/home/user/cache/recognizer'
    relocated['speech_activity_model']['path'] = '/home/user/cache/vad'
    again = engine.analyze_recording(req, relocated, tmp_path/'job')
    scenes = [{'scene_id': 's', 'start': 0., 'end': 1.}]
    assert len(model.calls) == 1, 'Relocation repeated recognition'
    assert first == again
    assert project_audio(first, scenes) == project_audio(again, scenes)
    changed = deepcopy(relocated)
    changed['language'] = 'auto'
    assert profile_identity(changed) != profile_identity(p)
    changed = deepcopy(relocated)
    changed['recognizer']['sha256'] = 'd'*64
    assert profile_identity(changed) != profile_identity(p)


def test_old_evidence_keeps_original_ids_and_unknown_identity_methods_fail():
    from tests.unit.test_audio_engine_consumers import recording
    old = recording()
    before = deepcopy(old)
    validate_evidence(old)
    assert old == before and 'config_identity_method' not in old['provenance']
    old['provenance']['config_identity_method'] = 'unknown'
    with pytest.raises(ValueError, match='identity method'):
        validate_evidence(old)


@pytest.mark.parametrize('autocrlf', ['true', 'false'])
def test_git_checkout_preserves_recording_worker_fingerprint(tmp_path, monkeypatch, autocrlf):
    import os
    import subprocess
    repo = Path(__file__).resolve().parents[2]
    expected = engine._worker_digest()
    names = subprocess.check_output(
        ['git', '-C', str(repo), 'ls-files', '-z', '--', 'wsl2_audio/*.py'],
    ).decode().split('\0')
    names = [name for name in names if name]
    assert names
    env = dict(os.environ, GIT_INDEX_FILE=str(tmp_path/'temp.index'))
    subprocess.run(
        ['git', '-C', str(repo), '-c', 'core.autocrlf='+autocrlf, 'add', '--', *names],
        check=True, capture_output=True, env=env,
    )
    checkout_dir = tmp_path/'checkout'
    subprocess.run(
        ['git', '-C', str(repo), '-c', 'core.autocrlf='+autocrlf,
         'checkout-index', '--prefix='+checkout_dir.as_posix()+'/', '--', *names],
        check=True, capture_output=True, env=env,
    )
    monkeypatch.setattr(engine, '__file__', str(checkout_dir/'wsl2_audio/recording_engine.py'))
    assert engine._worker_digest() == expected


@pytest.fixture
def native_job(tmp_path, ffmpeg, monkeypatch):
    root = tmp_path/'linux-owned';root.mkdir()
    _atomic_json({'schema': scratch.SCHEMA}, root/'.goodq-native-scratch.json')
    monkeypatch.setattr(scratch, '_root', lambda location, **kwargs: root)
    monkeypatch.setattr(scratch, '_lock', lambda *args: nullcontext())
    monkeypatch.setattr(scratch.subprocess, 'check_output', lambda *args, **kwargs: '9p\n')
    req = make_request(tmp_path, ffmpeg, count=16000, silent=True)
    req.update(source_sha256=_sha_file(Path(req['source_path'])),
               scenes=[{'scene_id': 's', 'start': 0., 'end': 1.}],
               processing_root=str(tmp_path/'windows-processing'))
    p = profile()
    asset = tmp_path/'model';asset.write_bytes(b'fixture-only-never-loaded')
    for name in ('recognizer', 'speech_activity_model'):
        p[name].update(path=str(asset), sha256=_sha_file(asset))
    reqfile = tmp_path/'request.json';_atomic_json(req, reqfile)
    prof = tmp_path/'profile.json';_atomic_json(p, prof)
    output = tmp_path/'windows-job';output.mkdir()
    plan = dict(schema=scratch.SCHEMA, job_key='a'*64, scratch_root=str(root),
                request=str(reqfile), profile=str(prof), output=str(output),
                worker_root=str(Path(__file__).resolve().parents[2]),
                request_sha256=_sha_file(reqfile), profile_sha256=_sha_file(prof),
                worker_sha256=engine._worker_digest(), python='test', timeout_seconds=60)
    calls = []
    def worker(plan, job, code, ecapa, deadline):
        calls.append(job)
        (job/'worker.log').write_text('real decoder; digital silence; no models\n')
        engine.main([str(job/'request.json'), str(job/'profile.json'), str(job/'output')])
    monkeypatch.setattr(scratch, '_run_worker', worker)
    return root, output, plan, calls, worker


def test_export_resume_and_cleanup_require_windows_acceptance(native_job, monkeypatch):
    root, output, plan, calls, worker = native_job
    original_copy = scratch._copy
    failed = []
    def fail_publication(source, dest, expected, **kwargs):
        if dest == output/'scene_audio.json' and not failed:
            failed.append(True)
            raise OSError('injected export interruption')
        return original_copy(source, dest, expected, **kwargs)
    monkeypatch.setattr(scratch, '_copy', fail_publication)
    with pytest.raises(OSError, match='export interruption'):
        scratch.execute(plan)
    job = root/'jobs'/plan['job_key']
    assert job.is_dir() and not (output/'scene_audio.json').exists()
    assert not list(job.glob('source.*')), 'Native audio duplicated the full source media'
    assert json.loads((job/'request.json').read_text())['source_path'] == json.loads(Path(plan['request']).read_text())['source_path']
    checkpoints = {p: (p.stat().st_mtime_ns, _sha_file(p)) for p in (job/'output/decode').rglob('*') if p.is_file()}
    scratch.execute(plan)
    assert len(calls) == 2
    assert all((p.stat().st_mtime_ns, _sha_file(p)) == old for p, old in checkpoints.items())
    request = json.loads(Path(plan['request']).read_text())
    receipt = scratch.verify_export(output, request['processing_root'], plan)
    assert len(list((root/'models').iterdir())) == 1, 'Identical assets copied twice'
    assert len(list((root/'code').iterdir())) == 1
    with pytest.raises(FileNotFoundError):
        scratch.execute(plan, finalize=True)
    assert job.exists()
    _atomic_json({'reusable': True, 'handle': {'sha256': receipt['files']['output/scene_audio.json']}}, output/'job.json')
    scratch.execute(plan, finalize=True)
    assert not job.exists()
    assert (root/'models').is_dir() and (root/'code').is_dir()
    assert (output/'scene_audio.json').is_file()
    scratch.execute(plan, finalize=True)  # acknowledgement is idempotent


def test_corrupt_export_blocks_cleanup_and_preserves_resume(native_job):
    root, output, plan, calls, worker = native_job
    scratch.execute(plan)
    receipt = json.loads((output/'native-export.json').read_text())
    _atomic_json({'reusable': True, 'handle': {'sha256': receipt['files']['output/scene_audio.json']}}, output/'job.json')
    (output/'evidence.json').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='export bytes changed'):
        scratch.execute(plan, finalize=True)
    assert (root/'jobs'/plan['job_key']).exists()


def test_export_verifies_each_resolved_target_once(native_job, monkeypatch):
    root, output, plan, calls, worker = native_job
    scratch.execute(plan)
    request = json.loads(Path(plan['request']).read_text())
    receipt = json.loads((output/'native-export.json').read_text())
    targets = {}
    for name in receipt['files']:
        prefix, relative = name.split('/', 1)
        parent = output if prefix == 'output' else Path(request['processing_root'])
        targets[parent.resolve()/relative] = 0
    original = Path.resolve
    def counted(path, *args, **kwargs):
        if path in targets:
            targets[path] += 1
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'resolve', counted)
    assert scratch.verify_export(output, request['processing_root'], plan) == receipt
    assert targets and set(targets.values()) == {1}


@pytest.mark.parametrize('fault', ['corrupt_bytes', 'escaped_manifest'])
def test_windows_prepare_rejects_invalid_export_before_acceptance(tmp_path, monkeypatch, native_job, fault):
    from scripts import wsl2_audio_bridge as bridge
    from steps.audio import recording_ingestion as caller
    root, plan, request, cfg, executions = _connect_caller(tmp_path, monkeypatch, native_job)
    original = bridge.run_recording_request
    def damaged_export(req, prof, job, options):
        original(req, prof, job, options)
        if fault == 'corrupt_bytes':
            (job/'evidence.json').write_bytes(b'changed after Linux export verification')
        else:
            receipt = json.loads((job/'native-export.json').read_text())
            receipt['files']['output/../outside'] = '0'*64
            _atomic_json(receipt, job/'native-export.json')
    monkeypatch.setattr(bridge, 'run_recording_request', damaged_export)
    with pytest.raises(ValueError, match='export bytes changed|Unsafe scratch/export'):
        caller.prepare(cfg, request['source_path'], request['scenes'])
    output = Path(executions[0]['output'])
    assert not (output/'job.json').exists()
    assert not (output/'native-cleanup.json').exists()
    assert (root/'jobs'/plan['job_key']/'owner.json').exists()


def test_existing_staged_model_is_not_silently_overwritten(native_job):
    root, output, plan, calls, worker = native_job
    scratch.execute(plan)
    asset = next((root/'models').glob('*/asset'))
    asset.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='Retained staged'):
        scratch.execute(plan)
    assert len(calls) == 1


def test_export_retains_review_bytes_and_rejects_corruption(native_job, monkeypatch):
    from array import array
    from tests.unit.test_audio_engine_consumers import recording
    from wsl2_audio.scene_consumers import publish_scene_audio
    from wsl2_audio.scene_projection import legacy_audio
    root, output, plan, calls, worker = native_job
    def reviewed_worker(plan, job, code, ecapa, deadline):
        req = json.loads((job/'request.json').read_text())
        evidence = recording()
        pcm = job/'review-source.f64le';pcm.write_bytes(array('d', [.125]*32000).tobytes())
        evidence['source'].update(sha256=req['source_sha256'], pcm_sha256=_sha_file(pcm))
        evidence['provenance'].update(worker_sha256=plan['worker_sha256'],run_id=req['run_id'],epoch_id=req['epoch_id'])
        rec = {'source': evidence['source'], 'pcm': {'path': str(pcm)}}
        _atomic_json(evidence, job/'output/evidence.json')
        scenes = publish_scene_audio(evidence, req['scenes'], rec, job/'processing')
        _atomic_json({k:legacy_audio(v) for k,v in scenes.items()}, job/'output/scene_audio.json')
        (job/'worker.log').write_text('fixture observations, real review publication')
    monkeypatch.setattr(scratch, '_run_worker', reviewed_worker)
    scratch.execute(plan)
    req = json.loads(Path(plan['request']).read_text())
    receipt = scratch.verify_export(output, req['processing_root'], plan)
    reviews = [name for name in receipt['files'] if name.startswith('processing/')]
    assert len(reviews) == 1
    review = scratch._inside(req['processing_root'], reviews[0].split('/',1)[1])
    assert review.read_bytes().startswith(b'RIFF')
    review.write_bytes(b'corrupt review')
    with pytest.raises(ValueError, match='export bytes changed'):
        scratch.verify_export(output, req['processing_root'], plan)


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'C:/drive', 'x\\escape', '.'])
def test_export_and_cleanup_paths_are_bounded(tmp_path, name):
    with pytest.raises(ValueError):
        scratch._inside(tmp_path, name)


def test_native_setting_cannot_silently_select_wrong_transport():
    from scripts.config_schema import RecordingEngineConfig
    with pytest.raises(ValueError):
        RecordingEngineConfig(native_scratch_root='/home/user/scratch')
    with pytest.raises(ValueError):
        RecordingEngineConfig(transport='wsl', native_scratch_root='/home/user/../other')
    assert RecordingEngineConfig().native_scratch_root is None


def test_native_root_rejects_windows_mount_and_existing_unowned_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(scratch.subprocess, 'check_output', lambda *args, **kwargs: '9p\n')
    with pytest.raises(ValueError, match='native Linux filesystem'):
        scratch._root(str(tmp_path/'mounted'))
    existing = tmp_path/'existing';existing.mkdir();(existing/'keep').write_text('unchanged')
    with pytest.raises(ValueError, match='unowned'):
        scratch._root(str(existing))
    assert (existing/'keep').read_text() == 'unchanged'


def test_actual_windows_prepare_accepts_export_before_cleanup_and_cache_reuse(tmp_path, monkeypatch, native_job):
    from scripts import wsl2_audio_bridge as bridge
    from steps.audio import recording_ingestion as caller
    root, output, plan, calls, worker = native_job
    request = json.loads(Path(plan['request']).read_text())
    monkeypatch.setattr(caller, 'runtime_path', lambda p, transport: str(Path(p).resolve()))
    executions = []
    def run(req, prof, job, options):
        current = dict(plan, request=str(req), profile=str(prof), output=str(job),
                       request_sha256=_sha_file(req), profile_sha256=_sha_file(prof))
        _atomic_json(current, job/'native-plan.json');executions.append(current)
        scratch.execute(current)
    def finalize(job, options):
        current = json.loads((job/'native-plan.json').read_text())
        assert (job/'job.json').exists(), 'Cleaned before durable Windows acceptance'
        scratch.execute(current, finalize=True)
    monkeypatch.setattr(bridge, 'run_recording_request', run)
    monkeypatch.setattr(bridge, 'finalize_recording_request', finalize)
    cfg = {'audio': {'recording_engine': dict(enabled=True, transport='wsl', distro='fixture', user='fixture',
            python='fixture', profile=plan['profile'], source_revision='fixture', native_scratch_root='/home/fixture/scratch')},
           'run': {'id': 'r', 'epoch_id': 'e'}, 'paths': {'db_dir': str(tmp_path/'epoch')}}
    handle = caller.prepare(cfg, request['source_path'], request['scenes'])
    assert caller.scene_result(handle, 's')['transcript_outcome'] == 'no_speech'
    assert caller.prepare(cfg, request['source_path'], request['scenes']) == handle
    assert len(executions) == 1 and not (root/'jobs'/plan['job_key']).exists()


def _connect_caller(tmp_path, monkeypatch, native_job):
    from scripts import wsl2_audio_bridge as bridge
    from steps.audio import recording_ingestion as caller
    root, output, plan, calls, worker = native_job
    request=json.loads(Path(plan['request']).read_text())
    monkeypatch.setattr(caller, 'runtime_path', lambda p, transport: str(Path(p).resolve()))
    executions=[]
    def run(req, prof, job, options):
        if not options.get('native_scratch_root'):
            engine.main([str(req),str(prof),str(job)])
            return
        current=dict(plan,request=str(req),profile=str(prof),output=str(job),
                     request_sha256=_sha_file(req),profile_sha256=_sha_file(prof))
        _atomic_json(current,job/'native-plan.json');executions.append(current)
        scratch.execute(current)
    def finalize(job, options):
        if options.get('native_scratch_root'):
            scratch.execute(json.loads((job/'native-plan.json').read_text()),finalize=True)
    monkeypatch.setattr(bridge,'run_recording_request',run)
    monkeypatch.setattr(bridge,'finalize_recording_request',finalize)
    cfg={'audio':{'recording_engine':dict(enabled=True,transport='wsl',distro='fixture',user='fixture',
        python='fixture',profile=plan['profile'],source_revision='fixture',native_scratch_root='/home/fixture/scratch')},
        'run':{'id':'review','epoch_id':'isolated-review'},'paths':{'db_dir':str(tmp_path/'epoch')}}
    return root,plan,request,cfg,executions



def test_interrupted_retirement_retries_through_prepare(tmp_path, monkeypatch, native_job):
    from scripts import wsl2_audio_bridge as bridge
    from steps.audio import recording_ingestion as caller
    root, plan, request, cfg, executions = _connect_caller(tmp_path, monkeypatch, native_job)
    original = scratch.shutil.rmtree
    def interrupted(path):
        (Path(path)/'owner.json').unlink()
        raise OSError('injected cleanup interruption')
    monkeypatch.setattr(scratch.shutil, 'rmtree', interrupted)
    with pytest.raises(OSError, match='cleanup interruption'):
        caller.prepare(cfg, request['source_path'], request['scenes'])
    output = Path(executions[0]['output'])
    accepted = json.loads((output/'job.json').read_text())
    assert accepted['reusable'] and caller.load(accepted['handle'])
    intent = root/'retirements'/(plan['job_key']+'.json')
    assert intent.is_file()
    monkeypatch.setattr(scratch.shutil, 'rmtree', original)
    assert caller.prepare(cfg, request['source_path'], request['scenes']) == accepted['handle']
    assert len(executions) == 1 and not (root/'jobs'/plan['job_key']).exists()
    assert intent.is_file() and (output/'native-cleanup.json').is_file()


def test_retirement_cannot_borrow_another_jobs_ownership(native_job, monkeypatch):
    root, output, plan, calls, worker = native_job
    scratch.execute(plan)
    receipt = json.loads((output/'native-export.json').read_text())
    _atomic_json({'reusable':True, 'handle':{'sha256':receipt['files']['output/scene_audio.json']}}, output/'job.json')
    _atomic_json({'owner':{'schema':scratch.SCHEMA,'plan_sha256':'0'*64},
                  'scene_sha256':receipt['files']['output/scene_audio.json']}, root/'retirements'/(plan['job_key']+'.json'))
    with pytest.raises(ValueError, match='retirement ownership'):
        scratch.execute(plan, finalize=True)
    assert (root/'jobs'/plan['job_key']/'owner.json').exists()


@pytest.mark.parametrize('silent', [True, False])
@pytest.mark.parametrize('failure', ['missing', 'corrupt_cache'])
def test_optional_staging_failure_preserves_caller_outcomes(tmp_path, monkeypatch, native_job, silent, failure):
    from steps.audio import recording_ingestion as caller
    from tests.unit.test_audio_engine_recording import write_pcm
    from tests.unit.test_audio_engine_recording_call import Recognizer
    root, plan, request, cfg, executions = _connect_caller(tmp_path, monkeypatch, native_job)
    p = json.loads(Path(plan['profile']).read_text())
    p['enrichment'] = {'device':'cpu', 'runtime_packages':{}, 'models':{'overlap':{
        'id':'fixture-overlap','revision':'fixture','sha256':'e'*64,
        'path':str(tmp_path/'missing-optional-model')}}}
    if failure == 'corrupt_cache':
        asset = tmp_path/'optional-original';asset.write_bytes(b'original pinned asset')
        spec = p['enrichment']['models']['overlap']
        spec.update(path=str(asset), sha256=_sha_file(asset))
        cache = root/'models'/scratch._digest({'asset':spec['sha256']})
        cache.mkdir(parents=True);(cache/'asset').write_bytes(b'corrupt staged asset')
    _atomic_json(p, Path(plan['profile']))
    if not silent:
        write_pcm(Path(request['source_path']), [1]*16000)
        model = Recognizer()
        model.models = [{k:p[n][k] for k in ('id','revision','sha256')}
                        for n in ('recognizer','speech_activity_model')]
        monkeypatch.setattr(engine,'verify_recognizer', lambda p:{'models':model.models,'runtime':{'scope':'fixture'}})
        monkeypatch.setattr(engine,'load_recognizer', lambda *args:model)
    cfg['audio']['recording_engine']['native_scratch_root'] = None
    mounted = caller.prepare(cfg, request['source_path'], request['scenes'])
    mounted_result = caller.scene_result(mounted,'s')['audio_evidence']
    cfg['audio']['recording_engine']['native_scratch_root'] = '/home/fixture/scratch'
    native = caller.prepare(cfg, request['source_path'], request['scenes'])
    result = caller.scene_result(native,'s')['audio_evidence']
    assert result['recording_id'] == mounted_result['recording_id']
    output = Path(native['path']).parent
    diagnostics = json.loads((output/'native-staging.json').read_text())
    assert 'overlap' in diagnostics['optional_model_errors']
    if silent:
        assert result == mounted_result
        assert caller.scene_result(native,'s')['transcript_outcome'] == 'no_speech'
        assert not (root/'jobs'/plan['job_key']).exists()
    else:
        assert result['stages']['recognition']['status'] == 'ok'
        assert result['stages']['overlap']['status'] == 'error'
        assert 'Native model staging failed' in result['stages']['overlap']['error']
        assert not json.loads((output/'job.json').read_text())['reusable']
        assert (root/'jobs'/plan['job_key']).exists()
        assert not result.get('voice_signatures')


def test_expired_staging_stops_before_worker_and_export(native_job, monkeypatch):
    root, output, plan, calls, worker = native_job
    plan['timeout_seconds'] = 1
    clock = [0.0]
    monkeypatch.setattr(scratch.time, 'monotonic', lambda:clock[0])
    original = scratch._stage
    def slow_stage(*args):
        value = original(*args); clock[0] = 2.0; return value
    monkeypatch.setattr(scratch, '_stage', slow_stage)
    with pytest.raises(TimeoutError, match='deadline'):
        scratch.execute(plan)
    assert not calls and not (output/'scene_audio.json').exists()
    assert (root/'jobs'/plan['job_key']/'owner.json').is_file()


def test_expired_deadline_never_launches_process(tmp_path, monkeypatch):
    monkeypatch.setattr(scratch.time,'monotonic',lambda:2.0)
    monkeypatch.setattr(scratch.subprocess,'Popen',lambda *a,**kw:pytest.fail('expired worker launched'))
    with pytest.raises(TimeoutError,match='deadline'):
        scratch._run_worker({'python':'fixture'},tmp_path,tmp_path,None,deadline=1.0)


def test_retirement_rechecks_remaining_owner_marker(native_job):
    root, output, plan, calls, worker = native_job
    scratch.execute(plan)
    receipt = json.loads((output/'native-export.json').read_text())
    digest = receipt['files']['output/scene_audio.json']
    _atomic_json({'reusable': True, 'handle': {'sha256': digest}}, output/'job.json')
    job = root/'jobs'/plan['job_key']
    owner = json.loads((job/'owner.json').read_text())
    _atomic_json({'owner': owner, 'scene_sha256': digest}, root/'retirements'/(plan['job_key']+'.json'))
    _atomic_json({'schema': scratch.SCHEMA, 'plan_sha256': '0'*64}, job/'owner.json')
    with pytest.raises(ValueError, match='ownership changed during retirement'):
        scratch.execute(plan, finalize=True)
    assert job.exists() and not (output/'native-cleanup.json').exists()

def test_optional_staging_error_retains_other_evidence_through_prepare(tmp_path, monkeypatch, native_job):
    from steps.audio import recording_ingestion as caller
    from tests.unit.test_audio_engine_recording import write_pcm
    from tests.unit.test_audio_engine_enrichment_call import SpeechRecognizer, Observers
    from wsl2_audio import enrichment_models
    from wsl2_audio.eligibility import select_inputs
    root, plan, request, cfg, executions = _connect_caller(tmp_path, monkeypatch, native_job)
    write_pcm(Path(request['source_path']), [1]*32000)
    scenes = [{'scene_id':'s','start':0.,'end':2.}]
    p = json.loads(Path(plan['profile']).read_text())
    p.update(window={'core_seconds':20,'context_seconds':5}, enrichment={'device':'cpu','models':{
        'overlap':{'id':'fixture-overlap','revision':'fixture','sha256':'e'*64,
                   'path':str(tmp_path/'missing-overlap')}}})
    _atomic_json(p, Path(plan['profile']))
    model = SpeechRecognizer()
    model.models = [{k:p[n][k] for k in ('id','revision','sha256')}
                    for n in ('recognizer','speech_activity_model')]
    monkeypatch.setattr(engine,'verify_recognizer',lambda p:{'models':model.models,'runtime':{'scope':'fixture'}})
    monkeypatch.setattr(engine,'load_recognizer',lambda *args:model)
    monkeypatch.setattr(Observers,'silent',False,raising=False)
    monkeypatch.setattr(Observers,'calls',[])
    monkeypatch.setattr(enrichment_models,'RecordingObservers',Observers)
    handle = caller.prepare(cfg, request['source_path'], scenes)
    assert caller.scene_result(handle,'s')['audio_evidence']['stages']['recognition']['status'] == 'ok'
    evidence = json.loads((Path(handle['path']).parent/'evidence.json').read_text())
    assert evidence['utterances'][0]['text'] == 'Yay Joe'
    assert evidence['stages']['overlap']['status'] == 'error'
    assert 'overlap' not in Observers.calls
    assert all(evidence['stages'][name]['status']=='ok'
               for name in ('speaker_activity','phrase_activity','acoustic_events'))
    assert not select_inputs(evidence,'voice_sample') and not select_inputs(evidence,'vocal_delivery')


def test_warm_model_staging_skips_mounted_rereads_consolidates_findmnt_and_detects_source_mutation(
    tmp_path, native_job, monkeypatch
):
    root, output, plan, calls, worker = native_job
    model_dir = tmp_path / 'multi-file-model'
    model_dir.mkdir()
    files = {}
    for idx in range(5):
        name = f'part-{idx}.bin'
        part = model_dir / name
        part.write_bytes(f'pinned-bytes-{idx}'.encode())
        files[name] = _sha_file(part)
    prof_path = Path(plan['profile'])
    p = json.loads(prof_path.read_text())
    p['recognizer'] = {
        'id': 'fixture-multi', 'revision': 'fixture',
        'path': str(model_dir), 'files': files, 'sha256': scratch._digest(files),
    }
    _atomic_json(p, prof_path)
    plan['profile_sha256'] = _sha_file(prof_path)

    findmnt_calls = []
    def tracked_findmnt(cmd, *args, **kwargs):
        findmnt_calls.append(cmd)
        return '9p\n'
    monkeypatch.setattr(scratch.subprocess, 'check_output', tracked_findmnt)

    scratch.execute(plan)
    assert len(findmnt_calls) <= 2

    source_reads = []
    original_sha = scratch._sha_file
    resolved_parts = {p.resolve() for p in model_dir.iterdir()}
    def counted_sha(path):
        if Path(path).resolve() in resolved_parts:
            source_reads.append(Path(path).name)
        return original_sha(path)
    monkeypatch.setattr(scratch, '_sha_file', counted_sha)

    second_out = tmp_path / 'windows-job-2'
    second_out.mkdir()
    second_plan = dict(plan, job_key='b' * 64, output=str(second_out))
    scratch.execute(second_plan)
    assert source_reads == []

    (model_dir / 'part-0.bin').write_bytes(b'mutated-source-model-bytes-longer')
    third_out = tmp_path / 'windows-job-3'
    third_out.mkdir()
    third_plan = dict(plan, job_key='c' * 64, output=str(third_out))
    with pytest.raises(ValueError, match='Pinned model asset changed'):
        scratch.execute(third_plan)


def test_verify_export_resolves_each_root_once(native_job, monkeypatch):
    root, output, plan, calls, worker = native_job
    scratch.execute(plan)
    request = json.loads(Path(plan['request']).read_text())
    root_counts = {Path(output): 0, Path(request['processing_root']): 0}
    original = Path.resolve
    def counted(path, *args, **kwargs):
        if path in root_counts:
            root_counts[path] += 1
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'resolve', counted)
    scratch.verify_export(output, request['processing_root'], plan)
    assert root_counts[Path(output)] == 1
    assert root_counts[Path(request['processing_root'])] == 1
