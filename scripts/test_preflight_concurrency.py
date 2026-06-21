import subprocess
import time
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_preflight(index):
    # Stagger startup to prevent wsl.exe VM console/socket initialization collisions on Windows
    stagger_delay = (index - 1) * 1.5
    print(f"[Thread {index}] Waiting {stagger_delay:.1f}s to stagger WSL startup...")
    time.sleep(stagger_delay)
    
    start = time.time()
    cmd = [sys.executable, "scripts/wsl_audio_preflight.py", "--compact"]
    print(f"[Thread {index}] Starting preflight check...")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        duration = time.time() - start
        return {
            "index": index,
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "duration": duration,
            "stdout": proc.stdout,
            "stderr": proc.stderr
        }
    except Exception as e:
        duration = time.time() - start
        return {
            "index": index,
            "success": False,
            "error": str(e),
            "duration": duration
        }

def main():
    concurrency = 5
    print(f"Starting concurrency test for preflight check with {concurrency} workers using {sys.executable}...")
    
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(run_preflight, i): i for i in range(1, concurrency + 1)}
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            print(f"[Thread {res['index']}] Finished in {res['duration']:.2f}s (Success: {res['success']})")
            
    print("\n--- Summary of Concurrent Preflight Runs ---")
    all_success = True
    for res in sorted(results, key=lambda x: x["index"]):
        if not res["success"]:
            all_success = False
            print(f"Run {res['index']}: FAILED (rc={res.get('returncode')}, err={res.get('error')})")
            print(f"  stdout: {res.get('stdout', '').strip()}")
            print(f"  stderr: {res.get('stderr', '').strip()}")
        else:
            # Parse output
            try:
                data = json.loads(res["stdout"])
                ready = data.get("ready")
                abi_ready = data.get("abi_ready")
                diarization_ready = data.get("diarization_ready")
                print(f"Run {res['index']}: PASSED - ready={ready}, abi_ready={abi_ready}, diarization_ready={diarization_ready}")
            except Exception as e:
                all_success = False
                print(f"Run {res['index']}: FAILED to parse JSON stdout: {e}")
                print(f"  stdout: {res['stdout']}")
                
    if all_success:
        print("\nAll concurrent preflight runs completed successfully. Thread safety verified!")
        sys.exit(0)
    else:
        print("\nSome concurrent preflight runs failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
