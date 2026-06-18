"""Unit tests for offline packaging payload integrity."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


class TestVersionReceipt:
    """Verify sandbox_env_setup.py reads version from goodq_version.py."""

    def test_version_receipt_reads_goodq_version(self):
        """sandbox_env_setup.py must not contain a hardcoded '1.0.0' version literal."""
        setup_path = ROOT / "scripts" / "install" / "sandbox_env_setup.py"
        content = setup_path.read_text(encoding="utf-8")
        # The receipt block should import/read goodq_version, not hardcode "1.0.0"
        assert '"version": "1.0.0"' not in content, (
            "sandbox_env_setup.py still contains hardcoded version '1.0.0'. "
            "It should read from goodq_version.py dynamically."
        )


class TestManifestWheelCoverage:
    """Verify offline_dependencies_manifest.json covers lockfile packages."""

    @pytest.fixture()
    def lockfile_packages(self):
        lock_path = ROOT / "requirements-baseline-lock.txt"
        packages = []
        for line in lock_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("--"):
                continue
            # Parse 'package==version' or 'package==version+cpu'
            name = re.split(r"[=<>!~]", line)[0].strip().lower()
            if name:
                packages.append(name)
        return packages

    @pytest.fixture()
    def manifest_wheel_names(self):
        manifest_path = ROOT / "configs" / "offline_dependencies_manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        wheels = data.get("wheels", {}).get("wheelhouse", [])
        return [w["name"].lower() for w in wheels]

    def test_manifest_wheel_entries_cover_lockfile(self, lockfile_packages, manifest_wheel_names):
        """Every package in requirements-baseline-lock.txt must have a manifest entry."""
        missing = [p for p in lockfile_packages if p not in manifest_wheel_names]
        assert not missing, (
            f"Lockfile packages missing from offline_dependencies_manifest.json wheels.wheelhouse: "
            f"{missing}"
        )

    def test_manifest_artifact_schema_complete(self):
        """All wheelhouse entries must have required properties."""
        manifest_path = ROOT / "configs" / "offline_dependencies_manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        wheels = data.get("wheels", {}).get("wheelhouse", [])
        required_keys = {"artifact_id", "name", "python_tag", "platform_tag", "gpu_lane", "required"}
        for w in wheels:
            missing = required_keys - set(w.keys())
            assert not missing, (
                f"Wheel entry '{w.get('name', '?')}' missing keys: {missing}"
            )


class TestVersionInfo:
    """Verify versioninfo.json aligns with goodq_version.py."""

    def test_versioninfo_matches_goodq_version(self):
        """versioninfo.json version fields should match goodq_version.py."""
        version_py = ROOT / "goodq_version.py"
        ns = {}
        exec(version_py.read_text(encoding="utf-8"), ns)
        canonical = ns["GOODQ_VERSION"]
        parts = canonical.split(".")
        major, minor = int(parts[0]), int(parts[1])
        patch = int(parts[2]) if len(parts) > 2 else 0

        vi_path = ROOT / "scripts" / "install" / "versioninfo.json"
        vi = json.loads(vi_path.read_text(encoding="utf-8"))
        fv = vi["FixedFileInfo"]["FileVersion"]
        assert fv["Major"] == major and fv["Minor"] == minor and fv["Patch"] == patch, (
            f"versioninfo.json FileVersion {fv} does not match goodq_version.py {canonical}"
        )


class TestEggInfoIgnored:
    """Verify stale egg-info is git-ignored."""

    def test_egg_info_gitignored(self):
        """'.gitignore' must contain a pattern that covers goodq4all.egg-info/."""
        gitignore_path = ROOT / ".gitignore"
        content = gitignore_path.read_text(encoding="utf-8")
        # Either exact 'goodq4all.egg-info/' or glob '*.egg-info/' covers it
        assert "egg-info" in content.lower(), (
            ".gitignore does not contain any egg-info exclusion pattern"
        )
