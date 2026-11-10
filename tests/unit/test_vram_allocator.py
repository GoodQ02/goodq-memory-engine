import os
import json
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from common.vram_allocator import VRAMAllocator, FileLock, STEP_VRAM_FRACTIONS, REGISTRY_PATH, LOCK_PATH

@pytest.fixture
def simulated_gpu(monkeypatch):
    """Allocator arithmetic uses fake GPU memory, independently of host policy."""
    # A daemon could wake after monkeypatch restores the real registry paths.
    # These tests exercise reservations synchronously, not heartbeat scheduling.
    monkeypatch.setattr(VRAMAllocator, "start_heartbeat_daemon", lambda *args, **kwargs: None)
    for key in ("GOODQ_FORCE_CPU", "GOODQ_NO_AUTO_GPU", "GOODQ_CLAP_FORCE_CPU"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "GPU_ENHANCED")
    monkeypatch.setenv("GOODQ_DEVICE", "cuda")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")

@pytest.fixture(autouse=True)
def clean_registry(tmp_path, monkeypatch):
    mock_dir = tmp_path / "vram_registry"
    mock_dir.mkdir(parents=True, exist_ok=True)
    mock_reg = mock_dir / "vram_registry.json"
    mock_lock = mock_dir / "vram_registry.lock"
    
    import common.vram_allocator
    monkeypatch.setattr(common.vram_allocator, "REGISTRY_DIR", mock_dir)
    monkeypatch.setattr(common.vram_allocator, "REGISTRY_PATH", mock_reg)
    monkeypatch.setattr(common.vram_allocator, "LOCK_PATH", mock_lock)
    
    import sys
    for mod_name, mod in list(sys.modules.items()):
        if mod_name.endswith("test_vram_allocator") and mod:
            monkeypatch.setattr(mod, "REGISTRY_PATH", mock_reg)
            monkeypatch.setattr(mod, "LOCK_PATH", mock_lock)

    # Remove registry and lock files if they exist before/after test
    for path in [mock_reg, mock_lock]:
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
    yield
    for path in [mock_reg, mock_lock]:
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass

def test_file_lock_acquisition():
    # Test simple lock acquisition
    with FileLock() as lock:
        assert lock.has_lock
        assert LOCK_PATH.exists()
        
        # Nested acquisition should fail (timeout)
        with pytest.raises(TimeoutError):
            with FileLock(timeout=0.1, delay=0.01):
                pass
                
    assert not LOCK_PATH.exists()

def test_file_lock_stale_cleanup():
    # Create a stale lock file (backdate it)
    LOCK_PATH.touch()
    stale_time = time.time() - 40.0
    os.utime(LOCK_PATH, (stale_time, stale_time))
    
    # New FileLock should automatically clean it up and acquire
    with FileLock(timeout=0.5) as lock:
        assert lock.has_lock
        assert LOCK_PATH.exists()
    assert not LOCK_PATH.exists()

def test_query_gpu_memory():
    allocator = VRAMAllocator()
    
    # Mock successful nvidia-smi run
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "8192, 2048\n"
        
        total, used = allocator.query_gpu_memory()
        assert total == 8192
        assert used == 2048
        
    # Mock failed nvidia-smi run
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("not found")
        
        total, used = allocator.query_gpu_memory()
        assert total == 0
        assert used == 0

def test_clean_stale_claims():
    allocator = VRAMAllocator(stale_timeout_sec=10.0)
    
    registry = {
        "99999": {
            "step_name": "audio_diarize",
            "start_time": time.time(),
            "command": "",
            "claimed_vram_mb": 1000,
            "updated_at": time.time()
        },
        "88888": {
            "step_name": "image_caption",
            "start_time": time.time() - 20.0,
            "command": "",
            "claimed_vram_mb": 1000,
            "updated_at": time.time() - 20.0 # timed out
        }
    }
    
    with patch("common.vram_allocator.pid_exists") as mock_pid:
        # Mock 99999 as active, 88888 as active (but timed out)
        mock_pid.side_effect = lambda pid: pid == 99999
        
        cleaned = allocator.clean_stale_claims(registry)
        # 99999 is kept because active and not timed out
        assert "99999" in cleaned
        # 88888 is pruned because it's timed out (or because pid_exists would return False)
        assert "88888" not in cleaned

def test_vram_allocator_budget_limit(simulated_gpu):
    allocator = VRAMAllocator(budget_fraction=0.50)
    
    # Mock total GPU VRAM = 10,000 MB, used = 1,000 MB
    with patch.object(allocator, "query_gpu_memory", return_value=(10000, 1000)):
        with patch("common.vram_allocator.pid_exists", return_value=True):
            # Reserve for audio_diarize (fraction 0.35, req = 3500 MB)
            assert allocator.reserve("audio_diarize", 11111)
            
            # Now we have 3500 MB claimed. Attempting to reserve audio_transcribe (fraction 0.25, req = 2500 MB)
            # Total claims would be 3500 + 2500 = 6000 MB, which is > 5000 MB budget (0.50 * 10000)
            assert not allocator.reserve("audio_transcribe", 22222)
            
            # Releasing 11111 should allow 22222 to be reserved
            allocator.release(11111)
            assert allocator.reserve("audio_transcribe", 22222)

def test_vram_allocator_physical_limit(simulated_gpu):
    allocator = VRAMAllocator(budget_fraction=0.90)
    
    # Mock total GPU VRAM = 10,000 MB, used = 8,000 MB (already very high!)
    with patch.object(allocator, "query_gpu_memory", return_value=(10000, 8000)):
        with patch("common.vram_allocator.pid_exists", return_value=True):
            # audio_diarize requires 3500 MB.
            # Physical usage would become 8000 + 3500 = 11500 MB, which exceeds 95% of total (9500 MB)
            assert not allocator.reserve("audio_diarize", 33333)

def test_vram_allocator_update_pid(simulated_gpu):
    allocator = VRAMAllocator()
    with patch.object(allocator, "query_gpu_memory", return_value=(10000, 1000)):
        with patch("common.vram_allocator.pid_exists", return_value=True):
            # Reserve using temporary PID
            assert allocator.reserve("audio_diarize", 123)
            
            # Update to subprocess PID
            allocator.update_pid(123, 456)
            
            # Read registry to verify
            registry = allocator._read_registry()
            assert "123" not in registry
            assert "456" in registry
            assert registry["456"]["step_name"] == "audio_diarize"

def test_independent_reservations_share_parent_without_overwrite(monkeypatch, simulated_gpu):
    allocator = VRAMAllocator()
    monkeypatch.setattr(allocator, "query_gpu_memory", lambda: (10000, 0))
    monkeypatch.setattr(allocator, "start_heartbeat_daemon", lambda *a: None)
    monkeypatch.setattr("common.vram_allocator.pid_exists", lambda pid: True)
    assert allocator.reserve("audio_embed_clap", 123, reservation_id="launch-a")
    assert allocator.reserve("image_embed_clip", 123, reservation_id="launch-b")
    assert sum(c["claimed_vram_mb"] for c in allocator._read_registry().values()) == 4500
    allocator.update_pid("launch-b", 222)
    allocator.update_pid("launch-a", 111)
    claims = allocator._read_registry()
    assert claims["launch-a"]["pid"] == 111
    assert claims["launch-a"]["step_name"] == "audio_embed_clap"
    assert claims["launch-b"]["pid"] == 222
    allocator.release("launch-a")
    assert set(allocator._read_registry()) == {"launch-b"}
    allocator.release("launch-a")  # repeated cleanup must not affect a sibling
    assert set(allocator.clean_stale_claims(allocator._read_registry())) == {"launch-b"}
    monkeypatch.setattr("common.vram_allocator.pid_exists", lambda pid: False)
    assert allocator.clean_stale_claims(allocator._read_registry()) == {}


def test_cancel_during_reservation_releases_late_grant(monkeypatch, simulated_gpu):
    import threading
    allocator = VRAMAllocator()
    cancel = threading.Event()
    monkeypatch.setattr(allocator, "query_gpu_memory", lambda: (10000, 0))
    monkeypatch.setattr(allocator, "start_heartbeat_daemon", lambda *a: None)
    reserve = allocator.reserve
    def grant_then_cancel(*args, **kwargs):
        result = reserve(*args, **kwargs)
        assert "cancelled" in allocator._read_registry()
        cancel.set()
        return result
    monkeypatch.setattr(allocator, "reserve", grant_then_cancel)
    assert not allocator.wait_and_reserve("audio_embed_clap", os.getpid(),
                                         reservation_id="cancelled", cancel_event=cancel)
    assert allocator._read_registry() == {}


def test_run_step_integration_with_vram_allocator_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("GOODQ_TEST_VRAM_ALLOCATOR", "1")
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "GPU_ENHANCED")
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "0")
    monkeypatch.delenv("GOODQ_NO_AUTO_GPU", raising=False)
    
    # Mock wait_and_reserve to return False (indicating VRAM limit breached)
    with patch("common.vram_allocator.VRAMAllocator.wait_and_reserve", return_value=False):
        from cli.run_ingestion import _run_step
        
        mock_popen = MagicMock()
        mock_popen.pid = 9999
        mock_popen.communicate.return_value = ("{}", "")
        mock_popen.returncode = 0
        
        captured_env = {}
        def fake_popen(cmd, env, **kwargs):
            nonlocal captured_env
            captured_env = env
            return mock_popen
            
        monkeypatch.setattr("subprocess.Popen", fake_popen)
        monkeypatch.setattr("cli.run_ingestion.resolve_conda", lambda: "conda")
        monkeypatch.setattr("cli.run_ingestion.shutil.which", lambda _: "conda")
        
        cfg_json = tmp_path / "config.json"
        cfg_json.write_text("{}", encoding="utf-8")
        
        payload = {
            "source_path": str(tmp_path / "scene_0001.jpg"),
            "video_id": "test_video",
            "scene_id": "scene_0001",
        }
        
        # Run a GPU step: dino
        result = _run_step(
            env_name="goodq_image_caption",
            step_name="image_embed_dino",
            payload=payload,
            cfg_json=cfg_json
        )
        
        # Check that preflight allocation rejection triggered CPU fallback env variables
        assert captured_env.get("GOODQ_NO_AUTO_GPU") == "1"
        assert captured_env.get("GOODQ_DINO_FORCE_CPU") == "1"


def test_vram_allocator_follows_effective_backend_for_object_detect_and_emotion_classify(monkeypatch):
    allocator = VRAMAllocator(budget_fraction=0.90)
    monkeypatch.setattr(allocator, "query_gpu_memory", lambda: (10000, 1000))
    monkeypatch.setattr(allocator, "start_heartbeat_daemon", lambda *a: None)
    monkeypatch.setattr("common.vram_allocator.pid_exists", lambda pid: True)
    monkeypatch.delenv("GOODQ_FORCE_CPU", raising=False)
    monkeypatch.delenv("GOODQ_NO_AUTO_GPU", raising=False)
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "GPU_ENHANCED")

    assert STEP_VRAM_FRACTIONS["object_detect"] == 0.25
    assert STEP_VRAM_FRACTIONS["emotion_classify"] == 0.20
    assert "face_embed" not in STEP_VRAM_FRACTIONS

    # When effective backend resolves to CPU, reserve() succeeds without claiming GPU VRAM
    monkeypatch.setattr("steps.object_detect.step.resolve_effective_device", lambda **_k: "cpu")
    monkeypatch.setattr("steps.emotion_classify.step.resolve_effective_device", lambda **_k: "cpu")
    assert allocator.reserve("object_detect", 501, reservation_id="od-cpu")
    assert allocator.reserve("emotion_classify", 502, reservation_id="emo-cpu")
    assert allocator._read_registry() == {}

    # When effective backend resolves to CUDA, reserve() checks budget and records VRAM claims
    monkeypatch.setattr("steps.object_detect.step.resolve_effective_device", lambda **_k: "cuda")
    monkeypatch.setattr("steps.emotion_classify.step.resolve_effective_device", lambda **_k: "cuda")
    assert allocator.reserve("object_detect", 503, reservation_id="od-gpu")
    assert allocator.reserve("emotion_classify", 504, reservation_id="emo-gpu")
    claims = allocator._read_registry()
    assert claims["od-gpu"]["claimed_vram_mb"] == 2500
    assert claims["emo-gpu"]["claimed_vram_mb"] == 2000


def test_vram_allocator_reserve_honors_worker_env_when_parent_is_baseline(monkeypatch):
    # Parent environment is marked CPU-baseline, but worker policy_env is GPU_ENHANCED.
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "BASELINE")
    worker_gpu_env = {
        "GOODQ_HOST_PROFILE": "GPU_ENHANCED",
        "GOODQ_NO_AUTO_GPU": "0",
        "GOODQ_FORCE_CPU": "0",
        "CUDA_VISIBLE_DEVICES": "0",
    }
    allocator = VRAMAllocator(budget_fraction=0.90, env=worker_gpu_env, conda_env="goodq_image_caption")
    monkeypatch.setattr(allocator, "query_gpu_memory", lambda: (10000, 1000))
    monkeypatch.setattr(allocator, "start_heartbeat_daemon", lambda *a: None)
    monkeypatch.setattr("common.vram_allocator.pid_exists", lambda pid: True)

    assert allocator.reserve("image_caption", 701, reservation_id="worker-gpu")
    claims = allocator._read_registry()
    assert "worker-gpu" in claims
    assert claims["worker-gpu"]["claimed_vram_mb"] == 4000

    # Conversely, when parent is GPU_ENHANCED and worker is BASELINE, reserve() creates no claim.
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "GPU_ENHANCED")
    assert allocator.reserve(
        "image_caption",
        702,
        reservation_id="worker-cpu",
        env={"GOODQ_HOST_PROFILE": "BASELINE"},
    )
    assert "worker-cpu" not in allocator._read_registry()


def test_object_detect_probes_worker_runtime_instead_of_parent_process(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import steps.object_detect.step as od_step

    monkeypatch.setenv("CONDA_DEFAULT_ENV", "goodq_core")
    monkeypatch.setattr(od_step, "_WORKER_ORT_CUDA_CACHE", {})
    monkeypatch.setattr(od_step, "_sealed_model_path", lambda _model_id: tmp_path / "yolox.onnx")

    fake_worker_python = tmp_path / "goodq_object_detect_python.exe"
    fake_worker_python.write_bytes(b"exe")
    monkeypatch.setattr("configs.python_paths.get_env_python", lambda env_name: fake_worker_python if env_name == "goodq_object_detect" else None)

    probed_cmds = []

    def _probe_cuda_supported(cmd, **_kw):
        probed_cmds.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", _probe_cuda_supported)
    worker_env = {"GOODQ_HOST_PROFILE": "GPU_ENHANCED", "GOODQ_NO_AUTO_GPU": "0", "CUDA_VISIBLE_DEVICES": "0"}
    assert od_step.resolve_effective_device(env=worker_env, conda_env="goodq_object_detect") == "cuda"
    assert len(probed_cmds) == 1
    assert str(fake_worker_python.resolve()) == probed_cmds[0][0]
    assert "onnxruntime" in probed_cmds[0][2] and "CUDAExecutionProvider" in probed_cmds[0][2]

    # Reset cache and verify a CPU-only worker ONNX Runtime reports 'cpu'
    monkeypatch.setattr(od_step, "_WORKER_ORT_CUDA_CACHE", {})
    monkeypatch.setattr("subprocess.run", lambda cmd, **_kw: SimpleNamespace(returncode=1, stdout="", stderr=""))
    assert od_step.resolve_effective_device(env=worker_env, conda_env="goodq_object_detect") == "cpu"

def test_failed_object_detect_probe_is_unknown_and_not_cached_as_cpu(monkeypatch, tmp_path):
    import subprocess
    from types import SimpleNamespace
    import steps.object_detect.step as od_step
    from common.vram_allocator import step_uses_gpu_backend

    monkeypatch.setenv("CONDA_DEFAULT_ENV", "goodq_core")
    monkeypatch.setattr(od_step, "_WORKER_ORT_CUDA_CACHE", {})
    monkeypatch.setattr(od_step, "_sealed_model_path", lambda _model_id: tmp_path / "yolox.onnx")

    fake_worker_python = tmp_path / "goodq_object_detect_python.exe"
    fake_worker_python.write_bytes(b"exe")
    monkeypatch.setattr(
        "configs.python_paths.get_env_python",
        lambda env_name: fake_worker_python if env_name == "goodq_object_detect" else None,
    )
    worker_env = {
        "GOODQ_HOST_PROFILE": "GPU_ENHANCED",
        "GOODQ_NO_AUTO_GPU": "0",
        "CUDA_VISIBLE_DEVICES": "0",
    }

    # 1. TimeoutExpired must return 'unknown', leave cache empty, and require conservative GPU admission
    def _raise_timeout(cmd, **_kw):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)

    monkeypatch.setattr("subprocess.run", _raise_timeout)
    assert od_step.resolve_effective_device(env=worker_env, conda_env="goodq_object_detect") == "unknown"
    assert od_step._WORKER_ORT_CUDA_CACHE == {}
    assert step_uses_gpu_backend("object_detect", env=worker_env, conda_env="goodq_object_detect") is True

    # 2. Subprocess crash (returncode=1 with traceback) must also be treated as 'unknown' and not cached
    monkeypatch.setattr(
        "subprocess.run",
        lambda cmd, **_kw: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="Traceback (most recent call last):\nImportError: DLL load failed",
        ),
    )
    assert od_step.resolve_effective_device(env=worker_env, conda_env="goodq_object_detect") == "unknown"
    assert od_step._WORKER_ORT_CUDA_CACHE == {}

    # 3. Because failed probes were not cached, a subsequent successful probe resolves to 'cuda' and caches True
    monkeypatch.setattr(
        "subprocess.run",
        lambda cmd, **_kw: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    assert od_step.resolve_effective_device(env=worker_env, conda_env="goodq_object_detect") == "cuda"
    assert od_step._WORKER_ORT_CUDA_CACHE[str(fake_worker_python.resolve())] is True


def test_run_step_and_run_step_async_failed_object_probe_cannot_launch_unreserved_cuda_worker(monkeypatch, tmp_path):
    import asyncio
    import subprocess
    from types import SimpleNamespace
    import steps.object_detect.step as od_step
    from cli.run_ingestion import _run_step, _run_step_async

    monkeypatch.setenv("GOODQ_TEST_VRAM_ALLOCATOR", "1")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "goodq_core")
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "GPU_ENHANCED")
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "0")
    monkeypatch.delenv("GOODQ_NO_AUTO_GPU", raising=False)
    monkeypatch.delenv("GOODQ_FORCE_CPU", raising=False)
    monkeypatch.delenv("GOODQ_OBJECT_DETECT_FORCE_CPU", raising=False)

    monkeypatch.setattr(od_step, "_WORKER_ORT_CUDA_CACHE", {})
    monkeypatch.setattr(od_step, "_sealed_model_path", lambda _model_id: tmp_path / "yolox.onnx")

    fake_worker_python = tmp_path / "goodq_object_detect_python.exe"
    fake_worker_python.write_bytes(b"exe")
    monkeypatch.setattr(
        "configs.python_paths.get_env_python",
        lambda env_name: fake_worker_python if env_name == "goodq_object_detect" else None,
    )
    monkeypatch.setattr("cli.run_ingestion.resolve_conda", lambda: "conda")
    monkeypatch.setattr("cli.run_ingestion.shutil.which", lambda _: "conda")

    # Simulate probe timeout whenever _onnxruntime_supports_cuda probes fake_worker_python
    def _fake_subprocess_run(cmd, **_kw):
        if cmd and str(cmd[0]) == str(fake_worker_python.resolve()):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)
        return SimpleNamespace(returncode=0, stdout="10000, 1000\n", stderr="")

    monkeypatch.setattr("subprocess.run", _fake_subprocess_run)
    monkeypatch.setattr("common.vram_allocator.VRAMAllocator.start_heartbeat_daemon", lambda *a: None)
    monkeypatch.setattr("common.vram_allocator.pid_exists", lambda pid: True)

    cfg_json = tmp_path / "config.json"
    cfg_json.write_text("{}", encoding="utf-8")
    payload = {
        "source_path": str(tmp_path / "scene_0001.jpg"),
        "video_id": "test_video",
        "scene_id": "scene_0001",
    }

    # --- Subcase A: VRAM available -> both _run_step and _run_step_async MUST reserve VRAM before worker runs ---
    sync_registry_during_run = {}
    mock_popen = MagicMock()
    mock_popen.pid = 41001
    mock_popen.returncode = 0

    def _sync_communicate(**_kw):
        nonlocal sync_registry_during_run
        sync_registry_during_run = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        return ('{"objects": [], "detect_meta": {"status": "ok"}}', "")

    mock_popen.communicate.side_effect = _sync_communicate
    monkeypatch.setattr("subprocess.Popen", lambda cmd, env, **_kw: mock_popen)

    _run_step("goodq_object_detect", "object_detect", payload, cfg_json)
    assert len(sync_registry_during_run) == 1
    claim_sync = next(iter(sync_registry_during_run.values()))
    assert claim_sync["step_name"] == "object_detect"
    assert claim_sync["claimed_vram_mb"] == 2500
    assert claim_sync["pid"] == 41001
    assert od_step._WORKER_ORT_CUDA_CACHE == {}

    async_registry_during_run = {}

    class _FakeAsyncProc:
        pid = 41002
        returncode = 0

        async def communicate(self):
            nonlocal async_registry_during_run
            async_registry_during_run = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
            return (b'{"objects": [], "detect_meta": {"status": "ok"}}', b"")

    async def _fake_create_subprocess_exec(*cmd, **kwargs):
        return _FakeAsyncProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_create_subprocess_exec)
    async_res = asyncio.run(_run_step_async("goodq_object_detect", "object_detect", payload, cfg_json))
    assert async_res["status"] == "ok"
    assert len(async_registry_during_run) == 1
    claim_async = next(iter(async_registry_during_run.values()))
    assert claim_async["step_name"] == "object_detect"
    assert claim_async["claimed_vram_mb"] == 2500
    assert claim_async["pid"] == 41002

    # --- Subcase B: VRAM admission denied (GOODQ_REQUIRE_GPU=0) -> both callers force CPU on the worker ---
    monkeypatch.setattr("common.vram_allocator.VRAMAllocator.wait_and_reserve", lambda *a, **kw: False)

    sync_captured_env = {}
    mock_popen.communicate.side_effect = None
    mock_popen.communicate.return_value = ('{"objects": [], "detect_meta": {"status": "ok"}}', "")

    def _capture_sync_popen(cmd, env, **_kw):
        nonlocal sync_captured_env
        sync_captured_env = dict(env)
        return mock_popen

    monkeypatch.setattr("subprocess.Popen", _capture_sync_popen)
    _run_step("goodq_object_detect", "object_detect", payload, cfg_json)
    assert sync_captured_env.get("GOODQ_NO_AUTO_GPU") == "1"
    assert sync_captured_env.get("GOODQ_OBJECT_DETECT_FORCE_CPU") == "1"
    assert od_step._force_cpu(sync_captured_env) is True
    assert od_step._yolox_device(sync_captured_env) == "cpu"

    async_captured_env = {}

    async def _capture_async_exec(*cmd, **kwargs):
        nonlocal async_captured_env
        async_captured_env = dict(kwargs.get("env") or {})
        return _FakeAsyncProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", _capture_async_exec)
    asyncio.run(_run_step_async("goodq_object_detect", "object_detect", payload, cfg_json))
    assert async_captured_env.get("GOODQ_NO_AUTO_GPU") == "1"
    assert async_captured_env.get("GOODQ_OBJECT_DETECT_FORCE_CPU") == "1"
    assert od_step._force_cpu(async_captured_env) is True
    assert od_step._yolox_device(async_captured_env) == "cpu"

    # --- Subcase C: Required-GPU admission failure blocks launch and remains visible in error evidence ---
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "1")
    launched = []
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: launched.append("sync") or mock_popen)
    monkeypatch.setattr("asyncio.create_subprocess_exec", lambda *a, **kw: launched.append("async"))

    with pytest.raises(RuntimeError, match="VRAM allocation failed for GPU-required step 'object_detect'"):
        _run_step("goodq_object_detect", "object_detect", payload, cfg_json)

    err_envelope = asyncio.run(_run_step_async("goodq_object_detect", "object_detect", payload, cfg_json))
    assert err_envelope["status"] == "error"
    assert "VRAM allocation failed for GPU-required step 'object_detect'" in str(err_envelope.get("errors"))
    assert launched == []


def test_emotion_classify_cpu_parent_cuda_worker_reserves_vram_and_confirmed_cpu_worker_skips(monkeypatch, tmp_path):
    import subprocess
    from types import SimpleNamespace
    import steps.emotion_classify.step as emo_step

    # Configure parent process as CPU-only across all parent state surfaces
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "goodq_cpu_parent")
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "BASELINE")
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")
    monkeypatch.setenv("GOODQ_FORCE_CPU", "1")
    monkeypatch.setenv("GOODQ_DEVICE", "cpu")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "-1")
    monkeypatch.setattr(emo_step, "setup_step_gpu", lambda _step: {"device": "cpu"})
    monkeypatch.setattr("steps.common.device_config.device_config._device_kind", "cpu")
    monkeypatch.setattr("steps.common.device_config.device_config._initialized", True)
    monkeypatch.setitem(emo_step._EMO, "model", object())
    monkeypatch.setitem(emo_step._EMO, "device", "cpu")
    monkeypatch.setattr(emo_step, "_WORKER_EMOTION_CUDA_CACHE", {})
    monkeypatch.setattr(
        emo_step,
        "_resolve_emotion_snapshot",
        lambda: (
            tmp_path / "snapshot",
            "cardiffnlp/twitter-roberta-base-emotion-latest",
            "415620c4fbc8bd82b82b9fd46642fcec6519d537",
        ),
    )

    fake_worker_python = tmp_path / "goodq_core_python.exe"
    fake_worker_python.write_bytes(b"exe")
    monkeypatch.setattr(
        "configs.python_paths.get_env_python",
        lambda env_name: fake_worker_python if env_name in {"goodq_core", "goodq_emotion"} else None,
    )

    probed_envs = []

    def _probe_cuda_worker(cmd, **kw):
        probed_envs.append(dict(kw.get("env") or {}))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", _probe_cuda_worker)

    worker_gpu_env = {
        "GOODQ_HOST_PROFILE": "GPU_ENHANCED",
        "GOODQ_NO_AUTO_GPU": "0",
        "GOODQ_FORCE_CPU": "0",
        "CUDA_VISIBLE_DEVICES": "0",
    }

    # 1. CPU parent + CUDA worker resolves to 'cuda' and reserves 2000 MB VRAM
    assert emo_step.resolve_effective_device(env=worker_gpu_env, conda_env="goodq_core") == "cuda"
    assert len(probed_envs) == 1
    assert probed_envs[0].get("GOODQ_DEVICE") is None
    assert probed_envs[0].get("CUDA_VISIBLE_DEVICES") == "0"

    allocator = VRAMAllocator(budget_fraction=0.90, env=worker_gpu_env, conda_env="goodq_core")
    monkeypatch.setattr(allocator, "query_gpu_memory", lambda: (10000, 1000))
    monkeypatch.setattr(allocator, "start_heartbeat_daemon", lambda *a: None)
    monkeypatch.setattr("common.vram_allocator.pid_exists", lambda pid: True)

    assert allocator.reserve("emotion_classify", 801, reservation_id="emo-cuda-worker")
    claims = allocator._read_registry()
    assert "emo-cuda-worker" in claims
    assert claims["emo-cuda-worker"]["claimed_vram_mb"] == 2000
    allocator.release("emo-cuda-worker")

    # 2. Confirmed CPU worker via worker env flag skips reservation
    assert emo_step.resolve_effective_device(env={"GOODQ_HOST_PROFILE": "BASELINE"}, conda_env="goodq_core") == "cpu"
    assert allocator.reserve(
        "emotion_classify",
        802,
        reservation_id="emo-cpu-env",
        env={"GOODQ_HOST_PROFILE": "BASELINE"},
        conda_env="goodq_core",
    )
    assert allocator._read_registry() == {}

    # 3. Confirmed CPU worker via worker interpreter probe (returncode=1) skips reservation
    monkeypatch.setattr(emo_step, "_WORKER_EMOTION_CUDA_CACHE", {})
    monkeypatch.setattr(
        "subprocess.run",
        lambda cmd, **_kw: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )
    assert emo_step.resolve_effective_device(env=worker_gpu_env, conda_env="goodq_core") == "cpu"
    assert allocator.reserve(
        "emotion_classify",
        803,
        reservation_id="emo-cpu-probe",
        env=worker_gpu_env,
        conda_env="goodq_core",
    )
    assert allocator._read_registry() == {}

    # 4. Confirmed CPU worker when pinned safetensors snapshot is unavailable skips reservation
    monkeypatch.setattr(emo_step, "_WORKER_EMOTION_CUDA_CACHE", {})
    monkeypatch.setattr("subprocess.run", _probe_cuda_worker)
    monkeypatch.setattr(
        emo_step,
        "_resolve_emotion_snapshot",
        lambda: (_ for _ in ()).throw(OSError("missing pinned safetensors snapshot")),
    )
    assert emo_step.resolve_effective_device(env=worker_gpu_env, conda_env="goodq_core") == "cpu"
    assert allocator.reserve(
        "emotion_classify",
        804,
        reservation_id="emo-no-snapshot",
        env=worker_gpu_env,
        conda_env="goodq_core",
    )
    assert allocator._read_registry() == {}

    # 5. Failed emotion probe (timeout) is treated as 'unknown' (not cached) and conservatively reserves VRAM
    monkeypatch.setattr(
        emo_step,
        "_resolve_emotion_snapshot",
        lambda: (
            tmp_path / "snapshot",
            "cardiffnlp/twitter-roberta-base-emotion-latest",
            "415620c4fbc8bd82b82b9fd46642fcec6519d537",
        ),
    )
    monkeypatch.setattr(emo_step, "_WORKER_EMOTION_CUDA_CACHE", {})
    monkeypatch.setattr(
        "subprocess.run",
        lambda cmd, **_kw: (_ for _ in ()).throw(subprocess.TimeoutExpired(cmd=cmd, timeout=10)),
    )
    assert emo_step.resolve_effective_device(env=worker_gpu_env, conda_env="goodq_core") == "unknown"
    assert emo_step._WORKER_EMOTION_CUDA_CACHE == {}
    assert allocator.reserve(
        "emotion_classify",
        805,
        reservation_id="emo-unknown-probe",
        env=worker_gpu_env,
        conda_env="goodq_core",
    )
    assert allocator._read_registry()["emo-unknown-probe"]["claimed_vram_mb"] == 2000
