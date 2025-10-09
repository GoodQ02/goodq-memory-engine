"""
Validate all project paths are correctly configured and aligned.
"""
import sys
sys.path.insert(0, 'L:/')

from pathlib import Path
import yaml
import os

def load_yaml(path):
    """Load YAML configuration file."""
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def check_paths():
    """Validate all path configurations."""
    print("=" * 70)
    print("GoodQ Project Path Validation")
    print("=" * 70)
    
    # Check paths.py
    print("\n📁 Checking paths.py configuration...")
    from GoodQ_4_All.configs.paths import (
        PROJECT_ROOT, DATA_ROOT, DATABASE_DIR, MEMORY_DB,
        KNOWLEDGE_GRAPH_DB, LOGS_DIR, MODELS_DIR, TOOLS_DIR
    )
    
    paths_py = {
        "PROJECT_ROOT": PROJECT_ROOT,
        "DATA_ROOT": DATA_ROOT,
        "DATABASE_DIR": DATABASE_DIR,
        "MEMORY_DB": MEMORY_DB,
        "KNOWLEDGE_GRAPH_DB": KNOWLEDGE_GRAPH_DB,
        "LOGS_DIR": LOGS_DIR,
        "MODELS_DIR": MODELS_DIR,
        "TOOLS_DIR": TOOLS_DIR
    }
    
    for name, path in paths_py.items():
        status = "✓" if path.exists() or name.endswith("_DB") else "✗"
        print(f"  {status} {name}: {path}")
    
    # Check paths.yaml
    print("\n📄 Checking paths.yaml configuration...")
    paths_yaml_file = Path("L:/GoodQ_4_All/configs/paths.yaml")
    if paths_yaml_file.exists():
        paths_yaml = load_yaml(paths_yaml_file)
        for key, value in paths_yaml.items():
            path = Path(value) if isinstance(value, str) else None
            if path:
                status = "✓" if path.exists() or path.parent.exists() else "✗"
                print(f"  {status} {key}: {value}")
    else:
        print("  ✗ paths.yaml not found!")
    
    # Check config.yaml
    print("\n⚙️  Checking config.yaml configuration...")
    config_file = Path("L:/GoodQ_4_All/config.yaml")
    if config_file.exists():
        config = load_yaml(config_file)
        if 'paths' in config:
            for key, value in config['paths'].items():
                path = Path(value) if isinstance(value, str) else None
                if path:
                    status = "✓" if path.exists() or path.parent.exists() else "✗"
                    print(f"  {status} {key}: {value}")
    else:
        print("  ✗ config.yaml not found!")
    
    # Check environment variables
    print("\n🔧 Checking environment variables (.env.local)...")
    env_vars = {
        "HF_HOME": os.environ.get("HF_HOME"),
        "TORCH_HOME": os.environ.get("TORCH_HOME"),
        "TRANSFORMERS_CACHE": os.environ.get("TRANSFORMERS_CACHE")
    }
    
    for name, value in env_vars.items():
        if value:
            path = Path(value)
            status = "✓" if path.exists() or path.parent.exists() else "✗"
            print(f"  {status} {name}: {value}")
        else:
            print(f"  ⚠ {name}: Not set")
    
    # Check for consistency
    print("\n🔍 Checking path consistency...")
    issues = []
    
    # All paths should use L:/_DATA/GoodQ_Data for data
    if str(DATA_ROOT) != "L:\\_DATA\\GoodQ_Data":
        issues.append(f"DATA_ROOT should be L:/_DATA/GoodQ_Data, got {DATA_ROOT}")
    
    # Models should be in L:/_DATA/models
    if str(MODELS_DIR) != "L:\\_DATA\\models":
        issues.append(f"MODELS_DIR should be L:/_DATA/models, got {MODELS_DIR}")
    
    # Tools should be in L:/_TOOLS
    if str(TOOLS_DIR) != "L:\\_TOOLS":
        issues.append(f"TOOLS_DIR should be L:/_TOOLS, got {TOOLS_DIR}")
    
    if issues:
        print("  ✗ Issues found:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("  ✓ All paths are consistent!")
    
    # Summary
    print("\n" + "=" * 70)
    print("Validation Summary")
    print("=" * 70)
    
    if not issues:
        print("✓ All paths are correctly configured and aligned!")
        return 0
    else:
        print(f"✗ Found {len(issues)} issue(s) that need attention.")
        return 1

if __name__ == "__main__":
    sys.exit(check_paths())
