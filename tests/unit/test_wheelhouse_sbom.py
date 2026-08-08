from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "install" / "generate_wheelhouse_sbom.py"


def _wheel(directory: Path, filename: str, name: str, version: str, license_expression: str = "MIT") -> None:
    with ZipFile(directory / filename, "w") as archive:
        archive.writestr(
            f"{name.replace('-', '_')}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n"
            + (f"License-Expression: {license_expression}\n" if license_expression else ""),
        )


def test_wheelhouse_sbom_records_exact_hashes_and_declared_license(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheels"
    wheelhouse.mkdir()
    _wheel(wheelhouse, "demo-1.0.0-py3-none-any.whl", "demo", "1.0.0")
    output = tmp_path / "wheelhouse-sbom.json"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--wheelhouse", str(wheelhouse), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    sbom = json.loads(output.read_text(encoding="utf-8"))
    assert sbom["package_count"] == 1
    assert sbom["packages"][0]["name"] == "demo"
    assert sbom["packages"][0]["license"] == "MIT"
    assert len(sbom["packages"][0]["sha256"]) == 64


def test_wheelhouse_sbom_rejects_duplicate_distribution_versions(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheels"
    wheelhouse.mkdir()
    _wheel(wheelhouse, "demo-1.0.0-py3-none-any.whl", "demo", "1.0.0")
    _wheel(wheelhouse, "demo-2.0.0-py3-none-any.whl", "demo", "2.0.0")
    output = tmp_path / "wheelhouse-sbom.json"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--wheelhouse", str(wheelhouse), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "duplicate distribution" in result.stderr
    assert not output.exists()
