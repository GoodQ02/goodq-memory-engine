"""Recording evidence must cross the actual callers without old ASR or lost consumers."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import types

import pytest

from tests.unit.test_audio_engine_consumers import recording
from steps.audio import recording_ingestion as shared
from wsl2_audio.scene_projection import project_audio, legacy_audio
from wsl2_audio.recording_audio import _sha_file


@pytest.fixture
def job(tmp_path):
    evidence = recording()
    scenes = [{'scene_id': 'scene', 'start': 0., 'end': 2.}]
    projection = project_audio(evidence, scenes)['scene']
    path = tmp_path / 'scene_audio.json'
    path.write_text(json.dumps({'scene': legacy_audio(projection)}))
    handle = {'path': str(path), 'sha256': _sha_file(path),
        'source_sha256': evidence['source']['sha256'],
        **{key: evidence['provenance'][key] for key in ('run_id', 'epoch_id')}}
    return handle, projection


@pytest.mark.parametrize('asynchronous', [False, True])
@pytest.mark.parametrize('scene_wav', [True, False])
def test_video_scene_consumes_shared_job_and_preserves_enrichment(monkeypatch, tmp_path, job, asynchronous, scene_wav):
    from cli import run_ingestion as runner
    from steps.common import progress_tracker
    handle, projection = job
    wav = tmp_path / 'scene.wav'; wav.write_bytes(b'fixture sound')
    cfg = tmp_path / 'cfg.json'; cfg.write_text('{}')
    calls = []
    monkeypatch.setattr(runner, '_extract_audio_chunk', lambda *a, **kw: wav if scene_wav else None)
    monkeypatch.setattr(runner, '_log_audio_to_ucf_ledger', lambda *a, **kw: calls.append('ledger'))
    monkeypatch.setattr(runner, 'log_step_run', lambda *a, **kw: None)
    monkeypatch.setattr(runner, '_record_run_warning', lambda *a, **kw: None)
    monkeypatch.setattr(progress_tracker, 'get_tracker', lambda: types.SimpleNamespace(update_step=lambda *a, **kw: None))
    def dispatch(env, name, item, *args, **kwargs):
        calls.append(name)
        assert name not in shared.RECOGNITION_STEPS, 'Per-scene recognition re-entered'
        if name != 'audio_metadata':
            assert item.get('audio_evidence') == projection or name == 'text_embed'
        return {}
    monkeypatch.setattr(runner, '_run_step', dispatch)
    async def dispatch_async(*a, **kw):
        return {'status': 'ok', 'outputs': dispatch(*a, **kw)}
    monkeypatch.setattr(runner, '_run_step_async', dispatch_async)
    args = (cfg, 'ffmpeg', wav, {'index': 0, 'start': 0., 'end': 2.}, tmp_path, tmp_path/'artifacts', 'video', 'scene')
    kwargs = {'recording_audio': handle, 'audio_runtime_contract': {'selected': 'recording', 'reason': 'test'}}
    if asynchronous:
        async def run():
            return await runner._process_audio_async(*args, asyncio.Lock(), asyncio.Lock(), **kwargs)
        value = asyncio.run(run())
    else:
        value = runner._process_audio(*args, **kwargs)
    assert value['data']['audio_evidence'] == projection
    assert value['data']['audio_backend_effective'] == 'recording'
    assert {'audio_music_events','audio_time_hints','sentiment','emotion_classify','text_embed','ledger'} <= set(calls)
    if scene_wav:
        assert {'audio_metadata','audio_embed_clap'} <= set(calls)
    else:
        assert not {'audio_metadata','audio_embed_clap'} & set(calls)
        assert value['data']['clap_meta']['reason']=='scene_audio_extraction_failed'
        assert value['path'] is None
    attribution = runner._resolve_audio_backend_attribution(value, skip_audio=False, audio_error=None,
        audio_runtime_contract=kwargs['audio_runtime_contract'], run_context={}, scene_id='scene', scene_index=0)
    assert attribution['audio_backend_selected'] == attribution['audio_backend_effective'] == 'recording'
    assert not attribution['audio_backend_downgraded']


@pytest.mark.parametrize('name', sorted(shared.RECOGNITION_STEPS))
def test_direct_dispatch_consumes_job_without_recognizer(name, job):
    from cli.step_runner import run_step
    handle, projection = job
    value = run_step(name, {'scene_id':'scene','recording_audio':handle}, {})
    assert value['audio_evidence'] == projection


def test_selected_direct_step_does_not_recognize_a_scene_crop():
    from cli.step_runner import run_step
    with pytest.raises(ValueError, match='scene crops'):
        run_step('audio_transcribe_local', {'source_path':'scene.wav'}, {'audio':{'recording_engine':{'enabled':True}}})


@pytest.mark.parametrize('surface', ['transcribe','diarize','emotion','unified','legacy','legacy_combined'])
def test_bridge_aliases_share_the_same_evidence(surface, job, monkeypatch):
    from steps.audio import audio_wsl2_bridge as bridge
    from wsl2_audio import audio_bridge as legacy
    handle, projection = job
    monkeypatch.setattr(bridge, 'WSL2AudioBridge', lambda: pytest.fail('old worker initialized'))
    monkeypatch.setattr(legacy, 'get_bridge', lambda: pytest.fail('old worker initialized'))
    methods={'transcribe':bridge.audio_transcribe_wsl2,'diarize':bridge.audio_diarize_wsl2,
        'emotion':bridge.audio_emotion_wsl2,'unified':bridge.audio_unified_wsl2,
        'legacy':legacy.transcribe_wsl2,'legacy_combined':legacy.transcribe_and_diarize_wsl2}
    assert methods[surface]('unused.wav', recording_audio=handle, scene_id='scene')['audio_evidence']==projection


@pytest.mark.parametrize('mode', ['shadow', 'authoritative'])
def test_selected_chunk_modes_rejected_before_runtime_probe(mode, monkeypatch):
    from cli.run_ingestion import _resolve_audio_runtime_contract
    cfg={'audio':{'recording_engine':{'enabled':True,'profile':'profile','python':'python','source_revision':'revision'}},
         'segmentation':{'activation':mode}}
    with pytest.raises(ValueError, match='chunk audio modes are unsupported'):
        _resolve_audio_runtime_contract(cfg)
    cfg['segmentation']['activation']='off'
    monkeypatch.setenv('GOODQ_SEGMENTATION_MODE',mode)
    with pytest.raises(ValueError, match='chunk audio modes are unsupported'):
        _resolve_audio_runtime_contract(cfg)


def test_phase4_cannot_bypass_recording_selection():
    from steps.audio.segmentation.phase4_audio_processor import Phase4AudioProcessor
    with pytest.raises(ValueError, match='chunk recognition'):
        Phase4AudioProcessor({'audio':{'recording_engine':{'enabled':True}}})


@pytest.mark.parametrize('terms',[None,['Kathi']])
def test_recording_cannot_silently_ignore_configured_vocabulary(tmp_path,monkeypatch,terms):
    source=tmp_path/'source.wav';source.write_bytes(b'original')
    profile=tmp_path/'profile.json';profile.write_text(json.dumps({'vocabulary':terms}))
    cfg={'audio':{'transcribe':{'vocabulary':['Joe']},'recording_engine':{
        'enabled':True,'profile':str(profile),'python':'python','source_revision':'revision'}},
        'run':{'id':'run'},'paths':{'db_dir':str(tmp_path/'epoch')}}
    monkeypatch.setattr(shared,'_complete_job',lambda *args:pytest.fail('mismatched context reached a job'))
    with pytest.raises(ValueError,match='profile must declare'):
        shared.prepare(cfg,source,[{'scene_id':'s','start':0.,'end':2.}])
    assert not (tmp_path/'epoch').exists()


@pytest.mark.parametrize('configured',[None,[' Joe ','joe']])
def test_recording_profile_owns_explicit_vocabulary_when_configuration_agrees(tmp_path,monkeypatch,configured):
    source=tmp_path/'source.wav';source.write_bytes(b'original')
    profile=tmp_path/'profile.json';profile.write_text(json.dumps({'vocabulary':['Joe']}))
    cfg={'audio':{'transcribe':{'vocabulary':configured},'recording_engine':{
        'enabled':True,'profile':str(profile),'python':'python','source_revision':'revision'}},
        'run':{'id':'run'},'paths':{'db_dir':str(tmp_path/'epoch')}}
    calls=[]
    def complete(job,identity,request,source,pinned,*args):
        calls.append(identity);assert pinned==profile
        return 'verified-context-job'
    monkeypatch.setattr(shared,'_complete_job',complete)
    assert shared.prepare(cfg,source,[{'scene_id':'s','start':0.,'end':2.}])=='verified-context-job'
    assert calls[0]['profile_sha256']==_sha_file(profile)


def test_shared_job_replay_calls_worker_once_and_rejects_changed_result(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from scripts import wsl2_audio_bridge as transport
    source=tmp_path/'source.wav'; source.write_bytes(b'original')
    profile=tmp_path/'profile.json'; profile.write_text('{}')
    cfg={'audio':{'recording_engine':{'enabled':True,'profile':str(profile),'python':'python','source_revision':'revision'}},
        'run':{'id':'run','epoch_id':'epoch'},'paths':{'db_dir':str(tmp_path/'epoch')}}
    calls=[]
    def worker(req, prof, root, options):
        request=json.loads(req.read_text());calls.append(request)
        evidence=recording();evidence['source']['sha256']=_sha_file(source)
        evidence['provenance'].update(run_id='run',epoch_id='epoch')
        out={k:legacy_audio(p) for k,p in project_audio(evidence,request['scenes']).items()}
        (root/'scene_audio.json').write_text(json.dumps(out))
    monkeypatch.setattr(transport,'run_recording_request',worker)
    scenes=[{'scene_id':'s','start':0.,'end':2.}]
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=[pool.submit(shared.prepare,cfg,source,scenes) for _ in range(2)]
        handle=pending[0].result()
        assert pending[1].result()==handle
    assert shared.prepare(cfg,source,scenes)==handle and len(calls)==1
    assert calls[0]['source_path']==str(source.resolve())
    Path(handle['path']).write_text('{}')
    with pytest.raises(ValueError,match='artifact changed'):shared.prepare(cfg,source,scenes)
    assert len(calls)==1


def test_resume_rejects_old_audio_and_changed_policy_but_allows_new_execution(job):
    from wsl2_audio.scene_projection import seal_scene_audio
    handle,projection=job
    with pytest.raises(ValueError,match='another engine'):
        shared.require_matching_resume({'transcript':'old'},handle,'scene')
    changed=deepcopy(projection);changed['provenance']['run_id']='older-run'
    changed=seal_scene_audio(changed)
    shared.require_matching_resume({'data':legacy_audio(changed)},handle,'scene')
    changed['recording_id']='different-model-policy';changed=seal_scene_audio(changed)
    with pytest.raises(ValueError,match='differs'):
        shared.require_matching_resume({'audio_evidence':changed},handle,'scene')


def test_scene_and_source_binding_cannot_be_reused_for_wrong_owner(job):
    handle,_=job
    with pytest.raises(ValueError,match='bounds'):shared.scene_result(handle,'scene',{'start':1,'end':2})
    handle['source_sha256']='0'*64
    with pytest.raises(ValueError,match='binding'):shared.scene_result(handle,'scene')


def test_fresh_text_scores_bind_to_only_admitted_words_and_summary(job):
    from steps.common.context_analyzer_llm import _recording_scene_meta
    _,projection=job
    item={'audio_evidence':projection,'transcript':'stale text','text':'stale text',
          'document_text':'stale document','ocr_text':'stale OCR','caption':'stale caption',
          'transcript_meta':{'segments':[{'text':'stale cue'}]}}
    def scorer(clean,cfg):
        assert clean['text']==clean['transcript']=='Yay Joe'
        assert not any(clean[k] for k in ('document_text','ocr_text','caption'))
        assert clean['transcript_meta']['segments'][0]['text']=='Yay Joe'
        return {'sentiment':{'label':'positive','score':.8},'sentiment_meta':{'status':'ok'}}
    result=shared.analyze_text('sentiment',scorer,item,{})
    consumed=_recording_scene_meta({**item,**result})
    assert consumed['sentiment']==result['sentiment']
    bad=deepcopy(result);bad['sentiment_meta']['input_binding']['text_sha256']='0'*64
    assert _recording_scene_meta({**item,**bad})['sentiment'] is None


def test_invalid_or_missing_candidate_configuration_never_autoselects():
    assert not shared.selected({})
    with pytest.raises(ValueError,match='profile'):shared.settings({'audio':{'recording_engine':{'enabled':True}}})


def test_voice_selection_diagnostics_preserve_existing_rules():
    from wsl2_audio.enrichment import select_voice_groups
    evidence=recording();u=evidence['utterances'][0]
    diagnostics={}
    assert select_voice_groups(evidence,{u['id']:'scene'},diagnostics=diagnostics)==[]
    assert diagnostics['minimum_segment_seconds']==.75 and diagnostics['minimum_voiced_seconds']==4.
    assert diagnostics['minimum_segments']==2
    assert diagnostics['groups'][0]['reasons']==['below_segment_count','below_total_voiced_duration']


def test_ucf_records_scene_relative_times_once_and_preserves_raw_evidence(monkeypatch,tmp_path):
    import sqlite3
    from contextlib import closing
    from cli.run_ingestion import _log_audio_to_ucf_ledger
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    evidence=recording();evidence['source'].update(origin_num=1,origin_den=1)
    scene={'scene_id':'scene','start':.5,'end':3.}
    projection=project_audio(evidence,[scene])['scene'];audio=legacy_audio(projection)
    root=tmp_path/'epoch';(root/'ucf').mkdir(parents=True)
    ledger=UCFLedgerClient(str(root/'ucf/ucf_ledger.db'));ledger.init_schema()
    ledger.register_media(evidence['source']['sha256'],'source.wav',3.,0.,0,0);ledger.close()
    cfg=tmp_path/'config.json';cfg.write_text(json.dumps({'paths':{'db_dir':str(root)},'run':{'id':'test'}}))
    artifacts=tmp_path/'artifacts';artifacts.mkdir()
    for name,rows in [('transcript',audio['segments']),('diarization',audio['speaker_segments'])]:
        (artifacts/f'scene_raw_{name}.json').write_text(json.dumps(rows))
    _log_audio_to_ucf_ledger(cfg,evidence['source']['sha256'],'scene',scene,artifacts,audio,strict=True)
    with closing(sqlite3.connect(root/'ucf/ucf_ledger.db')) as db:
        db.row_factory=sqlite3.Row;rows=[dict(r) for r in db.execute('SELECT * FROM context_frames')]
    envelope,=[r for r in rows if r['worker_name']=='recording_audio']
    assert json.loads(Path(envelope['raw_ref']).read_text())==projection
    transcript,=[r for r in rows if r['worker_name']=='audio_transcribe']
    # Existing UCF columns round display seconds to ms; source samples stay exact.
    assert transcript['t_start']==round(projection['utterances'][0]['display_span']['start'],3)
    assert transcript['t_end']==round(projection['utterances'][0]['display_span']['end'],3)
    assert json.loads(transcript['payload'])['source_sample_start']==projection['utterances'][0]['span']['start']
    assert transcript['confidence']==0 and json.loads(transcript['payload'])['confidence'] is None
    assert json.loads(transcript['payload'])['confidence_basis']=='uncalibrated_model_score'
    assert all(row['promotion_status']=='staged' for row in rows)


def test_transport_pins_cached_encoder_and_uses_argv(tmp_path,monkeypatch):
    from scripts import wsl2_audio_bridge as bridge
    calls=[]
    monkeypatch.setattr(bridge.subprocess,'run',lambda *a,**kw: calls.append((a,kw)) or types.SimpleNamespace(returncode=0))
    opts={'transport':'wsl','python':'/candidate/python','distro':'Ubuntu test','user':'test user',
          'timeout_seconds':90,'ecapa_model_dir':str(tmp_path/'model dir')}
    bridge.run_recording_request(tmp_path/'request file.json',tmp_path/'profile.json',tmp_path,opts)
    argv=calls[0][0][0]
    assert 'Ubuntu test' in argv and 'test user' in argv and '--exec' in argv
    assert any(arg.startswith('GOODQ_ECAPA_MODEL_DIR=') for arg in argv)
    assert calls[0][1].get('shell') is not True


def test_standalone_candidate_keeps_actual_dispatch_and_staged_persistence(standalone_audio_dispatch,monkeypatch,tmp_path):
    from scripts import wsl2_audio_bridge as transport
    from tests.unit.test_standalone_lifecycle_producer import ledger_rows
    processor,source,observed,cfg,_=standalone_audio_dispatch
    profile=tmp_path/'profile.json';profile.write_text('{}')
    candidate={'enabled':True,'profile':str(profile),'python':'fixture','source_revision':'test'}
    processor._cfg_base['audio']['recording_engine']=candidate
    calls=[]
    def worker(req,prof,root,options):
        request=json.loads(req.read_text());calls.append(request)
        evidence=recording();evidence['source']['sha256']=_sha_file(source)
        evidence['provenance'].update(run_id=request['run_id'],epoch_id=request['epoch_id'])
        outputs={k:legacy_audio(v) for k,v in project_audio(evidence,request['scenes']).items()}
        (root/'scene_audio.json').write_text(json.dumps(outputs))
    monkeypatch.setattr(transport,'run_recording_request',worker)
    assert processor.ingest_audio(source,'candidate-run')
    assert len(calls)==1 and not observed['local_calls']
    assert not (shared.RECOGNITION_STEPS & set(observed['steps']))
    root=Path(cfg['paths']['processing'])/_sha_file(source)
    temporal=json.loads((root/'temporal_index.json').read_text())['segments'][0]
    assert temporal['audio_evidence']['source']['sha256']==_sha_file(source)
    rows=ledger_rows(cfg)
    assert any(row['worker_name']=='recording_audio' for row in rows)
    assert all(row['promotion_status']=='staged' for row in rows)


from tests.unit.test_watchdog_safety import standalone_audio_dispatch


def test_top_level_video_runner_prepares_once_before_scene_fanout(tmp_path,monkeypatch):
    from tests.unit.test_progressive_ingestion_caller import _runner_fixture
    from cli import run_ingestion as runner
    from scripts import wsl2_audio_bridge as transport
    run,scenes,_,checkpoint=_runner_fixture(tmp_path,monkeypatch)
    profile=tmp_path/'profile.json';profile.write_text('{}')
    actual_contract=runner._resolve_audio_runtime_contract
    def choose(cfg):
        cfg['audio']={'recording_engine':{'enabled':True,'profile':str(profile),'python':'fixture','source_revision':'test'}}
        return actual_contract(cfg)
    monkeypatch.setattr(runner,'_resolve_audio_runtime_contract',choose)
    jobs=[];consumed=[]
    def worker(req,prof,root,options):
        request=json.loads(req.read_text());jobs.append(request)
        evidence=recording();evidence['source']['sha256']=_sha_file(Path(request['source_path']))
        evidence['provenance'].update(run_id=request['run_id'],epoch_id=request['epoch_id'])
        (root/'scene_audio.json').write_text(json.dumps({k:legacy_audio(v)
            for k,v in project_audio(evidence,request['scenes']).items()}))
    monkeypatch.setattr(transport,'run_recording_request',worker)
    async def audio(_cfg,_ffmpeg,_video,scene,_dir,_artifacts,_hash,scene_id,*args,**kwargs):
        handle=kwargs['recording_audio'];consumed.append(handle)
        return {'path':str(tmp_path/'audio.wav'),'data':shared.scene_result(handle,scene_id,scene)}
    monkeypatch.setattr(runner,'_process_audio_async',audio)
    result=run()
    assert len(jobs)==1 and len(consumed)==2 and consumed[0]==consumed[1]
    assert [(s['start'],s['end']) for s in jobs[0]['scenes']]==[(s['start'],s['end']) for s in scenes]
    assert all(s['audio']['audio_evidence']['scene']['scene_id']==s['scene_id'] for s in result['scenes'])
    assert result['audio_runtime_contract']['selected']=='recording'
    assert result['audio_backend_selected']==result['audio_backend_effective']=='recording'


def test_recording_runtime_failure_keeps_video_and_never_falls_back(tmp_path,monkeypatch):
    from tests.unit.test_progressive_ingestion_caller import _runner_fixture
    from cli import run_ingestion as runner
    run,scenes,frames,checkpoint=_runner_fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(runner,'_resolve_audio_runtime_contract',lambda cfg: {'selected':'recording','reason':'test'})
    monkeypatch.setattr(shared,'prepare',lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('worker unavailable')))
    async def forbidden(*a,**kw):pytest.fail('Failed recording entered another audio path')
    monkeypatch.setattr(runner,'_process_audio_async',forbidden)
    import typer
    with pytest.raises(typer.Exit) as stopped:
        run()
    assert stopped.value.exit_code==1  # Failed audio remains an observable failed run.
    result=json.loads((tmp_path/'results.json').read_text())[0]
    assert len(frames)==len(scenes)==2
    assert all(s['transcript_outcome']=='runtime_failure' for s in result['scenes'])
    receipt=json.loads((checkpoint.parent/'recording_audio_failure.json').read_text())
    assert receipt['legacy_fallback'] is False and 'worker unavailable' in receipt['error']


@pytest.mark.parametrize('corruption',['missing','changed'])
def test_job_cache_cannot_claim_lost_review_media_is_retained(tmp_path,corruption):
    from tests.unit.test_audio_engine_consumers import decoded
    from wsl2_audio.scene_consumers import publish_scene_audio
    evidence=recording();pcm=decoded(tmp_path,evidence)
    processing=tmp_path/'processing'
    projection=publish_scene_audio(evidence,[{'scene_id':'s','start':0.,'end':2.}],pcm,processing)['s']
    output=tmp_path/'scene_audio.json';output.write_text(json.dumps({'s':legacy_audio(projection)}))
    handle={'path':str(output),'processing_root':str(processing),'sha256':_sha_file(output),
        'source_sha256':evidence['source']['sha256'],
        **{k:evidence['provenance'][k] for k in ('run_id','epoch_id')}}
    shared.load(handle)
    wav=processing/projection['voice_reviews'][0]['relative_path']
    if corruption=='missing':wav.unlink()  # Owned test fixture only.
    else:wav.write_bytes(b'altered')
    with pytest.raises((ValueError,OSError)):
        shared.load(handle)
