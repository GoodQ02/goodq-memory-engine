import sys
import os
import json
import sqlite3
import shutil
import subprocess
import urllib.request
import yaml
from pathlib import Path

def count_qdrant_points(video_hash: str, collection: str = "goodq_clip") -> int:
    try:
        url = f"http://localhost:6333/collections/{collection}/points/scroll"
        req_data = {
            "filter": {
                "must": [
                    {"key": "video_id", "match": {"value": video_hash}}
                ]
            },
            "limit": 1000
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(req_data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            res = json.loads(response.read().decode("utf-8"))
            return len(res.get("result", {}).get("points", []))
    except Exception as e:
        print(f"Warning: Qdrant query to {collection} failed: {e}")
        return 0

def get_db_stats(db_path: Path):
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    stats = {}
    try:
        # Check scenes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scenes'")
        if cursor.fetchone():
            cursor.execute("SELECT count(*) FROM scenes")
            stats["scenes_count"] = cursor.fetchone()[0]
            cursor.execute("SELECT id, start, end FROM scenes ORDER BY start")
            stats["scenes_list"] = [{"id": r[0], "start": r[1], "end": r[2]} for r in cursor.fetchall()]
        
        # Check video segments / transcripts
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='video_segments'")
        if cursor.fetchone():
            cursor.execute("SELECT count(*) FROM video_segments")
            stats["video_segments_count"] = cursor.fetchone()[0]

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entity_resolutions'")
        if cursor.fetchone():
            cursor.execute("SELECT count(*) FROM entity_resolutions")
            stats["entity_resolutions_count"] = cursor.fetchone()[0]
    except Exception as e:
        print(f"DB check failed: {e}")
    finally:
        conn.close()
    return stats

def get_kg_stats(kg_path: Path):
    if not kg_path.exists():
        return {"nodes": 0, "edges": 0}
    conn = sqlite3.connect(kg_path)
    cursor = conn.cursor()
    stats = {"nodes": 0, "edges": 0}
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='nodes'")
        if cursor.fetchone():
            cursor.execute("SELECT count(*) FROM nodes")
            stats["nodes"] = cursor.fetchone()[0]
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='edges'")
        if cursor.fetchone():
            cursor.execute("SELECT count(*) FROM edges")
            stats["edges"] = cursor.fetchone()[0]
    except Exception as e:
        print(f"KG check failed: {e}")
    finally:
        conn.close()
    return stats

def write_merged_config(config_path: Path, db_dir: Path):
    # Load base config if exists
    config_data = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
    
    # Merge pathways db_dir and leaf overrides
    config_data.setdefault("paths", {})
    db_dir_str = str(db_dir.as_posix())
    
    config_data["paths"]["db_dir"] = db_dir_str
    config_data["paths"]["db_path"] = f"{db_dir_str}/memory.db"
    config_data["paths"]["knowledge_graph_db"] = f"{db_dir_str}/knowledge_graph.db"
    config_data["paths"]["faiss_dir"] = f"{db_dir_str}/faiss"
    config_data["paths"]["processing"] = f"{db_dir_str}/processing"
    config_data["paths"]["log_dir"] = f"{db_dir_str}/logs"
    config_data["paths"]["output_directory"] = f"{db_dir_str}/output"
    config_data["paths"]["csv_path"] = f"{db_dir_str}/logs/system_metrics.csv"
    config_data["paths"]["watchdog_state_file"] = f"{db_dir_str}/logs/watchdog_state.json"
    config_data["paths"]["watchdog_lock_file"] = f"{db_dir_str}/logs/watchdog.lock"

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config_data, f)

def main():
    os.environ["GOODQ_NO_AUTO_GPU"] = "1"
    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)

    config_local_path = repo_root / "configs" / "config.local.yaml"
    backup_config_path = repo_root / "configs" / "config.local.yaml.bak"

    # Backup existing config.local.yaml
    if config_local_path.exists():
        shutil.copy2(config_local_path, backup_config_path)

    temp_db_seq = repo_root / "temp_db_seq"
    temp_db_prog = repo_root / "temp_db_prog"

    # Clean prior temp DBs
    if temp_db_seq.exists():
        shutil.rmtree(temp_db_seq, ignore_errors=True)
    if temp_db_prog.exists():
        shutil.rmtree(temp_db_prog, ignore_errors=True)

    try:
        # === 1. RUN SEQUENTIAL INGESTION ===
        print("=== Running Sequential Ingestion ===")
        write_merged_config(config_local_path, temp_db_seq)

        # Run sequential
        cmd_seq = [
            sys.executable, "cli/run_ingestion.py",
            "--input-dir", "samples/",
            "--force"
        ]
        subprocess.run(cmd_seq, check=True)

        # Get video hash from sequential outputs
        processing_dirs = list((temp_db_seq / "processing").glob("*"))
        if not processing_dirs:
            raise RuntimeError("Sequential run failed to create processing directory.")
        video_name = processing_dirs[0].name
        
        manifest_path_seq = temp_db_seq / "processing" / video_name / "video" / "scene_manifest.json"
        if not manifest_path_seq.exists():
            raise RuntimeError("Sequential run did not create scene_manifest.json")
        
        manifest_data_seq = json.loads(manifest_path_seq.read_text(encoding="utf-8"))
        video_hash = manifest_data_seq.get("video_id")

        seq_db_stats = get_db_stats(temp_db_seq / "memory.db")
        seq_kg_stats = get_kg_stats(temp_db_seq / "knowledge_graph.db")
        seq_qdrant_clip = count_qdrant_points(video_hash, "goodq_clip")
        seq_qdrant_dino = count_qdrant_points(video_hash, "goodq_dino")

        temporal_index_path_seq = temp_db_seq / "processing" / video_name / "video" / "temporal_index.json"
        seq_temporal_index = {}
        if temporal_index_path_seq.exists():
            seq_temporal_index = json.loads(temporal_index_path_seq.read_text(encoding="utf-8"))

        # === 2. RUN PROGRESSIVE INGESTION ===
        print("=== Running Progressive Ingestion ===")
        write_merged_config(config_local_path, temp_db_prog)

        # Run progressive with short chunk/overlap
        cmd_prog = [
            sys.executable, "cli/run_ingestion.py",
            "--input-dir", "samples/",
            "--force",
            "--chunk-size", "5.0",
            "--chunk-overlap", "1.0"
        ]
        subprocess.run(cmd_prog, check=True)

        manifest_path_prog = temp_db_prog / "processing" / video_name / "video" / "scene_manifest.json"
        if not manifest_path_prog.exists():
            raise RuntimeError("Progressive run did not create scene_manifest.json")

        prog_db_stats = get_db_stats(temp_db_prog / "memory.db")
        prog_kg_stats = get_kg_stats(temp_db_prog / "knowledge_graph.db")
        prog_qdrant_clip = count_qdrant_points(video_hash, "goodq_clip")
        prog_qdrant_dino = count_qdrant_points(video_hash, "goodq_dino")

        temporal_index_path_prog = temp_db_prog / "processing" / video_name / "video" / "temporal_index.json"
        prog_temporal_index = {}
        if temporal_index_path_prog.exists():
            prog_temporal_index = json.loads(temporal_index_path_prog.read_text(encoding="utf-8"))

        # === 3. COMPARE AND GENERATE REPORT ===
        print("=== Auditing Ingestion Parity ===")
        report = {
            "video_hash": video_hash,
            "sequential": {
                "scenes_count": seq_db_stats.get("scenes_count", 0),
                "video_segments_count": seq_db_stats.get("video_segments_count", 0),
                "entities_count": seq_db_stats.get("entity_resolutions_count", 0),
                "kg_nodes": seq_kg_stats.get("nodes", 0),
                "kg_edges": seq_kg_stats.get("edges", 0),
                "qdrant_clip_points": seq_qdrant_clip,
                "qdrant_dino_points": seq_qdrant_dino,
                "temporal_index_scenes": len(seq_temporal_index.get("scenes", [])),
            },
            "progressive": {
                "scenes_count": prog_db_stats.get("scenes_count", 0),
                "video_segments_count": prog_db_stats.get("video_segments_count", 0),
                "entities_count": prog_db_stats.get("entity_resolutions_count", 0),
                "kg_nodes": prog_kg_stats.get("nodes", 0),
                "kg_edges": prog_kg_stats.get("edges", 0),
                "qdrant_clip_points": prog_qdrant_clip,
                "qdrant_dino_points": prog_qdrant_dino,
                "temporal_index_scenes": len(prog_temporal_index.get("scenes", [])),
            },
            "parity_status": "PASS"
        }

        # Validate parity matches exactly
        errors = []
        if report["sequential"]["scenes_count"] != report["progressive"]["scenes_count"]:
            errors.append(f"Scene count mismatch: {report['sequential']['scenes_count']} vs {report['progressive']['scenes_count']}")
        
        # Verify scene ID list matches
        seq_scenes = seq_db_stats.get("scenes_list", [])
        prog_scenes = prog_db_stats.get("scenes_list", [])
        if len(seq_scenes) != len(prog_scenes):
            errors.append("Scene lists length mismatch")
        else:
            for s_s, p_s in zip(seq_scenes, prog_scenes):
                if s_s["id"] != p_s["id"]:
                    errors.append(f"Scene ID mismatch: {s_s['id']} vs {p_s['id']}")
                if abs(s_s["start"] - p_s["start"]) > 1e-3 or abs(s_s["end"] - p_s["end"]) > 1e-3:
                    errors.append(f"Scene time mismatch: {s_s} vs {p_s}")

        if report["sequential"]["video_segments_count"] != report["progressive"]["video_segments_count"]:
            errors.append(f"Video segment count mismatch: {report['sequential']['video_segments_count']} vs {report['progressive']['video_segments_count']}")

        if report["sequential"]["kg_nodes"] != report["progressive"]["kg_nodes"]:
            errors.append(f"KG node count mismatch: {report['sequential']['kg_nodes']} vs {report['progressive']['kg_nodes']}")

        if report["sequential"]["kg_edges"] != report["progressive"]["kg_edges"]:
            errors.append(f"KG edge count mismatch: {report['sequential']['kg_edges']} vs {report['progressive']['kg_edges']}")

        # Qdrant and FAISS vector counts checking
        if report["sequential"]["qdrant_clip_points"] != report["progressive"]["qdrant_clip_points"]:
            errors.append(f"Qdrant CLIP points mismatch: {report['sequential']['qdrant_clip_points']} vs {report['progressive']['qdrant_clip_points']}")

        if report["sequential"]["temporal_index_scenes"] != report["progressive"]["temporal_index_scenes"]:
            errors.append(f"Temporal index scene coverage mismatch: {report['sequential']['temporal_index_scenes']} vs {report['progressive']['temporal_index_scenes']}")

        if errors:
            report["parity_status"] = "FAIL"
            report["errors"] = errors
            print("Parity Check FAILED with errors:")
            for err in errors:
                print(f" - {err}")
        else:
            print("Parity Check PASSED!")

        # Write progressive_parity_report.json
        report_path = repo_root / "progressive_parity_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Report written to {report_path}")

        if errors:
            sys.exit(1)

    finally:
        # Restore backup config.local.yaml
        if backup_config_path.exists():
            shutil.move(str(backup_config_path), str(config_local_path))
        elif config_local_path.exists():
            config_local_path.unlink()

        # Cleanup temp DBs
        if temp_db_seq.exists():
            shutil.rmtree(temp_db_seq, ignore_errors=True)
        if temp_db_prog.exists():
            shutil.rmtree(temp_db_prog, ignore_errors=True)

if __name__ == "__main__":
    main()
