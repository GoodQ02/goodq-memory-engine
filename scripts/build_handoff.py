#!/usr/bin/env python3
from pathlib import Path

def main():
    agent_dir = Path("L:/GOODCUBE/projects/goodq4all/.agents/worker_lifecycle")
    repo_root = Path("L:/GOODCUBE/projects/goodq4all")
    
    handoff_path = agent_dir / "handoff.md"
    run_lifecycle_path = repo_root / "scripts" / "run_lifecycle.py"
    check_qdrant_path = repo_root / "scripts" / "check_qdrant.py"
    lifecycle_run_log_path = agent_dir / "lifecycle_run.log"
    qdrant_verif_log_path = agent_dir / "qdrant_verification.log"
    
    # Read files
    handoff_text = handoff_path.read_text(encoding="utf-8")
    run_lifecycle_code = run_lifecycle_path.read_text(encoding="utf-8")
    check_qdrant_code = check_qdrant_path.read_text(encoding="utf-8")
    lifecycle_run_log = lifecycle_run_log_path.read_text(encoding="utf-8")
    qdrant_verif_log = qdrant_verif_log_path.read_text(encoding="utf-8")
    
    # Perform replacements
    handoff_text = handoff_text.replace(
        "# (Contents of scripts/run_lifecycle.py as written)",
        run_lifecycle_code.strip()
    )
    handoff_text = handoff_text.replace(
        "# (Contents of scripts/check_qdrant.py as written)",
        check_qdrant_code.strip()
    )
    handoff_text = handoff_text.replace(
        "(Log from scripts/run_lifecycle.py execution)",
        lifecycle_run_log.strip()
    )
    handoff_text = handoff_text.replace(
        "(Log from scripts/check_qdrant.py execution)",
        qdrant_verif_log.strip()
    )
    
    # Write back
    handoff_path.write_text(handoff_text, encoding="utf-8")
    print("Programmatic replacement in handoff.md completed successfully.")

if __name__ == "__main__":
    main()
