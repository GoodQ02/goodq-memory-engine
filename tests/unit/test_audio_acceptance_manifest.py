import hashlib
import json
import struct

from scripts.audio.run_acceptance import main, verify_manifest


def setup_manifest(tmp_path):
    data = struct.pack("<4f", 0.0, 0.25, -0.25, 0.0)
    fmt = struct.pack("<HHIIHH", 3, 1, 16000, 64000, 4, 32)
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(data)) + data
    audio = tmp_path / "control.wav"
    audio.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)
    manifest = tmp_path / "manifest.json"
    payload = {"schema_version": 1, "fixtures": [{"id": "float-wave", "path": "control.wav",
        "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(), "samples": 4,
        "sample_rate": 16000, "channels": 1}], "reference_receipts": [], "human_references": [],
        "pending_fixture_sets": ["independent_human_labels"]}
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest, payload


def test_float_wave_inventory_does_not_claim_inference_acceptance(tmp_path):
    manifest, _ = setup_manifest(tmp_path)
    report = verify_manifest(manifest, tmp_path)
    assert report["status"] == "verified"
    assert report["audio_files_verified"] == 1
    assert report["runtime_inference"] == "not_run"
    assert set(report["acceptance"].values()) == {"pending"}
    assert len(report["acceptance"]) == 25
    assert report["pending_fixture_sets"] == ["independent_human_labels"]


def test_changed_bytes_or_wrong_sample_metadata_fail(tmp_path):
    manifest, payload = setup_manifest(tmp_path)
    payload["fixtures"][0]["samples"] = 5
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    assert verify_manifest(manifest, tmp_path)["status"] == "failed"
    payload["fixtures"][0]["samples"] = 4
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with (tmp_path / "control.wav").open("ab") as stream:
        stream.write(b"changed")
    assert verify_manifest(manifest, tmp_path)["status"] == "failed"


def test_path_escape_and_missing_file_fail(tmp_path):
    manifest, payload = setup_manifest(tmp_path)
    for bad_path in ("../control.wav", "missing.wav"):
        payload["fixtures"][0]["path"] = bad_path
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        assert verify_manifest(manifest, tmp_path)["status"] == "failed"


def test_bad_reference_interval_cannot_be_called_verified(tmp_path):
    manifest, payload = setup_manifest(tmp_path)
    payload["human_references"] = [{"id": "ref1", "source_fixture": "float-wave",
        "source_sample_interval": [0, 5], "receipts": []}]
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    assert verify_manifest(manifest, tmp_path)["status"] == "failed"


def test_actual_cli_exit_and_json_expose_readiness_only(tmp_path, capsys):
    manifest, _ = setup_manifest(tmp_path)
    assert main(["verify-fixtures", "--manifest", str(manifest), "--fixture-root", str(tmp_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["runtime_inference"] == "not_run"
    (tmp_path / "control.wav").unlink()
    assert main(["verify-fixtures", "--manifest", str(manifest), "--fixture-root", str(tmp_path)]) == 1


def test_declared_encoding_must_match_the_actual_wave_header(tmp_path):
    manifest, payload = setup_manifest(tmp_path)
    payload["fixtures"][0].update(wav_format_tag=1, bits_per_sample=8)
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    assert verify_manifest(manifest, tmp_path)["status"] == "failed"
    payload["fixtures"][0].update(wav_format_tag=3, bits_per_sample=32)
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    assert verify_manifest(manifest, tmp_path)["status"] == "verified"
