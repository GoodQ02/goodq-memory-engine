<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: QUALIFIED_PROOF_TRAIL -->
<!-- DOC_LAST_VERIFIED: 2026-05-17 -->

# WSL Wav2Vec Transformers Lane Implementation Plan

> Status note (2026-05-17): This is the original qualification plan, not an
> active TODO queue. The lane is qualified; current runtime truth lives in
> `docs/reference/WSL_AUDIO_RUNTIME.md`, `docs/HANDOFF_BASEMENT_PHASE.md`,
> `docs/SYSTEM_SNAPSHOT.md`, and `docs/goodq4all_agent_status.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Qualify and, only if proven, add a bounded WSL `transformers` package lane so WSL-side Wav2Vec emotion, Wav2Vec embeddings, and speaker voice signatures can run without weakening the canonical WSL audio bootstrap contract.

**Architecture:** Treat this as package-lane qualification first, implementation second. The existing WSL audio runtime already has the Wav2Vec code paths and the model cache authority already includes `ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition` plus `facebook/wav2vec2-base-960h`; the missing piece is a proven, pinned `transformers` dependency lane and cache-dir-aware Wav2Vec loading. Keep WSL audio readiness separate from optional Wav2Vec enrichment readiness so missing emotion enrichment is visible without pretending ingestion is broken.

**Tech Stack:** WSL2 Ubuntu audio venv, Python 3.10, torch/torchvision/torchaudio `2.5.1+cu121`, `pyannote.audio==3.3.2`, `huggingface-hub==0.35.3`, proposed `transformers==4.43.3`, proposed `tokenizers==0.19.1`, proposed `safetensors==0.7.0`, `pytest`, `scripts/dev/run_pytest.ps1`.

---

## Current Evidence

- Execution checkpoint, 2026-05-08: the lane was qualified on the laptop with
  pinned `transformers==4.43.3`, `tokenizers==0.19.1`, and
  `safetensors==0.7.0`; no forbidden torch/PyAnnote/hub/numpy/scipy drift was
  observed, no-ingestion WSL smoke succeeded, and one-scene witness
  `20260508_173240_laptop_gpu_enhanced_one_scene_witness_wav2vec_artifact_fields`
  passed with Phase 6 complete, Qdrant ok, diarization success, Wav2Vec
  enrichment success, and `embedding_dim=768`.
- `wsl2_audio/process_audio.py` already contains optional Wav2Vec emotion and embedding paths guarded by `TRANSFORMERS_AVAILABLE`.
- When `transformers` is absent, runtime surfaces are truthful:
  - `emotion_status = "unavailable"`
  - `emotion_note = "transformers not installed"`
  - `embeddings_status = "unavailable"`
  - `embeddings_note = "transformers not installed"`
  - `speaker_voice_signature_meta.status = "unavailable"`
  - `speaker_voice_signature_meta.reason = "transformers_not_installed"`
- `scripts/wsl_audio_preflight.py` already requires the Wav2Vec model caches:
  - `ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition`
  - `facebook/wav2vec2-base-960h`
- `wsl2_audio/requirements-bootstrap-constraints.txt` is the active WSL package authority and currently omits `transformers`, `tokenizers`, and `safetensors`.
- `wsl2_audio/requirements-locked.txt` is explicitly historical and still reflects the rejected PyAnnote 4.x / torch 2.8 lane; do not use it as implementation authority.
- Existing step locks repeatedly use `transformers==4.43.3` and `tokenizers==0.19.1`; image/audio locks commonly use `safetensors==0.7.0`.

## Non-Goals

- Do not change the torch lane.
- Do not promote `2.8.0+cu128`.
- Do not update PyAnnote.
- Do not update Hugging Face Hub.
- Do not change ingestion orchestration.
- Do not require WSL-side emotion enrichment for baseline scene survival.
- Do not run broad ingestion before no-ingestion smoke passes.
- Do not use unpinned package installs.

## Files To Touch In A Future Implementation

- Modify: `wsl2_audio/requirements-bootstrap-constraints.txt`
  - Add the proposed pinned Wav2Vec dependency lane after dry-run qualification:
    - `transformers==4.43.3`
    - `tokenizers==0.19.1`
    - `safetensors==0.7.0`
- Modify: `wsl2_audio/setup_wsl2_audio.sh`
  - Ensure the install command explicitly requests `transformers`, `tokenizers`, and `safetensors` through the constraints file.
- Modify: `scripts/wsl2_quick_install.sh`
  - Keep quick install aligned with the canonical bootstrap constraints.
- Modify: `scripts/wsl_audio_preflight.py`
  - Add package-version probes for `transformers`, `tokenizers`, and `safetensors`.
  - Add a no-inference Wav2Vec import/cache probe.
  - Report `wav2vec_enrichment_ready` separately from `ready`.
- Modify: `wsl2_audio/process_audio.py`
  - Pass canonical HF cache dir into all Wav2Vec `from_pretrained(...)` calls.
  - Preserve optional semantics if Wav2Vec load fails.
- Modify: `tests/unit/test_bootstrap_install_wsl.py`
  - Prove constraints and installers request the pinned package lane.
- Modify: `tests/unit/test_wsl_audio_preflight.py`
  - Prove enrichment readiness is visible and separate from base WSL audio readiness.
- Modify: `tests/unit/test_wsl_process_audio_diarization.py`
  - Add focused Wav2Vec cache-dir tests beside the existing PyAnnote runtime cache-dir tests.
- Modify docs only after runtime proof:
  - `docs/reference/WSL_AUDIO_RUNTIME.md`
  - `docs/goodq4all_agent_status.md`
  - `docs/HANDOFF_BASEMENT_PHASE.md`
  - `docs/SYSTEM_SNAPSHOT.md`

---

### Task 1: Read-Only Package-Lane Audit

**Files:**
- Read: `wsl2_audio/requirements-bootstrap-constraints.txt`
- Read: `wsl2_audio/requirements-locked.txt`
- Read: `envs/locks/audio_diarize.lock.txt`
- Read: `envs/locks/audio_emotion.lock.txt`
- Read: `envs/locks/audio_embed.lock.txt`
- Read: `envs/locks/image_caption.lock.txt`
- Read: `scripts/wsl_audio_preflight.py`
- Read: `wsl2_audio/process_audio.py`

- [ ] **Step 1: Confirm canonical constraints omit Wav2Vec package lane**

Run:

```powershell
Select-String -Path wsl2_audio\requirements-bootstrap-constraints.txt -Pattern 'transformers|tokenizers|safetensors'
```

Expected:

```text
<no matches>
```

- [ ] **Step 2: Confirm stale WSL lock is not authority**

Run:

```powershell
Select-String -Path wsl2_audio\requirements-locked.txt -Pattern 'torch==|pyannote-audio==|huggingface-hub==|transformers==|tokenizers=='
```

Expected:

```text
torch==2.8.0
pyannote-audio==4.0.3
huggingface-hub==0.36.0
transformers==4.57.3
tokenizers==0.22.1
```

Interpretation:

```text
Historical drift snapshot only. Do not use as the target lane.
```

- [ ] **Step 3: Confirm proposed pins from active step locks**

Run:

```powershell
Select-String -Path envs\locks\audio_diarize.lock.txt,envs\locks\audio_emotion.lock.txt,envs\locks\audio_embed.lock.txt,envs\locks\image_caption.lock.txt -Pattern '^(transformers|tokenizers|safetensors|huggingface-hub|pyannote.audio)=='
```

Expected supporting evidence:

```text
transformers==4.43.3
tokenizers==0.19.1
huggingface-hub==0.35.3
pyannote.audio==3.3.2
```

Proposed lane for dry-run only:

```text
transformers==4.43.3
tokenizers==0.19.1
safetensors==0.7.0
```

- [ ] **Step 4: Commit nothing**

Expected:

```powershell
git status --short
```

Only pre-existing untracked local artifacts should appear.

### Task 2: Dry-Run The Proposed Lane Before Editing

**Files:**
- No file changes.

- [ ] **Step 1: Run WSL pip dry-run with canonical constraints and proposed packages**

Run:

```powershell
wsl -d Ubuntu-22.04 -- bash -lc "cd ~/goodq_audio && source ./setup_cuda_env.sh >/dev/null 2>&1 && python3 -m pip install --dry-run --no-cache-dir --constraint ./requirements-bootstrap-constraints.txt transformers==4.43.3 tokenizers==0.19.1 safetensors==0.7.0"
```

Expected:

```text
No torch upgrade is proposed.
No pyannote.audio upgrade is proposed.
No huggingface-hub upgrade is proposed.
No numpy/scipy upgrade is proposed.
```

- [ ] **Step 2: Fail the lane if pip proposes forbidden upgrades**

Reject the lane if the dry-run output includes any of:

```text
torch-2.8
torchvision-0.23
torchaudio-2.8
pyannote.audio-4
huggingface-hub-1
huggingface-hub-0.36
numpy-2.3
scipy-1.16
```

- [ ] **Step 3: Record dry-run evidence in the implementation notes**

Do not commit generated logs. Summarize:

```text
wsl_transformers_lane_qualification=pass|fail
torch_lane_preserved=true|false
pyannote_hub_pair_preserved=true|false
```

### Task 3: Add Failing Constraints And Installer Tests

**Files:**
- Modify: `tests/unit/test_bootstrap_install_wsl.py`

- [ ] **Step 1: Add the failing constraints assertions**

Add to `test_wsl_bootstrap_constraints_match_python310_cu121_lane()`:

```python
    assert pinned["transformers"] == "4.43.3"
    assert pinned["tokenizers"] == "0.19.1"
    assert pinned["safetensors"] == "0.7.0"

    assert "transformers==4.57.3" not in constraints
    assert "tokenizers==0.22.1" not in constraints
```

- [ ] **Step 2: Add installer request assertions**

Add to `test_wsl_audio_installers_use_bootstrap_constraints_and_post_install_validation()`:

```python
    for content in (shell_content, quick_content):
        assert "transformers" in content
        assert "tokenizers" in content
        assert "safetensors" in content
```

- [ ] **Step 3: Run the failing test**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\run_pytest.ps1 -q tests\unit\test_bootstrap_install_wsl.py::test_wsl_bootstrap_constraints_match_python310_cu121_lane tests\unit\test_bootstrap_install_wsl.py::test_wsl_audio_installers_use_bootstrap_constraints_and_post_install_validation
```

Expected:

```text
FAIL
```

Failure should show missing `transformers`, `tokenizers`, or `safetensors`.

### Task 4: Add The Minimal Package-Lane Pins

**Files:**
- Modify: `wsl2_audio/requirements-bootstrap-constraints.txt`
- Modify: `wsl2_audio/setup_wsl2_audio.sh`
- Modify: `scripts/wsl2_quick_install.sh`

- [ ] **Step 1: Add proposed pins to canonical constraints**

Add these lines to `wsl2_audio/requirements-bootstrap-constraints.txt` after `huggingface-hub==0.35.3`:

```text
transformers==4.43.3
tokenizers==0.19.1
safetensors==0.7.0
```

- [ ] **Step 2: Request packages through the constrained install**

In `wsl2_audio/setup_wsl2_audio.sh`, update the audio library install command to include:

```bash
    transformers \
    tokenizers \
    safetensors \
```

Keep the install under:

```bash
pip install -q \
    --constraint "$BOOTSTRAP_CONSTRAINTS_FILE" \
```

- [ ] **Step 3: Align quick install**

In `scripts/wsl2_quick_install.sh`, update the constrained install command so it requests:

```bash
transformers tokenizers safetensors
```

- [ ] **Step 4: Re-run focused bootstrap tests**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\run_pytest.ps1 -q tests\unit\test_bootstrap_install_wsl.py
```

Expected:

```text
PASS
```

- [ ] **Step 5: Commit package-lane pins only**

Stage explicitly:

```powershell
git add wsl2_audio/requirements-bootstrap-constraints.txt wsl2_audio/setup_wsl2_audio.sh scripts/wsl2_quick_install.sh tests/unit/test_bootstrap_install_wsl.py
git commit -m "fix: add wsl wav2vec transformer package lane"
```

### Task 5: Make Wav2Vec Runtime Loads Use Canonical Cache

**Files:**
- Modify: `wsl2_audio/process_audio.py`
- Modify: `tests/unit/test_wsl_process_audio_diarization.py`

- [ ] **Step 1: Add failing cache-dir tests for Wav2Vec emotion and embedding loads**

Add a focused test to `tests/unit/test_wsl_process_audio_diarization.py`:

```python
def test_process_audio_wav2vec_loads_use_canonical_hf_cache(monkeypatch, tmp_path: Path):
    from wsl2_audio import process_audio as mod

    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"wav")
    output_dir = tmp_path / "out"
    waveform = torch.zeros((1, 16000))
    captured: dict[str, list[dict[str, object]]] = {"calls": []}

    class _FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            info = types.SimpleNamespace(language="en", language_probability=1.0)
            return iter(()), info

    class _FakeFeatureExtractor:
        @classmethod
        def from_pretrained(cls, model_name, **kwargs):
            captured["calls"].append({"kind": "extractor", "model": model_name, **kwargs})
            return cls()

        def __call__(self, audio, sampling_rate, return_tensors, padding):
            return {"input_values": torch.zeros((1, 16000))}

    class _FakeEmotionModel:
        @classmethod
        def from_pretrained(cls, model_name, **kwargs):
            captured["calls"].append({"kind": "emotion_model", "model": model_name, **kwargs})
            return cls()

        def to(self, device):
            return self

        def __call__(self, **kwargs):
            return types.SimpleNamespace(logits=torch.tensor([[0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]))

    class _FakeEmbeddingModel:
        @classmethod
        def from_pretrained(cls, model_name, **kwargs):
            captured["calls"].append({"kind": "embedding_model", "model": model_name, **kwargs})
            return cls()

        def to(self, device):
            return self

        def __call__(self, **kwargs):
            return types.SimpleNamespace(last_hidden_state=torch.ones((1, 2, 3)))

    monkeypatch.setattr(mod, "_load_runtime_config", lambda: {
        "gpu": {"device": "cpu", "compute_type": "int8", "memory_fraction": 0.8},
        "models": {"whisper": "medium", "diarization": "pyannote/speaker-diarization-3.1"},
        "diarization": {"enabled": False},
        "processing": {"language": "en", "beam_size": 5},
        "_sources": [],
    })
    monkeypatch.setattr(mod, "require_gpu", lambda: False)
    monkeypatch.setattr(mod, "resolve_wsl_gpu_config", lambda cfg: dict(cfg))
    monkeypatch.setattr(mod.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(mod.torchaudio, "load", lambda _: (waveform.clone(), 16000))
    monkeypatch.setattr(mod, "WhisperModel", _FakeWhisperModel)
    monkeypatch.setattr(mod, "TRANSFORMERS_AVAILABLE", True)
    monkeypatch.setattr(mod, "Wav2Vec2ForSequenceClassification", _FakeEmotionModel)
    monkeypatch.setattr(mod, "Wav2Vec2FeatureExtractor", _FakeFeatureExtractor)
    monkeypatch.setattr(mod, "Wav2Vec2Model", _FakeEmbeddingModel)
    monkeypatch.setattr(mod, "clear_gpu_memory", lambda: None)
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", "/mnt/c/models/hub")

    result = mod.process_audio(str(audio_file), str(output_dir))

    assert result["emotion_status"] == "success"
    assert result["embeddings_status"] == "success"
    assert captured["calls"]
    assert all(call.get("cache_dir") == "/mnt/c/models/hub" for call in captured["calls"])
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\run_pytest.ps1 -q tests\unit\test_wsl_process_audio_diarization.py::test_process_audio_wav2vec_loads_use_canonical_hf_cache
```

Expected:

```text
FAIL
```

Failure should show missing `cache_dir` in one or more fake Wav2Vec calls.

- [ ] **Step 3: Patch Wav2Vec load calls**

In `wsl2_audio/process_audio.py`, add:

```python
wav2vec_cache_dir = _resolve_hf_cache_dir()
```

Use it in all Wav2Vec model/extractor loads:

```python
emotion_model = Wav2Vec2ForSequenceClassification.from_pretrained(
    "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
    cache_dir=wav2vec_cache_dir,
)
emotion_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
    "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
    cache_dir=wav2vec_cache_dir,
)
embed_model = Wav2Vec2Model.from_pretrained(
    "facebook/wav2vec2-base-960h",
    cache_dir=wav2vec_cache_dir,
)
embed_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
    "facebook/wav2vec2-base-960h",
    cache_dir=wav2vec_cache_dir,
)
```

- [ ] **Step 4: Re-run Wav2Vec tests**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\run_pytest.ps1 -q tests\unit\test_wsl_process_audio_diarization.py
```

Expected:

```text
PASS
```

- [ ] **Step 5: Commit runtime cache patch**

Stage explicitly:

```powershell
git add wsl2_audio/process_audio.py tests/unit/test_wsl_process_audio_diarization.py
git commit -m "fix: load wsl wav2vec models from canonical cache"
```

### Task 6: Add Enrichment Readiness To WSL Preflight

**Files:**
- Modify: `scripts/wsl_audio_preflight.py`
- Modify: `tests/unit/test_wsl_audio_preflight.py`

- [ ] **Step 1: Add failing preflight output-shape test**

Add to `tests/unit/test_wsl_audio_preflight.py`:

```python
def test_probe_wsl_audio_runtime_reports_wav2vec_enrichment_ready(monkeypatch):
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
        if "Wav2Vec2Model" in script:
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
    assert result["detected_versions"]["transformers"] == "4.43.3"
```

- [ ] **Step 2: Add degraded enrichment test**

Add:

```python
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
        if "Wav2Vec2Model" in script:
            return type("Probe", (), {"returncode": 0, "stdout": "wav2vec_enrichment_unavailable\ntransformers import failed\n", "stderr": ""})()
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
```

- [ ] **Step 3: Implement minimal preflight fields**

In `scripts/wsl_audio_preflight.py`, extend package inventory:

```python
"packages = ['torch', 'torchvision', 'torchaudio', 'torchcodec', 'pyannote.audio', 'faster-whisper', 'transformers', 'tokenizers', 'safetensors']\n"
```

Add detected versions:

```python
"transformers": package_versions.get("transformers"),
"tokenizers": package_versions.get("tokenizers"),
"safetensors": package_versions.get("safetensors"),
```

Add an enrichment probe script that imports:

```python
from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForSequenceClassification, Wav2Vec2Model
```

The probe should print exactly one of:

```text
wav2vec_enrichment_ready
wav2vec_enrichment_unavailable
```

Do not make `ready` false solely because Wav2Vec enrichment is unavailable. Add `wav2vec_enrichment_unavailable` to `runtime_warnings`.

- [ ] **Step 4: Run preflight tests**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\run_pytest.ps1 -q tests\unit\test_wsl_audio_preflight.py
```

Expected:

```text
PASS
```

- [ ] **Step 5: Commit preflight visibility**

Stage explicitly:

```powershell
git add scripts/wsl_audio_preflight.py tests/unit/test_wsl_audio_preflight.py
git commit -m "fix: expose wsl wav2vec enrichment readiness"
```

### Task 7: Run No-Ingestion WSL Qualification

**Files:**
- No source changes.
- Optional temp output only under a temp directory.

- [ ] **Step 1: Repair or create WSL venv only after package-lane pins are committed**

Run the bootstrap repair path that syncs WSL assets and applies constraints. Do not run ingestion.

Preferred:

```powershell
python scripts\bootstrap_install.py --yes --enable-wsl-audio --no-launch
```

If persistent service install needs sudo, allow the bootstrap to return `PENDING_SUDO` without treating direct WSL execution as failed.

- [ ] **Step 2: Run WSL package version probe**

Run:

```powershell
wsl -d Ubuntu-22.04 -- bash -lc "cd ~/goodq_audio && source ./setup_cuda_env.sh >/dev/null 2>&1 && python3 - <<'PY'
import importlib.metadata as md
for name in ['torch','torchvision','torchaudio','pyannote.audio','huggingface-hub','transformers','tokenizers','safetensors','faster-whisper']:
    try:
        print(f'{name}={md.version(name)}')
    except Exception as exc:
        print(f'{name}=MISSING:{type(exc).__name__}')
PY"
```

Expected:

```text
torch=2.5.1+cu121
torchvision=0.20.1+cu121
torchaudio=2.5.1+cu121
pyannote.audio=3.3.2
huggingface-hub=0.35.3
transformers=4.43.3
tokenizers=0.19.1
safetensors=0.7.0
faster-whisper=1.2.1
```

- [ ] **Step 3: Run Wav2Vec offline load probe**

Run:

```powershell
wsl -d Ubuntu-22.04 -- bash -lc "cd ~/goodq_audio && source ./setup_cuda_env.sh >/dev/null 2>&1 && python3 - <<'PY'
import os
from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForSequenceClassification, Wav2Vec2Model
cache_dir = os.getenv('HUGGINGFACE_HUB_CACHE') or os.getenv('HF_HUB_CACHE')
for model_name, loader in [
    ('ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition', Wav2Vec2ForSequenceClassification),
    ('ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition', Wav2Vec2FeatureExtractor),
    ('facebook/wav2vec2-base-960h', Wav2Vec2Model),
    ('facebook/wav2vec2-base-960h', Wav2Vec2FeatureExtractor),
]:
    loader.from_pretrained(model_name, cache_dir=cache_dir, local_files_only=True)
    print(f'ok {model_name} {loader.__name__}')
PY"
```

Expected:

```text
ok ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition Wav2Vec2ForSequenceClassification
ok ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition Wav2Vec2FeatureExtractor
ok facebook/wav2vec2-base-960h Wav2Vec2Model
ok facebook/wav2vec2-base-960h Wav2Vec2FeatureExtractor
```

- [ ] **Step 4: Run short audio processor smoke**

Use a tiny local audio fixture or synthesize one inside WSL:

```powershell
wsl -d Ubuntu-22.04 -- bash -lc "cd ~/goodq_audio && source ./setup_cuda_env.sh >/dev/null 2>&1 && python3 - <<'PY'
import json
import math
import os
import wave
from pathlib import Path
audio = Path('/tmp/goodq_wav2vec_probe.wav')
sr = 16000
with wave.open(str(audio), 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sr)
    frames = bytearray()
    for i in range(sr):
        val = int(8000 * math.sin(2 * math.pi * 440 * i / sr))
        frames += int(val).to_bytes(2, 'little', signed=True)
    w.writeframes(frames)
out = Path('/tmp/goodq_wav2vec_probe_out')
from process_audio import process_audio
result = process_audio(str(audio), str(out))
print(json.dumps({
    'status': result.get('status'),
    'emotion_status': result.get('emotion_status'),
    'embeddings_status': result.get('embeddings_status'),
    'speaker_voice_signature_meta': result.get('speaker_voice_signature_meta'),
}, sort_keys=True))
PY"
```

Expected acceptable result:

```json
{"embeddings_status":"success","emotion_status":"success","speaker_voice_signature_meta":{"reason":"diarization_unavailable","status":"skipped"},"status":"success"}
```

If synthetic tone produces an emotion model error, rerun with a known speech fixture before rejecting the lane.

### Task 8: One-Scene Witness Gate

**Files:**
- Generated witness artifacts only; do not commit.

- [ ] **Step 1: Run one controlled `GPU_ENHANCED` scene witness**

Use the same laptop material as the previous one-scene witness if available. Do not run a full episode yet.

- [ ] **Step 2: Inspect required output fields**

Confirm in scene results and manifest:

```text
audio_unified_wsl2 status=ok
diarization_status=success
emotion_status=success
embeddings_status=success
speaker_voice_signature_meta.status=ok|skipped
phase6_complete=true
qdrant_ok=true
```

- [ ] **Step 3: Confirm non-blocking semantics**

If Wav2Vec enrichment still fails:

```text
status=success
emotion_status=error|unavailable
embeddings_status=error|unavailable
speaker_voice_signature_meta.status=error|unavailable
phase6_complete=true
qdrant_ok=true
```

Classify this as optional-enrichment degradation, not pipeline failure.

### Task 9: Documentation Close-Out

**Files:**
- Modify: `docs/reference/WSL_AUDIO_RUNTIME.md`
- Modify: `docs/goodq4all_agent_status.md`
- Modify: `docs/HANDOFF_BASEMENT_PHASE.md`
- Modify: `docs/SYSTEM_SNAPSHOT.md`

- [ ] **Step 1: Update WSL runtime doctrine**

Add a short note:

```markdown
### WSL Wav2Vec Enrichment Lane

WSL audio base readiness is transcription + diarization + ABI/cache readiness.
Wav2Vec emotion, Wav2Vec embeddings, and speaker voice signatures are optional
enrichment surfaces. When the pinned `transformers` lane is present and the
Wav2Vec caches are available, preflight reports `wav2vec_enrichment_ready=true`.
When absent, runtime must surface `emotion_status` / `embeddings_status` as
`unavailable` rather than hiding the miss.
```

- [ ] **Step 2: Update handoff/status docs**

Record:

```text
WSL-side Wav2Vec enrichment package lane qualified: yes|no
transformers pin: 4.43.3 if qualified
tokenizers pin: 0.19.1 if qualified
safetensors pin: 0.7.0 if qualified
base WSL audio readiness remains separate from optional enrichment readiness
```

- [ ] **Step 3: Validate docs**

Run:

```powershell
python scripts\docs\doc_drift_lint.py
git diff --check
```

Expected:

```text
doc_drift_lint summary ... active_drive_root_violations=0
```

- [ ] **Step 4: Commit docs**

Stage explicitly:

```powershell
git add docs/reference/WSL_AUDIO_RUNTIME.md docs/goodq4all_agent_status.md docs/HANDOFF_BASEMENT_PHASE.md docs/SYSTEM_SNAPSHOT.md
git commit -m "docs: record wsl wav2vec enrichment lane"
```

## Final Validation Bundle

Run before any push:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\run_pytest.ps1 -q tests\unit\test_bootstrap_install_wsl.py tests\unit\test_wsl_audio_preflight.py tests\unit\test_wsl_process_audio_diarization.py tests\unit\test_phase6_audio_artifact_path_unified.py
python scripts\docs\doc_drift_lint.py
git diff --check
```

Run changed-file path scan:

```powershell
$files = git diff --name-only
if ($files) {
  $driveRootPattern = ('C:' + '\\') + '|' + ('L:' + '/') + '|' + ('\\' * 2) + 'wsl' + '\$'
  Select-String -Path $files -Pattern $driveRootPattern
}
```

Expected:

```text
No path leak hits in active changed files.
All targeted tests pass.
No ingestion was run until the one-scene witness gate.
```

## Decision Gates

- **Reject lane:** pip dry-run proposes torch, PyAnnote, hub, numpy, or scipy drift.
- **Defer lane:** no-ingestion Wav2Vec load fails from canonical cache even after package pins install.
- **Accept package lane:** dry-run preserves canonical pins, WSL package probe matches expected versions, offline Wav2Vec loads succeed, short audio smoke emits Wav2Vec status truthfully.
- **Record runtime doctrine:** one-scene witness shows base WSL audio remains healthy and optional Wav2Vec enrichment is either successful or truthfully degraded without Phase 6/Qdrant compromise.

## Commit Plan

Use separate commits:

```text
fix: add wsl wav2vec transformer package lane
fix: load wsl wav2vec models from canonical cache
fix: expose wsl wav2vec enrichment readiness
docs: record wsl wav2vec enrichment lane
```

Do not combine these with unrelated bootstrap, ingestion, recurrence, or docs cleanup work.

## Self-Review

- Spec coverage:
  - `transformers` presence is qualified before install.
  - WSL package lane remains pinned.
  - Wav2Vec runtime uses canonical cache.
  - Base WSL readiness remains separate from optional Wav2Vec enrichment.
  - One-scene witness remains the first ingestion gate.
- Placeholder scan:
  - No plan-rule placeholder markers or broad "handle errors" instructions remain.
- Type consistency:
  - Proposed fields use consistent names: `wav2vec_enrichment_ready`, `runtime_warnings`, `emotion_status`, `embeddings_status`, `speaker_voice_signature_meta`.
