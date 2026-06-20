#!/usr/bin/env python3
"""
Banned Token Leakage Lint Utility.
Scans log directories and output logs for raw Hugging Face tokens (hf_[a-zA-Z0-9]{34}).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

# Regular expression for Hugging Face token pattern
HF_TOKEN_PATTERN = re.compile(r"hf_[a-zA-Z0-9]{34}")

def redact_token(token: str) -> str:
    if len(token) > 10:
        return f"{token[:5]}...{token[-5:]}"
    return "hf_***"

def scan_file(file_path: Path) -> list[tuple[int, str]]:
    leaks = []
    try:
        # Read file with errors replaced to handle potential encoding mismatches
        content = file_path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(content.splitlines(), start=1):
            matches = HF_TOKEN_PATTERN.findall(line)
            if matches:
                for match in matches:
                    leaks.append((line_no, match))
    except Exception as e:
        # Ignore files that cannot be read
        pass
    return leaks

def main() -> None:
    print("[LINT] Scanning logs and outputs for Hugging Face token leaks...")
    
    # Resolve log folders to scan
    scan_dirs: list[Path] = []
    
    # 1. Project logs directory
    project_logs = _REPO_ROOT / "logs"
    if project_logs.is_dir():
        scan_dirs.append(project_logs)
        
    # 2. Resolve data-root epoch logs
    try:
        from steps.common.model_provisioner import resolve_models_root
        data_root = resolve_models_root().parent
        epochs_dir = data_root / "epochs"
        if epochs_dir.is_dir():
            for epoch_dir in epochs_dir.iterdir():
                if epoch_dir.is_dir():
                    logs_dir = epoch_dir / "logs"
                    if logs_dir.is_dir():
                        scan_dirs.append(logs_dir)
    except Exception:
        pass

    # Deduplicate scan directories
    scan_dirs = sorted(list(set(p.resolve() for p in scan_dirs)))
    
    total_files = 0
    leaks_found = 0
    
    for log_dir in scan_dirs:
        print(f"[LINT] Scanning directory: {log_dir}")
        for ext in ("*.log", "*.txt", "*.json", "*.jsonl", "*.csv"):
            for file_path in log_dir.glob(ext):
                total_files += 1
                leaks = scan_file(file_path)
                if leaks:
                    leaks_found += len(leaks)
                    for line_no, token in leaks:
                        redacted = redact_token(token)
                        print(f"[WARN] Leak detected in {file_path.name}:{line_no} -> token '{redacted}' found!")

    print("=" * 60)
    print(f"[LINT] Scan complete. Checked {total_files} files.")
    if leaks_found > 0:
        print(f"[FAIL] Found {leaks_found} token leakage instances! Action required.")
        sys.exit(1)
    else:
        print("[PASS] No token leakage detected in the examined logs.")
        sys.exit(0)

if __name__ == "__main__":
    main()
