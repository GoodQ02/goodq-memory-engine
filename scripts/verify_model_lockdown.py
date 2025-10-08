"""
Verify that all models are properly locked down with exact versions.
Checks registry integrity, file hashes, and version pins.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_VENDOR_DIR = _REPO_ROOT / "vendor"
if _VENDOR_DIR.exists():
    sys.path.insert(0, str(_VENDOR_DIR))


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def check_registry_file() -> Dict[str, Any]:
    """Check if model registry exists and is valid."""
    registry_path = _REPO_ROOT / "configs" / "model_registry.yaml"
    
    result = {
        'exists': registry_path.exists(),
        'path': str(registry_path),
        'valid': False,
        'models_count': 0,
    }
    
    if result['exists']:
        try:
            with open(registry_path, 'r', encoding='utf-8') as f:
                registry = yaml.safe_load(f)
            result['valid'] = True
            result['models_count'] = len(registry.get('huggingface_models', {}))
            result['external_count'] = len(registry.get('external_models', {}))
        except Exception as e:
            result['error'] = str(e)
    
    return result


def check_revision_pins(registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check that all HuggingFace models have proper revision pins."""
    results = []
    
    for model_key, model_info in registry.get('huggingface_models', {}).items():
        repo_id = model_info.get('repo_id', 'unknown')
        revision = model_info.get('revision', '')
        
        check = {
            'key': model_key,
            'repo_id': repo_id,
            'revision': revision,
            'status': 'ok',
            'issues': [],
        }
        
        # Check if revision exists
        if not revision:
            check['status'] = 'error'
            check['issues'].append("No revision specified")
        
        # Check if revision is a placeholder (all same character)
        elif len(set(revision)) == 1:
            check['status'] = 'warning'
            check['issues'].append("Placeholder revision detected (not real commit SHA)")
        
        # Check revision format (should be 40-char SHA or semantic version)
        elif len(revision) == 40 and revision.isalnum():
            check['status'] = 'ok'
        elif revision.count('.') >= 1:  # Semantic version like "2.1"
            check['status'] = 'ok'
            check['issues'].append("Using tagged release (not commit SHA)")
        else:
            check['status'] = 'warning'
            check['issues'].append("Unusual revision format")
        
        results.append(check)
    
    return results


def check_external_assets(registry: Dict[str, Any], models_dir: Path) -> List[Dict[str, Any]]:
    """Check external model assets."""
    results = []
    
    for model_key, model_info in registry.get('external_models', {}).items():
        local_path = models_dir / model_info.get('local_path', '')
        expected_sha = model_info.get('sha256', '')
        expected_size = model_info.get('file_size_bytes', 0)
        is_required = model_info.get('required', True)
        
        check = {
            'key': model_key,
            'path': str(local_path),
            'status': 'ok',
            'issues': [],
        }
        
        if not local_path.exists():
            if is_required:
                check['status'] = 'error'
                check['issues'].append("File not found (required)")
            else:
                check['status'] = 'ok'
                check['issues'].append("File not found (optional - not required)")
        else:
            actual_size = local_path.stat().st_size
            
            # Check file size
            if expected_size > 0 and actual_size != expected_size:
                check['status'] = 'warning'
                check['issues'].append(f"Size mismatch: expected {expected_size:,}, got {actual_size:,}")
            
            # Check SHA256 (only for smaller files and non-placeholder hashes)
            if expected_sha and 'placeholder' not in expected_sha.lower() and len(set(expected_sha)) > 1:
                if actual_size < 500 * 1024 * 1024:  # < 500MB
                    sha256 = hashlib.sha256()
                    with open(local_path, 'rb') as f:
                        while chunk := f.read(8192):
                            sha256.update(chunk)
                    actual_sha = sha256.hexdigest()
                    
                    if actual_sha != expected_sha:
                        check['status'] = 'error'
                        check['issues'].append("SHA256 hash mismatch!")
                else:
                    check['issues'].append("File too large for hash verification")
            elif expected_sha and 'placeholder' in expected_sha.lower():
                check['issues'].append("Placeholder SHA256 (hash not yet computed)")
        
        results.append(check)
    
    return results


def check_system_tools(registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check system tools are available."""
    results = []
    
    for tool_key, tool_info in registry.get('system_tools', {}).items():
        binary_path = Path(tool_info.get('binary_path', ''))
        
        check = {
            'key': tool_key,
            'path': str(binary_path),
            'status': 'ok',
            'issues': [],
        }
        
        if not binary_path.exists():
            check['status'] = 'error'
            check['issues'].append("Binary not found")
        
        results.append(check)
    
    return results


def print_results(results: List[Dict[str, Any]], title: str) -> Dict[str, int]:
    """Print check results with color coding."""
    print(f"\n{Colors.BOLD}{title}{Colors.RESET}")
    print("=" * 80)
    
    counts = {'ok': 0, 'warning': 0, 'error': 0}
    
    for result in results:
        status = result['status']
        counts[status] = counts.get(status, 0) + 1
        
        # Color code by status
        if status == 'ok':
            icon = f"{Colors.GREEN}✓{Colors.RESET}"
        elif status == 'warning':
            icon = f"{Colors.YELLOW}⚠{Colors.RESET}"
        else:
            icon = f"{Colors.RED}✗{Colors.RESET}"
        
        print(f"{icon} {result.get('key', result.get('name', 'unknown'))}")
        
        if result.get('repo_id'):
            print(f"  Repository: {result['repo_id']}")
        if result.get('revision'):
            print(f"  Revision: {result['revision']}")
        if result.get('path'):
            print(f"  Path: {result['path']}")
        
        for issue in result.get('issues', []):
            print(f"  {Colors.YELLOW}→{Colors.RESET} {issue}")
    
    return counts


def main() -> None:
    """Main verification function."""
    print(f"\n{Colors.BOLD}{'GoodQ Model Lockdown Verification':-^80}{Colors.RESET}\n")
    
    # Load registry
    registry_check = check_registry_file()
    
    if not registry_check['exists']:
        print(f"{Colors.RED}✗ Model registry not found!{Colors.RESET}")
        print(f"  Expected: {registry_check['path']}")
        sys.exit(1)
    
    if not registry_check['valid']:
        print(f"{Colors.RED}✗ Model registry is invalid!{Colors.RESET}")
        print(f"  Error: {registry_check.get('error')}")
        sys.exit(1)
    
    print(f"{Colors.GREEN}✓ Model registry found{Colors.RESET}")
    print(f"  Path: {registry_check['path']}")
    print(f"  HuggingFace models: {registry_check['models_count']}")
    print(f"  External models: {registry_check.get('external_count', 0)}")
    
    # Load full registry
    registry_path = _REPO_ROOT / "configs" / "model_registry.yaml"
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = yaml.safe_load(f)
    
    models_dir = Path(os.environ.get("GOODQ_MODELS_DIR", "L:/models"))
    
    # Run checks
    all_counts = {'ok': 0, 'warning': 0, 'error': 0}
    
    # Check HuggingFace model pins
    hf_results = check_revision_pins(registry)
    counts = print_results(hf_results, "HuggingFace Model Version Pins")
    for k, v in counts.items():
        all_counts[k] += v
    
    # Check external assets
    if 'external_models' in registry:
        ext_results = check_external_assets(registry, models_dir)
        counts = print_results(ext_results, "External Model Assets")
        for k, v in counts.items():
            all_counts[k] += v
    
    # Check system tools
    if 'system_tools' in registry:
        tool_results = check_system_tools(registry)
        counts = print_results(tool_results, "System Tools")
        for k, v in counts.items():
            all_counts[k] += v
    
    # Print summary
    print(f"\n{Colors.BOLD}{'Summary':-^80}{Colors.RESET}")
    print(f"  {Colors.GREEN}✓ OK:       {all_counts['ok']}{Colors.RESET}")
    print(f"  {Colors.YELLOW}⚠ Warning:  {all_counts['warning']}{Colors.RESET}")
    print(f"  {Colors.RED}✗ Error:    {all_counts['error']}{Colors.RESET}")
    
    # Check update policy
    update_policy = registry.get('update_policy', {})
    print(f"\n{Colors.BOLD}Update Policy{Colors.RESET}")
    print(f"  Auto-update: {Colors.RED if update_policy.get('auto_update') else Colors.GREEN}{update_policy.get('auto_update', False)}{Colors.RESET}")
    print(f"  Manual approval: {Colors.GREEN if update_policy.get('manual_approval_required') else Colors.RED}{update_policy.get('manual_approval_required', False)}{Colors.RESET}")
    
    print(f"\n{'='*80}\n")
    
    # Exit code based on errors
    if all_counts['error'] > 0:
        print(f"{Colors.RED}Lockdown verification FAILED with {all_counts['error']} error(s){Colors.RESET}")
        sys.exit(1)
    elif all_counts['warning'] > 0:
        print(f"{Colors.YELLOW}Lockdown verification PASSED with {all_counts['warning']} warning(s){Colors.RESET}")
        sys.exit(0)
    else:
        print(f"{Colors.GREEN}✓ Lockdown verification PASSED - All models properly pinned!{Colors.RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
