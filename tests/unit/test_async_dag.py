import os
import json
import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cli.run_ingestion import (
    _run_step_async,
    _make_async_step_envelope,
    _process_frame_async,
    _process_audio_async,
)

def test_make_async_step_envelope():
    envelope = _make_async_step_envelope(
        step_name="test_step",
        status="ok",
        outputs={"key": "val"},
        errors=None,
        duration_seconds=1.5,
        retry_count=0
    )
    assert envelope["step_name"] == "test_step"
    assert envelope["status"] == "ok"
    assert envelope["outputs"] == {"key": "val"}
    assert envelope["errors"] is None
    assert envelope["duration_seconds"] == 1.5
    assert envelope["retry_count"] == 0
    assert "started_at" in envelope
    assert "finished_at" in envelope

def test_run_step_async_basic(tmp_path):
    async def run_test():
        cfg_json = tmp_path / "config.json"
        cfg_json.write_text("{}", encoding="utf-8")
        
        mock_proc = AsyncMock()
        mock_proc.pid = 9999
        mock_proc.communicate.return_value = (b"{}", b"")
        mock_proc.returncode = 0
        
        # Patch create_subprocess_exec to return our mock process
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            with patch("cli.run_ingestion.resolve_conda", return_value="conda"):
                with patch("cli.run_ingestion.shutil.which", return_value="conda"):
                    envelope = await _run_step_async(
                        env_name="test_env",
                        step_name="test_step",
                        payload={"some": "payload"},
                        cfg_json=cfg_json
                    )
                    
                    assert mock_create.called
                    assert envelope["step_name"] == "test_step"
                    assert envelope["status"] == "ok"
                    assert envelope["outputs"] == {}
                    
    asyncio.run(run_test())

def test_supervised_gather_on_exception(tmp_path):
    async def run_test():
        # Verify that if one task fails, gather(..., return_exceptions=True) lets the other complete
        async def task_success():
            await asyncio.sleep(0.01)
            return {"status": "ok", "outputs": {"result": "success"}}
            
        async def task_failure():
            await asyncio.sleep(0.01)
            raise ValueError("Something went wrong")
            
        results = await asyncio.gather(task_success(), task_failure(), return_exceptions=True)
        
        assert len(results) == 2
        assert results[0] == {"status": "ok", "outputs": {"result": "success"}}
        assert isinstance(results[1], Exception)
        assert str(results[1]) == "Something went wrong"
        
    asyncio.run(run_test())

def test_cancellation_teardown(tmp_path):
    async def run_test():
        cfg_json = tmp_path / "config.json"
        cfg_json.write_text("{}", encoding="utf-8")
        
        mock_proc = AsyncMock()
        mock_proc.pid = 9999
        mock_proc.terminate = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock(return_value=0)
        
        # Simulate cancellation during communicate
        mock_proc.communicate.side_effect = asyncio.CancelledError()
        
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("cli.run_ingestion.resolve_conda", return_value="conda"):
                with patch("cli.run_ingestion.shutil.which", return_value="conda"):
                    with pytest.raises(asyncio.CancelledError):
                        await _run_step_async(
                            env_name="test_env",
                            step_name="test_step",
                            payload={"some": "payload"},
                            cfg_json=cfg_json
                        )
                        
                    # Verify subprocess teardown occurred
                    assert mock_proc.terminate.called
                    
    asyncio.run(run_test())

def test_db_and_faiss_locking():
    async def run_test():
        db_lock = asyncio.Lock()
        faiss_lock = asyncio.Lock()
        
        db_call_order = []
        faiss_call_order = []
        
        async def db_operation(name, delay):
            async with db_lock:
                db_call_order.append(f"{name}_start")
                await asyncio.sleep(delay)
                db_call_order.append(f"{name}_end")
                
        async def faiss_operation(name, delay):
            async with faiss_lock:
                faiss_call_order.append(f"{name}_start")
                await asyncio.sleep(delay)
                faiss_call_order.append(f"{name}_end")
                
        # Run them concurrently - lock should serialize them
        await asyncio.gather(
            db_operation("task1", 0.02),
            db_operation("task2", 0.01),
            faiss_operation("task1", 0.02),
            faiss_operation("task2", 0.01),
        )
        
        # Verify db locking serialization: task1 should fully complete before task2 starts, or vice versa
        assert (db_call_order[0] == "task1_start" and db_call_order[1] == "task1_end" and db_call_order[2] == "task2_start") or \
               (db_call_order[0] == "task2_start" and db_call_order[1] == "task2_end" and db_call_order[2] == "task1_start")
               
        # Verify faiss locking serialization
        assert (faiss_call_order[0] == "task1_start" and faiss_call_order[1] == "task1_end" and faiss_call_order[2] == "task2_start") or \
               (faiss_call_order[0] == "task2_start" and faiss_call_order[1] == "task2_end" and faiss_call_order[2] == "task1_start")
               
    asyncio.run(run_test())
