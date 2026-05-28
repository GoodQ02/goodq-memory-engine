#!/usr/bin/env python
"""Hydrates a locked, verified runtime from a vendored wheelhouse or signed package manifest,
and downloads, verifies, and installs chunked model assets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
from typing import Any, Dict, List

def _log(msg: str) -> None:
    print(msg, file=sys.stdout, flush=True)

def _err(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr, flush=True)

def compute_sha256(filepath: Path) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()

def check_disk_space(path: Path, required_bytes: int) -> bool:
    try:
        total, used, free = shutil.disk_usage(path.anchor)
        return free >= required_bytes
    except Exception:
        # Fallback to true if drive is not queryable (e.g. some network paths)
        return True

def download_chunk(
    url: str,
    temp_dest: Path,
    expected_size: int,
    expected_hash: str,
    mirrors: List[str] = None
) -> bool:
    urls = [url]
    if mirrors:
        # Generate mirror URLs by replacing base host
        base_path = url.split("releases/download/v1.0.0-models")[-1]
        for mirror in mirrors:
            urls.append(mirror.rstrip("/") + base_path)

    for attempt_url in urls:
        _log(f"Attempting download from: {attempt_url}")
        
        # Range/Resume check
        start_bytes = 0
        if temp_dest.exists():
            start_bytes = temp_dest.stat().st_size
            if start_bytes == expected_size:
                _log(f"Chunk already complete locally: {temp_dest.name}")
                if compute_sha256(temp_dest) == expected_hash:
                    return True
                _log(f"Checksum mismatch for cached chunk {temp_dest.name}. Discarding and restarting.")
                temp_dest.unlink()
                start_bytes = 0
            elif start_bytes > expected_size:
                _log(f"Cached chunk {temp_dest.name} is larger than expected. Discarding and restarting.")
                temp_dest.unlink()
                start_bytes = 0

        req = urllib.request.Request(attempt_url)
        if start_bytes > 0:
            req.add_header("Range", f"bytes={start_bytes}-")
            mode = "ab"
            _log(f"Resuming download from byte: {start_bytes}")
        else:
            mode = "wb"

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                status = response.getcode()
                # Status 206 is Partial Content (range supported)
                # Status 200 means whole file is served
                if start_bytes > 0 and status != 206:
                    _log("Server does not support Range. Restarting full download.")
                    temp_dest.unlink(missing_ok=True)
                    mode = "wb"
                
                with open(temp_dest, mode) as f:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        f.write(block)
            
            # Verify hash
            local_hash = compute_sha256(temp_dest)
            if local_hash == expected_hash:
                _log(f"Successfully downloaded and verified: {temp_dest.name}")
                return True
            else:
                _err(f"SHA256 checksum mismatch for chunk: {temp_dest.name} (Got: {local_hash}, Expected: {expected_hash})")
                temp_dest.unlink(missing_ok=True)
        except Exception as e:
            _err(f"Download failed from {attempt_url}: {e}")
            continue

    return False

def merge_chunks(chunks_paths: List[Path], final_dest: Path, expected_hash: str) -> bool:
    _log(f"Merging chunks into: {final_dest.name}...")
    temp_final = final_dest.with_suffix(".merge_tmp")
    try:
        with open(temp_final, "wb") as outfile:
            for path in chunks_paths:
                with open(path, "rb") as infile:
                    shutil.copyfileobj(infile, outfile)
        
        # Verify final hash
        final_hash = compute_sha256(temp_final)
        if final_hash == expected_hash:
            os.replace(temp_final, final_dest)
            _log("[OK] Merge completed and verified.")
            return True
        else:
            _err(f"SHA256 mismatch for merged archive: {final_dest.name} (Got: {final_hash}, Expected: {expected_hash})")
            temp_final.unlink(missing_ok=True)
    except Exception as e:
        _err(f"Failed to merge chunks: {e}")
        try:
            temp_final.unlink(missing_ok=True)
        except Exception:
            pass
    return False

def extract_archive(archive_path: Path, target_dir: Path) -> bool:
    _log(f"Extracting {archive_path.name} to {target_dir}...")
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
        _log(f"[OK] Extraction complete.")
        return True
    except Exception as e:
        _err(f"Failed to extract archive: {e}")
        return False

def hydrate_wheelhouse(runtime_dir: Path) -> None:
    # Executed inside installer step 6 to run wheel setup from locked wheelhouse
    wheelhouse = runtime_dir.parent / "wheelhouse"
    if not wheelhouse.exists():
        _log("No local wheelhouse detected; skipping offline package hydration.")
        return

    _log("Hydrating runtime environment from locked wheelhouse...")
    # Run pip locally using embedded python environment options
    pip_exe = runtime_dir / "Scripts" / "pip.exe"
    if not pip_exe.exists():
        pip_exe = runtime_dir / "pip.exe"

    python_exe = runtime_dir / "python.exe"
    
    # Run: python.exe -m pip install --no-index --find-links=wheelhouse -r requirements.lock.txt
    lock_file = runtime_dir.parent / "requirements.lock.txt"
    if not lock_file.exists():
        return

    import subprocess
    cmd = [
        str(python_exe), "-m", "pip", "install", 
        "--no-index", 
        f"--find-links={wheelhouse}", 
        "-r", str(lock_file)
    ]
    _log(f"Running hydration command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        _err(f"Pip hydration failed: {result.stderr}")
    else:
        _log("[OK] Locked environment hydrated successfully.")

def main() -> None:
    parser = argparse.ArgumentParser(description="GoodQ4All Sandboxed Hydration and Downloader")
    parser.add_argument("--packs", default="core", help="Comma-separated model packs to download")
    parser.add_argument("--data-dir", default="C:\\ProgramData\\GoodQ4All", help="Authoritative data root")
    parser.add_argument("--verify-only", action="store_true", help="Perform checksum checks without downloading")
    parser.add_argument("--cache-dir", default=None, help="Local directory to check for model files/chunks before downloading")
    args = parser.parse_args()

    data_root = Path(args.data_dir)
    models_root = data_root / "models"
    models_root.mkdir(parents=True, exist_ok=True)
    
    manifest_path = Path(__file__).resolve().parents[2] / "configs" / "model_download_manifest.json"
    if not manifest_path.exists():
        manifest_path = Path(os.getcwd()) / "configs" / "model_download_manifest.json"

    if not manifest_path.exists():
        _err(f"Model download manifest not found at: {manifest_path}")
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    selected_pack_keys = [p.strip() for p in args.packs.split(",") if p.strip()]
    if args.verify_only:
        # Verification runs over all registered/installed packs
        registry_path = data_root / ".model_packs_installed.json"
        if registry_path.exists():
            with open(registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
                selected_pack_keys = list(registry.keys())
        else:
            selected_pack_keys = ["core_memory"]

    # 1. Pre-calculate Required Disk Space
    required_space = 0
    packs_to_process = []
    for pack_key in selected_pack_keys:
        pack_manifest = manifest["model_packs"].get(pack_key)
        if not pack_manifest:
            _err(f"Selected pack '{pack_key}' is not defined in manifest.")
            sys.exit(1)
        packs_to_process.append((pack_key, pack_manifest))
        for file_info in pack_manifest.get("files", []):
            required_space += file_info.get("size_bytes", 0)

    if not args.verify_only and not check_disk_space(models_root, required_space):
        _err(f"Low Disk Space: Requires {required_space / (1024*1024*1024):.2f} GB free space on target drive.")
        sys.exit(2)

    # Load local installed state
    registry_path = data_root / ".model_packs_installed.json"
    installed_state: Dict[str, Any] = {}
    if registry_path.exists():
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                installed_state = json.load(f)
        except Exception:
            pass

    # Process Packs
    for pack_key, pack_manifest in packs_to_process:
        _log(f"Processing pack: {pack_manifest['name']}...")
        pack_verified = True

        for file_info in pack_manifest.get("files", []):
            final_file = data_root / file_info["destination"]
            final_file.parent.mkdir(parents=True, exist_ok=True)

            # Check if final file is already present and matches hash
            if final_file.exists() and compute_sha256(final_file) == file_info["sha256"]:
                _log(f"File already downloaded and verified: {final_file.name}")
                continue

            if args.verify_only:
                _err(f"Verification failure: {final_file.name} is missing or corrupted.")
                pack_verified = False
                continue

            # Check local cache directory for final file first
            final_file_copied = False
            if args.cache_dir:
                local_candidate = Path(args.cache_dir) / file_info["name"]
                if local_candidate.exists():
                    _log(f"Found local candidate for {file_info['name']} in cache-dir: {local_candidate}")
                    if compute_sha256(local_candidate) == file_info["sha256"]:
                        _log(f"Local candidate verified successfully. Copying to destination...")
                        shutil.copy2(local_candidate, final_file)
                        final_file_copied = True
                    else:
                        _log(f"Local candidate in cache-dir has incorrect hash. Skipping.")

            if final_file_copied:
                # Extract ZIP package
                extract_dir = models_root / "hub"
                if not extract_archive(final_file, extract_dir):
                    pack_verified = False
                    sys.exit(5)
                final_file.unlink(missing_ok=True)
                continue

            # Download chunks
            chunks_paths = []
            chunk_ok = True
            for chunk_info in file_info.get("chunks", []):
                chunk_url = f"{manifest['primary_base_url']}{chunk_info['relative_path']}"
                chunk_temp_file = models_root / "hub" / chunk_info["name"]
                chunk_temp_file.parent.mkdir(parents=True, exist_ok=True)

                # Check cache-dir first for individual chunks
                found_local_chunk = False
                if args.cache_dir:
                    local_chunk_candidate = Path(args.cache_dir) / chunk_info["name"]
                    if local_chunk_candidate.exists():
                        _log(f"Found local chunk candidate for {chunk_info['name']} in cache-dir.")
                        if compute_sha256(local_chunk_candidate) == chunk_info["sha256"]:
                            _log(f"Local chunk verified successfully. Copying to destination...")
                            shutil.copy2(local_chunk_candidate, chunk_temp_file)
                            found_local_chunk = True
                        else:
                            _log(f"Local chunk in cache-dir has incorrect hash. Skipping.")

                if not found_local_chunk:
                    if not download_chunk(
                        chunk_url,
                        chunk_temp_file,
                        chunk_info["size_bytes"],
                        chunk_info["sha256"],
                        manifest.get("mirror_base_urls")
                    ):
                        chunk_ok = False
                        pack_verified = False
                        break
                chunks_paths.append(chunk_temp_file)

            if not chunk_ok:
                _err(f"Failed to complete downloads for pack: {pack_manifest['name']}")
                sys.exit(3)

            # Merge chunks
            if not merge_chunks(chunks_paths, final_file, file_info["sha256"]):
                pack_verified = False
                _err(f"Merge failure for: {final_file.name}")
                sys.exit(4)

            # Extract ZIP package
            extract_dir = models_root / "hub"
            if not extract_archive(final_file, extract_dir):
                pack_verified = False
                sys.exit(5)

            # Clean up chunks and merged zip
            for cp in chunks_paths:
                cp.unlink(missing_ok=True)
            final_file.unlink(missing_ok=True)

        if pack_verified and not args.verify_only:
            installed_state[pack_key] = {
                "version": manifest["schema_version"],
                "installed_at": os.environ.get("INSTALL_TIME", "n/a"),
                "status": "verified"
            }
            # Save installed pack state JSON atomized
            temp_registry = registry_path.with_name(".model_packs_installed.json.tmp")
            with open(temp_registry, "w", encoding="utf-8") as rf:
                json.dump(installed_state, rf, indent=2)
            os.replace(temp_registry, registry_path)
            _log(f"Pack {pack_manifest['name']} registered in local manifest.")

    if args.verify_only and not pack_verified:
        sys.exit(6)

    _log("Downloader script finished successfully.")

if __name__ == "__main__":
    main()
