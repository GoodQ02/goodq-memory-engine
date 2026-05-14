from __future__ import annotations

from pathlib import Path

from scripts.validate_model_registry import main, validate_registry


VALID_REGISTRY = """
huggingface_models:
  caption:
    repo_id: example/caption-model
    revision: 0123456789abcdef0123456789abcdef01234567
    required: true
external_models:
  detector:
    source_url: https://example.invalid/model.bin
    sha256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
    local_path: detector/model.bin
    file_size_bytes: 123
    required: true
system_tools:
  ffmpeg:
    binary_path: '@config.tools.ffmpeg_exe'
    required: true
    verify_command: ffmpeg -version
""".strip()


def _write_registry(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "model_registry.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_current_model_registry_passes_static_validation():
    path = Path(__file__).resolve().parents[2] / "configs" / "model_registry.yaml"

    result = validate_registry(path)

    assert result.errors == ()


def test_placeholder_revision_fails(tmp_path: Path):
    path = _write_registry(
        tmp_path,
        VALID_REGISTRY.replace("0123456789abcdef0123456789abcdef01234567", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
    )

    result = validate_registry(path)

    assert "huggingface_models.caption.revision must be an immutable commit SHA" in result.errors


def test_mutable_revision_fails(tmp_path: Path):
    path = _write_registry(
        tmp_path,
        VALID_REGISTRY.replace("0123456789abcdef0123456789abcdef01234567", "main"),
    )

    result = validate_registry(path)

    assert "huggingface_models.caption.revision must be an immutable commit SHA" in result.errors


def test_required_external_asset_metadata_is_checked(tmp_path: Path):
    path = _write_registry(
        tmp_path,
        VALID_REGISTRY.replace(
            "sha256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "sha256: placeholder",
        ),
    )

    result = validate_registry(path)

    assert "external_models.detector.sha256 must be a 64-character SHA256" in result.errors


def test_cli_returns_nonzero_for_invalid_registry(tmp_path: Path):
    path = _write_registry(tmp_path, "huggingface_models: {}\n")

    assert main(["--registry", str(path)]) == 1


def test_cli_returns_zero_for_valid_registry(tmp_path: Path):
    path = _write_registry(tmp_path, VALID_REGISTRY)

    assert main(["--registry", str(path), "--json"]) == 0
