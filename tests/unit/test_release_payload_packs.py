import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Callable

import pytest

import scripts.install.release_payload_packs as payload_packs
from scripts.install.release_payload_packs import (
    DEFAULT_MAX_PACK_BYTES,
    PayloadPackError,
    apply,
    build,
)


PROFILE = "PUBLIC_GPU_ENHANCED"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_inventory_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_staging_fixture(
    root: Path,
    *,
    payload_size: int = 5,
    add_orphan_model: bool = False,
) -> Path:
    staging = root / "staged"
    (staging / "vendor").mkdir(parents=True)
    (staging / "wheels").mkdir()
    (staging / "models" / "hub").mkdir(parents=True)
    (staging / "configs").mkdir()
    (staging / "vendor" / "dependency.bin").write_bytes(b"v" * payload_size)
    (staging / "wheels" / "dependency.whl").write_bytes(b"w" * payload_size)
    model_path = staging / "models" / "hub" / "model.safetensors"
    model_path.write_bytes(b"m" * payload_size)
    (staging / "wheelhouse-sbom.json").write_text("s" * payload_size, encoding="utf-8")
    if add_orphan_model:
        (staging / "models" / "hub" / "orphan.bin").write_bytes(b"orphan")

    model_members = [
        {
            "path": "hub/model.safetensors",
            "size_bytes": model_path.stat().st_size,
            "sha256": _sha256_bytes(model_path.read_bytes()),
            "asset_id": "fixture_model",
            "source_manifest_sha256": "3" * 64,
            "provenance": {
                "type": "sealed_source_copy",
                "source_path": "model.safetensors",
                "source_sha256": _sha256_bytes(model_path.read_bytes()),
            },
        }
    ]
    model_manifest = {
        "schema_version": 2,
        "profile": PROFILE,
        "member_count": len(model_members),
        "inventory_sha256": _json_inventory_sha256(model_members),
        "members": model_members,
    }
    model_manifest_path = staging / "configs" / "model_member_manifest.json"
    model_manifest_path.write_text(
        json.dumps(model_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    selected = {
        "schema_version": 2,
        "profile": PROFILE,
        "distribution": "public",
        "selected_asset_ids": ["fixture_model"],
        "selector_sha256": "1" * 64,
        "asset_inventory_sha256": "2" * 64,
        "asset_closure": {},
        "payload_asset_ids": ["fixture_model"],
        "payloads": [],
        "model_member_manifest": {
            "path": "model_member_manifest.json",
            "sha256": _sha256_bytes(model_manifest_path.read_bytes()),
            "inventory_sha256": model_manifest["inventory_sha256"],
            "member_count": model_manifest["member_count"],
        },
    }
    (staging / "configs" / "selected_capabilities.json").write_text(
        json.dumps(selected, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return staging


def _build_fixture(root: Path, *, payload_size: int = 5, max_pack_bytes: int = 4096) -> tuple[Path, Path]:
    staging = _write_staging_fixture(root, payload_size=payload_size)
    output = root / "output"
    manifest_path = build(
        staging_root=staging,
        output_root=output,
        version="3.0.1",
        profile=PROFILE,
        max_pack_bytes=max_pack_bytes,
    )
    return output, manifest_path


def _rewrite_pack(
    pack_path: Path,
    transform: Callable[
        [list[tuple[str, bytes]]],
        list[tuple[str, bytes]],
    ],
) -> None:
    with zipfile.ZipFile(pack_path) as archive:
        members = [
            (item.filename, archive.read(item))
            for item in archive.infolist()
            if not item.is_dir()
        ]
    rewritten = transform(members)
    with zipfile.ZipFile(pack_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for name, content in rewritten:
            archive.writestr(name, content, compress_type=zipfile.ZIP_STORED)


def _refresh_pack_record(manifest_path: Path, pack_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = next(
        item for item in manifest["packs"] if Path(item["path"]).name == pack_path.name
    )
    record["size_bytes"] = pack_path.stat().st_size
    record["sha256"] = _sha256_bytes(pack_path.read_bytes())
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _apply_fixture(root: Path, output: Path, manifest_path: Path) -> Path:
    return apply(
        bundle_root=output,
        install_dir=root / "install",
        data_dir=root / "data",
        manifest_bytes=manifest_path.read_bytes(),
    )


def test_default_pack_boundary_accepts_largest_sealed_gpu_model_member() -> None:
    """Public GPU packages must accommodate every pinned monolithic model member."""
    deepseek_14b_shard_bytes = 8_714_116_464
    gemma_4_12b_model_bytes = 23_919_549_408

    assert DEFAULT_MAX_PACK_BYTES >= deepseek_14b_shard_bytes
    assert DEFAULT_MAX_PACK_BYTES >= gemma_4_12b_model_bytes


def test_build_emits_per_pack_copy_and_hash_heartbeats(tmp_path: Path) -> None:
    staging = _write_staging_fixture(tmp_path)
    events: list[str] = []

    build(
        staging_root=staging,
        output_root=tmp_path / "output",
        version="3.0.1",
        profile=PROFILE,
        max_pack_bytes=1024 * 1024,
        progress=events.append,
        heartbeat_seconds=0,
    )

    assert any("plan:" in event for event in events)
    assert any("writing pack" in event for event in events)
    assert any("copy heartbeat" in event for event in events)
    assert any("hash heartbeat" in event for event in events)
    assert any("completed pack" in event for event in events)


def test_schema_v2_multi_pack_round_trip_verifies_every_installed_member(tmp_path: Path) -> None:
    output, manifest_path = _build_fixture(tmp_path, payload_size=400, max_pack_bytes=650)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 2
    assert len(manifest["packs"]) >= 2
    assert manifest["members"] == sorted(manifest["members"], key=lambda item: item["path"])
    assert manifest["member_inventory_sha256"] == _json_inventory_sha256(manifest["members"])
    assert manifest["selected_asset_selector_sha256"] == "1" * 64
    assert manifest["model_member_inventory_sha256"]

    receipt_path = _apply_fixture(tmp_path, output, manifest_path)

    assert (tmp_path / "install" / "vendor" / "dependency.bin").read_bytes() == b"v" * 400
    assert (tmp_path / "data" / "models" / "hub" / "model.safetensors").read_bytes() == b"m" * 400
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["schema_version"] == 2
    assert receipt["status"] == "applied_and_verified"
    assert receipt["member_inventory_sha256"] == manifest["member_inventory_sha256"]
    assert len(receipt["installed_members"]) == len(manifest["members"])
    assert all(item["status"] == "verified" for item in receipt["installed_members"])


def test_apply_rejects_changed_member_even_when_pack_hash_is_refreshed(tmp_path: Path) -> None:
    output, manifest_path = _build_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    victim = manifest["members"][0]
    pack_path = output / victim["pack_path"]

    def change(members: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
        return [(name, b"x" * len(content) if name == victim["path"] else content) for name, content in members]

    _rewrite_pack(pack_path, change)
    _refresh_pack_record(manifest_path, pack_path)

    with pytest.raises(PayloadPackError, match="member SHA256 mismatch"):
        _apply_fixture(tmp_path, output, manifest_path)


def test_apply_rejects_missing_member(tmp_path: Path) -> None:
    output, manifest_path = _build_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    victim = manifest["members"][0]
    pack_path = output / victim["pack_path"]
    _rewrite_pack(pack_path, lambda members: [(name, content) for name, content in members if name != victim["path"]])
    _refresh_pack_record(manifest_path, pack_path)

    with pytest.raises(PayloadPackError, match="membership mismatch"):
        _apply_fixture(tmp_path, output, manifest_path)


def test_apply_rejects_extra_member(tmp_path: Path) -> None:
    output, manifest_path = _build_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pack_path = output / manifest["packs"][0]["path"]
    _rewrite_pack(pack_path, lambda members: [*members, ("program_files/extra.bin", b"extra")])
    _refresh_pack_record(manifest_path, pack_path)

    with pytest.raises(PayloadPackError, match="membership mismatch"):
        _apply_fixture(tmp_path, output, manifest_path)


def test_apply_rejects_duplicate_declared_member(tmp_path: Path) -> None:
    output, manifest_path = _build_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["members"].append(dict(manifest["members"][0]))
    manifest["member_count"] = len(manifest["members"])
    manifest["member_inventory_sha256"] = _json_inventory_sha256(manifest["members"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(PayloadPackError, match="unique and sorted"):
        _apply_fixture(tmp_path, output, manifest_path)


@pytest.mark.parametrize(
    ("member_name", "message"),
    [
        ("../outside.bin", "unsafe payload path"),
        ("windows/system32/evil.bin", "unsupported target"),
    ],
)
def test_apply_rejects_unsafe_or_misplaced_archive_member(
    tmp_path: Path, member_name: str, message: str
) -> None:
    output, manifest_path = _build_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pack_path = output / manifest["packs"][0]["path"]
    _rewrite_pack(pack_path, lambda members: [*members, (member_name, b"bad")])
    _refresh_pack_record(manifest_path, pack_path)

    with pytest.raises(PayloadPackError, match=message):
        _apply_fixture(tmp_path, output, manifest_path)


def test_apply_does_not_reinterpret_historical_v1_as_v2_evidence(tmp_path: Path) -> None:
    output, manifest_path = _build_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 1
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(PayloadPackError, match="historical schema v1"):
        _apply_fixture(tmp_path, output, manifest_path)


def test_build_rejects_model_member_not_declared_by_signed_model_inventory(tmp_path: Path) -> None:
    staging = _write_staging_fixture(tmp_path, add_orphan_model=True)

    with pytest.raises(PayloadPackError, match="model membership mismatch"):
        build(
            staging_root=staging,
            output_root=tmp_path / "output",
            version="3.0.1",
            profile=PROFILE,
            max_pack_bytes=4096,
        )


def test_apply_consumes_authenticated_manifest_bytes_without_reopening_path(tmp_path: Path) -> None:
    """Replacing the external manifest after authentication must not alter apply."""

    output, manifest_path = _build_fixture(tmp_path)
    manifest_bytes = manifest_path.read_bytes()
    manifest_path.unlink()

    receipt_path = apply(
        bundle_root=output,
        install_dir=tmp_path / "install",
        data_dir=tmp_path / "data",
        manifest_bytes=manifest_bytes,
    )

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["payload_manifest"] == "GoodQ4All_Setup_3.0.1.payload_manifest.json"
    assert receipt["payload_manifest_sha256"] == _sha256_bytes(manifest_bytes)


def test_apply_holds_one_pack_handle_from_hash_through_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path replacement after hashing must not become the extracted archive."""

    output, manifest_path = _build_fixture(tmp_path)
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    pack_path = output / manifest["packs"][0]["path"]
    replacement = tmp_path / "replacement.zip"
    replacement.write_bytes(pack_path.read_bytes())

    with zipfile.ZipFile(replacement) as archive:
        replacement_members = [
            (item.filename, archive.read(item))
            for item in archive.infolist()
            if not item.is_dir()
        ]
    with zipfile.ZipFile(
        replacement,
        "w",
        compression=zipfile.ZIP_STORED,
        allowZip64=True,
    ) as archive:
        for index, (name, content) in enumerate(replacement_members):
            changed = (b"x" * len(content)) if index == 0 else content
            archive.writestr(name, changed, compress_type=zipfile.ZIP_STORED)

    real_zip_file = zipfile.ZipFile
    pack_open_count = 0

    def replace_path_when_archive_opens(source: object, *args: object, **kwargs: object) -> zipfile.ZipFile:
        nonlocal pack_open_count
        pack_open_count += 1
        if replacement.exists():
            try:
                os.replace(replacement, pack_path)
            except PermissionError:
                pass
        return real_zip_file(source, *args, **kwargs)

    monkeypatch.setattr(payload_packs.zipfile, "ZipFile", replace_path_when_archive_opens)

    receipt_path = apply(
        bundle_root=output,
        install_dir=tmp_path / "install",
        data_dir=tmp_path / "data",
        manifest_bytes=manifest_bytes,
    )

    assert receipt_path.is_file()
    assert pack_open_count == len(manifest["packs"])
    assert all(
        item["status"] == "verified"
        for item in json.loads(receipt_path.read_text(encoding="utf-8"))["installed_members"]
    )


def test_apply_cli_requires_manifest_on_stdin(tmp_path: Path) -> None:
    """The elevated installer apply path must not accept an external manifest path."""

    output, manifest_path = _build_fixture(tmp_path)
    script = Path(payload_packs.__file__).resolve()
    command = [
        sys.executable,
        str(script),
        "apply",
        "--bundle-root",
        str(output),
        "--install-dir",
        str(tmp_path / "install"),
        "--data-dir",
        str(tmp_path / "data"),
        "--manifest-stdin",
    ]

    applied = subprocess.run(
        command,
        input=manifest_path.read_bytes(),
        capture_output=True,
        check=False,
    )
    path_reopen = subprocess.run(
        [*command, "--manifest-path", str(manifest_path)],
        input=manifest_path.read_bytes(),
        capture_output=True,
        check=False,
    )

    assert applied.returncode == 0, applied.stderr.decode(errors="replace")
    assert path_reopen.returncode != 0
    assert b"unrecognized arguments: --manifest-path" in path_reopen.stderr
