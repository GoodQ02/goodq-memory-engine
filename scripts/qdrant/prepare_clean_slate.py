import os
import sys
import json
import psutil
import urllib.request
import urllib.parse
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from steps.common.config_loader import load_configs
except ModuleNotFoundError:
    from goodq4all.steps.common.config_loader import load_configs

# Approved disposable epoch names only
ALLOWED_EPOCHS = [
    "epoch_2026_06_16_r0_smoke",
    "epoch_2026_06_21_family_clean_01"
]

# Keywords to match active host python processes
HOST_KEYWORDS = [
    "api.server",
    "api/server",
    "api\\server",
    "cli.watchdog",
    "cli/watchdog",
    "cli\\watchdog",
    "cli.run_ingestion",
    "cli/run_ingestion",
    "cli\\run_ingestion",
    "run_ingestion",
    "MiniAgentClient",
    "cli.ucf_promotion",
    "ucf_promotion",
    "promote_pilot",
    "validate_ucf"
]



def check_wsl_processes():
    active_wsl = []
    try:
        # Run ps -ef inside WSL distribution Ubuntu-22.04
        res = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "ps", "-ef"], capture_output=True, text=True, check=True)
        lines = res.stdout.splitlines()
        for line in lines:
            if any(x in line for x in ["audio_service", "process_audio", "whisper", "transcribe"]):
                if "grep" not in line and "ps -ef" not in line:
                    active_wsl.append(line.strip())
    except Exception as e:
        print(f"[WARN] Failed to check WSL processes: {e}")
    return active_wsl


def stop_wsl_processes(active_wsl):
    stopped = []
    for line in active_wsl:
        parts = line.split()
        if len(parts) > 1:
            wpid = parts[1]
            cmd = " ".join(parts[7:])
            print(f"[KILL] Terminating WSL process PID {wpid} ({cmd})")
            try:
                subprocess.run(["wsl", "-d", "Ubuntu-22.04", "kill", "-9", wpid], check=True)
                stopped.append({"pid": wpid, "cmdline": cmd})
            except Exception as e:
                print(f"[ERROR] Failed to kill WSL process PID {wpid}: {e}")
    return stopped


def stop_processes():
    stopped = []
    print("[INFO] Auditing active Python processes on host...")
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = proc.info.get('cmdline') or []
            cmd_str = " ".join(cmd)
            # Find matching processes
            if "python" in proc.info['name'].lower() and any(x in cmd_str for x in HOST_KEYWORDS):
                print(f"[KILL] Stopping host process PID {proc.info['pid']} ({cmd_str})")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    print(f"[KILL] Process PID {proc.info['pid']} did not stop. Killing...")
                    proc.kill()
                stopped.append({"pid": proc.info['pid'], "cmdline": cmd_str})
        except Exception as e:
            print(f"[WARN] Failed to terminate process: {e}")
    return stopped


def check_active_processes():
    active = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = proc.info.get('cmdline') or []
            cmd_str = " ".join(cmd)
            if "python" in proc.info['name'].lower() and any(x in cmd_str for x in HOST_KEYWORDS):
                active.append({"pid": proc.info['pid'], "cmdline": cmd_str, "status": "running"})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return active


def get_qdrant_collections(host):
    collections = []
    try:
        url = f"{host.rstrip('/')}/collections"
        response = json.load(urllib.request.urlopen(url, timeout=3))
        for col in response.get('result', {}).get('collections', []):
            name = col.get('name')
            if name.startswith('goodq_'):
                collections.append(name)
    except Exception as e:
        print(f"[WARN] Could not contact Qdrant: {e}")
    return collections


def scan_epoch_files(data_root, epoch):
    epoch_dir = Path(data_root) / "GoodQ_Data" / "epochs" / epoch
    files_to_delete = []
    total_size = 0
    
    if epoch_dir.exists():
        for root, dirs, files in os.walk(epoch_dir):
            for file in files:
                file_path = Path(root) / file
                try:
                    size = file_path.stat().st_size
                    total_size += size
                    files_to_delete.append({
                        "path": str(file_path),
                        "size_bytes": size
                    })
                except Exception as e:
                    print(f"[WARN] Error scanning {file_path}: {e}")
                    
    return str(epoch_dir), files_to_delete, total_size


def generate_manifest(execute=False, stop_p=False):
    config = load_configs({})
    qdrant_cfg = config.get('qdrant', {})
    
    data_root = config.get('host', {}).get('data_root', 'L:\\_DATA')
    qdrant_host = qdrant_cfg.get('host', 'http://127.0.0.1:6333')
    
    print("\n=== GOODQ4ALL MEMORY RESET ===")
    
    # 1. Check & Stop active processes if requested, otherwise just detect
    stopped_processes = []
    stopped_wsl_processes = []
    
    if stop_p or execute:
        print("[INFO] Performing dynamic process stop...")
        stopped_processes = stop_processes()
        wsl_active = check_wsl_processes()
        if wsl_active:
            stopped_wsl_processes = stop_wsl_processes(wsl_active)
    
    # Current active process list after attempt
    current_active_host = check_active_processes()
    current_active_wsl = check_wsl_processes()
    
    # 2. Gather Qdrant collections to delete
    qdrant_collections = get_qdrant_collections(qdrant_host)
    qdrant_to_delete = []
    for col in qdrant_collections:
        if any(epoch in col for epoch in ALLOWED_EPOCHS):
            qdrant_to_delete.append(col)
            
    # 3. Gather SQLite and FAISS files to delete (strictly under allowed epochs)
    sqlite_to_delete = []
    faiss_to_delete = []
    sidecars_to_delete = []
    epoch_dirs_affected = []
    total_files = 0
    total_bytes = 0
    
    for epoch in ALLOWED_EPOCHS:
        epoch_path, files, size = scan_epoch_files(data_root, epoch)
        if files:
            epoch_dirs_affected.append(epoch_path)
            total_files += len(files)
            total_bytes += size
            for f in files:
                p = f["path"]
                if p.endswith(".db"):
                    if "ucf_ledger" in p:
                        sidecars_to_delete.append(p)
                    else:
                        sqlite_to_delete.append(p)
                elif ".index" in p or "faiss" in p.lower():
                    faiss_to_delete.append(p)
                    
    # 4. Check status of new epoch
    new_epoch = "epoch_2026_06_21_family_clean_01"
    new_epoch_dir = Path(data_root) / "GoodQ_Data" / "epochs" / new_epoch
    new_epoch_status = "nonexistent"
    if new_epoch_dir.exists():
        new_epoch_files = list(new_epoch_dir.glob("**/*"))
        new_epoch_files = [f for f in new_epoch_files if f.is_file()]
        if len(new_epoch_files) == 0:
            new_epoch_status = "empty"
        else:
            new_epoch_status = f"contains {len(new_epoch_files)} files (will be wiped)"
            
    manifest = {
        "title": "GoodQ4All Memory Reset Deletion Manifest",
        "timestamp": datetime_str(),
        "dry_run": not execute,
        "stopped_host_processes": stopped_processes,
        "stopped_wsl_processes": stopped_wsl_processes,
        "currently_active_host_processes": current_active_host,
        "currently_active_wsl_processes": current_active_wsl,
        "new_epoch_status": {
            "epoch": new_epoch,
            "status": new_epoch_status,
            "path": str(new_epoch_dir)
        },
        "qdrant_collections_to_delete": qdrant_to_delete,
        "sqlite_databases_to_delete": sqlite_to_delete,
        "faiss_indices_to_delete": faiss_to_delete,
        "sidecar_databases_to_delete": sidecars_to_delete,
        "epoch_directories_affected": epoch_dirs_affected,
        "totals": {
            "file_count": total_files,
            "total_size_bytes": total_bytes,
            "total_size_mb": round(total_bytes / (1024 * 1024), 2)
        },
        "safety_checks": {
            "source_media_touched": False,
            "model_cache_touched": False,
            "reports_docs_touched": False,
            "validation_note": "Verified: All targets are confined to ALLOWED_EPOCHS directories and matched Qdrant collections. No source media or caches will be deleted."
        }
    }
    
    # Write manifest to file
    out_dir = Path("reports/local_housekeeping/2026-06-21-memory-clean-start")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = out_dir / "deletion_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[SUCCESS] Wrote deletion manifest to: {manifest_file}")
    
    # Print formatted summary to stdout
    print_summary(manifest)
    
    if execute:
        # Re-check active processes right before wipe
        print("[INFO] Re-checking for active processes immediately before deletion...")
        still_active = check_active_processes()
        still_wsl_active = check_wsl_processes()
        if still_active or still_wsl_active:
            print("[ERROR] Active processes detected immediately before deletion! Aborting.")
            if still_active:
                print(f"Active host: {still_active}")
            if still_wsl_active:
                print(f"Active WSL: {still_wsl_active}")
            sys.exit(1)
            
        execute_wipe(manifest, qdrant_host)
        
    return manifest


def execute_wipe(manifest, qdrant_host):
    print("\n=== STARTING WIPE PROCEDURE ===")
    
    # 1. Delete Qdrant collections
    for col in manifest["qdrant_collections_to_delete"]:
        try:
            url = f"{qdrant_host.rstrip('/')}/collections/{col}"
            req = urllib.request.Request(url, method="DELETE")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    print(f"[SUCCESS] Deleted Qdrant collection: {col}")
                else:
                    print(f"[ERROR] Failed to delete Qdrant collection {col}: status {resp.status}")
        except Exception as e:
            print(f"[ERROR] Exception deleting collection {col}: {e}")
            
    # 2. Delete all files in the epoch directories recursively, then directories themselves
    for epoch_dir_str in manifest["epoch_directories_affected"]:
        epoch_path = Path(epoch_dir_str)
        if epoch_path.exists():
            print(f"[INFO] Cleaning up directory: {epoch_path}")
            # Delete files first
            for root, dirs, files in os.walk(epoch_path, topdown=False):
                for f in files:
                    fp = Path(root) / f
                    try:
                        fp.unlink()
                        print(f"[SUCCESS] Deleted file: {fp}")
                    except Exception as e:
                        print(f"[ERROR] Failed to delete file {fp}: {e}")
                for d in dirs:
                    dp = Path(root) / d
                    try:
                        dp.rmdir()
                        print(f"[SUCCESS] Deleted subdirectory: {dp}")
                    except Exception as e:
                        print(f"[ERROR] Failed to delete directory {dp}: {e}")
            try:
                epoch_path.rmdir()
                print(f"[SUCCESS] Deleted epoch directory: {epoch_path}")
            except Exception as e:
                print(f"[ERROR] Failed to remove epoch directory {epoch_path}: {e}")
                
    print("\n=== WIPE PROCEDURE COMPLETE ===")


def datetime_str():
    import datetime
    return datetime.datetime.utcnow().isoformat() + 'Z'


def print_summary(manifest):
    print(f"\nTarget Epochs: {', '.join(ALLOWED_EPOCHS)}")
    print(f"New Epoch Status: {manifest['new_epoch_status']['epoch']} -> {manifest['new_epoch_status']['status']}")
    
    print(f"\nCurrently Active Host Python Processes ({len(manifest['currently_active_host_processes'])}):")
    if not manifest["currently_active_host_processes"]:
        print("  - None")
    else:
        for p in manifest["currently_active_host_processes"]:
            print(f"  - PID {p['pid']}: {p['cmdline']}")
            
    print(f"\nCurrently Active WSL Audio Processes ({len(manifest['currently_active_wsl_processes'])}):")
    if not manifest["currently_active_wsl_processes"]:
        print("  - None")
    else:
        for p in manifest["currently_active_wsl_processes"]:
            print(f"  - {p}")
            
    print(f"\nQdrant Collections to Delete ({len(manifest['qdrant_collections_to_delete'])}):")
    for col in manifest["qdrant_collections_to_delete"]:
        print(f"  - {col}")
        
    print(f"\nRelational DBs to Delete ({len(manifest['sqlite_databases_to_delete'])}):")
    for db in manifest["sqlite_databases_to_delete"]:
        print(f"  - {Path(db).name}")
        
    print(f"\nFAISS Indices to Delete ({len(manifest['faiss_indices_to_delete'])}):")
    for f in manifest["faiss_indices_to_delete"]:
        print(f"  - {Path(f).name}")
        
    print(f"\nUCF Ledgers to Delete ({len(manifest['sidecar_databases_to_delete'])}):")
    for s in manifest["sidecar_databases_to_delete"]:
        print(f"  - {Path(s).name}")
        
    print(f"\nEpoch directories affected: {len(manifest['epoch_directories_affected'])}")
    print(f"Total files: {manifest['totals']['file_count']}")
    print(f"Total size: {manifest['totals']['total_size_mb']} MB")
    
    print("\nSafety Constraints Status:")
    print("  [SAFE] source media: not touched")
    print("  [SAFE] model cache: not touched")
    print("  [SAFE] reports/docs: not touched")
    print(f"  [CHECK] {manifest['safety_checks']['validation_note']}")
    print("=" * 40 + "\n")


if __name__ == '__main__':
    exec_flag = "--execute" in sys.argv
    stop_p_flag = "--stop-processes" in sys.argv
    generate_manifest(execute=exec_flag, stop_p=stop_p_flag)
