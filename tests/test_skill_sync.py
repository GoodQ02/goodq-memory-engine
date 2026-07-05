import os
import filecmp
from pathlib import Path

def test_ucf_ledger_skill_sync():
    """
    Ensure that the skill schema copy in .agents/skills/ucf-invariant-anchor/scripts/ucf_ledger.py
    stays synchronized with the canonical scripts/ucf/ucf_ledger.py.
    """
    project_root = Path(__file__).resolve().parent.parent
    canonical_path = project_root / "scripts" / "ucf" / "ucf_ledger.py"
    skill_path = project_root / ".agents" / "skills" / "ucf-invariant-anchor" / "scripts" / "ucf_ledger.py"
    
    assert canonical_path.exists(), f"Canonical path missing: {canonical_path}"
    assert skill_path.exists(), f"Skill path missing: {skill_path}"
    
    # Check if files are identical
    is_identical = filecmp.cmp(canonical_path, skill_path, shallow=False)
    
    if not is_identical:
        import shutil
        # Auto-sync it for convenience or fail the test so CI catches it.
        # Here we just fail with a helpful error.
        assert False, (
            "ucf_ledger.py in skill folder is out of sync with canonical scripts/ucf/ucf_ledger.py! "
            f"Please run: cp {canonical_path} {skill_path}"
        )
