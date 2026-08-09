"""Unit tests for offline packaging payload integrity."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement

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


def test_audio_pack_verify_honors_explicit_requested_pack(tmp_path: Path):
    """Audio readiness checks must not silently verify core instead."""
    script = ROOT / "scripts" / "install" / "sandbox_env_setup.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--packs",
            "audio_standard",
            "--verify-only",
            "--data-dir",
            str(tmp_path / "data"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 6
    assert "not published in this baseline" in result.stderr


def test_installer_model_pack_setup_installs_only_packaged_sealed_assets() -> None:
    installer = ROOT / "scripts" / "install" / "goodq4all_installer.nsi"
    content = installer.read_text(encoding="utf-8")

    assert "Sealed NanoDet baseline payload" in content
    assert "sandbox_env_setup.py\" --packs core_memory --local-only" not in content


def test_local_only_model_pack_setup_refuses_remote_download(tmp_path: Path):
    script = ROOT / "scripts" / "install" / "sandbox_env_setup.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--packs",
            "core_memory",
            "--local-only",
            "--data-dir",
            str(tmp_path / "data"),
            "--cache-dir",
            str(tmp_path / "empty-cache"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 6
    assert "not published in this baseline" in result.stderr


def test_cpu_baseline_stager_uses_cpu_pytorch_index() -> None:
    stager = ROOT / "scripts" / "install" / "stage_dependencies.ps1"
    content = stager.read_text(encoding="utf-8")

    assert "https://download.pytorch.org/whl/cpu" in content
    assert "https://download.pytorch.org/whl/cu121" not in content


def test_stager_resolves_the_baseline_lock_from_its_own_directory() -> None:
    stager = (ROOT / "scripts" / "install" / "stage_dependencies.ps1").read_text(encoding="utf-8")

    assert 'Join-Path $ScriptDir "..\\..\\requirements-baseline-lock.txt"' in stager


def test_wheel_staging_replaces_stale_cache_and_payload_before_download() -> None:
    """A release build may not inherit arbitrary wheels from a prior staging run."""
    stager = (ROOT / "scripts" / "install" / "stage_dependencies.ps1").read_text(encoding="utf-8")
    builder = (ROOT / "scripts" / "install" / "build_installer.bat").read_text(encoding="utf-8")

    assert 'Remove-Item -LiteralPath $wheelsDir -Recurse -Force' in stager
    assert 'rmdir /s /q "staged\\wheels"' in builder


def test_wheel_acquisition_never_leaves_a_partial_file_at_the_final_name() -> None:
    """An interrupted download must not masquerade as a valid staged wheel."""
    stager = (ROOT / "scripts" / "install" / "stage_dependencies.ps1").read_text(encoding="utf-8")

    assert "DestinationPath.partial" in stager
    assert "Move-Item -LiteralPath $temporaryPath -Destination $DestinationPath -Force" in stager
    assert "Downloaded artifact is empty" in stager
    assert "curl.exe" in stager
    assert "--continue-at" in stager
    assert "--retry-all-errors" in stager
    assert "--retry-max-time" in stager
    assert "Preserving resumable partial" in stager
    assert "$LASTEXITCODE:" not in stager


def test_installer_generates_and_ships_a_strict_wheelhouse_sbom() -> None:
    """The compiled installer must carry the verified wheel closure it installs."""
    builder = (ROOT / "scripts" / "install" / "build_installer.bat").read_text(encoding="utf-8")
    installer = (ROOT / "scripts" / "install" / "goodq4all_installer.nsi").read_text(encoding="utf-8")

    assert "generate_wheelhouse_sbom.py" in builder
    assert "--requirements ..\\..\\requirements-baseline-lock.txt" in builder
    assert 'File "staged\\wheelhouse-sbom.json"' in installer


def test_cpu_torch_wheels_are_hash_pinned() -> None:
    manifest_path = ROOT / "configs" / "offline_dependencies_manifest.json"
    wheels = json.loads(manifest_path.read_text(encoding="utf-8"))["wheels"]["wheelhouse"]
    torch_wheels = [wheel for wheel in wheels if wheel["name"] in {"torch", "torchvision", "torchaudio"}]

    assert len(torch_wheels) == 3
    assert all(wheel["gpu_lane"] == "cpu" for wheel in torch_wheels)
    assert all(wheel.get("source_url") and wheel.get("sha256") for wheel in torch_wheels)


def test_installer_ships_explicit_audio_standard_launcher() -> None:
    launcher = ROOT / "scripts" / "install" / "INSTALL_AUDIO_STANDARD.bat"
    installer = ROOT / "scripts" / "install" / "goodq4all_installer.nsi"

    assert "--profile audio_standard" in launcher.read_text(encoding="utf-8")
    assert "audio_standard_report.json" in launcher.read_text(encoding="utf-8")
    assert 'Install Audio Standard.lnk' in installer.read_text(encoding="utf-8")


def test_baseline_lock_covers_the_clap_runtime_imports() -> None:
    """A baseline witness must not reach CLAP and then discover librosa is absent."""
    lockfile = (ROOT / "requirements-baseline-lock.txt").read_text(encoding="utf-8")

    assert "librosa==0.10.2.post1" in lockfile
    assert "soundfile==0.12.1" in lockfile


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
            packages.append(Requirement(line).name.lower())
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
        clean_canonical = canonical.lstrip('v')
        parts = clean_canonical.split(".")
        major, minor = int(parts[0]), int(parts[1])
        import re
        patch_part = parts[2] if len(parts) > 2 else "0"
        patch_match = re.match(r'^(\d+)', patch_part)
        patch = int(patch_match.group(1)) if patch_match else 0

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
