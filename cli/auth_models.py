import argparse
import sys
import getpass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

# Ensure vendor dir is in sys.path
_VENDOR_DIR = _REPO_ROOT / "vendor"
if _VENDOR_DIR.exists() and str(_VENDOR_DIR) not in sys.path:
    sys.path.append(str(_VENDOR_DIR))

from steps.common.model_provisioner import resolve_models_root

def update_env_local(env_path: Path, token: str) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    hf_replaced = False
    pyannote_replaced = False
    
    if env_path.is_file():
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
                
    if not hf_replaced:
        lines.append(f"HF_TOKEN={token}")
    if not pyannote_replaced:
        lines.append(f"PYANNOTE_TOKEN={token}")
        
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description="Authenticate gated Hugging Face models")
    parser.add_argument("--enable-gated", action="store_true", help="Prompt and enable gated models access")
    args = parser.parse_args()
    
    if not args.enable_gated:
        print("[ERROR] Please run with --enable-gated to initiate Hugging Face authentication.")
        sys.exit(1)
        
    print("=" * 60)
    print("GoodQ4All Gated Model Authentication Setup")
    print("=" * 60)
    
    try:
        token = getpass.getpass("Enter your Hugging Face Access Token (starts with hf_): ").strip()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
        
    if not token:
        print("[ERROR] Missing token: token cannot be empty.")
        sys.exit(1)
        
    if not token.startswith("hf_"):
        print("[WARNING] The entered token does not start with 'hf_'. It might be invalid.")
        
    # Validate token
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
                print("[ERROR] Invalid token: The provided Hugging Face token is invalid or unauthorized.")
                sys.exit(1)
            elif "connection" in err_str or "dns" in err_str or "offline" in err_str:
                print("[ERROR] Network offline: Unable to connect to Hugging Face API. Please check your internet connection.")
                sys.exit(1)
            else:
                print(f"[ERROR] Authentication failed: {auth_exc}")
                sys.exit(1)
                
        # Check PyAnnote access
        print("[AUTH] Checking access to pyannote/speaker-diarization-3.1...")
        try:
            api.model_info("pyannote/speaker-diarization-3.1")
            print("[OK] Access to pyannote/speaker-diarization-3.1 is verified and accepted!")
        except GatedRepoError:
            print("[ERROR] Terms not accepted: You have not accepted the user agreement for 'pyannote/speaker-diarization-3.1' on Hugging Face yet. Please visit https://huggingface.co/pyannote/speaker-diarization-3.1 to accept terms.")
            sys.exit(1)
        except Exception as e:
            err_str = str(e).lower()
            if "403" in err_str or "gated" in err_str:
                print("[ERROR] Terms not accepted: You have not accepted the user agreement for 'pyannote/speaker-diarization-3.1' on Hugging Face yet. Please visit https://huggingface.co/pyannote/speaker-diarization-3.1 to accept terms.")
            elif "401" in err_str or "unauthorized" in err_str:
                print("[ERROR] Invalid token: The provided Hugging Face token is invalid or unauthorized.")
            elif "connection" in err_str or "dns" in err_str or "offline" in err_str:
                print("[ERROR] Network offline: Unable to connect to Hugging Face API. Please check your internet connection.")
            else:
                print(f"[ERROR] Failed to check PyAnnote repository access: {e}")
            sys.exit(1)
            
    except ImportError:
        print("[ERROR] huggingface_hub library not available.")
        sys.exit(1)
    except Exception as network_exc:
        err_str = str(network_exc).lower()
        if "connection" in err_str or "dns" in err_str or "offline" in err_str:
            print(f"[ERROR] Network offline: Unable to connect to Hugging Face API ({network_exc})")
        else:
            print(f"[ERROR] Other failure: {network_exc}")
        sys.exit(1)
        
    # Write to data-root .env.local
    try:
        models_root = resolve_models_root()
        data_root = models_root.parent
        env_path = data_root / ".env.local"
        print(f"\n[ENV] Writing token to data-root environment: {env_path.absolute()}")
        update_env_local(env_path, token)
        print("[OK] Environment file updated successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to write environment file: {e}")
        sys.exit(1)
        
    # Run token linting check
    lint_script = _REPO_ROOT / "scripts" / "utils" / "banned_token_lint.py"
    if lint_script.is_file():
        print("\n[LINT] Running banned-token leakage check...")
        import subprocess
        try:
            subprocess.run([sys.executable, str(lint_script)], check=True)
        except Exception as e:
            print(f"[LINT] Failed to execute lint check: {e}")
            
    print("\n[OK] Setup complete!")

if __name__ == "__main__":
    main()
