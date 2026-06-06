import os
from pathlib import Path

def test_nsis_paths():
    # Find the nsi file relative to this test file
    test_dir = Path(__file__).parent
    repo_root = test_dir.parent.parent
    nsi_path = repo_root / "scripts/install/goodq4all_installer.nsi"
    
    assert nsi_path.exists(), f"NSIS installer script not found at {nsi_path}"
    
    content = nsi_path.read_text(encoding="utf-8")
    
    # Assert $COMMONAPPDATA\GoodQ4All is present
    assert "$COMMONAPPDATA\\GoodQ4All" in content
    
    # Assert $APPDATA\GoodQ4All is no longer used for mutable data directories or setup commands
    assert "$APPDATA\\GoodQ4All" not in content, "Found reference to legacy $APPDATA\\GoodQ4All path"


def test_launcher_paths():
    test_dir = Path(__file__).parent
    repo_root = test_dir.parent.parent
    launcher_path = repo_root / "scripts/install/LAUNCH_GOODQ.go"
    
    assert launcher_path.exists(), f"Go launcher source not found at {launcher_path}"
    
    content = launcher_path.read_text(encoding="utf-8")
    
    # Assert launcher resolves to ProgramData (or environment equivalent) on Windows
    assert 'progData := os.Getenv("ProgramData")' in content or 'os.Getenv("ProgramData")' in content
    assert 'filepath.Join(progData, "GoodQ4All")' in content
    
    # Assert that install root (Program Files) and mutable root are separate
    assert 'programFilesDir := filepath.Dir(os.Args[0])' in content
