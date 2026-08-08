"""Behavioral tests for immutable personal asset snapshots."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.assets.personal_asset_vault import (
    AdmissionResult,
    VaultError,
    build_acquisition_plan,
    cleanup_duplicates,
    evaluate_pack_admission,
    main,
    seal_snapshot,
    verify_snapshot,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _terms_file(tmp_path: Path) -> Path:
    terms = tmp_path / "terms.txt"
    terms.write_text("source terms", encoding="utf-8")
    return terms


def test_seal_copies_canonical_members_and_records_duplicate_hashes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "one.zip").write_bytes(b"same")
    (source / "two.zip").write_bytes(b"same")
    (source / "unique.zip").write_bytes(b"unique")

    result = seal_snapshot(
        source,
        tmp_path / "vault",
        "nrc_emotion",
        "0.92",
        [_terms_file(tmp_path)],
        source_url="https://example.invalid/nrc",
        disposition="personal_only",
    )

    assert (result.path / "seal.json").is_file()
    assert (result.path / "source" / "one.zip").read_bytes() == b"same"
    assert not (result.path / "source" / "two.zip").exists()
    duplicates = json.loads((result.path / "duplicates.json").read_text(encoding="utf-8"))
    assert duplicates["duplicates"] == [
        {"canonical": "one.zip", "duplicate": "two.zip"}
    ]
    assert verify_snapshot(result.path).asset_id == "nrc_emotion"


def test_seal_refuses_missing_terms_and_existing_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "asset.zip").write_bytes(b"asset")

    with pytest.raises(VaultError, match="terms"):
        seal_snapshot(source, tmp_path / "vault", "nrc_emotion", "0.92", [])

    seal_snapshot(source, tmp_path / "vault", "nrc_emotion", "0.92", [_terms_file(tmp_path)])
    with pytest.raises(VaultError, match="already exists"):
        seal_snapshot(source, tmp_path / "vault", "nrc_emotion", "0.92", [_terms_file(tmp_path)])


def test_cleanup_removes_only_sealed_duplicate_after_source_verification(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "one.zip").write_bytes(b"same")
    (source / "two.zip").write_bytes(b"same")
    result = seal_snapshot(source, tmp_path / "vault", "nrc_emotion", "0.92", [_terms_file(tmp_path)])

    removed = cleanup_duplicates(source, result.path)

    assert removed == ["two.zip"]
    assert (source / "one.zip").is_file()
    assert not (source / "two.zip").exists()


def test_cleanup_refuses_when_retained_source_drifted(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "one.zip").write_bytes(b"same")
    (source / "two.zip").write_bytes(b"same")
    result = seal_snapshot(source, tmp_path / "vault", "nrc_emotion", "0.92", [_terms_file(tmp_path)])
    (source / "one.zip").write_bytes(b"changed")

    with pytest.raises(VaultError, match="retained source verification failed"):
        cleanup_duplicates(source, result.path)


def test_inventory_cli_writes_a_machine_readable_receipt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "asset.zip").write_bytes(b"asset")

    assert main(["inventory", "--source-dir", str(source)]) == 0

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["members"][0]["path"] == "asset.zip"


def test_pack_admission_refuses_personal_only_assets_for_public_distribution() -> None:
    catalog = {
        "assets": {
            "nrc_emotion": {
                "status": "personal_only",
                "vault_scope": "personal",
            }
        }
    }

    result = evaluate_pack_admission(catalog, asset_id="nrc_emotion", distribution="public")

    assert result == AdmissionResult(False, "personal_only assets cannot enter public packs")


def test_acquisition_plan_requires_revision_and_terms_evidence() -> None:
    with pytest.raises(VaultError, match="revision"):
        build_acquisition_plan(
            {
                "asset_id": "missing-revision",
                "source": "owner/model",
                "license_class": "mit",
                "vault_scope": "personal_and_distributable",
                "hardware_profile": "cpu",
                "expected_terms": "LICENSE",
            }
        )


def test_sealed_nrc_collection_is_admissible_only_for_personal_distribution() -> None:
    catalog = yaml.safe_load(
        (REPO_ROOT / "configs" / "offline_asset_catalog.yaml").read_text(encoding="utf-8")
    )

    personal = evaluate_pack_admission(
        catalog, asset_id="nrc_lexicon_collection", distribution="personal"
    )
    public = evaluate_pack_admission(
        catalog, asset_id="nrc_lexicon_collection", distribution="public"
    )

    assert personal.allowed is True
    assert public.allowed is False
    with pytest.raises(VaultError, match="expected_terms"):
        build_acquisition_plan(
            {
                "asset_id": "missing-terms",
                "source": "owner/model",
                "revision": "a" * 40,
                "license_class": "mit",
                "vault_scope": "personal_and_distributable",
                "hardware_profile": "cpu",
            }
        )
