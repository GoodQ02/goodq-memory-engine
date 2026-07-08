"""
GoodQ4All — Phase 3: Name Mention Extractor
============================================
Mines transcript segments for name and family-role signals.

NO NAMES ARE HARDCODED in this script. All known names come from
the private user-curated family_terms.yaml. If that file is absent,
the script runs a frequency-only pass and surfaces the top 50
capitalized word candidates — it does not assert any of them are names.

The family_roster.yaml is the ONLY authority on identity.
This script produces evidence for the roster; it does not create identities.

Usage:
    conda run -n goodq_core python scripts/identity/extract_name_mentions.py \\
        --epoch-id epoch_2026_07_05_home_memory_clean_01 \\
        [--data-path L:/_DATA/GoodQ_Data/identity]

Output (all gitignored):
    name_mentions.json          — per-name, per-scene, per-video frequency table
    reports/name_mention_report.html — browsable frequency report
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DEFAULT_EPOCH_ROOT = "L:/_DATA/GoodQ_Data/epochs"
DEFAULT_DATA_PATH  = "L:/_DATA/GoodQ_Data/identity"
TERMS_FILE_NAME    = "family_terms.yaml"


def _epoch_dir(epoch_root: str, epoch_id: str) -> Path:
    p = Path(epoch_root) / epoch_id
    if not p.exists():
        raise FileNotFoundError(f"Epoch directory not found: {p}")
    return p


def load_family_terms(data_path: Path) -> dict | None:
    """
    Loads family_terms.yaml if present. Returns None if absent.
    Never falls back to hardcoded terms.
    """
    terms_path = data_path / TERMS_FILE_NAME
    if not terms_path.exists():
        log.warning(
            "family_terms.yaml not found at %s. "
            "Running frequency-only mode — no names assumed. "
            "Copy configs/identity/family_terms.template.yaml and populate it "
            "to enable targeted name extraction.",
            terms_path,
        )
        return None
    try:
        import yaml
    except ImportError:
        # Fallback: simple YAML key: [list] parser for minimal dependency
        return _parse_simple_yaml(terms_path)
    with open(terms_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _parse_simple_yaml(path: Path) -> dict:
    """Minimal YAML list parser — handles names: [...] and aliases: {...} only."""
    result = {"names": [], "aliases": {}, "roles": []}
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # Extract names list
    m = re.search(r'^names:\s*\[([^\]]*)\]', content, re.MULTILINE)
    if m:
        result["names"] = [t.strip().strip('"\'') for t in m.group(1).split(',') if t.strip()]
    # Extract roles list
    m = re.search(r'^roles:\s*\[([^\]]*)\]', content, re.MULTILINE)
    if m:
        result["roles"] = [t.strip().strip('"\'') for t in m.group(1).split(',') if t.strip()]
    return result


def load_segments(mem_db_path: Path) -> list:
    """Returns all segments with transcripts from memory.db."""
    conn = sqlite3.connect(str(mem_db_path))
    cur = conn.cursor()
    cur.execute(
        "SELECT video_hash, speaker, meta, ucf_provenance FROM segments"
    )
    rows = cur.fetchall()
    conn.close()
    segments = []
    for video_hash, speaker, meta_json, ucf_prov in rows:
        if not meta_json:
            continue
        try:
            meta = json.loads(meta_json)
        except (json.JSONDecodeError, TypeError):
            continue
        # Meta field is 'text' not 'transcript'
        transcript = (meta.get("text") or meta.get("transcript", "")).strip()
        if not transcript:
            continue
        scene_id = meta.get("scene_id", "")
        segments.append({
            "video_hash": video_hash,
            "scene_id": scene_id,
            "speaker": speaker,
            "transcript": transcript,
            "ucf_provenance": ucf_prov,
        })
    log.info("Loaded %d transcript segments from memory.db", len(segments))
    return segments


def extract_capitalized_candidates(segments: list, top_n: int = 50) -> dict:
    """
    Frequency-only pass: counts all capitalized words across transcripts.
    Returns top_n as candidates — does NOT assert any are names.
    Filters out common non-name capitalized words (sentence starters, 'I', etc.).
    """
    STOP_CAPS = {
        "I", "A", "The", "This", "That", "It", "He", "She", "We", "They",
        "You", "My", "Your", "His", "Her", "Our", "Their", "Is", "Are", "Was",
        "Were", "And", "But", "Or", "So", "To", "In", "On", "At", "Of", "For",
        "With", "Oh", "Yeah", "Okay", "OK", "No", "Yes", "Now", "Just",
    }
    freq: dict[str, int] = defaultdict(int)
    for seg in segments:
        words = re.findall(r'\b[A-Z][a-z]{2,}\b', seg["transcript"])
        for w in words:
            if w not in STOP_CAPS:
                freq[w] += 1
    top = sorted(freq.items(), key=lambda x: -x[1])[:top_n]
    return {w: {"count": c, "is_curated": False, "is_candidate": True} for w, c in top}


def extract_curated_mentions(
    segments: list,
    family_terms: dict,
) -> dict:
    """
    Extracts mentions of curated names, aliases, and role terms from transcripts.
    Returns a mention table: term -> {total_mentions, scenes, videos, sample_quotes}.
    """
    names = family_terms.get("names", []) or []
    aliases_map = family_terms.get("aliases", {}) or {}
    roles = family_terms.get("roles", []) or []

    # Build a flat list of (search_term, canonical_key) pairs
    search_pairs: list[tuple[str, str]] = []
    for name in names:
        search_pairs.append((name, name))
    for canonical, alias_list in aliases_map.items():
        for alias in (alias_list or []):
            search_pairs.append((alias, canonical))
    for role in roles:
        search_pairs.append((role, role))

    if not search_pairs:
        log.warning("family_terms.yaml loaded but contains no names, aliases, or roles.")
        return {}

    mention_table: dict[str, dict] = {}
    for canonical in set(k for _, k in search_pairs):
        mention_table[canonical] = {
            "total_mentions": 0,
            "scenes": [],
            "videos": [],
            "sample_quotes": [],
            "is_curated": True,
            "is_candidate": False,
        }

    for seg in segments:
        text = seg["transcript"]
        for search_term, canonical in search_pairs:
            pattern = re.compile(rf'\b{re.escape(search_term)}\b', re.IGNORECASE)
            matches = pattern.findall(text)
            if matches:
                entry = mention_table[canonical]
                entry["total_mentions"] += len(matches)
                if seg["scene_id"] and seg["scene_id"] not in entry["scenes"]:
                    entry["scenes"].append(seg["scene_id"])
                if seg["video_hash"] and seg["video_hash"] not in entry["videos"]:
                    entry["videos"].append(seg["video_hash"])
                if len(entry["sample_quotes"]) < 3:
                    snippet = text[:120].replace("\n", " ")
                    entry["sample_quotes"].append(f"[{seg['speaker']}] {snippet}")

    # Remove zero-mention entries
    return {k: v for k, v in mention_table.items() if v["total_mentions"] > 0}


def generate_html_report(mentions: dict, is_frequency_mode: bool, output_path: Path) -> None:
    """Generates a browsable name mention frequency report."""
    mode_label = "Frequency-Only Mode (no curated terms)" if is_frequency_mode else "Curated Terms Mode"
    rows = []
    for term, data in sorted(mentions.items(), key=lambda x: -(x[1].get("total_mentions") or x[1].get("count", 0))):
        count = data.get("total_mentions") or data.get("count", 0)
        videos = ", ".join(v[:8] for v in data.get("videos", []))
        quotes = "<br>".join(
            f'<span style="color:#888;font-size:11px">{q[:100]}</span>'
            for q in data.get("sample_quotes", [])
        )
        badge = (
            '<span style="color:#4af">curated</span>'
            if data.get("is_curated")
            else '<span style="color:#fa4">candidate</span>'
        )
        rows.append(f"""
        <tr>
          <td style="padding:8px;font-weight:bold;color:#eee">{term}</td>
          <td style="padding:8px">{badge}</td>
          <td style="padding:8px;color:#4f4">{count}</td>
          <td style="padding:8px">{len(data.get('scenes', []))}</td>
          <td style="padding:8px;font-size:11px;color:#888">{videos}</td>
          <td style="padding:8px">{quotes}</td>
        </tr>""")

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Name Mention Report — GoodQ4All</title>
<style>
  body {{ background:#1a1a1a; color:#eee; font-family:sans-serif; margin:24px; }}
  h1 {{ color:#4af; }}
  table {{ border-collapse:collapse; width:100%; }}
  th {{ background:#222; color:#aaa; text-align:left; padding:8px; }}
  tr:hover {{ background:#1e2a3a; }}
  tr {{ border-bottom:1px solid #333; }}
</style>
</head>
<body>
<h1>Name Mention Report</h1>
<p style="color:#888">Mode: <strong>{mode_label}</strong></p>
<p style="color:#888">Total terms: {len(mentions)}</p>
<p style="color:#f84;background:#2a1a00;padding:8px;border-radius:4px">
⚠ This report surfaces evidence. The family_roster.yaml is the ONLY authority on identity.
</p>
<table>
  <thead>
    <tr><th>Term</th><th>Type</th><th>Mentions</th><th>Scenes</th><th>Videos</th><th>Samples</th></tr>
  </thead>
  <tbody>
    {''.join(rows)}
  </tbody>
</table>
</body>
</html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    log.info("Name mention report written: %s", output_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GoodQ4All Phase 3: Name Mention Extractor"
    )
    parser.add_argument("--epoch-id", required=True)
    parser.add_argument("--epoch-root", default=DEFAULT_EPOCH_ROOT)
    parser.add_argument("--data-path", default=DEFAULT_DATA_PATH)
    args = parser.parse_args()

    data_path = Path(args.data_path)
    data_path.mkdir(parents=True, exist_ok=True)
    manifest_path = data_path / "name_mentions.json"
    report_path   = data_path / "reports" / "name_mention_report.html"

    log.info("=== GoodQ4All Phase 3: Name Mention Extractor ===")
    log.info("Epoch: %s", args.epoch_id)

    epoch_dir = _epoch_dir(args.epoch_root, args.epoch_id)
    mem_db = epoch_dir / "memory.db"
    if not mem_db.exists():
        log.error("memory.db not found at %s", mem_db)
        sys.exit(1)

    segments = load_segments(mem_db)
    if not segments:
        log.error("No transcript segments found in memory.db. Aborting.")
        sys.exit(1)

    family_terms = load_family_terms(data_path)
    is_frequency_mode = family_terms is None

    if is_frequency_mode:
        log.info("Running in frequency-only mode (family_terms.yaml absent)")
        mentions = extract_capitalized_candidates(segments)
    else:
        log.info(
            "Running curated extraction — names=%d, aliases=%d, roles=%d",
            len(family_terms.get("names") or []),
            len(family_terms.get("aliases") or {}),
            len(family_terms.get("roles") or []),
        )
        mentions = extract_curated_mentions(segments, family_terms)
        if not mentions:
            log.warning(
                "No curated matches found. Check that family_terms.yaml names "
                "match the actual spelling in transcripts. Consider running in "
                "frequency mode first to see what words appear."
            )

    manifest = {
        "epoch_id": args.epoch_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "frequency_only" if is_frequency_mode else "curated",
        "note": (
            "Name mentions are evidence for the family_roster.yaml, not identities. "
            "The roster is the only authority."
        ),
        "mention_count": len(mentions),
        "mentions": mentions,
    }

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("Mention manifest written: %s (%d terms)", manifest_path, len(mentions))

    generate_html_report(mentions, is_frequency_mode, report_path)

    log.info("=== Phase 3 complete ===")
    if is_frequency_mode:
        log.info(
            "Frequency mode surfaced %d candidate capitalized terms. "
            "Review the report, then populate family_terms.yaml with actual names.",
            len(mentions),
        )
    else:
        log.info(
            "Found mentions for %d curated terms. "
            "Review the report and add confirmed names to family_roster.yaml.",
            len(mentions),
        )


if __name__ == "__main__":
    main()
