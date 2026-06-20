#!/usr/bin/env python3
"""
Secure Gated Model Login CLI for GoodQ4All.
Prompts for Hugging Face token, validates it, and updates data-root .env.local safely.
"""

from __future__ import annotations

import getpass
import os
import sys
import re
from pathlib import Path

# Add repo root to path for imports
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

# Ensure vendor dir is in sys.path
_VENDOR_DIR = _REPO_ROOT / "vendor"
if _VENDOR_DIR.exists() and str(_VENDOR_DIR) not in sys.path:
    sys.path.append(str(_VENDOR_DIR))

from steps.common.model_provisioner import resolve_models_root

def update_env_local(env_path: Path, token: str) -> None:
    """Updates HF_TOKEN and PYANNOTE_TOKEN in .env.local without changing other keys."""
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    
    hf_replaced = False
    pyannote_replaced = False
    
    if env_path.is_file():
        # Read existing file
        content = env_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line_strip = line.strip()
            if line_strip.startswith("HF_TOKEN="):
                lines.append(f"HF_TOKEN={token}")
                hf_replaced = True
            elif line_strip.startswith("PYANNOTE_TOKEN="):
                lines.append(f"PYANNOTE_TOKEN={token}")
                pyannote_replaced = True
            else:
                lines.append(line)
    
    # Append if not replaced
    if not hf_replaced:
        lines.append(f"HF_TOKEN={token}")
    if not pyannote_replaced:
        lines.append(f"PYANNOTE_TOKEN={token}")
        
    # Write back
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def run_lint() -> None:
    """Run token leakage check."""
    lint_script = _REPO_ROOT / "scripts" / "utils" / "banned_token_lint.py"
    if lint_script.is_file():
        print("\n[LINT] Running banned-token leakage check...")
        import subprocess
        try:
            subprocess.run([sys.executable, str(lint_script)], check=True)
        except Exception as e:
            print(f"[LINT] Failed to execute lint check: {e}")

def main() -> None:
    print("=" * 60)
    print("GoodQ4All Gated Model Authentication Setup")
    print("=" * 60)
    print("Some models used in the GoodQ pipeline (such as PyAnnote diarization")
    print("and segmentation) are gated and require accepting terms of use on")
    print("Hugging Face Hub (https://huggingface.co) before downloading.")
    print("\nTerms must be accepted on Hugging Face for:")
    print("  1. https://huggingface.co/pyannote/segmentation-3.0")
    print("  2. https://huggingface.co/pyannote/speaker-diarization-3.1")
    print("=" * 60)
    
    # Prompt securely using getpass
    try:
        token = getpass.getpass("Enter your Hugging Face Access Token (starts with hf_): ").strip()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
        
    if not token:
        print("[ERROR] Token cannot be empty.")
        sys.exit(1)
        
    if not token.startswith("hf_"):
        print("[WARNING] The entered string does not start with 'hf_'. It might be invalid.")

    # Validate against Hugging Face API
    print("\n[AUTH] Validating token against Hugging Face API...")
    try:
        from huggingface_hub import HfApi
        from huggingface_hub.utils import GatedRepoError
        api = HfApi(token=token)
        
        try:
            user_info = api.whoami()
            username = user_info.get("username", "Unknown")
            print(f"[OK] Token is valid. Authenticated as user: '{username}'")
        except Exception as auth_exc:
            err_str = str(auth_exc).lower()
            if "unauthorized" in err_str or "401" in err_str:
                print("[ERROR] Invalid token: Hugging Face API returned 401 Unauthorized.")
            else:
                print(f"[ERROR] Failed to authenticate token: {auth_exc}")
            sys.exit(1)
            
        # Check PyAnnote access
        print("[AUTH] Verifying access to pyannote/speaker-diarization-3.1...")
        try:
            api.model_info("pyannote/speaker-diarization-3.1")
            print("[OK] Access to pyannote/speaker-diarization-3.1 is verified and accepted!")
        except GatedRepoError:
            print("[WARNING] Access Denied: You have not accepted the user agreement for")
            print("          'pyannote/speaker-diarization-3.1' on Hugging Face yet.")
            print("          Please visit the URL to accept terms, then rerun this login script.")
        except Exception as e:
            print(f"[WARNING] Could not check PyAnnote repository access: {e}")
            
    except ImportError:
        print("[WARNING] huggingface_hub library not available for token validation.")
        print("          Proceeding with writing the token directly.")
    except Exception as network_exc:
        # Distinguish network/offline failures
        print(f"[ERROR] Network error: Unable to connect to Hugging Face API ({network_exc})")
        print("        Please check your internet connection.")
        sys.exit(1)

    # Write to data-root .env.local
    data_root = resolve_models_root().parent
    env_path = data_root / ".env.local"
    
    print(f"\n[ENV] Writing token to data-root environment: {env_path.absolute()}")
    try:
        update_env_local(env_path, token)
        print("[OK] Environment file updated successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to write environment file: {e}")
        sys.exit(1)
        
    # Run the banned token lint check
    run_lint()
    
    print("\n[OK] Setup complete!")

if __name__ == "__main__":
    main()
