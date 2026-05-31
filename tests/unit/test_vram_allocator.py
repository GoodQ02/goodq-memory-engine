import os
import json
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from common.vram_allocator import VRAMAllocator, FileLock, STEP_VRAM_FRACTIONS, REGISTRY_PATH, LOCK_PATH

@pytest.fixture(autouse=True)
def clean_registry():
    # Remove registry and lock files if they exist before/after test
    for path in [REGISTRY_PATH, LOCK_PATH]:
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
    yield
    for path in [REGISTRY_PATH, LOCK_PATH]:
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

def test_vram_allocator_budget_limit():
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

def test_vram_allocator_physical_limit():
    allocator = VRAMAllocator(budget_fraction=0.90)
    
    # Mock total GPU VRAM = 10,000 MB, used = 8,000 MB (already very high!)
    with patch.object(allocator, "query_gpu_memory", return_value=(10000, 8000)):
        with patch("common.vram_allocator.pid_exists", return_value=True):
            # audio_diarize requires 3500 MB.
            # Physical usage would become 8000 + 3500 = 11500 MB, which exceeds 95% of total (9500 MB)
            assert not allocator.reserve("audio_diarize", 33333)

def test_vram_allocator_update_pid():
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

def test_run_step_integration_with_vram_allocator_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("GOODQ_TEST_VRAM_ALLOCATOR", "1")
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "GPU_ENHANCED")
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "0")
    
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
