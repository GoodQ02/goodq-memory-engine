import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from scripts.wsl_audio_preflight import probe_wsl_audio_runtime

def test_preflight_concurrency_execution():
    """Run the preflight check multiple times concurrently to test thread safety and system response."""
    distro = "Ubuntu-22.04"
    workspace = "/home/jdben/goodq_audio"
    num_threads = 5
    
    print(f"\nStarting {num_threads} concurrent preflight check runs...")
    
    start_time = time.time()
    
    results = []
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {
            executor.submit(probe_wsl_audio_runtime, distro, workspace): i
            for i in range(num_threads)
        }
        
        for future in as_completed(futures):
            thread_idx = futures[future]
            try:
                result = future.result()
                results.append((thread_idx, result, None))
                print(f"Thread {thread_idx} finished successfully.")
            except Exception as e:
                results.append((thread_idx, None, e))
                print(f"Thread {thread_idx} failed with exception: {e}")
                
    end_time = time.time()
    total_duration = end_time - start_time
    print(f"All runs completed in {total_duration:.2f} seconds.")
    
    assert len(results) == num_threads
    
    failures = 0
    for idx, res, err in results:
        if err is not None:
            failures += 1
            print(f"Failure in Thread {idx}: {err}")
        else:
            ready = res.get("ready")
            distro_used = res.get("distro")
            workspace_used = res.get("workspace")
            print(f"Thread {idx} Result - Ready: {ready}, Distro: {distro_used}, Workspace: {workspace_used}")
            # Assert each thread succeeded and probed correctly
            assert ready is True
            assert distro_used == distro
            assert workspace_used == workspace
            
    assert failures == 0, f"Expected 0 failures, got {failures}"
