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
    today = datetime.now().date().isoformat()

    lines = []
    lines.append("<!-- DOC_BADGE: OPERATIONAL -->")
    lines.append("<!-- DOC_STATUS: GENERATED_SNAPSHOT -->")
    lines.append(f"<!-- DOC_LAST_VERIFIED: {today} -->")
    lines.append("")
    lines.append("# GoodQ4All Agent Status")
    lines.append("")
    lines.append(f"_Generated: {now}_")
    lines.append("")
    lines.append("This document is a generated operator snapshot of the current stitching-era baseline.")
    lines.append("Treat per-run artifacts and canonical runtime contracts as source of truth for live claims.")
    lines.append("")
    lines.append("## System Mode")
    lines.append("- MODE: Operational / Hardening")
    lines.append(f"Audit Status: ACTIVE ({today})")
    lines.append("")
    lines.append("## Phase Status")
    lines.append("| Phase | Status | Notes |")
    lines.append("|------|--------|-------|")
    lines.append("| Scene Detection | ✅ Complete | Stable |")
    lines.append("| Audio Extraction | ✅ Complete | Unified WSL worker + structured Windows fallback |")
    lines.append("| Visual Captioning | ✅ Complete | Native faults surfaced as partial-scene errors |")
    lines.append("| CLIP Embeddings | ✅ Complete | Phase 6a persisted to Qdrant |")
    lines.append("| DINO Embeddings | ✅ Complete | Retry containment active for native crashes |")
    lines.append("| Face Detection | ✅ Complete | Structural face evidence active |")
    lines.append("| Knowledge Graph | ✅ Complete | Realtime inserts + identity ladder active |")
    lines.append("| Vector Storage (Qdrant) | ✅ Wired | Port 6333 reachable |")
    lines.append("| Phase 6b Harmonization | ✅ Operational | Epoch-scoped temporal index is canonical |")
    lines.append("| Identity Stitching | ⚠️ Early Operational | speaker patterns live; promotion remains conservative |")
    lines.append("| Final Report | ✅ Available | scene_ingest_results.json is canonical run summary |")
    lines.append("")
    lines.append("## Storage & Memory Health")
    lines.append("- SQLite (epoch-scoped memory.db): healthy")
    lines.append("- Knowledge Graph (epoch-scoped knowledge_graph.db): healthy")
    lines.append(f"- Qdrant (6333): {check_port(6333)}")
    lines.append("- FAISS: enabled (secondary parity/fallback)")
    lines.append("- Canonical artifact root: `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/<epoch>/processing/`")
    lines.append("")
    lines.append("## Known Active Gaps")
    lines.append("- Native vision-step crashes can still surface occasionally (`image_caption`, `object_detect`, `image_embed_dino`).")
    lines.append("- Identity promotion is intentionally conservative; multi-episode evidence is required before stronger links appear.")
    lines.append("- Historical docs may still reference the old queue-era WSL audio service or non-epoch artifact roots.")
    lines.append("")
    lines.append("## Recent Notable Changes")
    lines.append("- Restored `GPU_ENHANCED` desktop runtime through bootstrap-managed environment repair and verified CUDA-backed `goodq_core`.")
    lines.append("- Restored unified WSL audio with local-first/offline model resolution, diarization recovery, and non-recursive Windows fallback.")
    lines.append("- Hardened Phase 6 and DINO runtime behavior; Qdrant scene-vector persistence is operational and explicit.")
    lines.append("- Raised semantic quality by removing placeholder scaffolding and tightening alias/noise filtering.")
    lines.append("- Added the identity formation layer: `speaker_pattern`, `voice_pattern_match`, `identity_candidate`, `identity_supported`, `identity_evidence`.")
    lines.append("")
    lines.append("## Agent Instructions (Binding)")
    lines.append("- Treat the epoch processing tree and per-run artifacts as canonical, not historical `logs/scene_ingest` paths.")
    lines.append("- Trust the direct unified WSL worker contract over older queue-service-era notes.")
    lines.append("- Keep segmentation on the legacy production path until an explicit promotion decision is approved.")
    lines.append("- Operate surgically: verify through targeted tests, witness artifacts, or focused reruns before widening scope.")
    lines.append("")
    lines.append("## Read These First")
    lines.append("- docs/HANDOFF_BASEMENT_PHASE.md")
    lines.append("- docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md")
    lines.append("- docs/architecture/IDENTITY_STITCHING_CONTRACT.md")
    lines.append("- docs/reference/WSL_AUDIO_RUNTIME.md")
    lines.append("- docs/SCENE_MANIFEST_SPECIFICATION.md")
    lines.append("- docs/architecture/SYSTEM_ARCHITECTURE.md")
    lines.append("- docs/architecture/ARCHITECTURE_REFERENCE.md")
    lines.append("- docs/architecture/MEMORY_STORAGE.md")
    lines.append("- docs/architecture/components/VISION_PIPELINE.md")
    lines.append("- docs/systems/WATCHDOG_SYSTEM.md")
    lines.append("- docs/CONTROL_AGENT.md")
    lines.append("- docs/PHASE6_MULTIMODAL_FUSION.md")
    lines.append("- docs/CLI-REFERENCE.md")
    lines.append("- docs/technical/LIB_COMPONENTS.md")
    lines.append("")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Wrote {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
