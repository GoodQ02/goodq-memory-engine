"""
GoodQ UI-Safe Conduits v1 (offline/on-demand).

Invoke:
  python -m cli.ui_conduits_rollup

This tool creates/updates derived *UI-safe* tables only. It must not expose raw event tables, raw transcripts,
raw embeddings/vectors, or absolute filesystem paths.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .media_refs import tokenize_processing_path

# Best-effort to keep this tool low-impact (avoid writing __pycache__ for subsequent imports).
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scene_modality_coverage (
  video_id TEXT NOT NULL,
  scene_id TEXT NOT NULL,
  has_clip INTEGER NOT NULL,
  has_dino INTEGER NOT NULL,
  has_audio_clap INTEGER NOT NULL,
  has_text_frame INTEGER NOT NULL,
  has_text_transcript INTEGER NOT NULL,
  provenance_coverage_pct REAL,
  last_commit_ts_utc TEXT,
  PRIMARY KEY (video_id, scene_id)
);

CREATE INDEX IF NOT EXISTS idx_smc_video ON scene_modality_coverage(video_id);
CREATE INDEX IF NOT EXISTS idx_smc_scene ON scene_modality_coverage(scene_id);

CREATE TABLE IF NOT EXISTS scene_index_public (
  video_id TEXT NOT NULL,
  scene_id TEXT NOT NULL,
  start REAL,
  end REAL,
  phase6_complete INTEGER,
  phase6_harmonized INTEGER,
  media_refs_json TEXT NOT NULL,
  PRIMARY KEY (video_id, scene_id)
);

CREATE INDEX IF NOT EXISTS idx_sip_video ON scene_index_public(video_id);
CREATE INDEX IF NOT EXISTS idx_sip_scene ON scene_index_public(scene_id);
"""


def _load_configs() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        from steps.common.config_loader import load_configs

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            cfg = load_configs({})
        noise = buf.getvalue().strip() or None
        if not isinstance(cfg, dict):
            return None, f"load_configs returned {type(cfg)}"
        return cfg, noise
    except Exception as exc:
        return None, str(exc)


def _cfg_paths(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}


def _best_effort_wal(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    try:
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def _wsl_mount_path(win_path: str) -> Optional[str]:
    m = re.match(r"^([a-zA-Z]):[\\/](.*)$", win_path)
    if not m:
        return None
    drive = m.group(1).lower()
    rest = m.group(2).replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def _tokenize_under_processing_root(*, raw_path: str, processing_root: str, video_id: str) -> Optional[str]:
    return tokenize_processing_path(raw_path=raw_path, processing_root=processing_root, video_id=video_id)


@dataclass(frozen=True)
class _VideoFlags:
    phase6_complete: Optional[bool] = None
    phase6_harmonized: Optional[bool] = None


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _discover_processing_artifacts(processing_root: str) -> Tuple[Dict[str, _VideoFlags], Dict[Tuple[str, str], List[Dict[str, str]]]]:
    video_flags: Dict[str, _VideoFlags] = {}
    scene_media: Dict[Tuple[str, str], List[Dict[str, str]]] = {}

    if not isinstance(processing_root, str) or not processing_root.strip():
        return video_flags, scene_media
    root = processing_root

    # Video flags from temporal_index.json (contains phase6_harmonized).
    try:
        for dirpath, _, filenames in os.walk(root):
            if "temporal_index.json" not in filenames:
                continue
            p = os.path.join(dirpath, "temporal_index.json")
            data = _read_json(p)
            if not isinstance(data, dict):
                continue
            vid = data.get("video_id")
            if not isinstance(vid, str) or not vid.strip():
                continue
            flags = _VideoFlags(
                phase6_complete=bool(data.get("phase6_complete")) if "phase6_complete" in data else None,
                phase6_harmonized=bool(data.get("phase6_harmonized")) if "phase6_harmonized" in data else None,
            )
            if vid not in video_flags:
                video_flags[vid] = flags
    except Exception:
        pass

    # Scene media refs from canonical scene manifests.
    try:
        for dirpath, _, filenames in os.walk(root):
            if "scene_manifest.json" not in filenames:
                continue
            if os.path.basename(dirpath).lower() != "video":
                continue
            p = os.path.join(dirpath, "scene_manifest.json")
            data = _read_json(p)
            if not isinstance(data, dict):
                continue
            vid = data.get("video_id")
            if not isinstance(vid, str) or not vid.strip():
                continue

            # If temporal_index.json wasn't found for this video, still capture phase6_complete from manifest.
            if vid not in video_flags:
                video_flags[vid] = _VideoFlags(
                    phase6_complete=bool(data.get("phase6_complete")) if "phase6_complete" in data else None,
                    phase6_harmonized=None,
                )

            scenes = data.get("scenes")
            if not isinstance(scenes, list):
                continue

            for sc in scenes:
                if not isinstance(sc, dict):
                    continue
                scene_id = sc.get("scene_id")
                if not isinstance(scene_id, str) or not scene_id.strip():
                    continue

                refs: List[Dict[str, str]] = [{"kind": "manifest", "rel": f"{vid}/video/scene_manifest.json"}]

                rep = sc.get("representative_frame")
                if isinstance(rep, str) and rep.strip():
                    rel = _tokenize_under_processing_root(raw_path=rep, processing_root=root, video_id=vid)
                    if rel:
                        refs.append({"kind": "keyframe", "rel": rel})
                if len(refs) == 1:
                    frame_paths = sc.get("frame_paths")
                    if isinstance(frame_paths, list):
                        for fp in frame_paths:
                            if isinstance(fp, str) and fp.strip():
                                rel = _tokenize_under_processing_root(raw_path=fp, processing_root=root, video_id=vid)
                                if rel:
                                    refs.append({"kind": "keyframe", "rel": rel})
                                    break

                # De-dupe refs (stable order).
                seen = set()
                uniq: List[Dict[str, str]] = []
                for r in refs:
                    key = (r.get("kind"), r.get("rel"))
                    if key in seen:
                        continue
                    if not isinstance(r.get("kind"), str) or not isinstance(r.get("rel"), str):
                        continue
                    seen.add(key)
                    uniq.append(r)

                scene_media[(vid, scene_id)] = uniq
    except Exception:
        pass

    return video_flags, scene_media


def _update_scene_modality_coverage(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT
          s.video_hash,
          s.id,
          MAX(CASE WHEN m.modality = 'clip' AND m.committed = 1 THEN 1 ELSE 0 END) AS has_clip,
          MAX(CASE WHEN m.modality = 'dino' AND m.committed = 1 THEN 1 ELSE 0 END) AS has_dino,
          MAX(CASE WHEN m.modality = 'audio' AND m.committed = 1 THEN 1 ELSE 0 END) AS has_audio_clap,
          MAX(CASE WHEN m.modality = 'frame_text' AND m.committed = 1 THEN 1 ELSE 0 END) AS has_text_frame,
          MAX(CASE WHEN m.modality = 'audio_transcript' AND m.committed = 1 THEN 1 ELSE 0 END) AS has_text_transcript,
          MAX(CASE WHEN m.committed = 1 THEN m.ts_utc ELSE NULL END) AS last_commit_ts_utc
        FROM scenes s
        LEFT JOIN memory_commit_events m ON m.scene_id = s.id
        GROUP BY s.video_hash, s.id
        """
    ).fetchall()

    out: List[Tuple[Any, ...]] = []
    for (
        video_id,
        scene_id,
        has_clip,
        has_dino,
        has_audio_clap,
        has_text_frame,
        has_text_transcript,
        last_commit_ts_utc,
    ) in rows:
        c = int(has_clip or 0) + int(has_dino or 0) + int(has_audio_clap or 0) + int(has_text_frame or 0) + int(has_text_transcript or 0)
        pct = float(c) / 5.0
        out.append(
            (
                video_id,
                scene_id,
                int(has_clip or 0),
                int(has_dino or 0),
                int(has_audio_clap or 0),
                int(has_text_frame or 0),
                int(has_text_transcript or 0),
                pct,
                last_commit_ts_utc if isinstance(last_commit_ts_utc, str) and last_commit_ts_utc.strip() else None,
            )
        )

    with conn:
        conn.executemany(
            """
            INSERT INTO scene_modality_coverage(
              video_id, scene_id,
              has_clip, has_dino, has_audio_clap, has_text_frame, has_text_transcript,
              provenance_coverage_pct, last_commit_ts_utc
            )
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(video_id, scene_id) DO UPDATE SET
              has_clip = excluded.has_clip,
              has_dino = excluded.has_dino,
              has_audio_clap = excluded.has_audio_clap,
              has_text_frame = excluded.has_text_frame,
              has_text_transcript = excluded.has_text_transcript,
              provenance_coverage_pct = excluded.provenance_coverage_pct,
              last_commit_ts_utc = excluded.last_commit_ts_utc
            """,
            out,
        )
    return len(out)


def _update_scene_index_public(
    conn: sqlite3.Connection,
    *,
    video_flags: Dict[str, _VideoFlags],
    scene_media: Dict[Tuple[str, str], List[Dict[str, str]]],
) -> int:
    rows = conn.execute("SELECT id, video_hash, start, end FROM scenes").fetchall()
    out: List[Tuple[Any, ...]] = []
    for scene_id, video_id, start, end in rows:
        flags = video_flags.get(video_id) if isinstance(video_id, str) else None
        media = scene_media.get((video_id, scene_id)) if isinstance(video_id, str) and isinstance(scene_id, str) else None
        media_json = "[]"
        if isinstance(media, list):
            try:
                media_json = json.dumps(media, ensure_ascii=False)
            except Exception:
                media_json = "[]"
        out.append(
            (
                video_id,
                scene_id,
                float(start) if isinstance(start, (int, float)) else None,
                float(end) if isinstance(end, (int, float)) else None,
                1 if (flags is not None and flags.phase6_complete is True) else (0 if (flags is not None and flags.phase6_complete is False) else None),
                1
                if (flags is not None and flags.phase6_harmonized is True)
                else (0 if (flags is not None and flags.phase6_harmonized is False) else None),
                media_json,
            )
        )

    with conn:
        conn.executemany(
            """
            INSERT INTO scene_index_public(
              video_id, scene_id, start, end, phase6_complete, phase6_harmonized, media_refs_json
            )
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(video_id, scene_id) DO UPDATE SET
              start = excluded.start,
              end = excluded.end,
              phase6_complete = excluded.phase6_complete,
              phase6_harmonized = excluded.phase6_harmonized,
              media_refs_json = excluded.media_refs_json
            """,
            out,
        )
    return len(out)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GoodQ UI-Safe Conduits v1 (offline/on-demand)")
    parser.add_argument("--skip-index", action="store_true", help="Skip scene_index_public update")
    parser.add_argument("--skip-coverage", action="store_true", help="Skip scene_modality_coverage update")
    args = parser.parse_args(list(argv) if argv is not None else None)

    cfg, err = _load_configs()
    if cfg is None:
        print(f"FAIL: load_configs() failed: {err}")
        return 2

    paths = _cfg_paths(cfg)
    db_path = paths.get("db_path")
    processing_root = paths.get("processing")
    if not isinstance(db_path, str) or not db_path.strip():
        print("FAIL: cfg['paths']['db_path'] missing")
        return 2

    try:
        conn = sqlite3.connect(db_path, timeout=2.0, check_same_thread=False)
    except Exception as exc:
        print(f"FAIL: could not open db: {exc}")
        return 2

    try:
        _best_effort_wal(conn)
        conn.executescript(_SCHEMA_SQL)

        video_flags: Dict[str, _VideoFlags] = {}
        scene_media: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
        if not args.skip_index and isinstance(processing_root, str) and processing_root.strip() and os.path.isdir(processing_root):
            video_flags, scene_media = _discover_processing_artifacts(processing_root)

        updated = 0
        if not args.skip_coverage:
            n = _update_scene_modality_coverage(conn)
            updated += 1
            print(f"OK: scene_modality_coverage upserted rows={n}")
        if not args.skip_index:
            n = _update_scene_index_public(conn, video_flags=video_flags, scene_media=scene_media)
            updated += 1
            print(f"OK: scene_index_public upserted rows={n} videos_discovered={len(video_flags)} media_rows={len(scene_media)}")

        if updated == 0:
            print("OK: nothing to do (both updates skipped)")
        return 0
    except Exception as exc:
        print(f"FAIL: ui conduits rollup failed: {exc}")
        return 2
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
