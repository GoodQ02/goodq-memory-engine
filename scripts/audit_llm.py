#!/usr/bin/env python3
"""Automated LLM Codebase Audit Script for GoodQ4All

This script bundles the active Python, configuration, and manifest files,
calls the Gemini 2.5 Pro model on Vertex AI, and generates a comprehensive
architecture and security report.
"""
from __future__ import annotations

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path

# Target core directories to include in the audit context
CORE_DIRS = ["agents", "api", "cli", "common", "configs", "pipelines", "retrieval"]

# Non-source and binary extensions to exclude
EXCLUDE_EXTENSIONS = [
    ".exe", ".png", ".jpg", ".jpeg", ".ico", ".gif", ".zip", ".tar", ".gz",
    ".mp3", ".wav", ".db", ".sqlite", ".shm", ".wal", ".sig", ".npz", ".lnk",
    ".hex", ".nsi", ".dll", ".pyd", ".whl", ".onnx", ".bz2", ".pem", ".crt",
    ".obj", ".o", ".a", ".syso", ".bin", ".chm", ".cat"
]

# Large directories to exclude completely
EXCLUDE_PATTERNS = [
    "node_modules", ".git", "__pycache__", "venv", "envs", ".venv",
    "archive", "branding", "docs", "tests", "vendor", "wsl2_audio"
]

def get_gcloud_token() -> str:
    """Retrieve active gcloud access token."""
    try:
        res = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=True,
            shell=True
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to fetch gcloud token. Ensure you are logged in via 'gcloud auth login'. Details: {e.stderr}", file=sys.stderr)
        sys.exit(1)

def get_quota_project() -> str:
    """Retrieve active billing/quota project from gcloud."""
    try:
        res = subprocess.run(
            ["gcloud", "config", "get-value", "billing/quota_project"],
            capture_output=True,
            text=True,
            check=True,
            shell=True
        )
        project = res.stdout.strip()
        if not project or "(unset)" in project:
            # Fallback to core/project
            res = subprocess.run(
                ["gcloud", "config", "get-value", "core/project"],
                capture_output=True,
                text=True,
                check=True,
                shell=True
            )
            project = res.stdout.strip()
        return project
    except Exception:
        return ""

def build_context(repo_root: Path) -> str:
    """Traverse directories and bundle file contents into a single markdown string."""
    bundle_lines = []
    
    # 1. Directory Structure Map
    bundle_lines.append("# Codebase Structure")
    bundle_lines.append("```")
    for d in CORE_DIRS:
        dir_path = repo_root / d
        if dir_path.exists():
            bundle_lines.append(f"/{d}")
            for root, dirs, files in os.walk(dir_path):
                # Prune excluded directories in-place
                dirs[:] = [di for di in dirs if di not in EXCLUDE_PATTERNS]
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext not in EXCLUDE_EXTENSIONS:
                        rel_dir = os.path.relpath(root, dir_path)
                        if rel_dir == ".":
                            bundle_lines.append(f"  - {f}")
                        else:
                            bundle_lines.append(f"  - {rel_dir}/{f}")
    bundle_lines.append("```\n")
    
    # 2. Key Root Manifests
    bundle_lines.append("# Core System Guidelines & Manifests")
    root_files = ["AGENTS.md", "requirements-baseline-lock.txt", "environment.yml"]
    for rf in root_files:
        p = repo_root / rf
        if p.exists():
            bundle_lines.append(f"## File: {rf}")
            bundle_lines.append("```")
            bundle_lines.append(p.read_text(encoding="utf-8", errors="ignore"))
            bundle_lines.append("```\n")
            
    # 3. Source File Context
    bundle_lines.append("# Core Source Files Content")
    for d in CORE_DIRS:
        dir_path = repo_root / d
        if dir_path.exists():
            for root, dirs, files in os.walk(dir_path):
                dirs[:] = [di for di in dirs if di not in EXCLUDE_PATTERNS]
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in EXCLUDE_EXTENSIONS:
                        continue
                    if f.startswith("."):
                        continue
                        
                    full_path = Path(root) / f
                    rel_path = full_path.relative_to(repo_root)
                    
                    bundle_lines.append(f"## File: {rel_path.as_posix()}")
                    lang = ext.replace(".", "")
                    if lang in ["py", "yaml", "yml", "json", "sh", "bat", "ps1", "md"]:
                        bundle_lines.append(f"```{lang}")
                    else:
                        bundle_lines.append("```")
                    
                    bundle_lines.append(full_path.read_text(encoding="utf-8", errors="ignore"))
                    bundle_lines.append("```\n")
                    
    return "\n".join(bundle_lines)

def run_audit(repo_root: Path, output_file: Path, region: str, project_id: str):
    """Bundle codebase and invoke Gemini 2.5 Pro on Vertex AI."""
    print("[AUDIT ENGINE] Bundling repository files...")
    context = build_context(repo_root)
    
    print("[AUDIT ENGINE] Fetching gcloud authentication token...")
    token = get_gcloud_token()
    
    system_prompt = (
        "You are Q from James Bond - a senior system architect and security officer. "
        "Your voice is concise, calm, and surgical. Your focus is system integrity over cleverness. "
        "Perform a comprehensive, professional, read-only code audit of the provided repository context."
    )
    
    user_prompt = f"""Conduct a detailed design and security audit of the GoodQ4All codebase context. Ensure you evaluate the system against the authoritative guidelines defined in the AGENTS.md file.

Your audit report must include:
1. Executive Summary: Overall health of the architecture and code quality.
2. AGENTS.md Conformance: Check whether configurations, paths, env isolation, and WSL2/GPU bindings conform to the non-negotiable protocol. Specifically look for hardcoded directories or bypasses.
3. API & Entry-point Analysis: Audit api/main.py, api/server.py, and routes for concurrency locks, error handling (e.g. silent suppression checks), and route safety.
4. Security & Data Integrity Posture: Scan for vulnerabilities, SQL injection risks (in SQLite logic), Qdrant indexing concerns, or leakage of sensitive variables.
5. Specific Code Action Items: Provide a list of file-specific recommendations, pinpointing exact code lines/patterns where changes are needed.

[CODEBASE CONTEXT]
{context}"""

    url = f"https://{region}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{region}/publishers/google/models/gemini-2.5-pro:generateContent"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    data = {
        "contents": {
            "role": "user",
            "parts": {
                "text": user_prompt
            }
        },
        "systemInstruction": {
            "role": "system",
            "parts": {
                "text": system_prompt
            }
        },
        "generationConfig": {
            "maxOutputTokens": 8192,
            "temperature": 0.2
        }
    }
    
    print(f"[AUDIT ENGINE] Submitting audit request to Gemini 2.5 Pro ({region})...")
    
    try:
        import requests
    except ImportError:
        print("Error: Python 'requests' library is required to run this script.", file=sys.stderr)
        sys.exit(1)
        
    res = requests.post(url, headers=headers, json=data)
    if res.status_code == 200:
        res_json = res.json()
        try:
            output_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
            output_file.write_text(output_text, encoding="utf-8")
            print(f"[AUDIT ENGINE] Success! Audit report written to: {output_file}")
        except Exception as e:
            print(f"Error: Failed to parse JSON response. Details: {e}", file=sys.stderr)
            print(json.dumps(res_json, indent=2), file=sys.stderr)
    else:
        print(f"Error: API call failed with status code {res.status_code}", file=sys.stderr)
        print(f"Response: {res.text}", file=sys.stderr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LLM-based audit of GoodQ4All codebase")
    parser.add_argument("--region", default="us-central1", help="Google Cloud location region (default: us-central1)")
    parser.add_argument("--project", help="GCP project ID (defaults to active gcloud config project)")
    parser.add_argument("--output", default="reports/llm_audit_report.md", help="Output file path (default: reports/llm_audit_report.md)")
    
    args = parser.parse_args()
    
    repo_root = Path(__file__).parent.parent
    output_file = repo_root / args.output
    
    # Ensure reports directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    project_id = args.project or get_quota_project()
    if not project_id or "(unset)" in project_id:
        print("Error: Could not determine GCP project. Set it via --project or run 'gcloud config set core/project <id>'", file=sys.stderr)
        sys.exit(1)
        
    run_audit(repo_root, output_file, args.region, project_id)
