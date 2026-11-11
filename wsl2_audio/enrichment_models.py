"""Pinned offline observation adapters. No recognition, scene ownership or retries."""

from copy import deepcopy
from fractions import Fraction
from importlib.metadata import version
import hashlib
import json
import math
from pathlib import Path

from wsl2_audio.recording_audio import _json_bytes, _sha_file, read_channel
from wsl2_audio.recognition import _model_audio
from wsl2_audio.source_clock import SampleSpan
from wsl2_audio.profile_identity import profile_identity


def _union(spans):
    merged = []
    for span in sorted(spans, key=lambda p: (p['start'], p['end'])):
        if merged and span['start'] <= merged[-1]['end']:
            merged[-1]['end'] = max(merged[-1]['end'], span['end'])
        else:
            merged.append(dict(span))
    return merged


def _runs(mask):
    import numpy as np
    return np.flatnonzero(np.diff(np.r_[False, mask, False])).reshape(-1, 2).tolist()


class RecordingObservers:
    """Bounded CPU/CUDA candidate; existing runner owns process resource admission."""

    BOUNDED_POLICY_LIMITS = {'bounded_recording_v1': 3600, 'bounded_recording_v2': 28800}

    def __init__(self, profile, evidence, recording):
        self.profile, self.evidence, self.recording = profile, evidence, recording
        self.settings = profile['enrichment']
        self.rate, self.count = evidence['source']['sample_rate'], evidence['source']['sample_count']
        self.channels = evidence['source']['channels']
        self.duration = self.count/self.rate
        policy = self.settings.get('recording_policy')
        maximum = 300
        if policy is not None:
            limit = self.BOUNDED_POLICY_LIMITS.get(policy.get('id')) if isinstance(policy, dict) else None
            if (limit is None or set(policy) != {'id', 'max_duration_seconds'}
                    or type(policy['max_duration_seconds']) is not int
                    or not 300 < policy['max_duration_seconds'] <= limit):
                raise ValueError('Invalid bounded recording policy')
            maximum = policy['max_duration_seconds']
        device = self.settings.get('device')
        if device not in ('cpu', 'cuda'):
            raise ValueError('Unsupported enrichment device; explicit cpu or cuda required with no automatic device fallback')
        if device == 'cuda':
            import torch
            if not torch.cuda.is_available():
                raise ValueError('CUDA enrichment profile requested but CUDA is unavailable; no automatic device fallback')
        if not 0 < self.duration <= maximum:
            if policy is not None:
                raise ValueError(f'Recording exceeds the explicit {device.upper()} recording budget')
            raise ValueError(f'Initial enrichment candidate requires explicit {device.upper()} and at most 300 seconds')
        self.device = device
        self.full = SampleSpan(0, self.count)
        self.long_recording = self.duration > 300
        if self.long_recording:
            from wsl2_audio.bounded_audio import model_channel
            self.model_audio, self.channel_silent = [], []
            for channel in range(self.channels):
                audio, silent = model_channel(recording, channel, reader=read_channel)
                self.model_audio.append(audio)
                self.channel_silent.append(silent)
            self.silent = all(self.channel_silent)
        else:
            self.signal = [read_channel(recording, self.full, ch) for ch in range(self.channels)]
            self.channel_silent = [not any(samples) for samples in self.signal]
            self.silent = all(self.channel_silent)

    def spec(self, name):
        return self.profile['speech_activity_model'] if name == 'phrase_activity' else self.settings['models'].get(name)

    def verify(self, name):
        if self.silent:
            return
        if not {'torch', 'torchaudio', 'pyannote.audio', 'transformers', 'numpy', 'scipy', 'onnxruntime'} <= set(self.settings['runtime_packages']):
            raise ValueError('Incomplete independent runtime manifest')
        for package, expected in self.settings['runtime_packages'].items():
            if version(package) != expected:
                raise ValueError('Independent observation runtime mismatch: '+package)
        spec = self.spec(name)
        if not spec:
            raise ValueError('No pinned model configured for '+name)
        if name == 'acoustic_events':
            from wsl2_audio.frame_events import SUPPORTED_POLICIES
            expected_policy = SUPPORTED_POLICIES.get(spec.get('backend'))
            if expected_policy is None or spec.get('analysis_policy') != expected_policy:
                raise ValueError('Frame-event analysis policy differs from the pinned candidate configuration')
        if name == 'phrase_activity':
            if _sha_file(Path(spec['path'])) != spec['sha256']:
                raise ValueError('Phrase activity model hash mismatch')
            return
        root = Path(spec['path']).resolve(strict=True)
        required = {'speaker_activity': {'config.yaml', 'segmentation/pytorch_model.bin', 'embedding/pytorch_model.bin',
                                          'plda/plda.npz', 'plda/xvec_transform.npz'},
                    'overlap': {'config.json', 'model.safetensors', 'processor_config.json'},
                    'acoustic_events': {'efficientsed_fmn10_tf256.onnx', 'labels.json'},
                    'vocal_delivery': {'config.json', 'model.safetensors', 'preprocessor_config.json'}}[name]
        if not required <= set(spec['files']):
            raise ValueError('Incomplete independent model asset manifest: '+name)
        for relative, expected in spec['files'].items():
            candidate = root/relative
            # HF snapshots may use symlinked blobs; bound relative names, then hash
            # the actual target bytes without requiring snapshot-local blobs.
            if Path(relative).is_absolute() or '..' in Path(relative).parts or _sha_file(candidate) != expected:
                raise ValueError('Independent model asset mismatch: '+relative)
        if hashlib.sha256(_json_bytes(spec['files'])).hexdigest() != spec['sha256']:
            raise ValueError('Independent model manifest digest mismatch')

    def _span(self, start, end, *, frame_slack=0.):
        if (not all(type(x) in (int, float) and math.isfinite(x) for x in (start, end))
                or start < -frame_slack or end > self.duration+frame_slack or start >= end):
            raise ValueError('Observation outside the source clock')
        left, right = Fraction(str(max(0., start)))*self.rate, Fraction(str(min(self.duration, end)))*self.rate
        a = 0 if start <= 0 else left.numerator//left.denominator
        # The terminal sample is an exact integer, not a decimal duration
        # converted back through ceil. This bounds frame geometry only.
        b = self.count if end >= self.duration else -(-right.numerator//right.denominator)
        if not 0 <= a < b <= self.count:
            raise ValueError('Empty/out-of-source observation')
        return {'start': a, 'end': b}

    def _audio(self, channel, span=None):
        span = span or self.full
        if getattr(self, 'long_recording', False) and span == self.full:
            return self.model_audio[channel]
        samples = self.signal[channel] if span == self.full else read_channel(self.recording, span, channel)
        return _model_audio(samples, self.rate, span)[1]

    def observe(self, name, prior):
        import os
        # Per-process privacy policy, before importing pyannote's pipeline.
        os.environ['PYANNOTE_METRICS_ENABLED'] = '0'
        import torch
        import numpy as np
        import random
        torch.set_num_threads(4)
        torch.manual_seed(0)
        np.random.seed(0)
        random.seed(0)
        spec = self.spec(name)
        result = {'status': 'ok', 'model_id': spec['id'] if spec else None,
                  'assessed_spans': [], 'channel_assessed_spans': {}, 'channels': {},
                  'qualification': 'model_observations_unqualified'}
        fields = {'speaker_activity': ('tracks', 'flags', 'local_overlap'),
                  'overlap': ('intervals', 'single_activity'),
                  'acoustic_events': ('events', 'speech_intervals'), 'phrase_activity': ('regions',)}[name]
        result.update({field: [] for field in fields})
        if name == 'acoustic_events':
            from wsl2_audio.frame_events import ANALYSIS_POLICY, METHOD, SUPPORTED_POLICIES, THRESHOLD
            backend = spec.get('backend') if spec else METHOD
            policy_value = SUPPORTED_POLICIES.get(backend, ANALYSIS_POLICY)
            result.update(method=backend, threshold=THRESHOLD, analysis_policy=dict(policy_value))
        device_name = getattr(self, 'device', 'cpu')
        model = extractor = None
        try:
            if not self.silent:
                if name == 'speaker_activity':
                    from pyannote.audio import Pipeline
                    model = Pipeline.from_pretrained(spec['path']).to(torch.device(device_name))
                    if getattr(self, 'long_recording', False) and self.duration > 3600:
                        for batch_attr in ('segmentation_batch_size', 'embedding_batch_size'):
                            if isinstance(getattr(model, batch_attr, None), int) and getattr(model, batch_attr) > 16:
                                setattr(model, batch_attr, 16)
                elif name == 'overlap':
                    from transformers import AutoModelForAudioFrameClassification, AutoProcessor
                    model, info = AutoModelForAudioFrameClassification.from_pretrained(spec['path'], local_files_only=True,
                        trust_remote_code=False, dtype=torch.float32, output_loading_info=True)
                    self._strict(info)
                    if model.config.model_type != 'nemotron3_diarization':
                        raise ValueError('Wrong additional activity architecture')
                    model = model.to(torch.device(device_name))
                    model.eval()
                    extractor = AutoProcessor.from_pretrained(spec['path'], local_files_only=True, trust_remote_code=False)
                elif name == 'acoustic_events':
                    import onnxruntime as ort
                    from wsl2_audio.frame_events import SUPPORTED_POLICIES
                    if spec.get('backend') not in SUPPORTED_POLICIES or spec.get('analysis_policy') != SUPPORTED_POLICIES[spec['backend']]:
                        raise ValueError('Unsupported recording acoustic backend; no automatic fallback')
                    options = ort.SessionOptions()
                    options.intra_op_num_threads, options.inter_op_num_threads = 4, 1
                    model = ort.InferenceSession(str(Path(spec['path'])/'efficientsed_fmn10_tf256.onnx'),
                        sess_options=options, providers=['CPUExecutionProvider'])
                    if ([(x.name, x.type, x.shape) for x in model.get_inputs()] != [('waveform', 'tensor(float)', [1,160000])]
                            or [(x.name, x.type, x.shape) for x in model.get_outputs()] != [('scores', 'tensor(float)', [1,250,447])]
                            or model.get_providers() != ['CPUExecutionProvider']):
                        raise ValueError('Frame-event model/runtime interface differs from the pinned profile')
                    extractor = json.loads((Path(spec['path'])/'labels.json').read_text())
            for channel in range(self.channels):
                try:
                    if self.channel_silent[channel]:
                        row = {'status': 'not_applicable', 'reason': 'digital_silence', 'assessed_spans': [vars(self.full)]}
                    elif self.long_recording and name in ('overlap', 'phrase_activity'):
                        row = self._bounded_activity(name, channel, model, extractor, prior)
                    else:
                        row = getattr(self, '_'+name)(channel, model, extractor, prior)
                    result['channels'][str(channel)] = row
                    result['channel_assessed_spans'][str(channel)] = row.get('assessed_spans', [])
                    for field in fields:
                        result[field].extend(row.get(field, []))
                except Exception as exc:
                    from wsl2_audio.model_cache import redact_sensitive_info
                    result['channels'][str(channel)] = {'status': 'error', 'reason': 'channel_observation_failed',
                                                       'error': redact_sensitive_info(str(exc))}
                    result['channel_assessed_spans'][str(channel)] = []
            result['assessed_spans'] = _union([s for spans in result['channel_assessed_spans'].values() for s in spans])
            states = [row['status'] for row in result['channels'].values()]
            if self.silent:
                result.update(status='not_applicable', reason='digital_silence')
            elif any(state not in ('ok', 'not_applicable') for state in states):
                result.update(status='partial' if result['assessed_spans'] else 'unavailable', reason='incomplete_channel_assessment')
            return result
        finally:
            del model, extractor
            if device_name == 'cuda' and torch.cuda.is_available():
                torch.cuda.empty_cache()

    @staticmethod
    def _strict(info):
        if any(info.get(key) for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')):
            raise ValueError('Inference weights did not load strictly')

    def _speaker_activity(self, channel, model, extractor, prior):
        import torch
        from wsl2_audio.process_audio import _diarize_with_review
        local = {}
        output, review = _diarize_with_review(model, {'waveform': torch.from_numpy(self._audio(channel)).unsqueeze(0),
                                                     'sample_rate': 16000}, overlap_evidence=local, observe_empty=True)
        annotation = getattr(output, 'speaker_diarization', output)
        def source_intersection(start, end):
            if not all(math.isfinite(x) for x in (start, end)) or start >= end:
                raise ValueError('Invalid padded model interval')
            # Pyannote analyzes padded windows. Preserve those raw intervals,
            # but project only their intersection with real input samples.
            if start >= self.duration or end <= 0:
                return None
            return self._span(max(0., start), min(self.duration, end))
        raw_tracks, tracks = [], []
        for turn, _, label in annotation.itertracks(yield_label=True):
            start, end = float(turn.start), float(turn.end)
            raw_tracks.append({'start': start, 'end': end, 'speaker': str(label)})
            span = source_intersection(start, end)
            if span:
                tracks.append({'span': span, 'channel': channel, 'speaker': str(label),
                    'raw_seconds': [start, end], 'precision': 'model_frame',
                    'source_censored': start < 0 or end > self.duration})
        if local.get('status') != 'ok' or review.get('status') != 'ok':
            raise ValueError('Local activity/reconstruction evidence missing')
        result = {'status': 'ok', 'assessed_spans': [vars(self.full)], 'tracks': tracks, 'raw_tracks': raw_tracks,
                'flags': [{'span': span, 'channel': channel} for r in review['flags']
                          if (span := source_intersection(r['start'], r['end']))],
                'local_overlap': [{'span': span, 'channel': channel,
                                   'status': 'observed', 'detector': 'local_segmentation'} for r in local['intervals']
                                  if (span := source_intersection(r['start'], r['end']))],
                'raw_local_overlap': local, 'raw_review': review}
        if getattr(self, 'long_recording', False):
            result['continuity'] = {'method': 'pinned_recording_global_clustering',
                'waveform': 'file_backed_16khz', 'segmentation_batch_size': model.segmentation_batch_size,
                'embedding_batch_size': model.embedding_batch_size,
                'identity_claim': False, 'qualification': 'unreviewed_recording_local_tracks'}
        return result

    def _bounded_activity(self, name, channel, model, extractor, prior):
        """Fixed source windows; retain all overlap exclusions, own core positives.

        No speaker identity is stitched here. Recording-wide clustering remains
        with the pinned primary diarizer. Window checkpoints are source/config/
        worker bound and resume cannot convert missing assessment into purity.
        """
        from wsl2_audio.recording_audio import _atomic_json
        from wsl2_audio.source_clock import SourceClock, plan_windows
        from wsl2_audio.model_cache import redact_sensitive_info

        fields = ('intervals', 'single_activity') if name == 'overlap' else ('regions',)
        result = {'status': 'ok', 'assessed_spans': [], 'windows': [], **{k: [] for k in fields}}
        clock = SourceClock(self.rate, self.count, 0, 1)
        for window in plan_windows(clock, 60*self.rate, 5*self.rate):
            context, core = window.context, window.core
            identity = {'source': self.evidence['source'], 'provenance': self.evidence.get('provenance'),
                        'profile': profile_identity(self.profile), 'stage': name, 'channel': channel,
                        'core': vars(core), 'context': vars(context),
                        'implementation': _sha_file(Path(__file__))}
            key = hashlib.sha256(_json_bytes(identity)).hexdigest()
            cache = Path(self.recording['pcm']['path']).parent/'bounded-observations'/(key+'.json')
            try:
                if cache.is_file():
                    saved = json.loads(cache.read_text(encoding='utf-8'))
                    row = saved['observation']
                    if saved['identity'] != identity or saved['sha256'] != hashlib.sha256(_json_bytes(row)).hexdigest():
                        raise ValueError('Bounded observation checkpoint mismatch')
                else:
                    local = object.__new__(RecordingObservers)
                    local.rate, local.count = self.rate, context.end-context.start
                    local.duration, local.full = local.count/self.rate, SampleSpan(0, local.count)
                    local.device = getattr(self, 'device', 'cpu')
                    local._audio = lambda ch: self._audio(ch, context)
                    row = getattr(local, '_'+name)(channel, model, extractor, {})
                    _atomic_json({'identity': identity, 'observation': row,
                                  'sha256': hashlib.sha256(_json_bytes(row)).hexdigest()}, cache)
                if row['status'] != 'ok':
                    raise ValueError('Incomplete bounded activity assessment')
                result['windows'].append({'core': vars(core), 'context': vars(context), 'observation': row})
                result['assessed_spans'].append(vars(core))
                for field in fields:
                    for observed in row[field]:
                        span = observed['span']
                        start, end = span['start']+context.start, span['end']+context.start
                        # Conflicting/context overlap is always an exclusion. Positive
                        # single activity and VAD regions own only their fixed core.
                        if field != 'intervals':
                            start, end = max(start, core.start), min(end, core.end)
                        if start < end:
                            result[field].append({**observed, 'span': {'start': start, 'end': end}})
            except Exception as exc:
                result['status'] = 'partial'
                result['windows'].append({'core': vars(core), 'context': vars(context), 'status': 'error',
                    'reason': 'bounded_activity_failed', 'error': redact_sensitive_info(str(exc))})
        result['assessed_spans'] = _union(result['assessed_spans'])
        positive = 'single_activity' if name == 'overlap' else 'regions'
        result[positive] = [{'span': s, 'channel': channel} for s in _union([r['span'] for r in result[positive]])]
        if name == 'overlap':
            result['intervals'].extend(deepcopy(r) for r in prior.get('speaker_activity', {}).get('local_overlap', [])
                                       if r['channel'] == channel)
            result.update(threshold=.5, frame_step=.01, reason='bounded_independent_activity_observations')
        else:
            result['parameters'] = {'threshold': .5, 'min_silence_duration_ms': 100, 'speech_pad_ms': 0,
                'purpose': 'boundary_observation_only_never_recognition_input_selection'}
        result['window_policy'] = {'core_seconds': 60, 'context_seconds': 5, 'id': 'source_core_activity_v1'}
        return result

    def _overlap(self, channel, model, extractor, prior):
        import torch
        device_name = getattr(self, 'device', 'cpu')
        audio = self._audio(channel)
        inputs = extractor(audio, sampling_rate=16000).to(device_name, dtype=torch.float32)
        with torch.inference_mode():
            logits = model(**inputs).logits
        if logits.ndim != 3 or logits.shape[0] != 1 or logits.shape[-1] < 2 or not torch.isfinite(logits).all():
            raise ValueError('Invalid additional speaker-activity logits')
        raw_mask = inputs.attention_mask
        if not ((raw_mask == 0) | (raw_mask == 1)).all():
            raise ValueError('Invalid additional activity frame mask')
        mask = raw_mask.bool()
        if tuple(mask.shape) != tuple(logits.shape[:2]):
            raise ValueError('Additional activity frame mask mismatch')
        hop = extractor.feature_extractor.hop_length/extractor.feature_extractor.sampling_rate
        if hop != .01:
            raise ValueError('Additional activity frame rate differs from pinned profile')
        # The pinned centered extractor assesses floor(samples / hop_length)
        # consecutive frames, followed only by batch padding. Missing frames
        # must not turn into an overlap-free full-recording assessment.
        expected = len(audio)//extractor.feature_extractor.hop_length
        expected_mask = torch.arange(mask.shape[1], device=mask.device)[None, :] < expected
        if expected <= 0 or expected > mask.shape[1] or not torch.equal(mask, expected_mask):
            raise ValueError('Incomplete additional activity frame assessment')
        counts = (logits.sigmoid() > .5).sum(dim=-1)[0].cpu().numpy()
        valid = mask[0].cpu().numpy()
        def rows(wanted):
            return [{'span': self._span(a*hop, min(b*hop, self.duration)), 'channel': channel,
                     'status': 'observed', 'detector': 'nemotron3', 'precision': '10ms_model_frame'}
                    for a, b in _runs(wanted & valid) if a*hop < self.duration]
        primary = prior.get('speaker_activity', {})
        channel_state = primary.get('channels', {}).get(str(channel), {}).get('status')
        intervals = rows(counts >= 2) + [deepcopy(r) for r in primary.get('local_overlap', []) if r['channel'] == channel]
        return {'status': 'ok',
                'reason': 'independent_exclusion_and_activity_observations',
                'assessed_spans': [vars(self.full)], 'primary_activity_status': channel_state,
                'intervals': intervals, 'single_activity': rows(counts == 1),
                'threshold': .5, 'frame_step': hop, 'frame_counts': counts[valid].tolist()}

    def _phrase_activity(self, channel, model, extractor, prior):
        from faster_whisper.vad import VadOptions, get_speech_timestamps
        regions = get_speech_timestamps(self._audio(channel), VadOptions(threshold=.5,
            min_speech_duration_ms=0, min_silence_duration_ms=100, speech_pad_ms=0))
        return {'status': 'ok', 'assessed_spans': [vars(self.full)],
                'regions': [{'span': self._span(r['start']/16000, min(r['end']/16000, self.duration)), 'channel': channel}
                            for r in regions],
                'parameters': {'threshold': .5, 'min_silence_duration_ms': 100, 'speech_pad_ms': 0,
                               'purpose': 'boundary_observation_only_never_recognition_input_selection'}}

    def _acoustic_events(self, channel, model, extractor, prior):
        from wsl2_audio.frame_events import observe_frames
        spec = self.spec('acoustic_events') if hasattr(self, 'settings') else None
        reader = (lambda span: read_channel(self.recording, span, channel)) if getattr(self, 'long_recording', False) else (
            lambda span: self.signal[channel][span.start:span.end])
        return observe_frames(model, extractor, reader,
                              self.rate, self.count, channel, self.evidence['source']['sha256'],
                              policy=spec.get('analysis_policy') if spec else None)

    def vocal_delivery(self, utterances):
        import torch
        from transformers import Wav2Vec2FeatureExtractor
        from wsl2_audio.process_audio import _load_trained_wav2vec
        device_name = getattr(self, 'device', 'cpu')
        spec = self.spec('vocal_delivery')
        model, loading = _load_trained_wav2vec(spec['path'], cache_dir=None, is_offline=True, emotion=True)
        if device_name != 'cpu' and callable(getattr(model, 'to', None)):
            model = model.to(torch.device(device_name))
        extractor = Wav2Vec2FeatureExtractor.from_pretrained(spec['path'], local_files_only=True)
        results, errors = [], []
        try:
            for u in utterances:
                try:
                    audio = self._audio(u['channel'], SampleSpan(**u['span']))
                    inputs = extractor(audio, sampling_rate=16000, return_tensors='pt', padding=True)
                    if device_name != 'cpu':
                        inputs = (inputs.to(device_name) if callable(getattr(inputs, 'to', None)) else
                                  {k: v.to(device_name) if hasattr(v, 'to') else v for k, v in inputs.items()})
                    with torch.inference_mode():
                        logits = model(**inputs).logits[0]
                    if not torch.isfinite(logits).all():
                        raise ValueError('Non-finite vocal-delivery scores')
                    scores = logits.softmax(dim=-1).cpu().tolist()
                    labels = [model.config.id2label[i] for i in range(len(scores))]
                    results.append({'utterance_id': u['id'], 'span': deepcopy(u['span']), 'channel': u['channel'],
                        'model_id': spec['id'], 'label': labels[max(range(len(scores)), key=scores.__getitem__)],
                        'scores': dict(zip(labels, scores)), 'status': 'uncertain', 'qualification': 'unqualified',
                        'basis': 'vocal_delivery_only', 'review_status': 'unreviewed',
                        'input_samples': len(audio), 'input_sample_rate': 16000,
                        'input_sha256': hashlib.sha256(audio.tobytes()).hexdigest(), 'strict_weights': loading['strict']})
                except Exception as exc:
                    from wsl2_audio.model_cache import redact_sensitive_info
                    errors.append({"utterance_id": u["id"], "reason": "vocal_delivery_failed",
                                   "error": redact_sensitive_info(str(exc))})
            return {"results": results, "errors": errors}
        finally:
            del model, extractor
            if device_name == 'cuda' and torch.cuda.is_available():
                torch.cuda.empty_cache()
