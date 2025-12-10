"""
GoodQ4All System Status Dashboard
Quick diagnostic tool to check system health.
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Dict, Any
import json

# Ensure proper Python path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def check_environment():
    """Check Python environment and dependencies."""
    print("\n" + "="*80)
    print("ENVIRONMENT STATUS")
    print("="*80)
    
    print(f"Python: {sys.version.split()[0]}")
    print(f"Repo Root: {REPO_ROOT}")
    print(f"Python Path Includes Repo: {str(REPO_ROOT) in sys.path}")
    
    # Check critical imports
    critical_modules = [
        "torch",
        "transformers",
        "cv2",
        "PIL",
        "yaml",
        "pydantic",
    ]
    
    print("\nCritical Dependencies:")
    for mod in critical_modules:
        try:
            __import__(mod)
            print(f"  [PASS] {mod}")
        except ImportError:
            print(f"  [FAIL] {mod} - NOT INSTALLED")


def check_config():
    """Check configuration status."""
    print("\n" + "="*80)
    print("CONFIGURATION STATUS")
    print("="*80)
    
    config_path = REPO_ROOT / "configs" / "config.yaml"
    
    if not config_path.exists():
        print(f"[FAIL] config.yaml not found at {config_path}")
        return None
    
    print(f"[PASS] Config file: {config_path}")
    
    try:
        from goodq4all.steps.common.config_loader import load_configs
        cfg = load_configs({})
        
        print("[PASS] Config loads successfully")
        print(f"\nTop-level keys:")
        for key in sorted(cfg.keys()):
            print(f"  - {key}")
        
        return cfg
        
    except Exception as e:
        print(f"[FAIL] Config loading failed: {e}")
        return None


def check_directories(cfg: Dict[str, Any] | None):
    """Check that required directories exist."""
    print("\n" + "="*80)
    print("DIRECTORY STATUS")
    print("="*80)
    
    if not cfg:
        print("[WARN]  Cannot check directories without config")
        return
    
    paths_to_check = []
    
    if 'paths' in cfg:
        paths_cfg = cfg['paths']
        paths_to_check = [
            ("Import Inbox", paths_cfg.get('import_inbox')),
            ("Processing", paths_cfg.get('processing')),
            ("Data Root", paths_cfg.get('data_root')),
            ("Models Cache", paths_cfg.get('models_cache')),
            ("Logs", paths_cfg.get('log_dir')),
        ]
    
    for name, path_str in paths_to_check:
        if not path_str:
            print(f"[WARN]  {name}: Not configured")
            continue
        
        path = Path(path_str)
        if path.exists():
            if path.is_dir():
                file_count = len(list(path.glob('*')))
                print(f"[PASS] {name}: {path} ({file_count} items)")
            else:
                print(f"[WARN]  {name}: {path} (exists but not a directory)")
        else:
            print(f"[FAIL] {name}: {path} (does not exist)")


def check_recent_ingestions(cfg: Dict[str, Any] | None):
    """Check for recent ingestion outputs."""
    print("\n" + "="*80)
    print("RECENT INGESTIONS")
    print("="*80)
    
    if not cfg or 'paths' not in cfg:
        print("[WARN]  Cannot check without config paths")
        return
    
    processing_root = Path(cfg['paths'].get('processing', 'L:/_DATA/GoodQ_Data/processing'))
    
    if not processing_root.exists():
        print(f"[FAIL] Processing directory does not exist: {processing_root}")
        return
    
    video_dirs = [d for d in processing_root.iterdir() if d.is_dir()]
    
    if not video_dirs:
        print("No ingested videos found")
        return
    
    # Sort by modification time
    video_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    
    print(f"Found {len(video_dirs)} ingested video(s):\n")
    
    for video_dir in video_dirs[:5]:  # Show top 5
        video_id = video_dir.name
        temporal_index = video_dir / "temporal_index.json"
        scene_manifest = video_dir / "video" / "scene_manifest.json"
        
        status_items = []
        
        if temporal_index.exists():
            try:
                with open(temporal_index, 'r') as f:
                    ti = json.load(f)
                scene_count = len(ti.get('scenes', []))
                phase5 = "[PASS]" if ti.get('phase5_complete') else "[FAIL]"
                phase6 = "[PASS]" if ti.get('phase6_complete') else "[FAIL]"
                status_items.append(f"{scene_count} scenes, P5:{phase5}, P6:{phase6}")
            except:
                status_items.append("temporal_index (parse error)")
        else:
            status_items.append("[FAIL] no temporal_index")
        
        if scene_manifest.exists():
            status_items.append("[PASS] scene_manifest")
        else:
            status_items.append("[FAIL] no scene_manifest")
        
        print(f"  [VIDEO] {video_id}")
        print(f"     {', '.join(status_items)}")


def main():
    """Run system status checks."""
    print("\n" + "==="*40)
    print("GOODQ4ALL SYSTEM STATUS DASHBOARD")
    print("==="*40)
    
    check_environment()
    cfg = check_config()
    check_directories(cfg)
    check_recent_ingestions(cfg)
    
    print("\n" + "="*80)
    print("STATUS CHECK COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
