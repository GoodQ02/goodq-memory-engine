"""
Fetch and pin exact model versions (commit SHAs) for all HuggingFace models.
Updates model_registry.yaml with actual commit hashes from the HF Hub.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

# Add vendor to path
_REPO_ROOT = Path(__file__).resolve().parents[1]
_VENDOR_DIR = _REPO_ROOT / "vendor"
if _VENDOR_DIR.exists():
    sys.path.insert(0, str(_VENDOR_DIR))

try:
    from huggingface_hub import HfApi, hf_hub_download
except ImportError:
    print("ERROR: huggingface_hub not available. Install via: pip install huggingface_hub")
    sys.exit(1)


def get_latest_commit_sha(repo_id: str, token: str | None = None) -> str | None:
    """Fetch the latest commit SHA for a HuggingFace model repo."""
    try:
        api = HfApi()
        info = api.model_info(repo_id, token=token)
        return info.sha
    except Exception as e:
        print(f"WARNING: Could not fetch commit SHA for {repo_id}: {e}")
        return None


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_external_model(model_info: Dict[str, Any], models_dir: Path) -> Dict[str, Any]:
    """Verify an external model file exists and optionally compute its hash."""
    local_path = models_dir / model_info.get('local_path', '')
    result = {
        'exists': local_path.exists(),
        'path': str(local_path),
    }
    
    if local_path.exists():
        result['file_size'] = local_path.stat().st_size
        # Only compute hash if file is reasonable size (< 500MB)
        if result['file_size'] < 500 * 1024 * 1024:
            result['sha256'] = compute_file_hash(local_path)
        else:
            result['sha256'] = "(file too large, hash not computed)"
    
    return result


def main() -> None:
    """Main function to pin all model versions."""
    registry_path = _REPO_ROOT / "configs" / "model_registry.yaml"
    
    if not registry_path.exists():
        print(f"ERROR: Registry file not found: {registry_path}")
        sys.exit(1)
    
    # Load registry
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = yaml.safe_load(f)
    
    # Get tokens
    hf_token = os.environ.get("HF_TOKEN")
    pyannote_token = os.environ.get("PYANNOTE_TOKEN") or hf_token
    
    models_dir = Path(os.environ.get("GOODQ_MODELS_DIR", "L:/models"))
    
    print(f"{'='*80}")
    print(f"Model Version Pinning Tool")
    print(f"{'='*80}\n")
    print(f"Registry: {registry_path}")
    print(f"Models Directory: {models_dir}\n")
    
    # Process HuggingFace models
    if 'huggingface_models' in registry:
        print(f"\n{'HuggingFace Models':-^80}")
        updated_count = 0
        
        for model_key, model_info in registry['huggingface_models'].items():
            repo_id = model_info.get('repo_id')
            current_revision = model_info.get('revision', 'unknown')
            requires_auth = model_info.get('requires_auth', False)
            
            print(f"\n{model_key}: {repo_id}")
            print(f"  Current revision: {current_revision}")
            
            # Use appropriate token
            token = pyannote_token if requires_auth else hf_token
            
            # Fetch latest SHA
            latest_sha = get_latest_commit_sha(repo_id, token)
            
            if latest_sha:
                print(f"  Latest commit:    {latest_sha}")
                
                # Check if it's a placeholder hash (all same character repeated)
                if current_revision and len(set(current_revision)) == 1:
                    print(f"  → Updating placeholder revision to actual commit SHA")
                    model_info['revision'] = latest_sha
                    updated_count += 1
                elif current_revision != latest_sha:
                    print(f"  [SYMBOL] Revision differs from latest (not updating, use manual review)")
                else:
                    print(f"  [SYMBOL] Already pinned to latest")
            else:
                print(f"  [SYMBOL] Could not fetch latest commit")
        
        print(f"\nUpdated {updated_count} model(s) with placeholder revisions")
    
    # Verify external models
    if 'external_models' in registry:
        print(f"\n{'External Models':-^80}")
        
        for model_key, model_info in registry['external_models'].items():
            print(f"\n{model_key}: {model_info.get('name')}")
            verification = verify_external_model(model_info, models_dir)
            
            if verification['exists']:
                print(f"  [SYMBOL] Found: {verification['path']}")
                print(f"    Size: {verification['file_size']:,} bytes")
                
                # Update registry with actual values
                if 'sha256' in verification and isinstance(verification['sha256'], str) and len(verification['sha256']) == 64:
                    current_hash = model_info.get('sha256', '')
                    if current_hash and len(set(current_hash)) == 1:
                        print(f"    → Updating placeholder SHA256")
                        model_info['sha256'] = verification['sha256']
                    elif current_hash != verification['sha256']:
                        print(f"    [SYMBOL] SHA256 mismatch!")
                        print(f"      Expected: {current_hash}")
                        print(f"      Actual:   {verification['sha256']}")
                    else:
                        print(f"    [SYMBOL] SHA256 verified")
                
                if verification['file_size'] != model_info.get('file_size_bytes', 0):
                    print(f"    → Updating file_size_bytes")
                    model_info['file_size_bytes'] = verification['file_size']
            else:
                print(f"  [SYMBOL] Not found: {verification['path']}")
                print(f"    Download from: {model_info.get('source_url')}")
    
    # Save updated registry
    backup_path = registry_path.with_suffix('.yaml.bak')
    registry_path.rename(backup_path)
    print(f"\n{'='*80}")
    print(f"Backup saved: {backup_path}")
    
    with open(registry_path, 'w', encoding='utf-8') as f:
        yaml.dump(registry, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    print(f"Registry updated: {registry_path}")
    print(f"{'='*80}\n")
    
    # Create summary report
    report = {
        'registry_path': str(registry_path),
        'models_dir': str(models_dir),
        'huggingface_models': len(registry.get('huggingface_models', {})),
        'external_models': len(registry.get('external_models', {})),
        'timestamp': str(Path(__file__).stat().st_mtime),
    }
    
    report_path = _REPO_ROOT / "logs" / "model_pin_report.json"
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    
    print(f"Report saved: {report_path}")


if __name__ == "__main__":
    main()
