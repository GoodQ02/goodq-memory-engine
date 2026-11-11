from array import array
from types import SimpleNamespace

import pytest

from wsl2_audio import recognition
from wsl2_audio import transcription_contract
from wsl2_audio.source_clock import SampleSpan


class Model:
    def __init__(self, segments, fail=False):
        self.segments, self.fail, self.calls = segments, fail, []

    def transcribe(self, audio, **options):
        self.calls.append((audio.copy(), options))

        def rows():
            yield from self.segments
            if self.fail:
                raise RuntimeError('injected later decoder failure')
        return rows(), SimpleNamespace(language='en', language_probability=.9)


def segment(start=.2, end=.8):
    return SimpleNamespace(start=start, end=end, text='Yay Joe!', words=None,
                           avg_logprob=-.2, no_speech_prob=.02, temperature=0)


def run(model, monkeypatch, *, vad=True, rate=16000, context=None):
    monkeypatch.setattr(transcription_contract, '_source_speech_regions',
                        lambda audio: [{'start': 0, 'end': len(audio)}] if vad else [])
    return recognition.recognize_window(model, array('d', [.001] * rate), rate,
                                        context or SampleSpan(rate, rate*2), language='en')


def test_recognition_gets_whole_window_even_when_vad_finds_nothing(monkeypatch):
    model = Model([segment()])
    result = run(model, monkeypatch, vad=False)
    assert len(model.calls) == 1
    audio, options = model.calls[0]
    assert len(audio) == 16000
    assert options['vad_filter'] is False
    assert options['word_timestamps'] is False
    assert options['temperature'] == 0.0
    assert options['condition_on_previous_text'] is False
    assert result['utterances'][0]['text'] == 'Yay Joe!'
    assert result['utterances'][0]['quality']['speech_coverage'] == 0


def test_profile_vocabulary_reaches_decoder_once_and_does_not_change_gate_options(monkeypatch):
    import sys
    model=Model([segment()])
    monkeypatch.setitem(sys.modules,'faster_whisper',SimpleNamespace(WhisperModel=lambda *a,**kw:model))
    monkeypatch.setattr(transcription_contract,'_source_speech_regions',lambda audio:[])
    adapter=recognition.FasterWhisperRecognizer({'vocabulary':[' Joe ','Kathi','joe']},
        {'models':[],'runtime':{},'model_path':'fixture'})
    result=adapter.observe(array('d',[.001]*16000),16000,SampleSpan(0,16000),'en')
    assert len(model.calls)==1
    options=model.calls[0][1]
    assert options==dict(recognition.DECODE_OPTIONS,language='en',hotwords='Joe, Kathi')
    assert result['decoding']==options
    assert options['initial_prompt'] is None and options['vad_filter'] is False
    assert recognition.DECODE_OPTIONS['hotwords'] is None
    assert result['utterances'][0]['quality']['speech_coverage']==0


@pytest.mark.parametrize('value',['Joe',[''],['x'*65],['a\nb'],['Joe']*33,[1]])
def test_invalid_profile_vocabulary_fails_before_model_load(monkeypatch,value):
    import sys
    monkeypatch.setitem(sys.modules,'faster_whisper',SimpleNamespace(
        WhisperModel=lambda *a,**kw:pytest.fail('invalid vocabulary loaded a model')))
    with pytest.raises(ValueError,match='vocabulary'):
        recognition.FasterWhisperRecognizer({'vocabulary':value},
            {'models':[],'runtime':{},'model_path':'fixture'})


def test_punctuation_and_native_model_bounds_do_not_certify_completeness(monkeypatch):
    result = run(Model([segment()]), monkeypatch)
    assert result['utterances'][0]['span'] == {'start': 19200, 'end': 28800}
    assert result['utterances'][0]['completeness'] == 'unresolved'
    assert result['utterances'][0]['speaker']['status'] == 'unresolved'


def test_native_phrase_and_word_timing_are_independent_without_a_second_decode(monkeypatch):
    raw = segment()
    raw.words = [SimpleNamespace(word='Yay', start=.2, end=.2, probability=.9),
                 SimpleNamespace(word=' Joe!', start=.4, end=.7, probability=.9)]
    monkeypatch.setattr(transcription_contract, '_align_after_decoding',
                        lambda model, audio, segments, language: (segments, {'status': 'completed'}))
    model = Model([raw])
    result = run(model, monkeypatch)
    utterance = result['utterances'][0]
    assert utterance['text'] == 'Yay Joe!'
    assert utterance['span'] == {'start': 19200, 'end': 28800}
    assert utterance['words'][0]['span'] is None
    assert utterance['words'][1]['span'] == {'start': 22400, 'end': 27200}
    assert len(model.calls) == 1


def test_valid_word_outside_coarse_native_segment_keeps_its_source_time(monkeypatch):
    raw = segment(start=.2, end=.6)
    raw.words = [SimpleNamespace(word='Yay', start=.15, end=.4, probability=.9),
                 SimpleNamespace(word=' Joe!', start=.4, end=.8, probability=.9)]
    monkeypatch.setattr(transcription_contract, '_align_after_decoding',
                        lambda model, audio, segments, language: (segments, {'status': 'completed'}))
    model = Model([raw])
    result = run(model, monkeypatch)
    u = result['utterances'][0]
    assert u['words'][0]['span'] == {'start': 18400, 'end': 22400}
    assert u['words'][1]['span'] == {'start': 22400, 'end': 28800}
    assert u['span'] == {'start': 18400, 'end': 28800}
    assert u['native_span'] == {'start': 19200, 'end': 25600}
    assert u['completeness'] == 'unresolved'
    assert result['raw_segments'][0]['start'] == .2 and result['raw_segments'][0]['end'] == .6
    assert len(model.calls) == 1


@pytest.mark.parametrize('bounds', [(0.9, 1.1), (.4, .4), (.1, .3)])
def test_separating_word_and_native_clocks_does_not_accept_invalid_or_reordered_words(monkeypatch, bounds):
    raw = segment(start=.2, end=.6)
    raw.words = [SimpleNamespace(word='Yay', start=.2, end=.4, probability=.9),
                 SimpleNamespace(word=' Joe!', start=bounds[0], end=bounds[1], probability=.9)]
    monkeypatch.setattr(transcription_contract, '_align_after_decoding',
                        lambda model, audio, segments, language: (segments, {'status': 'completed'}))
    u = run(Model([raw]), monkeypatch)['utterances'][0]
    assert u['words'][1]['span'] is None
    assert u['completeness'] == 'unresolved'


def test_resampling_maps_back_to_source_samples_without_applying_media_origin(monkeypatch):
    result = run(Model([segment()]), monkeypatch, rate=44100)
    assert result['utterances'][0]['span'] == {'start': 52920, 'end': 79380}
    assert result['transform']['source_rate'] == 44100
    assert result['transform']['target_rate'] == 16000


def test_unplaceable_text_stays_raw_instead_of_getting_invented_timestamps(monkeypatch):
    result = run(Model([segment(start=1.1, end=1.2)]), monkeypatch)
    assert not result['utterances']
    assert result['unplaced_hypotheses'][0]['text'] == 'Yay Joe!'


def test_outside_native_envelope_preserves_complete_valid_alignment_without_clamping(monkeypatch):
    raw = segment(start=0, end=1.2)
    raw.words = [SimpleNamespace(word='Yay', start=.2, end=.4, probability=.9),
                 SimpleNamespace(word=' Joe!', start=.4, end=.8, probability=.9)]
    monkeypatch.setattr(transcription_contract, '_align_after_decoding',
                        lambda model, audio, segments, language: (segments, {'status': 'completed'}))
    model = Model([raw])
    result = run(model, monkeypatch)
    assert result['raw_segments'][0]['end'] == 1.2
    assert len(result['raw_segments'][0]['words']) == 2
    u = result['utterances'][0]
    assert u['text'] == 'Yay Joe!' and u['span'] == {'start':19200,'end':28800}
    assert u['alignment_source']['reason'] == 'native_envelope_outside_input'
    assert u['completeness'] == 'unresolved' and len(model.calls) == 1


@pytest.mark.parametrize('failure',['missing_word','invalid_word','window_edge','no_speech'])
def test_native_failure_recovery_never_invents_words_boundaries_or_speech(monkeypatch,failure):
    raw=segment(start=0,end=1.2)
    raw.words=[SimpleNamespace(word='Yay',start=.2,end=.4,probability=.9),
               SimpleNamespace(word=' Joe!',start=.4,end=.8,probability=.9)]
    if failure=='missing_word': raw.words.pop()
    if failure=='invalid_word': raw.words[1].end=.4
    if failure=='window_edge': raw.words[0].start=0
    monkeypatch.setattr(transcription_contract,'_align_after_decoding',
                        lambda *args:(args[2],{'status':'completed'}))
    result=run(Model([raw]),monkeypatch,vad=failure!='no_speech')
    assert result['raw_segments'][0]['words']
    if failure=='no_speech':
        assert result['utterances'][0]['quality']['speech_coverage']==0
    else:
        assert not result['utterances'] and result['unplaced_hypotheses']


def test_later_decoder_failure_preserves_earlier_text_with_partial_coverage(monkeypatch):
    result = run(Model([segment()], fail=True), monkeypatch)
    assert result['status'] == 'partial'
    assert result['utterances'][0]['text'] == 'Yay Joe!'
    assert result['assessed_spans'] == [{'start': 19200, 'end': 28800}]


def test_float_transform_cannot_turn_nonzero_source_into_silence():
    with pytest.raises(ValueError, match='precision'):
        recognition.recognize_window(Model([]), array('d', [1e-320] * 16000), 16000,
                                     SampleSpan(0, 16000), language='en')


def test_decoder_context_budget_includes_prompt_tokens(monkeypatch):
    class LimitedModel(Model):
        def transcribe(self, audio, **options):
            limit = options['max_new_tokens']
            if limit is not None and limit + 3 > 448:
                raise ValueError('Prompt plus output exceeds pinned model context')
            return super().transcribe(audio, **options)

    result = run(LimitedModel([segment()]), monkeypatch)
    assert result['status'] == 'ok'
    assert result['utterances'][0]['text'] == 'Yay Joe!'


def test_short_resampled_speech_activity_uses_integer_source_boundaries(monkeypatch):
    monkeypatch.setattr(transcription_contract, '_source_speech_regions',
                        lambda audio: [{'start': 0, 'end': len(audio)}])
    result = recognition.recognize_window(Model([]), array('d', [.001]*101), 44100,
                                          SampleSpan(44100, 44201), language='en')
    assert result['speech_activity']['spans'] == [{'start': 44100, 'end': 44201}]


def _recognizer_profile_fixture(tmp_path, monkeypatch, *, device='cpu', compute_type='int8'):
    import hashlib
    import faster_whisper.vad
    from wsl2_audio.recording_audio import _json_bytes, _sha_file

    model_dir = tmp_path / 'whisper'
    model_dir.mkdir()
    files = {}
    for name in ('model.bin', 'config.json', 'tokenizer.json', 'vocabulary.json'):
        target = model_dir / name
        target.write_bytes(name.encode('utf-8'))
        files[name] = _sha_file(target)
    from pathlib import Path
    vad_path = (Path(faster_whisper.vad.__file__).parent / 'assets' / 'silero_vad_v6.onnx').resolve()
    monkeypatch.setattr(recognition, 'version', lambda pkg: {
        'faster-whisper': '1.2.1', 'ctranslate2': '4.8.4', 'numpy': '2.2.6', 'scipy': '1.15.3'}[pkg])
    return {
        'device': device,
        'compute_type': compute_type,
        'runtime_packages': {'faster-whisper': '1.2.1', 'ctranslate2': '4.8.4', 'numpy': '2.2.6', 'scipy': '1.15.3'},
        'recognizer': {'id': 'fixture-whisper', 'revision': 'rev1', 'path': str(model_dir),
                       'files': files, 'sha256': hashlib.sha256(_json_bytes(files)).hexdigest()},
        'speech_activity_model': {'id': 'silero-vad', 'revision': 'v6', 'path': str(vad_path),
                                  'sha256': _sha_file(vad_path)},
    }


@pytest.mark.parametrize('compute_type', ['float16', 'int8_float16', 'float32', 'int8'])
def test_explicit_cuda_recognizer_verifies_and_loads_without_cpu_fallback(tmp_path, monkeypatch, compute_type):
    import sys
    import ctranslate2
    monkeypatch.setattr(ctranslate2, 'get_cuda_device_count', lambda: 1)
    profile = _recognizer_profile_fixture(tmp_path, monkeypatch, device='cuda', compute_type=compute_type)
    verified = recognition.verify_recognizer(profile)
    assert verified['runtime']['device'] == 'cuda'
    assert verified['runtime']['compute_type'] == compute_type
    loaded_kwargs = {}

    def fake_whisper(path, **kwargs):
        loaded_kwargs.update(kwargs)
        return Model([segment()])

    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=fake_whisper))
    adapter = recognition.FasterWhisperRecognizer(profile, verified)
    assert loaded_kwargs['device'] == 'cuda'
    assert loaded_kwargs['compute_type'] == compute_type
    assert loaded_kwargs['local_files_only'] is True
    adapter.close()
    assert adapter.model is None


def test_cuda_recognizer_fails_hard_when_cuda_runtime_unavailable(tmp_path, monkeypatch):
    import ctranslate2
    monkeypatch.setattr(ctranslate2, 'get_cuda_device_count', lambda: 0)
    profile = _recognizer_profile_fixture(tmp_path, monkeypatch, device='cuda', compute_type='float16')
    with pytest.raises(ValueError, match='no automatic device fallback'):
        recognition.verify_recognizer(profile)


@pytest.mark.parametrize('device,compute_type', [('cpu', 'float16'), ('mps', 'float16'), ('cuda', 'bf99')])
def test_unsupported_recognizer_device_or_compute_type_rejected(tmp_path, monkeypatch, device, compute_type):
    import ctranslate2
    monkeypatch.setattr(ctranslate2, 'get_cuda_device_count', lambda: 1)
    profile = _recognizer_profile_fixture(tmp_path, monkeypatch, device=device, compute_type=compute_type)
    with pytest.raises(ValueError, match='no automatic device fallback'):
        recognition.verify_recognizer(profile)
