"""Verify and seal one pinned Hugging Face model snapshot into the personal vault.

The command never selects a revision itself.  It accepts an immutable revision,
compares the local cache with the upstream file list, optionally hydrates only
missing files for that same revision, and seals the verified result through the
personal-asset-vault contract.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Iterable

from huggingface_hub import HfApi, hf_hub_download, snapshot_download

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.assets.personal_asset_vault import VaultError, seal_snapshot
from steps.common.model_provisioner import resolve_hf_token


def cache_key(source: str) -> str:
    """Return Hugging Face's deterministic cache directory name for a repo."""

    parts = source.split("/")
    if len(parts) not in {1, 2} or any(not part for part in parts):
        raise VaultError(f"invalid Hugging Face source: {source!r}")
    return "models--" + source.replace("/", "--")


def find_snapshot(models_root: Path, source: str, revision: str) -> Path | None:
    """Locate the most complete exact snapshot in either GoodQ cache layout."""

    candidates: list[Path] = []
    for root in (models_root, models_root / "hub"):
        candidate = root / cache_key(source) / "snapshots" / revision
        if candidate.is_dir():
            candidates.append(candidate)
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: sum(1 for item in candidate.rglob("*") if item.is_file()))


def snapshot_members(snapshot: Path) -> set[str]:
    """List cache files relative to a snapshot, rejecting non-file entries."""

    members: set[str] = set()
    for candidate in snapshot.rglob("*"):
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise VaultError(f"snapshot contains a non-file member: {candidate}")
        members.add(candidate.relative_to(snapshot).as_posix())
    return members


def compare_members(expected: Iterable[str], observed: Iterable[str]) -> tuple[list[str], list[str]]:
    """Return deterministic missing and unexpected member lists."""

    expected_set = set(expected)
    observed_set = set(observed)
    return sorted(expected_set - observed_set), sorted(observed_set - expected_set)


def verify_or_hydrate_snapshot(
    *, source: str, revision: str, models_root: Path, fetch_missing: bool
) -> tuple[Path, list[str], list[str]]:
    """Verify one snapshot against upstream, hydrating its exact revision only if allowed."""

    token = resolve_hf_token(source)
    api = HfApi(token=token)
    expected = api.list_repo_files(source, revision=revision)
    snapshot = find_snapshot(models_root, source, revision)
    observed = snapshot_members(snapshot) if snapshot else []
    missing, unexpected = compare_members(expected, observed)
    if missing and fetch_missing:
        snapshot_download(
            repo_id=source,
            revision=revision,
            cache_dir=models_root,
            local_files_only=False,
            token=token,
        )
        snapshot = find_snapshot(models_root, source, revision)
        observed = snapshot_members(snapshot) if snapshot else []
        missing, unexpected = compare_members(expected, observed)
    if snapshot is None:
        raise VaultError(f"snapshot was not found after verification: {source}@{revision}")
    if missing or unexpected:
        raise VaultError(
            f"snapshot membership mismatch for {source}@{revision}: "
            f"missing={missing}; unexpected={unexpected}"
        )
    return snapshot, missing, unexpected


def seal_hf_snapshot(
    *,
    asset_id: str,
    source: str,
    revision: str,
    models_root: Path,
    vault_root: Path,
    fetch_missing: bool,
    disposition: str,
) -> dict[str, str]:
    """Hydrate the pinned model-card evidence, verify all files, then immutably seal."""

    snapshot = find_snapshot(models_root, source, revision)
    token = resolve_hf_token(source)
    if fetch_missing or snapshot is None or not (snapshot / "README.md").is_file():
        hf_hub_download(
            repo_id=source,
            filename="README.md",
            revision=revision,
            cache_dir=models_root,
            token=token,
        )
    snapshot, _, _ = verify_or_hydrate_snapshot(
        source=source,
        revision=revision,
        models_root=models_root,
        fetch_missing=fetch_missing,
    )
    with tempfile.TemporaryDirectory(prefix=f"goodq-{asset_id}-") as raw_staging:
        staging = Path(raw_staging)
        source_dir = staging / "source"
        shutil.copytree(snapshot, source_dir)
        terms = source_dir / "README.md"
        if not terms.is_file():
            raise VaultError(f"pinned model card is missing: {source}@{revision}")
        result = seal_snapshot(
            source_dir,
            vault_root,
            asset_id,
            revision,
            [terms],
            source_url=f"https://huggingface.co/{source}/tree/{revision}",
            disposition=disposition,
        )
    return {
        "asset_id": result.asset_id,
        "manifest_sha256": result.manifest_sha256,
        "seal_path": str(result.path),
        "source": source,
        "revision": revision,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify and seal one pinned Hugging Face snapshot")
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--models-root", type=Path, required=True)
    parser.add_argument("--vault-root", type=Path, required=True)
    parser.add_argument("--disposition", required=True)
    parser.add_argument("--fetch-missing", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        receipt = seal_hf_snapshot(
            asset_id=args.asset_id,
            source=args.source,
            revision=args.revision,
            models_root=args.models_root,
            vault_root=args.vault_root,
            fetch_missing=args.fetch_missing,
            disposition=args.disposition,
        )
    except VaultError as exc:
        print(f"asset intake error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
