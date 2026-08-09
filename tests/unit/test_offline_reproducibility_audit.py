from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.assets.offline_reproducibility_audit import build_report
from scripts.assets.personal_asset_vault import seal_snapshot


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_audit_distinguishes_sealed_models_from_staged_installer_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("terms", encoding="utf-8")
    (source / "weights.bin").write_bytes(b"weights")
    vault = tmp_path / "vault"
    sealed = seal_snapshot(source, vault, "example_model", "a" * 40, [source / "README.md"])
    personal_sealed = seal_snapshot(source, vault, "personal_model", "a" * 40, [source / "README.md"])
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        yaml.safe_dump(
            {
                "assets": {
                    "example_model": {
                        "kind": "model",
                        "source": "owner/model",
                        "revision": "a" * 40,
                        "status": "eligible",
                        "vault_scope": "personal_and_distributable",
                        "pack_scope": "core_cpu",
                        "expected_terms": "https://example.invalid/terms",
                        "sealed_manifest_sha256": sealed.manifest_sha256,
                    },
                    "held_model": {
                        "kind": "model",
                        "source": "owner/held",
                        "revision": "b" * 40,
                        "status": "agreement_gated",
                        "vault_scope": "personal",
                        "pack_scope": "optional",
                    },
                    "personal_model": {
                        "kind": "model",
                        "source": "owner/personal",
                        "revision": "a" * 40,
                        "status": "personal_only",
                        "vault_scope": "personal",
                        "pack_scope": "optional",
                        "expected_terms": "https://example.invalid/personal-terms",
                        "sealed_manifest_sha256": personal_sealed.manifest_sha256,
                    },
                    "personal_alias": {
                        "kind": "lexicon",
                        "source": "owner/personal-subset",
                        "revision": "subset-v1",
                        "status": "personal_only",
                        "vault_scope": "personal",
                        "pack_scope": "optional",
                        "source_snapshot_parent": "personal_model",
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {
            "toolchains": {},
            "dependencies": {"runtime": {"required": True, "target_path": "payload.bin"}},
            "wheels": {"wheelhouse": []},
        },
    )
    (tmp_path / "payload.bin").write_bytes(b"payload")

    report = build_report(catalog_path=catalog, manifest_path=manifest, vault_root=vault, repo_root=tmp_path)

    assert report["summary"]["models_and_data"] == {
        "held_by_acceptance": 1,
        "personal_snapshot_via_parent": 1,
        "personal_snapshot_confirmed": 1,
        "sealed_manifest_confirmed": 1,
    }
    assert report["summary"]["installer_artifacts"] == {"staged_target_present": 1}
    assert report["wheelhouse_closure"]["state"] == "missing_sbom"
