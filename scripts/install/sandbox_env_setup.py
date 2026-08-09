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

def resolve_cached_file(cache_path: Path | None, filename: str) -> Path | None:
    if not cache_path or not filename:
        return None
    # 1. Search directly in the cache directory
    direct_path = cache_path / filename
    if direct_path.exists():
        return direct_path
    # 2. Check: cache_path / ".." / "models" / "hub" / filename (standard offline suite payload layout)
    alt_suite_path = cache_path / ".." / "models" / "hub" / filename
    if alt_suite_path.exists():
         return alt_suite_path
    # 3. Check: cache_path / "payloads" / "models" / "hub" / filename (root-level layout)
    alt_root_path = cache_path / "payloads" / "models" / "hub" / filename
    if alt_root_path.exists():
         return alt_root_path
    # 4. Check: cache_path / "models" / "hub" / filename (standard local path)
    alt_local_path = cache_path / "models" / "hub" / filename
    if alt_local_path.exists():
         return alt_local_path
    return None

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
    parser.add_argument("--packs", default="core_memory", help="Comma-separated model packs to download or verify")
    parser.add_argument("--data-dir", default="C:\\ProgramData\\GoodQ4All", help="Authoritative data root")
    parser.add_argument("--verify-only", action="store_true", help="Perform checksum checks without downloading")
    parser.add_argument("--local-only", action="store_true", help="Hydrate only verified pack files already present in --cache-dir; never contact a model-pack URL")
    parser.add_argument("--cache-dir", default=None, help="Local directory to check for model files/chunks before downloading")
    parser.add_argument("--write-receipt", action="store_true", help="Write installation receipt to data directory")
    parser.add_argument("--install-dir", default="", help="Directory where GoodQ4All is installed")
    parser.add_argument("--service-mode", default="0", help="Service mode selection (0=Personal, 1=Always-On)")
    parser.add_argument("--wsl-status", default="skipped_wsl_unavailable", help="WSL import status log")
    parser.add_argument("--baseline-status", default="ok", help="Baseline profile status log")
    parser.add_argument("--gpu-enhanced-status", default="skipped", help="GPU enhanced profile status log")
    args = parser.parse_args()

    data_root = Path(args.data_dir)
    
    if args.write_receipt:
        receipt_path = data_root / "install_receipt.json"
        install_dir_clean = args.install_dir.replace("\\", "/")
        data_dir_clean = str(data_root).replace("\\", "/")
        # Read canonical version from goodq_version.py
        _install_version = "unknown"
        try:
            _ver_path = Path(args.install_dir) / "goodq_version.py" if args.install_dir else Path(__file__).resolve().parents[2] / "goodq_version.py"
            _ns = {}
            exec(_ver_path.read_text(encoding="utf-8"), _ns)
            _install_version = _ns.get("GOODQ_VERSION", "unknown")
        except Exception as _ve:
            print(f"[WARN] Could not read goodq_version.py: {_ve}")
        receipt_data = {
            "status": "installed",
            "version": _install_version,
            "install_dir": install_dir_clean,
            "data_dir": data_dir_clean,
            "service_mode": args.service_mode,
            "wsl_status": args.wsl_status,
            "baseline_status": args.baseline_status,
            "gpu_enhanced_status": args.gpu_enhanced_status
        }
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump(receipt_data, f, indent=2)
        print(f"[OK] Installation receipt written successfully to: {receipt_path}")
        sys.exit(0)
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
    if args.cache_dir:
        cache_path = Path(args.cache_dir)
        if cache_path.exists():
            for p_key, p_manifest in manifest["model_packs"].items():
                for f_info in p_manifest.get("files", []):
                    zip_name = f_info["name"]
                    chunks = f_info.get("chunks", [])
                    first_chunk = chunks[0].get("name", "") if (chunks and len(chunks) > 0) else ""
                    candidate_zip = resolve_cached_file(cache_path, zip_name)
                    candidate_chunk = resolve_cached_file(cache_path, first_chunk) if first_chunk else None
                    if candidate_zip or candidate_chunk:
                        if p_key not in selected_pack_keys:
                            selected_pack_keys.append(p_key)
    if args.verify_only and not selected_pack_keys:
        # Without an explicit selection, verify all registered packs. An
        # explicit --packs selection is an operator contract and must not be
        # replaced by the registry fallback.
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
            mode = str(manifest.get("distribution", {}).get("mode") or "unknown")
            if mode in {"none", "sealed_local_packs"}:
                _err(
                    f"Selected pack '{pack_key}' is not published in this baseline. "
                    "No remote model-pack download was attempted."
                )
                sys.exit(6)
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

            # Fallback verification: if the zip was unlinked after successful extraction
            if not final_file.exists() and args.verify_only:
                if installed_state.get(pack_key, {}).get("status") == "verified":
                    extract_dir = models_root / "hub"
                    has_files = False
                    if extract_dir.exists() and any(extract_dir.iterdir()):
                        has_files = True
                    if has_files:
                        _log(f"File {final_file.name} was unlinked after extraction. Verified via registry.")
                        continue

            if args.verify_only:
                _err(f"Verification failure: {final_file.name} is missing or corrupted.")
                pack_verified = False
                continue

            # Check local cache directory for final file first
            final_file_copied = False
            if args.cache_dir:
                local_candidate = resolve_cached_file(Path(args.cache_dir), file_info["name"])
                if local_candidate and local_candidate.exists():
                    _log(f"Found local candidate for {file_info['name']} in cache: {local_candidate}")
                    if compute_sha256(local_candidate) == file_info["sha256"]:
                        _log(f"Local candidate verified successfully. Copying to destination...")
                        shutil.copy2(local_candidate, final_file)
                        final_file_copied = True
                    else:
                        _log(f"Local candidate in cache has incorrect hash. Skipping.")

            if final_file_copied:
                # Extract ZIP package
                extract_dir = models_root / "hub"
                if not extract_archive(final_file, extract_dir):
                    pack_verified = False
                    sys.exit(5)
                final_file.unlink(missing_ok=True)
                continue

            if args.local_only:
                _err(
                    f"Local-only pack setup could not find a verified '{file_info['name']}' in the supplied cache. "
                    "No remote model-pack download was attempted."
                )
                sys.exit(6)

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
                    local_chunk_candidate = resolve_cached_file(Path(args.cache_dir), chunk_info["name"])
                    if local_chunk_candidate and local_chunk_candidate.exists():
                        _log(f"Found local chunk candidate for {chunk_info['name']} in cache: {local_chunk_candidate}")
                        if compute_sha256(local_chunk_candidate) == chunk_info["sha256"]:
                            _log(f"Local chunk verified successfully. Copying to destination...")
                            shutil.copy2(local_chunk_candidate, chunk_temp_file)
                            found_local_chunk = True
                        else:
                            _log(f"Local chunk in cache has incorrect hash. Skipping.")

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
