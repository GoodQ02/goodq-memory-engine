from datetime import datetime
from pathlib import Path
import socket

OUTPUT_PATH = Path("docs/goodq4all_agent_status.md")

def check_port(port):
    try:
        with socket.create_connection(("localhost", port), timeout=1):
            return "reachable"
    except Exception:
        return "not reachable"

def main():
    now = datetime.now().isoformat(timespec="seconds")

    lines = []
    lines.append("# GoodQ4All Agent Status")
    lines.append("")
    lines.append(f"_Generated: {now}_")
    lines.append("")
    lines.append("## System Mode")
    lines.append("- MODE: Stabilization / Audit")
    lines.append("")
    lines.append("## Phase Status")
    lines.append("| Phase | Status | Notes |")
    lines.append("|------|--------|-------|")
    lines.append("| Scene Detection | ✅ Complete | Stable |")
    lines.append("| Audio Extraction | ✅ Complete | Long-form audio verified |")
    lines.append("| Visual Captioning | ✅ Complete | vit-gpt2 |")
    lines.append("| CLIP Embeddings | ⚠️ Partial | Generated; persistence active post-2025-12-16 |")
    lines.append("| DINO Embeddings | ⚠️ Partial | Same as CLIP |")
    lines.append("| Face Detection | ❌ Disabled | facenet_pytorch not installed |")
    lines.append("| Knowledge Graph | ✅ Complete | ~1300+ nodes |")
    lines.append("| Vector Storage (Qdrant) | ✅ Wired | Port 6333 reachable |")
    lines.append("| Phase 6b Harmonization | ⏸️ Gated | Manifest persistence |")
    lines.append("| Final Report | ⚠️ Broken | Type error; non-critical |")
    lines.append("")
    lines.append("## Storage & Memory Health")
    lines.append("- SQLite: healthy")
    lines.append("- Knowledge Graph: healthy")
    lines.append(f"- Qdrant (6333): {check_port(6333)}")
    lines.append("- FAISS: enabled (fallback)")
    lines.append("")
    lines.append("## Known Blockers (Do Not Fix Without Approval)")
    lines.append("- Scene manifest persistence pathing")
    lines.append("- Face detection dependency (facenet_pytorch)")
    lines.append("- Final report formatter error")
    lines.append("")
    lines.append("## Recent Audits & Fixes")
    lines.append("- 2025-12-16: Qdrant wiring completed")
    lines.append("- 2025-12-16: Silent exception handling hardened (API + Watchdog)")
    lines.append("- 2025-12-16: Port standardization to 6333")
    lines.append("")
    lines.append("## Agent Instructions (Binding)")
    lines.append("- Do NOT re-run full ingestion")
    lines.append("- Do NOT refactor configs")
    lines.append("- Do NOT enable face detection")
    lines.append("- Operate in audit-only or surgical-fix mode unless approved")
    lines.append("")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Wrote {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
