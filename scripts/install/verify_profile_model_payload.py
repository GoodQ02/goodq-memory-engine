"""Verify an installed selected-capability payload without downloading anything."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(*, install_dir: Path, models_root: Path) -> dict[str, Any]:
    manifest_path = install_dir / "configs" / "selected_capabilities.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = list(payload.get("payloads") or [])
    if not entries:
        raise ValueError("selected capability receipt declares no model or lexicon payloads")
    install_text = str(install_dir.resolve())
    if install_text not in sys.path:
        sys.path.insert(0, install_text)
    os.environ["GOODQ_DATA_ROOT"] = str(models_root.parent)
    os.environ["GOODQ_MODELS_DIR"] = str(models_root)
    from steps.common.model_provisioner import ensure_model_cached

    verified: list[str] = []
    for entry in entries:
        asset_id = str(entry["asset_id"])
        path = models_root / str(entry["runtime_path"])
        if not path.exists():
            raise ValueError(f"{asset_id} payload is missing: {path}")
        delivery = str(entry["delivery"])
        if delivery == "huggingface_cache":
            result = ensure_model_cached(asset_id, offline=True)
            if result.status != "cached":
                raise ValueError(f"{asset_id} does not resolve from installed cache: {result.status}")
        elif delivery == "external_model":
            expected = str(entry.get("sha256") or "")
            if not path.is_file() or _sha256(path).casefold() != expected.casefold():
                raise ValueError(f"{asset_id} external model hash mismatch")
        elif delivery != "bundled_reference_lexicon":
            raise ValueError(f"{asset_id} declares unknown delivery mode: {delivery}")
        verified.append(asset_id)
    return {"status": "ok", "profile": payload.get("profile"), "verified_asset_ids": verified}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--models-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(install_dir=args.install_dir, models_root=args.models_root), sort_keys=True))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"profile payload verification failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
