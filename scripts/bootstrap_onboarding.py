"""
GoodQ4All - Onboarding Ingestion Bootstrap Script
Downloads a 100% public domain NASA video of the Apollo 11 moon landing,
transcodes it, sets up the onboarding sandbox, and runs the pipeline.
"""
from __future__ import annotations

import os
import sys
import shutil
import subprocess
import time
from pathlib import Path

# Ensure root of repo is in path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

COMMONS_URL = "https://upload.wikimedia.org/wikipedia/commons/a/a6/Apollo_11_Landing_-_first_steps_on_the_moon.ogv"
FIXTURE_PATH = REPO_ROOT / "samples" / "onboarding_fixture.mp4"
INBOX_DIR = REPO_ROOT / "logs" / "inbox_onboarding"
WORKSPACE_DIR = REPO_ROOT / "processing_onboarding"


def get_ffmpeg_exe() -> str:
    """Find a system-wide ffmpeg that has libx264 support (not the limited conda one)."""
    # Prefer explicit system tools directory path
    default_system = r"C:\Tools\ffmpeg\bin\ffmpeg.exe"
    if os.path.exists(default_system):
        return default_system
    
    # Try resolving via where.exe, selecting first one that is outside conda/miniconda env
    try:
        out = subprocess.check_output(["where.exe", "ffmpeg"], text=True)
        for path in out.strip().split("\n"):
            path = path.strip()
            if path and "miniconda" not in path.lower() and "conda" not in path.lower():
                return path
    except Exception:
        pass
    return "ffmpeg"


def ensure_fixture():
    """Download and transcode the public domain Apollo 11 clip using ffmpeg."""
    if FIXTURE_PATH.is_file() and FIXTURE_PATH.stat().st_size > 10000:
        print(f"[BOOTSTRAP] Onboarding fixture already exists at: {FIXTURE_PATH}")
        return True

    print("[BOOTSTRAP] Onboarding fixture not found. Downloading public domain Apollo 11 clip from Wikimedia Commons...")
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    ffmpeg_exe = get_ffmpeg_exe()
    
    # We transcode the first 20 seconds to H.264/AAC MP4.
    # Set a custom user_agent to bypass Wikimedia's automated request blocker.
    cmd = [
        ffmpeg_exe, "-y",
        "-user_agent", "GoodQOnboardingBot/1.0 (contact: admin@goodq.ai)",
        "-ss", "00:00:00",
        "-i", COMMONS_URL,
        "-t", "20",
        "-c:v", "libx264",
        "-c:a", "aac",
        str(FIXTURE_PATH)
    ]
    
    try:
        print(f"[BOOTSTRAP] Executing: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and FIXTURE_PATH.exists() and FIXTURE_PATH.stat().st_size > 10000:
            print(f"[BOOTSTRAP] Successful transcode. Saved to {FIXTURE_PATH} ({FIXTURE_PATH.stat().st_size} bytes)")
            return True
        else:
            print("[BOOTSTRAP] [ERROR] ffmpeg transcoding failed.")
            print(f"Stdout: {res.stdout}")
            print(f"Stderr: {res.stderr}")
            return False
    except Exception as e:
        print(f"[BOOTSTRAP] [ERROR] Failed to run ffmpeg: {e}")
        return False


def run_pipeline():
    """Set up sandbox input directory and trigger run_ingestion CLI."""
    if INBOX_DIR.exists():
        shutil.rmtree(INBOX_DIR)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    # Copy fixture to inbox
    dest_path = INBOX_DIR / FIXTURE_PATH.name
    shutil.copy2(FIXTURE_PATH, dest_path)
    print(f"[BOOTSTRAP] Staged onboarding fixture in sandbox: {dest_path}")

    # Prepare ingestion command
    cmd = [
        sys.executable, "-m", "cli.run_ingestion",
        "--input-dir", str(INBOX_DIR),
        "--workspace", str(WORKSPACE_DIR),
        "--verbose",
        "--force"  # Force reprocessing for test reproducibility
    ]

    print("[BOOTSTRAP] Running ingestion pipeline (this should complete under 2 minutes)...")
    start_time = time.time()
    
    try:
        # Run directly in terminal, piping output in real-time
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        if p.stdout:
            for line in p.stdout:
                print(f"  {line.rstrip()}")
        p.wait()
        
        duration = time.time() - start_time
        if p.returncode == 0:
            print(f"\n[BOOTSTRAP] [SUCCESS] Onboarding ingestion completed successfully in {duration:.1f} seconds!")
            return True
        else:
            print(f"\n[BOOTSTRAP] [FAIL] Ingestion pipeline exited with code: {p.returncode}")
            return False
    except Exception as e:
        print(f"\n[BOOTSTRAP] [ERROR] Ingestion process failed to launch: {e}")
        return False


def main():
    print("=" * 60)
    print("  GoodQ4All - Onboarding Media Fixture Bootstrapper")
    print("=" * 60)
    
    if not ensure_fixture():
        print("[BOOTSTRAP] [FAIL] Could not generate onboarding fixture. Aborting.")
        sys.exit(1)
        
    if not run_pipeline():
        print("[BOOTSTRAP] [FAIL] Onboarding ingestion run failed.")
        sys.exit(1)

    print("\n[BOOTSTRAP] [DONE] Onboarding fixture setup and verification complete.")


if __name__ == "__main__":
    main()
