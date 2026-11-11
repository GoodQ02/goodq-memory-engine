"""Passive projection of ingestion's frozen identity comparison receipts."""
import os
from pathlib import Path
import re

import yaml

from lib.identity_matching import SCHEMA, digest, file_digest, read_json, report_root, reviewed_source_roots


def active_roster_path(cfg):
    roster_path = (cfg.get("identity_search") or {}).get("roster_path")
    if roster_path:
        return Path(str(roster_path))
    env_path = os.environ.get("GOODQ_IDENTITY_PATH")
    if env_path:
        path = Path(env_path)
        return path if path.suffix.lower() in {".yaml", ".yml"} else path / "family_roster.yaml"
    return None


def merged_report_people(cfg, report):
    """Combine frozen reference people with active-epoch roster entries (read-only)."""
    people = [dict(person) for person in report["people"]]
    by_id = {person["id"]: person["display_name"] for person in people}
    roster_path = active_roster_path(cfg)
    if not roster_path or not roster_path.is_file():
        return people
    loaded = yaml.safe_load(roster_path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("Active family roster must be a mapping")
    identities = loaded.get("identities") or []
    if not isinstance(identities, list):
        raise ValueError("Active family roster identities must be a list")
    extras = []
    seen_active = set()
    for entry in identities:
        if not isinstance(entry, dict):
            raise ValueError("Active family roster entry must be an object")
        pid = entry.get("id")
        name = entry.get("display_name")
        if not isinstance(pid, str) or not pid.strip() or not isinstance(name, str) or not name.strip():
            raise ValueError("Active family roster people need stable IDs and display names")
        if pid in seen_active:
            raise ValueError("Duplicate person ID in active family roster")
        seen_active.add(pid)
        if pid in by_id:
            if by_id[pid] != name:
                raise ValueError("Active family roster person conflicts with frozen comparison person")
            continue
        by_id[pid] = name
        extras.append({"id": pid, "display_name": name})
    extras.sort(key=lambda item: item["id"])
    return people + extras


def read_report(cfg, report_id):
    if not re.fullmatch(r"[0-9a-f]{64}", report_id):
        raise ValueError("Invalid comparison ID")
    report = read_json(report_root(cfg) / "reports" / f"{report_id}.json")
    content = {k: v for k, v in report.items() if k != "content_sha256"}
    if (report.get("schema") != SCHEMA or report.get("id") != report_id
            or report.get("epoch_id") != Path(cfg["paths"]["db_path"]).parent.name
            or report.get("applied") is not False or digest(content) != report.get("content_sha256")):
        raise ValueError("Comparison evidence does not match its saved receipt")
    return report


def _summary(report):
    base = {k: report[k] for k in ("id", "epoch_id", "video_id", "video_name", "run_id", "status",
                                   "applied", "summary", "references_sha256", "content_sha256")}
    base["people_count"] = len(report.get("people") or [])
    base["face_reference_count"] = sum(
        1 for ref in (report.get("references") or []) if (ref.get("media") or {}).get("kind") == "image"
    )
    return base


def list_reports(cfg):
    directory = report_root(cfg) / "reports"
    if not directory.is_dir():
        return {"reports": []}
    paths = sorted(directory.glob("*.json"), key=lambda path: (-path.stat().st_mtime_ns, path.stem))
    return {"reports": [_summary(read_report(cfg, path.stem)) for path in paths]}


def public_report(cfg, report_id):
    report = read_report(cfg, report_id)
    result = {**_summary(report), "people": merged_report_people(cfg, report), "policy": report["policy"],
              "errors": report["errors"], "records": [], "references": []}
    for key in ("records", "references"):
        for record in report[key]:
            public = {k: v for k, v in record.items() if k not in {"embedding", "media"}}
            public["media"] = {k: v for k, v in record["media"].items() if k not in {"path", "sha256"}}
            public["media"]["url"] = f"/api/identity/matches/{report_id}/media/{record['id']}"
            result[key].append(public)
    return result


def media_file(cfg, report_id, evidence_id):
    report = read_report(cfg, report_id)
    matches = [r for r in report["records"] + report["references"] if r["id"] == evidence_id]
    if len(matches) != 1:
        raise ValueError("Comparison evidence is missing or ambiguous")
    media = matches[0]["media"]
    path = Path(media["path"]).resolve(strict=True)
    roots = [Path(cfg["paths"]["db_path"]).resolve().parent / "processing"]
    roots += [root / "processing" for root in reviewed_source_roots(cfg.get("identity_matching") or {})]
    if not any(path.is_relative_to(root) for root in roots) or file_digest(path) != media["sha256"]:
        raise ValueError("Comparison media is outside its source or has changed")
    return path, "image/jpeg" if media["kind"] == "image" else "audio/wav"
