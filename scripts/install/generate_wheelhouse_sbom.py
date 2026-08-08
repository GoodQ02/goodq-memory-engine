#!/usr/bin/env python3
"""Create a strict, reproducible inventory for an offline wheelhouse.

The release builder runs this before NSIS compilation.  A wheelhouse is valid
only when every wheel has unambiguous package identity and license evidence,
and when it contains one version of each distribution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from zipfile import BadZipFile, ZipFile


def _normalise_name(value: str) -> str:
    return "-".join(value.lower().replace("_", "-").replace(".", "-").split("-"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _wheel_record(path: Path) -> dict[str, object]:
    try:
        with ZipFile(path) as archive:
            metadata_names = sorted(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
            if len(metadata_names) != 1:
                raise ValueError("expected exactly one .dist-info/METADATA file")
            metadata = BytesParser(policy=default).parsebytes(archive.read(metadata_names[0]))
            name = metadata.get("Name")
            version = metadata.get("Version")
            if not name or not version:
                raise ValueError("METADATA is missing Name or Version")
            license_expression = metadata.get("License-Expression")
            license_value = metadata.get("License")
            classifiers = metadata.get_all("Classifier", [])
            license_classifier = next((item for item in classifiers if item.startswith("License ::")), None)
            license_files = sorted(
                name for name in archive.namelist()
                if ".dist-info/licenses/" in name.lower() or name.lower().endswith(".dist-info/license")
            )
    except (BadZipFile, OSError, ValueError) as exc:
        raise ValueError(f"{path.name}: {exc}") from exc

    if license_expression:
        license_text, evidence = license_expression, "License-Expression"
    elif license_value and license_value.strip() and license_value.strip().upper() != "UNKNOWN":
        license_text, evidence = license_value.strip(), "License"
    elif license_classifier:
        license_text, evidence = license_classifier, "Classifier"
    elif license_files:
        license_text, evidence = "SEE LICENSE FILE", "Bundled license file"
    else:
        raise ValueError(f"{path.name}: missing license evidence in wheel metadata")

    return {
        "name": _normalise_name(name),
        "version": version,
        "filename": path.name,
        "sha256": _sha256(path),
        "license": license_text,
        "license_evidence": evidence,
        "license_files": license_files,
    }


def _locked_requirements(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        result[_normalise_name(name.strip())] = version.strip()
    return result


def _build_sbom(wheelhouse: Path, requirements: Path | None) -> dict[str, object]:
    wheels = sorted(wheelhouse.rglob("*.whl"))
    if not wheels:
        raise ValueError("wheelhouse contains no wheels")
    records = [_wheel_record(path) for path in wheels]
    by_name: dict[str, list[dict[str, object]]] = {}
    for record in records:
        by_name.setdefault(str(record["name"]), []).append(record)
    duplicates = sorted(name for name, entries in by_name.items() if len(entries) > 1)
    if duplicates:
        raise ValueError(f"duplicate distribution entries: {', '.join(duplicates)}")
    if requirements:
        required = _locked_requirements(requirements)
        actual = {str(record["name"]): str(record["version"]) for record in records}
        missing = sorted(name for name, version in required.items() if actual.get(name) != version)
        if missing:
            raise ValueError(f"locked requirements missing or version-mismatched: {', '.join(missing)}")
    records.sort(key=lambda item: (str(item["name"]), str(item["version"]), str(item["filename"])))
    closure_digest = hashlib.sha256("\n".join(f"{entry['filename']}:{entry['sha256']}" for entry in records).encode()).hexdigest()
    return {"schema_version": "1.0", "wheelhouse_sha256": closure_digest, "package_count": len(records), "packages": records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requirements", type=Path)
    args = parser.parse_args()
    try:
        sbom = _build_sbom(args.wheelhouse, args.requirements)
    except ValueError as exc:
        print(f"[ERROR] wheelhouse SBOM rejected: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output.parent, delete=False) as handle:
        json.dump(sbom, handle, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(args.output)
    print(f"[OK] wheelhouse SBOM: {args.output} ({sbom['package_count']} packages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
