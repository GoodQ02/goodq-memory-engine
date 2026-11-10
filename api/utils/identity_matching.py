"""Passive projection of ingestion's frozen identity comparison receipts."""
from pathlib import Path
import re

from lib.identity_matching import SCHEMA, digest, file_digest, read_json, report_root, reviewed_source_roots


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
    return {k: report[k] for k in ("id", "epoch_id", "video_id", "video_name", "run_id", "status",
                                 "applied", "summary", "references_sha256", "content_sha256")}


def list_reports(cfg):
    directory = report_root(cfg) / "reports"
    return {"reports": [_summary(read_report(cfg, path.stem)) for path in sorted(directory.glob("*.json"))]}


def public_report(cfg, report_id):
    report = read_report(cfg, report_id)
    result = {**_summary(report), "people": report["people"], "policy": report["policy"],
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
