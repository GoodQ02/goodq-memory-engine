from __future__ import annotations
import sys
# Global encoding safeguard for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

import json
from pathlib import Path
from typing import Optional

import typer

from steps.common.config_loader import load_configs
from typing import Any, Dict

app = typer.Typer(add_completion=False, help="GoodQ memory management CLI")


def _missing_memory_management(command_name: str, exc: ModuleNotFoundError) -> None:
    typer.echo(
        (
            f"cli.memory {command_name} is unavailable because the legacy "
            f"memory_management package is missing ({exc.name})."
        ),
        err=True,
    )
    raise typer.Exit(code=2)


@app.command("health-check")
def health_check(output_file: Optional[str] = typer.Option(None, help="Write report to file")) -> None:
    try:
        from lib.memory_management.diagnostics import run_all_diagnostics
    except ModuleNotFoundError as exc:
        _missing_memory_management("health-check", exc)

    cfg = load_configs({})
    paths = cfg.get("paths", {}) or {}
    report = run_all_diagnostics(paths)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    typer.echo(text)
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(text)
    # exit non-zero if error or warning
    if report.get("status") not in ("ok",):
        raise typer.Exit(code=1)


@app.command("backup")
def backup() -> None:
    try:
        from lib.memory_management.utils import create_memory_backup
    except ModuleNotFoundError as exc:
        _missing_memory_management("backup", exc)

    cfg = load_configs({})
    paths = cfg.get("paths", {}) or {}
    backup_root = (paths.get("log_dir") or ".")
    dest = create_memory_backup(paths, backup_root)
    typer.echo(json.dumps({"backup_dir": dest}, ensure_ascii=False))


@app.command("verify-schema")
def verify_schema() -> None:
    try:
        from lib.memory_management.diagnostics import check_schema_drift
    except ModuleNotFoundError as exc:
        _missing_memory_management("verify-schema", exc)

    cfg = load_configs({})
    paths = cfg.get("paths", {}) or {}
    rep = check_schema_drift(paths.get("db_path") or "")
    if rep.get("status") == "ok":
        typer.echo("Schema OK")
        raise typer.Exit(code=0)
    else:
        typer.echo("ERROR: Schema drift detected!", err=True)
        typer.echo(json.dumps(rep, ensure_ascii=False, indent=2))
        raise typer.Exit(code=1)


@app.command("migrate")
def migrate() -> None:
    """Run safe DB migration to enforce NOT NULLs and drop legacy tables."""
    try:
        from lib.memory_management.migrate import migrate_database
    except ModuleNotFoundError as exc:
        _missing_memory_management("migrate", exc)

    cfg = load_configs({})
    paths = cfg.get("paths", {}) or {}
    db_path = paths.get("db_path")
    log_dir = paths.get("log_dir") or "."
    if not db_path:
        typer.echo("No db_path configured.", err=True)
        raise typer.Exit(code=2)
    report = migrate_database(db_path, backup_dir=log_dir)
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("status") != "ok":
        raise typer.Exit(code=1)


@app.command("seed-missing-assets")
def seed_missing_assets() -> None:
    """Create minimal assets so diagnostics pass (audio index + id-map DBs).

    This seeds a single vector into the audio FAISS index (dim=512) and ensures
    'clap_id_map', 'clip_id_map', and 'dino_id_map' tables exist with at least
    one row, using seeded sentinel entries if needed.
    """
    import os
    import sqlite3
    from pathlib import Path
    import random

    cfg = load_configs({})
    paths = cfg.get("paths", {}) or {}
    changes = {"created": [], "updated": [], "notes": []}

    # Audio FAISS index
    audio_index = paths.get("faiss_audio_path")
    try:
        import faiss  # type: ignore
        if audio_index:
            ap = Path(str(audio_index))
            ap.parent.mkdir(parents=True, exist_ok=True)
            create = True
            if ap.exists():
                try:
                    idx = faiss.read_index(str(ap))
                    if int(getattr(idx, "ntotal", 0)) > 0 and int(getattr(idx, "d", 0)) == 512:
                        create = False
                except Exception:
                    create = True
            if create:
                idx = faiss.IndexHNSWFlat(512, 32)
                idx.hnsw.efConstruction = 200
                idx.hnsw.efSearch = 50
                import numpy as np  # type: ignore
                vec = np.random.randn(1, 512).astype("float32")
                uid = np.array([random.randint(1, 2**31 - 1)], dtype="int64")
                try:
                    idx.add_with_ids(vec, uid)
                except Exception:
                    idx.add(vec)
                faiss.write_index(idx, str(ap))
                changes["created"].append({"faiss_audio_path": str(ap)})
    except Exception as exc:
        changes["notes"].append(f"audio_index_seed_failed: {exc}")

    def _ensure_id_map(db_path: str | None, table: str, sample_path: str) -> None:
        if not db_path:
            return
        from steps.common.memory import ensure_id_map_table_schema
        ensure_id_map_table_schema(db_path, table)
        p = Path(str(db_path))
        con = sqlite3.connect(str(p), check_same_thread=False)
        try:
            with con:
                cur = con.execute(f"SELECT COUNT(*) FROM {table}")
                count = int(cur.fetchone()[0])
                if count == 0:
                    from datetime import datetime
                    now = datetime.utcnow().isoformat()
                    con.execute(
                        f"""
                        INSERT OR REPLACE INTO {table}(
                            video_hash, faiss_id, hash, source_path, created_at,
                            epoch_id, scene_id, scene_hash, worker_name, vector_model_tag, modality, ucf_frame_id
                        ) VALUES (?,?,?,?,?,NULL,NULL,NULL,NULL,NULL,NULL,NULL)
                        """,
                        ("sentinel_video_hash", 1, "seed_sentinel", sample_path, now),
                    )
                    changes["created"].append({table: str(p)})
        finally:
            try:
                con.close()
            except Exception:
                pass

    # Choose sample files if available
    repo_root = Path(__file__).resolve().parents[1]
    smoke = repo_root / "samples" / "ingestion"
    sample_img = str((smoke / "sample.jpg")) if (smoke / "sample.jpg").exists() else ""
    sample_wav = str((smoke / "sample.wav")) if (smoke / "sample.wav").exists() else sample_img or ""

    _ensure_id_map(paths.get("clap_id_map_db"), "clap_id_map", sample_wav)
    _ensure_id_map(paths.get("clip_id_map_db"), "clip_id_map", sample_img)
    _ensure_id_map(paths.get("dino_id_map_db"), "dino_id_map", sample_img)

    typer.echo(json.dumps({"status": "ok", "changes": changes}, ensure_ascii=False, indent=2))


def _populate_id_map_from_embeddings(paths: Dict[str, Any]) -> Dict[str, Any]:
    import sqlite3
    from datetime import datetime
    from pathlib import Path
    from steps.common.memory import ensure_id_map_table_schema

    db_path = paths.get("db_path")
    if not db_path:
        return {"status": "skip", "message": "No db_path configured"}
    con = sqlite3.connect(str(db_path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT 
                e.hash, 
                e.faiss_id, 
                e.source_path, 
                e.modality, 
                e.scene_id, 
                e.created_at,
                s.video_hash 
            FROM embeddings e
            LEFT JOIN scenes s ON e.scene_id = s.id
            WHERE e.faiss_id IS NOT NULL
            """
        )
        rows = cur.fetchall()
        now = datetime.utcnow().isoformat()
        
        def upsert(dbfile: str | None, table: str, filt_mod: str) -> int:
            if not dbfile:
                return 0
            ensure_id_map_table_schema(dbfile, table)
            
            # Resolve metadata based on filt_mod
            if filt_mod == "audio":
                model_tag = "laion/clap-htsat-fused"
                worker_name = "audio_embed_clap"
                modality = "audio"
            elif filt_mod == "clip":
                model_tag = "openai/clip-vit-large-patch14"
                worker_name = "image_embed_clip"
                modality = "video"
            elif filt_mod == "dino":
                model_tag = "facebook/dinov2-large"
                worker_name = "image_embed_dino"
                modality = "video"
            else:
                model_tag = None
                worker_name = None
                modality = None
                
            p = Path(str(dbfile))
            c = sqlite3.connect(str(p), check_same_thread=False)
            try:
                with c:
                    count = 0
                    for r in rows:
                        if (r["modality"] or "").lower() != filt_mod:
                            continue
                        c.execute(
                            f"""
                            INSERT OR REPLACE INTO {table} (
                                video_hash, faiss_id, hash, source_path, created_at,
                                epoch_id, scene_id, scene_hash, worker_name, vector_model_tag,
                                modality, ucf_frame_id
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                r["video_hash"] or "",
                                int(r["faiss_id"]),
                                r["hash"],
                                r["source_path"] or "",
                                r["created_at"] or now,
                                None,
                                r["scene_id"],
                                r["hash"],
                                worker_name,
                                model_tag,
                                modality,
                                None
                            ),
                        )
                        count += 1
                    return count
            finally:
                try:
                    c.close()
                except Exception:
                    pass

        wrote = {
            "clap_id_map": upsert(paths.get("clap_id_map_db"), "clap_id_map", "audio"),
            "clip_id_map": upsert(paths.get("clip_id_map_db"), "clip_id_map", "clip"),
            "dino_id_map": upsert(paths.get("dino_id_map_db"), "dino_id_map", "dino"),
        }
        return {"status": "ok", "wrote": wrote, "rows_seen": len(rows)}
    finally:
        try:
            con.close()
        except Exception:
            pass


@app.command("rebuild-id-maps")
def rebuild_id_maps() -> None:
    """Populate/refresh ID-map databases from the embeddings table."""
    cfg = load_configs({})
    paths = cfg.get("paths", {}) or {}
    rep = _populate_id_map_from_embeddings(paths)
    typer.echo(json.dumps(rep, ensure_ascii=False, indent=2))
    if rep.get("status") != "ok":
        raise typer.Exit(code=1)


@app.command("cleanup-seed-sentinels")
def cleanup_seed_sentinels() -> None:
    """Remove any seeded sentinel rows from ID-map DBs."""
    import sqlite3
    from pathlib import Path
    cfg = load_configs({})
    paths = cfg.get("paths", {}) or {}
    cleaned = []
    for key, table in (("clap_id_map_db", "clap_id_map"), ("clip_id_map_db", "clip_id_map"), ("dino_id_map_db", "dino_id_map")):
        dbf = paths.get(key)
        if not dbf:
            continue
        p = Path(str(dbf))
        if not p.exists():
            continue
        con = sqlite3.connect(str(p), check_same_thread=False)
        try:
            with con:
                con.execute(f"DELETE FROM {table} WHERE hash IN ('placeholder', 'seed_sentinel')")
                cleaned.append({"db": str(p), "table": table})
        finally:
            try:
                con.close()
            except Exception:
                pass
    typer.echo(json.dumps({"status": "ok", "cleaned": cleaned}, ensure_ascii=False, indent=2))



@app.command("register-scene-bundle")
def register_scene_bundle_cmd(bundle: Path = typer.Argument(..., help="Path to JSON bundle")) -> None:
    payload = json.loads(Path(bundle).read_text(encoding="utf-8"))
    video_hash = payload.get("video_hash")
    scene = payload.get("scene") or {}
    if not video_hash or not scene:
        raise typer.BadParameter("bundle must include video_hash and scene")

    cfg = load_configs({})
    from steps.common.memory import ensure_scene, register_scene_bundle

    scene_id = payload.get("scene_id")
    scene_start = float(scene.get("start", 0.0) or 0.0)
    scene_end = float(scene.get("end", scene_start) or scene_start)
    initial_meta = scene.get("meta") if isinstance(scene.get("meta"), dict) else None
    if not scene_id:
        scene_id = ensure_scene(cfg, video_hash, scene_start, scene_end, initial_meta)

    result = register_scene_bundle(
        cfg,
        video_hash=video_hash,
        scene=scene,
        scene_id=scene_id,
        detection_meta=payload.get("detection_meta"),
        frame=payload.get("frame"),
        audio=payload.get("audio"),
        errors=payload.get("errors"),
    )
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))

def main() -> None:
    app()


if __name__ == "__main__":
    main()
