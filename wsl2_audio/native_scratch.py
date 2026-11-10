"""Opt-in Linux scratch transport; Windows retains durable recording ownership.

Only owned, acknowledged jobs are retired. Models and small source snapshots are
content-addressed shared caches; interrupted jobs retain their exact checkpoints.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import select
import subprocess
import sys
import time
import uuid

from wsl2_audio.recording_audio import _atomic_json, _json_bytes, _sha_file

SCHEMA = 'goodq.native_scratch.v1'
_SUPERVISED = False


def _remaining(deadline):
    remaining = deadline-time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Native recording deadline expired')
    return remaining


def _digest(value):
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _inside(root, relative):
    name = PurePosixPath(relative)
    if (not relative or name.is_absolute() or '..' in name.parts or ':' in relative
            or '\\' in relative):
        raise ValueError('Unsafe scratch/export relative path')
    root = Path(root).resolve()
    target = root.joinpath(*name.parts)
    resolved = target.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError('Scratch/export path escapes its owner')
    return target


def _copy(source, destination, expected, *, replace=False):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        if _sha_file(destination) == expected:
            return
        if not replace:
            raise ValueError('Retained staged/exported bytes changed: '+str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.partial')
    try:
        with source.open('rb') as src, temporary.open('xb') as dst:
            shutil.copyfileobj(src, dst, length=8*1024*1024)
            dst.flush()
            os.fsync(dst.fileno())
        if _sha_file(temporary) != expected or _sha_file(source) != expected:
            raise ValueError('Source changed during verified staging/export')
        os.replace(temporary, destination)
        if _sha_file(destination) != expected:
            raise ValueError('Published copy failed verification')
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _lock(path, timeout):
    import fcntl
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        deadline = time.monotonic()+timeout
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Native scratch lock timed out')
                time.sleep(.1)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _root(location, deadline=None):
    path = Path(location)
    if not path.is_absolute() or '..' in path.parts or path == Path('/'):
        raise ValueError('Native scratch requires a dedicated absolute directory')
    path = path.resolve()
    marker = path/'.goodq-native-scratch.json'
    if path.exists() and not marker.exists() and any(path.iterdir()):
        raise ValueError('Refusing to adopt a nonempty unowned scratch directory')
    path.mkdir(parents=True, exist_ok=True)
    filesystem = subprocess.check_output(['findmnt', '-n', '-T', str(path), '-o', 'FSTYPE'],
                                        text=True, timeout=_remaining(deadline) if deadline else 30).strip()
    if filesystem not in ('ext4', 'ext3', 'ext2', 'xfs', 'btrfs'):
        raise ValueError('Scratch must use a persistent native Linux filesystem, got '+filesystem)
    with _lock(path/'.owner.lock', _remaining(deadline) if deadline else 30):
        if marker.exists():
            if json.loads(marker.read_text()) != {'schema': SCHEMA}:
                raise ValueError('Unknown native scratch owner')
        else:
            _atomic_json({'schema': SCHEMA}, marker)
    return path


def _model(root, spec):
    source = Path(spec['path']).resolve(strict=True)
    files = spec.get('files')
    if files is None:
        files = {'asset': spec['sha256']}
        sources = {'asset': source}
    else:
        # HF snapshots may contain symlinks to their own immutable blob store.
        for name in files:
            relative = PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts or ':' in name or '\\' in name or not name:
                raise ValueError('Unsafe model manifest path')
        sources = {name: source.joinpath(*PurePosixPath(name).parts) for name in files}
    for name, expected in files.items():
        if _sha_file(sources[name]) != expected:
            raise ValueError('Pinned model asset changed: '+str(sources[name]))
    filesystems = {subprocess.check_output(['findmnt', '-n', '-T', str(p.resolve()), '-o', 'FSTYPE'], text=True).strip() for p in sources.values()}
    if filesystems <= {'ext4', 'ext3', 'ext2', 'xfs', 'btrfs'}:
        return str(source)
    destination = _inside(root, 'models/'+_digest(files))
    for name, expected in files.items():
        _copy(sources[name], _inside(destination, name), expected)
    return str(destination if spec.get('files') is not None else destination/'asset')


def _stage(plan, root, job, deadline):
    original = Path(plan['worker_root']).resolve(strict=True)
    code_files = list(original.glob('wsl2_audio/*.py'))
    code_files += [original/name for name in ('steps/__init__.py', 'steps/common/__init__.py',
                                             'steps/common/profile_config.py', 'steps/common/tool_paths.py')]
    hashes = {p.relative_to(original).as_posix(): _sha_file(p) for p in code_files}
    code = _inside(root, 'code/'+_digest(hashes))
    profile = json.loads(Path(plan['profile']).read_text(encoding='utf-8-sig'))
    request = json.loads(Path(plan['request']).read_text(encoding='utf-8'))
    if _sha_file(Path(plan['profile'])) != plan['profile_sha256'] or _sha_file(Path(plan['request'])) != plan['request_sha256']:
        raise ValueError('Recording request/profile changed before staging')
    staging_errors = {}
    with _lock(root/'cache.lock', _remaining(deadline)):
        for relative, expected in hashes.items():
            _copy(original/relative, _inside(code, relative), expected)
        for name in ('recognizer', 'speech_activity_model'):
            profile[name]['path'] = _model(root, profile[name])
        for name, spec in profile.get('enrichment', {}).get('models', {}).items():
            _remaining(deadline)
            try:
                spec['path'] = _model(root, spec)
            except TimeoutError:
                raise
            except (OSError, ValueError) as exc:
                # The worker owns supported absence and optional-stage errors.
                # Never load an unverified asset or quietly fall back to it.
                from wsl2_audio.model_cache import redact_sensitive_info
                staging_errors[name] = redact_sensitive_info(str(exc))
        ecapa = None
        if plan.get('ecapa_model_dir'):
            from wsl2_audio.speaker_signature import FILES
            ecapa = _model(root, {'path': plan['ecapa_model_dir'], 'files': FILES})
    source = Path(request['source_path']).resolve(strict=True)
    if _sha_file(source) != request['source_sha256']:
        raise ValueError('Recording input changed before native decode')
    # Read the original once for decoding; repeated PCM access stays native.
    # In particular, do not duplicate a full video merely to analyze its audio.
    request.update(processing_root=str(job/'processing'), native_model_staging_errors=staging_errors)
    _atomic_json(request, job/'request.json')
    _atomic_json(profile, job/'profile.json')
    _atomic_json({'schema': SCHEMA, 'code': str(code), 'code_hashes': hashes,
                  'source_sha256': request['source_sha256'], 'ecapa_model_dir': ecapa,
                  'optional_model_errors': staging_errors}, job/'staging.json')
    return code, ecapa


def _run_worker(plan, job, code, ecapa, deadline):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    env.pop('PYTHONPATH', None)
    if ecapa:
        env['GOODQ_ECAPA_MODEL_DIR'] = ecapa
    args = [plan['python'], '-B', '-m', 'wsl2_audio.recording_engine',
            str(job/'request.json'), str(job/'profile.json'), str(job/'output')]
    _remaining(deadline)
    with (job/'worker.log').open('a', encoding='utf-8') as log:
        process = subprocess.Popen(args, cwd=code, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=not _SUPERVISED)
        try:
            result = process.wait(timeout=_remaining(deadline))
        finally:
            if process.poll() is None:
                if _SUPERVISED:
                    process.kill()  # the outer supervisor also reaps the whole group
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
    if result:
        raise RuntimeError(f'Native recording worker failed ({result}); retained {job}')


def verify_export(output, processing_root, plan):
    """Also called by Windows before accepting a durable recording handle."""
    output = Path(output)
    receipt = json.loads((output/'native-export.json').read_text(encoding='utf-8'))
    for key in ('job_key', 'request_sha256', 'profile_sha256', 'worker_sha256'):
        if receipt.get(key) != plan[key]:
            raise ValueError('Native export binding mismatch: '+key)
    if receipt.get('schema') != SCHEMA or not {'output/evidence.json', 'output/scene_audio.json'} <= receipt.get('files', {}).keys():
        raise ValueError('Incomplete native export manifest')
    for name, expected in receipt['files'].items():
        prefix, relative = name.split('/', 1)
        if prefix not in ('output', 'processing'):
            raise ValueError('Unknown export file scope')
        target = _inside(output if prefix == 'output' else processing_root, relative)
        if _sha_file(target) != expected:
            raise ValueError('Native export bytes changed: '+name)
    return receipt


def _export(plan, job, deadline):
    from wsl2_audio.evidence_contract import validate_evidence
    from wsl2_audio.scene_projection import validate_scene_audio
    from wsl2_audio.scene_consumers import validate_review
    output = Path(plan['output'])
    request = json.loads(Path(plan['request']).read_text())
    processing = Path(request['processing_root'])
    evidence_path = job/'output/evidence.json'
    evidence = validate_evidence(json.loads(evidence_path.read_text()))
    if evidence['provenance']['worker_sha256'] != plan['worker_sha256'] or evidence['source']['sha256'] != request['source_sha256']:
        raise ValueError('Native worker/source differs from the requested snapshot')
    scenes_path = job/'output/scene_audio.json'
    scenes = json.loads(scenes_path.read_text())
    files = {}
    for audio in scenes.values():
        projection = validate_scene_audio(audio['audio_evidence'])
        reviews = list(projection.get('voice_reviews', []))
        for signature in projection.get('voice_signatures', []):
            reviews.extend(signature['review_evidence'])
        for review in reviews:
            _remaining(deadline)
            validate_review(review, projection['source'], root=job/'processing')
            relative = review['relative_path']
            _copy(_inside(job/'processing', relative), _inside(processing, relative), review['sha256'])
            files['processing/'+relative] = review['sha256']
    for name in ('evidence.json', 'scene_audio.json'):
        files['output/'+name] = _sha_file(job/'output'/name)
    _copy(evidence_path, _inside(output, 'evidence.json'), files['output/evidence.json'], replace=True)
    files['output/native-staging.json'] = _sha_file(job/'staging.json')
    _copy(job/'staging.json', _inside(output, 'native-staging.json'),
          files['output/native-staging.json'], replace=True)
    receipt = {'schema': SCHEMA, **{k: plan[k] for k in ('job_key', 'request_sha256', 'profile_sha256', 'worker_sha256')}, 'files': files}
    # Scene output is the publication point. No handle is accepted until all
    # referenced bytes and this receipt are verified by the Windows caller.
    _atomic_json(receipt, _inside(output, 'native-export.json'))
    _remaining(deadline)
    _copy(scenes_path, _inside(output, 'scene_audio.json'), files['output/scene_audio.json'], replace=True)
    _copy(job/'worker.log', _inside(output, 'native-worker.log'), _sha_file(job/'worker.log'), replace=True)
    verify_export(output, processing, plan)


def execute(plan, *, finalize=False, deadline=None):
    if plan.get('schema') != SCHEMA or len(plan.get('job_key', '')) != 64 or any(c not in '0123456789abcdef' for c in plan['job_key']):
        raise ValueError('Invalid native recording plan')
    deadline = time.monotonic()+plan['timeout_seconds'] if deadline is None else deadline
    _remaining(deadline)
    root = _root(plan['scratch_root'], deadline=deadline)
    job = _inside(root, 'jobs/'+plan['job_key'])
    owner = {'schema': SCHEMA, 'plan_sha256': _digest(plan)}
    retirement = _inside(root, 'retirements/'+plan['job_key']+'.json')
    with _lock(_inside(root, 'locks/'+plan['job_key']+'.lock'), _remaining(deadline)):
        if finalize:
            request = json.loads(Path(plan['request']).read_text())
            receipt = verify_export(plan['output'], request['processing_root'], plan)
            saved = json.loads((Path(plan['output'])/'job.json').read_text())
            if not saved.get('reusable') or saved['handle']['sha256'] != receipt['files']['output/scene_audio.json']:
                raise ValueError('Windows has not accepted this native export')
            intent = {'owner': owner, 'scene_sha256': receipt['files']['output/scene_audio.json']}
            if retirement.exists():
                if json.loads(retirement.read_text()) != intent:
                    raise ValueError('Native retirement ownership changed')
            elif job.exists():
                if json.loads((job/'owner.json').read_text()) != owner:
                    raise ValueError('Native job ownership changed')
                # This survives any partial tree removal, including owner.json.
                _atomic_json(intent, retirement)
            if job.exists():
                _remaining(deadline)
                if (job/'owner.json').exists() and json.loads((job/'owner.json').read_text()) != owner:
                    raise ValueError('Native job ownership changed during retirement')
                # job is a validated child of this owned Linux root, never a
                # Windows source/destination or a caller-computed deletion path.
                shutil.rmtree(job)
            _atomic_json({'schema': SCHEMA, 'job_key': plan['job_key'], 'status': 'retired_after_verified_windows_acceptance'}, Path(plan['output'])/'native-cleanup.json')
            return
        if retirement.exists():
            raise ValueError('Native job already accepted; retry finalization instead')
        if job.exists():
            if not (job/'owner.json').is_file() or json.loads((job/'owner.json').read_text()) != owner:
                raise ValueError('Native job ownership changed')
        else:
            job.mkdir(parents=True)
            _atomic_json(owner, job/'owner.json')
        (job/'output').mkdir(exist_ok=True)
        code, ecapa = _stage(plan, root, job, deadline)
        _remaining(deadline)
        _run_worker(plan, job, code, ecapa, deadline)
        _remaining(deadline)
        _export(plan, job, deadline)
        _remaining(deadline)


def _supervise(operation, plan_path, plan, *, watch_parent=False):
    """Bound all Linux work, including blocked staging/export and descendants.

    The Windows caller holds stdin open for this invocation. EOF means that the
    caller disconnected or cancelled; no Windows PID is used as a Linux PID.
    """
    deadline = time.monotonic()+plan['timeout_seconds']
    process = subprocess.Popen([sys.executable, '-B', '-m', 'wsl2_audio.native_scratch',
        '_execute', operation, str(plan_path), str(deadline)], stdin=subprocess.DEVNULL,
        start_new_session=True)
    try:
        while process.poll() is None:
            remaining = _remaining(deadline)
            if watch_parent:
                ready, _, _ = select.select([sys.stdin.buffer], [], [], min(.1, remaining))
                if ready and not os.read(sys.stdin.fileno(), 1024):
                    raise InterruptedError('Native recording caller disconnected')
            else:
                time.sleep(min(.1, remaining))
        if process.returncode:
            raise RuntimeError(f'Native recording operation failed ({process.returncode})')
    finally:
        # Always remove descendants, even if their immediate parent exited first.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=10)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    global _SUPERVISED
    if len(args) == 4 and args[0] == '_execute' and args[1] in ('run', 'finalize'):
        _SUPERVISED = True
        execute(json.loads(Path(args[2]).read_text()), finalize=args[1] == 'finalize', deadline=float(args[3]))
        return
    watch_parent = len(args) == 3 and args[2] == '--watch-parent'
    if (len(args) != 2 and not watch_parent) or args[0] not in ('run', 'finalize'):
        raise SystemExit('usage: python -m wsl2_audio.native_scratch run|finalize PLAN.json [--watch-parent]')
    def interrupted(signum, frame):
        raise InterruptedError('Native scratch supervisor interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    _supervise(args[0], Path(args[1]), json.loads(Path(args[1]).read_text()), watch_parent=watch_parent)


if __name__ == '__main__':
    main()
