"""Production callers must preserve source coverage and never manufacture timing."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import numpy as np
import pytest


class Decoder:
    def __init__(self, fail_at=None, no_text=False):
        self.calls=[]; self.fail_at=fail_at; self.no_text=no_text
    def detect_language(self, **kwargs): return 'en', .8, []
    def transcribe(self, audio, **kwargs):
        self.calls.append(kwargs)
        assert kwargs['vad_filter'] is False and kwargs['condition_on_previous_text'] is False
        assert kwargs['temperature']==0.
        if len(self.calls)==self.fail_at: raise RuntimeError('region decoder failed')
        info=NS(language='en', transcription_options=NS(no_speech_threshold=.6,
            log_prob_threshold=-1., compression_ratio_threshold=2.4))
        words=[NS(word='hello',start=.1,end=.3,probability=.9),
               NS(word='world',start=None,end=float('nan'),probability=.7)]
        segments=[] if self.no_text else [NS(start=0.,end=.5,text='hello world',words=words,avg_logprob=-.2)]
        return iter(segments),info


@pytest.fixture
def source(monkeypatch,tmp_path):
    from wsl2_audio import transcription_contract as contract
    path=tmp_path/'source.wav'; path.write_bytes(b'RIFF')
    monkeypatch.setattr('faster_whisper.audio.decode_audio',lambda *a,**kw:np.zeros(12*16000,dtype=np.float32))
    monkeypatch.setattr(contract,'_source_speech_regions',lambda audio:[
        {'start':2*16000,'end':3*16000},{'start':9*16000,'end':10*16000}])
    monkeypatch.setattr(contract,'_recognition_source_regions',contract._source_speech_regions)
    return path


def test_local_decoder_preserves_regions_and_null_word_times(source):
    from steps.audio_transcribe.step import _transcribe_chunk_fw
    result=_transcribe_chunk_fw(str(source),0.,Decoder(),0.)
    assert result['transcription']=='hello world hello world'
    assert [w['start'] for w in result['word_timestamps']]==[2.1,None,9.1,None]
    assert result['transcription_decoding']['source_regions']['completed_region_count']==2
    json.dumps(result,allow_nan=False)


def local_caller(monkeypatch,source,decoder):
    from steps.audio_transcribe import step
    monkeypatch.setattr(step,'_detect_transcription_device',lambda:('cpu','fixture'))
    monkeypatch.setattr(step,'_audio_duration',lambda _:12.)
    monkeypatch.setattr(step,'require_wsl_audio',lambda:False)
    def no_diarization_slicing(*args): raise AssertionError('diarization must not select ASR audio')
    monkeypatch.setattr(step,'_build_chunks',no_diarization_slicing)
    class Context:
        def __enter__(self):return decoder
        def __exit__(self,*args):return False
    monkeypatch.setattr('lib.model_lifecycle.ModelLifecycleManager.load',lambda *a,**kw:Context())
    monkeypatch.setattr('steps.common.model_provisioner.ensure_model_cached',lambda *a,**kw:NS(status='ready',local_path='fixture'))
    return step.audio_transcribe({'source_path':str(source),'diarization':[{'start':3.,'end':4.,'speaker':'S0'}]},
        {'audio':{'transcribe':{'use_wsl2':False,'model':'medium'}}})


def test_local_caller_covers_speech_outside_diarization(monkeypatch,source):
    result=local_caller(monkeypatch,source,Decoder())
    assert result['transcript']=='hello world hello world'
    assert [s['start'] for s in result['segments']]==[2.,9.]
    assert result['transcript_meta']['transcription_decoding']['source_regions']['completed_region_count']==2


def test_local_partial_failure_preserves_words_and_coverage(monkeypatch,source):
    result=local_caller(monkeypatch,source,Decoder(fail_at=2))
    assert result['transcript']=='hello world'
    assert result['transcript_meta']['status']=='partial'
    assert 'region decoder failed' in result['transcript_meta']['error']
    coverage=result['transcript_meta']['transcription_decoding']['source_regions']
    assert coverage['status']=='error' and coverage['completed_region_count']==1
    assert [r['outcome'] for r in coverage['regions']]==['text_returned','error']


def test_local_empty_decoding_is_not_proof_of_absent_speech(monkeypatch,source):
    result=local_caller(monkeypatch,source,Decoder(no_text=True))
    assert result['transcript_outcome']!='no_speech'
    assert result['transcript_meta']['reason']=='speech_detected_without_words'


def test_compatibility_caller_forwards_policy_and_keeps_evidence(monkeypatch):
    from cli.step_runner import run_step
    from steps.audio import audio_wsl2_bridge as bridge
    calls=[]
    coverage={'policy':'source_audio_v2','status':'completed','regions':[]}
    class Runner:
        def process_audio(self,path,**kwargs):
            calls.append(kwargs)
            return {'status':'success','transcription_status':'success','transcription':'Yay Joe',
                'transcription_decoding':{'policy':'single_temperature_v1','temperature':0.,'source_regions':coverage},
                'word_alignment':{'words':[{'text':'Yay','start':None,'end':None}]}}
    monkeypatch.setattr(bridge,'WSL2AudioBridge',Runner)
    result=run_step('audio_transcribe',{'path':'clip.wav','duration':7},
        {'audio':{'transcribe':{'vocabulary':['Joe'],'temperature':0.}}})
    assert calls[0]['transcription_temperature']==0. and calls[0]['transcription_vocabulary']==['Joe']
    assert result['transcript_meta']['transcription_decoding']['source_regions']==coverage
    assert result['words']==result['word_timestamps']
    assert result['words'][0]['start'] is None


def test_standalone_wsl_helper_uses_shared_policy(monkeypatch,source,tmp_path):
    from wsl2_audio.fw_transcribe import main
    monkeypatch.setattr('faster_whisper.WhisperModel',lambda *a,**kw:Decoder())
    target=tmp_path/'result.json'
    rc=main(['fw_transcribe.py',str(source),str(target),json.dumps({'temperature':0.,'vocabulary':['Joe']})])
    assert rc==0
    result=json.loads(target.read_text())
    assert result['transcription_decoding']['source_regions']['completed_region_count']==2
    assert result['word_timestamps'][1]['start'] is None
    assert result['transcription_context']=={'status':'applied','source':'request_config',
        'kind':'vocabulary_hints','words':['Joe'],'identity_claim':False}


def test_cli_uses_source_regions_without_inventing_word_or_segment_times(monkeypatch,source):
    from steps.audio_transcribe.step import _transcribe_chunk_whisper_cli
    calls=[]
    def execute(command,**kwargs):
        calls.append(command)
        assert '--no-fallback' in command and command[command.index('--max-context')+1]=='0'
        output=Path(command[command.index('-of')+1]+'.json')
        output.write_text(json.dumps({'transcription':[
            {'offsets':{'from':0,'to':500},'text':'hello'},
            {'offsets':{'from':None,'to':None},'text':'unplaced'}]}))
        return NS(returncode=0)
    monkeypatch.setattr('steps.audio_transcribe.whisper_cpp.subprocess.run',execute)
    result=_transcribe_chunk_whisper_cli(str(source),0.,'fixture-cli','fixture-model')
    assert len(calls)==2 and result['transcription']=='hello hello'
    assert result['word_alignment']['status']=='no_word_alignment'
    coverage=result['transcription_decoding']['source_regions']
    assert all(r['unplaced_segments'][0]['text']=='unplaced' for r in coverage['regions'])
    assert all(r['unplaced_segment_count']==1 for r in coverage['regions'])
    assert result['segments'][1]['start']==9.


def test_scene_offset_keeps_words_regions_and_uncertainty_on_one_timeline(source):
    from cli.run_ingestion import _offset_local_audio_result_to_scene
    from steps.audio.audio_wsl2_bridge import _transcription_projection
    from wsl2_audio.transcription_contract import transcribe_file
    original=_transcription_projection(transcribe_file(Decoder(),source),engine='faster-whisper')
    result=_offset_local_audio_result_to_scene(original,100.)
    assert result['segments'][0]['words'][0]['start']==102.1
    assert result['word_timestamps'][0]['start']==102.1
    assert result['words'][0]['start']==102.1
    assert result['transcript_meta']['word_alignment']['words'][0]['start']==102.1
    assert result['word_timestamps'][1]['start'] is None
    coverage=result['transcript_meta']['transcription_decoding']['source_regions']
    assert coverage['regions'][0]['start']==102.
    assert coverage['timebase']=='video_seconds'
    assert original['word_timestamps'][0]['start']==2.1


def test_older_language_api_does_not_decode_concatenated_speech(source):
    from wsl2_audio.transcription_contract import transcribe_file
    class OlderDecoder(Decoder):
        detect_language=None
        def transcribe(self,audio,**kwargs):
            if kwargs['language'] is None:
                assert kwargs['word_timestamps'] is False
                def forbidden():
                    raise AssertionError('Language detection must not decode joined speech')
                    yield
                return forbidden(),NS(language='en',language_probability=.42)
            return super().transcribe(audio,**kwargs)
    model=OlderDecoder()
    result=transcribe_file(model,source)
    assert len(model.calls)==2
    assert result['transcription_decoding']['language']['detection_probability']==.42
    assert result['transcription_decoding']['source_regions']['language_detection_api']=='lazy_transcribe_metadata'


def test_transcription_only_does_not_depend_on_optional_diarization_bounds(monkeypatch):
    from steps.audio import audio_wsl2_bridge as bridge
    class Runner:
        def process_audio(self,*args,**kwargs):
            return {'status':'success','transcription_status':'success','transcription':'hello',
                'transcription_decoding':{'policy':'single_temperature_v1','temperature':0.,
                    'source_regions':{'policy':'source_audio_v2'}},
                'diarization':[{'start':2,'end':3,'speaker':'S0'}]}
    monkeypatch.setattr(bridge,'WSL2AudioBridge',Runner)
    assert bridge.audio_transcribe_wsl2('clip.wav',duration=1)['transcript']=='hello'


def test_old_worker_cannot_claim_source_coverage_when_it_has_no_receipt(monkeypatch):
    from steps.audio import audio_wsl2_bridge as bridge
    class Runner:
        def process_audio(self,*args,**kwargs):
            return {'status':'success','transcription_status':'success','transcription':'hello',
                'transcription_decoding':{'policy':'single_temperature_v1','temperature':0.}}
    monkeypatch.setattr(bridge,'WSL2AudioBridge',Runner)
    result=bridge.audio_transcribe_wsl2('clip.wav')
    assert result['status']=='error'
    assert result['bridge_error_reason']=='transcription_policy_unconfirmed'
