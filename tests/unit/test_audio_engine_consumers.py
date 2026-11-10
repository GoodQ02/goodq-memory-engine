from copy import deepcopy

import pytest

from tests.unit.test_audio_engine_enrichment import inputs
from wsl2_audio.enrichment import attach_observations
from wsl2_audio.scene_projection import project_audio, validate_scene_audio, legacy_audio, assign_owners


def recording():
    evidence, observations = inputs()
    result = attach_observations(evidence, observations)
    result.update(status='ok', quality_qualification='unqualified')
    return result


def test_scene_cut_keeps_whole_utterance_and_one_owner_without_promoting_confidence():
    evidence = recording()
    before = deepcopy(evidence)
    scenes = [{'scene_id':'a','start':0.,'end':.5}, {'scene_id':'b','start':.5,'end':2.}]
    result = project_audio(evidence, scenes)
    a, b = result['a']['utterances'][0], result['b']['utterances'][0]
    assert a['id']==b['id'] and a['span']==b['span']==evidence['utterances'][0]['span']
    assert a['owner_scene_id']==b['owner_scene_id']=='b'
    assert a['display_span']['end']==.5 and b['display_span']['start']==.5
    assert a['words']==b['words']==evidence['utterances'][0]['words']
    assert a['confidence']['status']=='uncalibrated_model_score'
    assert 'probability_correct' not in a['confidence']
    assert evidence==before


def test_owner_tie_and_gap_are_explicit_without_new_phantom_scene():
    evidence=recording();u=evidence['utterances'][0]
    midpoint=(u['span']['start']+u['span']['end'])/32000
    scenes=[{'scene_id':'z','start':0.,'end':midpoint}, {'scene_id':'a','start':midpoint,'end':2.}]
    assert assign_owners(evidence,scenes)[u['id']]=='z'
    assert assign_owners(evidence,[{'scene_id':'gap','start':1.9,'end':2.}])[u['id']] is None
    assert set(project_audio(evidence,[{'scene_id':'gap','start':1.9,'end':2.}]))=={'gap'}


def test_media_origin_applied_once_and_display_clip_does_not_change_sample_evidence():
    evidence=recording();evidence['source'].update(origin_num=-1,origin_den=2)
    u=evidence['utterances'][0]
    result=project_audio(evidence,[{'scene_id':'scene','start':0.,'end':1.}])['scene']
    row=result['utterances'][0]
    assert row['span']==u['span']
    assert row['media_span']=={'start':u['span']['start']/16000-.5,'end':u['span']['end']/16000-.5}
    assert row['display_span']['start']==0.
    legacy=legacy_audio(result)
    assert legacy['segments'][0]['start']==0.
    assert legacy['audio_evidence']['utterances'][0]['span']==u['span']


def test_mixed_words_survive_for_review_without_individual_emotion_or_signature():
    evidence,observations=inputs()
    observations['overlap']['intervals']=[{'span':{'start':3000,'end':10000},'channel':0,'status':'observed'}]
    evidence=attach_observations(evidence,observations)
    evidence.update(status='ok', quality_qualification='unqualified')
    result=project_audio(evidence,[{'scene_id':'s','start':0.,'end':2.}])['s']
    assert result['utterances'][0]['text']=='Yay Joe'
    legacy=legacy_audio(result)
    assert legacy['transcript']=='Yay Joe'
    assert legacy['emotion'] is None and legacy['audio_emotion'] is None
    assert not legacy['speaker_voice_signatures']
    assert result['utterances'][0]['eligibility']['voice_sample']['status']=='ineligible'


def test_uncertain_words_are_hypotheses_not_summary_fact_text():
    evidence=recording();u=evidence['utterances'][0]
    from wsl2_audio.eligibility import assess_eligibility,POLICY
    u['resolution']='conflicting_hypotheses'
    u['eligibility']=assess_eligibility(u,evidence,POLICY)
    result=project_audio(evidence,[{'scene_id':'s','start':0.,'end':2.}])['s']
    legacy=legacy_audio(result)
    assert legacy['transcript']==''
    assert legacy['audio_evidence']['utterances'][0]['text']=='Yay Joe'
    # Existing transcript-authority vocabulary: ambiguity is low confidence,
    # never fabricated silence or an unrecognized outcome string.
    assert legacy['transcript_outcome']=='low_confidence'


def test_hint_context_survives_summary_and_public_view_without_identity_or_admission_changes():
    from api.utils.audio_evidence import public_audio_evidence
    from steps.common.context_analyzer_llm import _recording_scene_meta,_build_scene_context_prompts
    evidence=recording()
    context={'vocabulary':['Joe','Kathi'],'basis':'explicit_profile_vocabulary','identity_claim':False}
    evidence['provenance']['transcription_context']=deepcopy(context)
    before=deepcopy(evidence)
    projected=project_audio(evidence,[{'scene_id':'s','start':0.,'end':2.}])['s']
    audio=legacy_audio(projected)
    assert audio['transcript_meta']['transcription_context']==context
    assert _recording_scene_meta(audio)['transcription_context']=={
        'basis':'explicit_profile_vocabulary','vocabulary_supplied':True,'identity_claim':False}
    _,prompt=_build_scene_context_prompts(audio)
    assert 'explicit_profile_vocabulary' in prompt
    assert 'Kathi' not in prompt  # Unheard roster names must not seed scene facts.
    public=public_audio_evidence('video',projected)
    assert public['transcription_context']==context and public['identity_claim'] is False
    assert public['utterances'][0]['eligibility']==evidence['utterances'][0]['eligibility']
    assert evidence==before


@pytest.mark.parametrize('metadata', [
    {'status':'unresolved','reason':'aligned_envelope_collision'},
    {'status':'unresolved','reason':'collapsed_local_speaker_change'},
    {'status':'observed','detector':'nemotron3','precision':'10ms_model_frame'},
    {'status':'observed','detector':'local_segmentation'},
])
def test_public_overlap_preserves_observation_basis_without_changing_admission(metadata):
    from api.utils.audio_evidence import public_audio_evidence
    from wsl2_audio.eligibility import assess_eligibility,POLICY
    evidence=recording()
    evidence['overlap']=[{'span':{'start':5000,'end':12000},'channel':0,**metadata}]
    for u in evidence['utterances']:
        u['eligibility']=assess_eligibility(u,evidence,POLICY)
    projection=project_audio(evidence,[{'scene_id':'s','start':0.,'end':2.}])['s']
    before=deepcopy(projection)
    public=public_audio_evidence('video',projection)
    assert {key:public['overlap'][0].get(key) for key in metadata}==metadata
    assert public['overlap'][0]['span']==evidence['overlap'][0]['span']
    assert public['utterances'][0]['eligibility']['voice_sample']['status']=='ineligible'
    assert public['utterances'][0]['eligibility']['vocal_delivery']['status']=='ineligible'
    assert projection==before


@pytest.mark.parametrize('change',['version','text','source','owner'])
def test_altered_or_unknown_projection_is_rejected(change):
    result=project_audio(recording(),[{'scene_id':'s','start':0.,'end':2.}])['s']
    if change=='version': result['schema']='unknown'
    elif change=='text': result['utterances'][0]['text']='invented'
    elif change=='source': result['source']['sha256']='b'*64
    else: result['utterances'][0]['owner_scene_id']='invented'
    with pytest.raises(ValueError):validate_scene_audio(result)


@pytest.mark.parametrize('scenes',[
    [{'scene_id':'a','start':0,'end':1},{'scene_id':'a','start':1,'end':2}],
    [{'scene_id':'a','start':0,'end':float('nan')}],
    [{'scene_id':'a','start':True,'end':1}],
])
def test_ambiguous_scene_geometry_fails(scenes):
    with pytest.raises(ValueError):project_audio(recording(),scenes)


def decoded(tmp_path, evidence):
    from array import array
    import hashlib
    import sys
    samples = array('d', (.05 for _ in range(evidence['source']['sample_count'])))
    if sys.byteorder != 'little': samples.byteswap()
    path = tmp_path/'source.f64le';path.write_bytes(samples.tobytes())
    evidence['source']['pcm_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'source': deepcopy(evidence['source']), 'pcm': {'path':str(path)}}


def voice_recording():
    result=recording();result['source']['sample_count']=160000
    for row in result['coverage']: row['span']['end']=160000
    for stage in result['stages'].values():
        if stage.get('status')=='ok':
            stage['assessed_spans']=[{'start':0,'end':160000}]
            stage.pop('channel_assessed_spans',None)
    original=deepcopy(result['utterances'][0]);result['utterances']=[]
    for i in range(3):
        u=deepcopy(original)
        u.update(id='u'+str(i),span={'start':i*48000,'end':i*48000+32000},words=[])
        u['boundary_evidence']['regions']=[{'span':deepcopy(u['span']),'channel':0}]
        result['utterances'].append(u)
    return result


def test_review_survives_scratch_cleanup_and_cross_scene_cut(tmp_path):
    from wsl2_audio.scene_consumers import publish_scene_audio, validate_review
    evidence=recording();pcm=decoded(tmp_path,evidence)
    scenes=[{'scene_id':'a','start':0.,'end':.5},{'scene_id':'b','start':.5,'end':2.}]
    result=publish_scene_audio(evidence,scenes,pcm,tmp_path/'processing')
    a=result['a']['voice_reviews'][0];b=result['b']['voice_reviews'][0]
    assert a==b and a['span']==evidence['utterances'][0]['span']
    from pathlib import Path
    Path(pcm['pcm']['path']).unlink()  # Owned disposable fixture, not source media.
    assert validate_review(a,evidence['source'],root=tmp_path/'processing').is_file()
    assert result['a']['voice_signature_status']=='insufficient_qualified_speech'


@pytest.mark.parametrize('mutation',['bytes','source','version','escape'])
def test_review_rejects_stale_altered_or_unbound_media(tmp_path,mutation):
    from wsl2_audio.scene_consumers import publish_scene_audio,validate_review,_digest
    evidence=recording();pcm=decoded(tmp_path,evidence)
    result=publish_scene_audio(evidence,[{'scene_id':'s','start':0.,'end':2.}],pcm,tmp_path/'processing')['s']
    review=deepcopy(result['voice_reviews'][0])
    if mutation=='bytes': (tmp_path/'processing'/review['relative_path']).write_bytes(b'changed')
    elif mutation=='source': review['source_sha256']='b'*64
    elif mutation=='version': review['schema']='future'
    else: review['relative_path']='../source.f64le'
    review['content_sha256']=_digest({k:v for k,v in review.items() if k!='content_sha256'})
    with pytest.raises(ValueError):validate_review(review,evidence['source'],root=tmp_path/'processing')


def test_signature_owner_cache_and_old_timing_contract(tmp_path):
    from wsl2_audio.scene_consumers import publish_scene_audio
    evidence=voice_recording();pcm=decoded(tmp_path,evidence);calls=[]
    def embed(pieces,rate):
        calls.append((list(map(len,pieces)),rate));return [1.]+[0.]*191
    scenes=[{'scene_id':'reference','start':0.,'end':.5},{'scene_id':'owner','start':.5,'end':10.}]
    root=tmp_path/'processing'
    result=publish_scene_audio(evidence,scenes,pcm,root,embed=embed)
    replay=publish_scene_audio(evidence,scenes,pcm,root,embed=embed)
    assert result==replay and len(calls)==1
    assert not result['reference']['voice_signatures']
    signature=legacy_audio(result['owner'])['speaker_voice_signatures'][0]
    assert signature['selected_segments']==[]
    assert signature['owner_scene_id']=='owner' and signature['segment_count']==3
    assert len(signature['review_evidence'])==3 and signature['identity_claim'] is False
    from lib.identity_matching import voice_clip
    review=voice_clip({'scene_id':'owner','start':.5,'end':10.,'audio':legacy_audio(result['owner'])},signature,root)
    assert review['timestamp']==0. and review['start']==0. and review['end']==2.


@pytest.mark.parametrize('artifact', ['.wav', '.json'])
def test_interrupted_scene_artifact_publication_can_retry_without_partial_final_file(tmp_path, monkeypatch, artifact):
    from pathlib import Path
    from wsl2_audio.scene_consumers import publish_scene_audio, validate_review
    evidence = voice_recording()
    pcm = decoded(tmp_path, evidence)
    root = tmp_path / 'processing'
    scenes = [{'scene_id':'s','start':0.,'end':10.}]
    original_open = Path.open

    class InterruptedWrite:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): self.stream.__enter__(); return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def write(self, contents):
            self.stream.write(contents[:64])
            self.stream.flush()
            raise OSError('interrupted artifact write')

    def interrupted_open(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        return InterruptedWrite(stream) if artifact in path.name and args and args[0] == 'xb' else stream

    embed = lambda *args: [1.] + [0.] * 191
    with monkeypatch.context() as scoped:
        scoped.setattr(Path, 'open', interrupted_open)
        if artifact == '.wav':
            with pytest.raises(OSError, match='interrupted artifact write'):
                publish_scene_audio(evidence, scenes, pcm, root, embed=embed)
        else:
            failed = publish_scene_audio(evidence, scenes, pcm, root, embed=embed)['s']
            assert failed['voice_signature_status'] == 'error'
    assert not [p for p in root.rglob('*' + artifact) if p.name != 'scenes.json']
    result = publish_scene_audio(evidence, scenes, pcm, root, embed=embed)['s']
    assert result['voice_signature_status'] == 'ok'
    for review in result['voice_reviews']:
        validate_review(review, evidence['source'], root=root)
    assert publish_scene_audio(evidence, scenes, pcm, root, embed=embed)['s'] == result


def test_scene_artifact_publication_never_replaces_a_conflicting_final_file(tmp_path):
    from wsl2_audio.scene_consumers import publish_scene_audio
    evidence = recording()
    pcm = decoded(tmp_path, evidence)
    scenes = [{'scene_id':'s','start':0.,'end':2.}]
    root = tmp_path / 'processing'
    first = publish_scene_audio(evidence, scenes, pcm, root)['s']
    path = root / first['voice_reviews'][0]['relative_path']
    path.write_bytes(b'existing changed artifact')
    with pytest.raises(ValueError, match='Retained audio artifact changed'):
        publish_scene_audio(evidence, scenes, pcm, root)
    assert path.read_bytes() == b'existing changed artifact'


def test_encoder_failure_is_visible_and_does_not_erase_review_or_words(tmp_path):
    from wsl2_audio.scene_consumers import publish_scene_audio
    evidence=voice_recording();pcm=decoded(tmp_path,evidence)
    def failed(*args):raise OSError('missing cached model')
    result=publish_scene_audio(evidence,[{'scene_id':'s','start':0.,'end':10.}],pcm,tmp_path/'processing',embed=failed)['s']
    assert result['voice_signature_status']=='error' and not result['voice_signatures']
    assert len(result['voice_reviews'])==3 and legacy_audio(result)['transcript']


def test_legacy_merge_uses_shared_decision_instead_of_scene_cut_reassessment():
    from steps.audio_speaker_merge.step import audio_speaker_merge
    projection=project_audio(recording(),[{'scene_id':'s','start':.5,'end':1.}])['s']
    result=audio_speaker_merge({'audio_evidence':projection,'transcript':'stale hallucination'}, {})
    assert result['transcript']=='Yay Joe'
    assert result['audio_evidence']==projection
    assert result['audio_evidence']['utterances'][0]['eligibility']['vocal_delivery']['status']=='eligible'


@pytest.mark.parametrize('clear',[False,True])
def test_actual_summary_caller_keeps_supported_words_visuals_and_uncertainty(clear):
    from steps.video import cross_modal_harmonizer as harmonizer
    from tests.unit.test_audio_summary_evidence import Client
    from wsl2_audio.eligibility import assess_eligibility,POLICY
    evidence=recording();u=evidence['utterances'][0]
    if not clear:
        u['resolution']='conflicting_hypotheses';u['eligibility']=assess_eligibility(u,evidence,POLICY)
    projection=project_audio(evidence,[{'scene_id':'s','start':0.,'end':2.}])['s']
    segment={'scene_id':'s','start':0.,'end':2.,'content_state':'signal','full_transcript':'stale vacation hallucination',
        'audio_evidence':projection, 'emotion_segments':[], 'visual_caption':'A person opens a wooden door.'}
    lookup={'s':{'index':0,'audio':{},'caption':'A person opens a wooden door.'}}
    client=Client(summary='A person opens a wooden door.')
    result=harmonizer._apply_scene_context_llm([segment],lookup,
        {'llm':{'features':{'scene_context_analysis':True}}},llm_client=client)
    assert result['evaluated_count']==1
    prompt=client.calls[0]['messages'][1]['content']
    assert 'stale vacation hallucination' not in prompt
    assert ('Yay Joe' in prompt) is clear
    summary=segment['scene_context_llm']
    assert ('Yay Joe' if clear else 'wooden door') in summary['narrative_summary']
    assert summary['emotional_arc']=='unqualified'
    assert summary['transcription_evidence']['text_status']==('available_model_estimate' if clear else 'withheld_recognition_uncertainty')
    assert projection['utterances'][0]['text']=='Yay Joe'


def test_identity_review_and_graph_replay_count_contribution_once(tmp_path):
    import json,sqlite3
    from lib.identity_matching import voice_clip
    from lib.kg_realtime_integration import update_kg_for_scene
    from wsl2_audio.scene_consumers import publish_scene_audio
    evidence=voice_recording();pcm=decoded(tmp_path,evidence);root=tmp_path/'processing'
    projection=publish_scene_audio(evidence,[{'scene_id':'s','start':0.,'end':10.}],pcm,root,
        embed=lambda *_:[1.]+[0.]*191)['s']
    audio=legacy_audio(projection);signature=audio['speaker_voice_signatures'][0]
    media=voice_clip({'scene_id':'s','start':0.,'end':10.,'audio':audio},signature,root)
    assert media['start']==0. and media['end']==2. and media['contribution_id']==signature['contribution_id']
    db=tmp_path/'graph.db';cfg={'paths':{'knowledge_graph_db':str(db)}}
    data={**audio,'speaker_ids':[signature['speaker']]}
    for _ in range(2): update_kg_for_scene(data,'s','video','sample.mp4',cfg)
    with sqlite3.connect(db) as conn:
        rows=conn.execute("SELECT properties,occurrence_count FROM nodes WHERE node_type='speaker_pattern'").fetchall()
        assert conn.execute("SELECT count(*) FROM nodes WHERE lower(node_type)='person'").fetchone()[0]==0
        assert conn.execute("SELECT count(*) FROM edges WHERE edge_type='identity_evidence'").fetchone()[0]==0
    assert len(rows)==1
    props=json.loads(rows[0][0])
    assert props['signature_count']==props['scene_count']==rows[0][1]==1
    assert len(props['voice_contributions'])==1
    assert props['total_voiced_seconds']==6.


def test_identical_fresh_run_reuses_voice_contribution_without_embedding_or_counting_again(tmp_path):
    from wsl2_audio.scene_consumers import publish_scene_audio
    evidence=voice_recording();pcm=decoded(tmp_path,evidence);calls=[]
    def embed(*_):calls.append(1);return [1.]+[0.]*191
    scenes=[{'scene_id':'s','start':0.,'end':10.}];root=tmp_path/'processing'
    before=publish_scene_audio(evidence,scenes,pcm,root,embed=embed)['s']
    evidence['provenance']['run_id']='a-new-run'
    after=publish_scene_audio(evidence,scenes,pcm,root,embed=embed)['s']
    assert before['provenance']!=after['provenance']
    assert before['voice_signatures']==after['voice_signatures'] and len(calls)==1
    assert before['recording_id']==after['recording_id']


def test_stale_text_analysis_cannot_bypass_versioned_summary_authority():
    from steps.common.context_analyzer_llm import _build_scene_context_prompts
    projection=project_audio(recording(),[{'scene_id':'s','start':0.,'end':2.}])['s']
    scene={'audio_evidence':projection,'sentiment':{'label':'STALE_SENTIMENT'},
        'sentiment_meta':{'text':'STALE_META'},'text_emotion_ranking':[{'label':'STALE_EMOTION','score':.99}],
        'music_events':[{'description':'STALE_LYRIC_CUE'}],'time_hints':{'year':['STALE_DATE']}}
    prompt=_build_scene_context_prompts(scene)[1]
    assert 'STALE_' not in prompt
    assert 'Yay Joe' in prompt


def test_scene_and_timeline_api_keep_review_evidence_and_bound_media(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.routes import scenes,timeline
    from wsl2_audio.scene_consumers import publish_scene_audio
    evidence=recording();pcm=decoded(tmp_path,evidence);root=tmp_path/'processing'
    projection=publish_scene_audio(evidence,[{'scene_id':'s','start':0.,'end':2.}],pcm,root)['s']
    segment={'scene_id':'s','start':0.,'end':2.,'audio_evidence':projection}
    class Loader:
        active=True
        def load_temporal_index(self,_):return {'segments':[segment]}
        def is_search_result_active(self,_):return self.active
    loader=Loader();monkeypatch.setattr(scenes,'get_data_loader',lambda:loader)
    monkeypatch.setattr(scenes,'_config',{'paths':{'db_path':str(tmp_path/'memory.db')}})
    view=scenes._build_scene_response('video',segment).model_dump()['audio_evidence']
    assert view==timeline._build_timeline_segment('video',segment).model_dump()['audio_evidence']
    assert 'voice_signatures' not in view and 'relative_path' not in str(view)
    app=FastAPI();app.include_router(scenes.router);client=TestClient(app)
    url=view['reviews'][0]['url'];response=client.get(url)
    assert response.status_code==200 and response.content[:4]==b'RIFF'
    loader.active=False
    assert client.get(url).status_code==404
    loader.active=True
    (root/projection['voice_reviews'][0]['relative_path']).write_bytes(b'altered')
    assert client.get(url).status_code==409
