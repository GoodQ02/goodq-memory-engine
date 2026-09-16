"""Generate and verify the external deterministic v3.0.1 coverage fixture pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Mapping


SCHEMA = "goodq.fixture-pack.v1"
MANIFEST_NAME = "fixture-pack-manifest.json"
COPY_CHUNK_BYTES = 16 * 1024 * 1024
TRUTH_KEYS = ("speech", "music", "silence", "face", "ocr", "object")
TRUTH_VALUES = {"positive", "negative", "not_asserted", "not_applicable"}

DEFAULT_SOURCE_SPECS: dict[str, dict[str, str]] = {
    "apollo_baseline": {
        "path": "samples/onboarding_fixture.mp4",
        "sha256": "da735e12e1dba6fcfc511d5c3d8a6428ad85845a8d4cef61a03f821e00c90a62",
    },
    "demo_poster": {
        "path": "samples/assets/goodq4all-demo-poster.jpg",
        "sha256": "9ddc58f15a2104dcc2e20128f71ae7d9d616d601bab1fc8d4ec4948daf293fdc",
    },
    "installer_mockup": {
        "path": "samples/assets/one_click_installer_mockup.png",
        "sha256": "a43a6139604bf41369a03eeac3aa92e5d9e8e1f3ba72858fa180d6356f35aeb8",
    },
    "ui_walkthrough": {
        "path": "samples/assets/ui_onboarding_walkthrough.mp4",
        "sha256": "25f03bbf0850c9df63eeac6f3d9337adc25175e6a38a30c09810bbf2ae705187",
    },
}


class FixturePackError(RuntimeError):
    """Raised when deterministic fixture generation or verification fails."""


CommandRunner = Callable[[list[str], Path], subprocess.CompletedProcess[str]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(COPY_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _expect_sha256(value: object, label: str) -> str:
    digest = str(value or "").casefold()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise FixturePackError(f"{label} is not a SHA256 digest")
    return digest


def _relative_path(value: object, label: str) -> PurePosixPath:
    text = str(value or "")
    posix_path = PurePosixPath(text)
    windows_path = PureWindowsPath(text)
    if (
        not text
        or "\x00" in text
        or "\\" in text
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or posix_path.as_posix() != text
        or any(part in {"", ".", ".."} for part in posix_path.parts)
    ):
        raise FixturePackError(f"{label} is unsafe: {value}")
    return posix_path


def _default_runner(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _truth(
    *,
    speech: str,
    music: str,
    silence: str,
    face: str,
    ocr: str,
    object_: str,
) -> dict[str, str]:
    return {
        "speech": speech,
        "music": music,
        "silence": silence,
        "face": face,
        "ocr": ocr,
        "object": object_,
    }


def _video_encode_args() -> list[str]:
    return [
        "-t",
        "5.000",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-vf",
        "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1",
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-threads:v",
        "1",
        "-g",
        "60",
        "-keyint_min",
        "60",
        "-sc_threshold",
        "0",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-flags:v",
        "+bitexact",
        "-flags:a",
        "+bitexact",
        "-map_metadata",
        "-1",
        "-metadata",
        "creation_time=1970-01-01T00:00:00Z",
        "-movflags",
        "+faststart",
        "-shortest",
    ]


def _member_specs() -> list[dict[str, Any]]:
    common = ["-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-fflags", "+bitexact"]
    silence_input = [
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
    ]
    specs = [
        {
            "id": "apollo_baseline",
            "path": "members/apollo_baseline_20s.mp4",
            "media_type": "video/mp4",
            "duration_seconds": 20.0,
            "source_ids": ["apollo_baseline"],
            "operation": "sealed_copy",
            "ffmpeg_args": [],
            "expected": _truth(
                speech="positive",
                music="negative",
                silence="negative",
                face="not_asserted",
                ocr="not_asserted",
                object_="not_asserted",
            ),
        },
        {
            "id": "apollo_speech",
            "path": "members/apollo_speech_10s.wav",
            "media_type": "audio/wav",
            "duration_seconds": 10.0,
            "source_ids": ["apollo_baseline"],
            "operation": "ffmpeg",
            "ffmpeg_args": [
                *common,
                "-ss",
                "0.000",
                "-i",
                "@source/apollo_baseline",
                "-t",
                "10.000",
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                "-flags:a",
                "+bitexact",
                "-map_metadata",
                "-1",
                "@member/members/apollo_speech_10s.wav",
            ],
            "expected": _truth(
                speech="positive",
                music="negative",
                silence="negative",
                face="not_applicable",
                ocr="not_applicable",
                object_="not_applicable",
            ),
        },
        {
            "id": "empty_negative",
            "path": "members/empty_negative_5s.mp4",
            "media_type": "video/mp4",
            "duration_seconds": 5.0,
            "source_ids": [],
            "operation": "ffmpeg",
            "ffmpeg_args": [
                *common,
                "-f",
                "lavfi",
                "-i",
                "color=c=black:size=1280x720:rate=30:duration=5.000",
                *silence_input,
                *_video_encode_args(),
                "@member/members/empty_negative_5s.mp4",
            ],
            "expected": _truth(
                speech="negative",
                music="negative",
                silence="positive",
                face="negative",
                ocr="negative",
                object_="negative",
            ),
        },
        {
            "id": "installer_ocr_no_face",
            "path": "members/installer_ocr_no_face_5s.mp4",
            "media_type": "video/mp4",
            "duration_seconds": 5.0,
            "source_ids": ["installer_mockup"],
            "operation": "ffmpeg",
            "ffmpeg_args": [
                *common,
                "-loop",
                "1",
                "-framerate",
                "30",
                "-i",
                "@source/installer_mockup",
                *silence_input,
                *_video_encode_args(),
                "@member/members/installer_ocr_no_face_5s.mp4",
            ],
            "expected": _truth(
                speech="negative",
                music="negative",
                silence="positive",
                face="negative",
                ocr="positive",
                object_="not_asserted",
            ),
        },
        {
            "id": "lounge_music",
            "path": "members/lounge_music_10s.wav",
            "media_type": "audio/wav",
            "duration_seconds": 10.0,
            "source_ids": ["ui_walkthrough"],
            "operation": "ffmpeg",
            "ffmpeg_args": [
                *common,
                "-ss",
                "30.000",
                "-i",
                "@source/ui_walkthrough",
                "-t",
                "10.000",
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "2",
                "-ar",
                "48000",
                "-c:a",
                "pcm_s16le",
                "-flags:a",
                "+bitexact",
                "-map_metadata",
                "-1",
                "@member/members/lounge_music_10s.wav",
            ],
            "expected": _truth(
                speech="negative",
                music="positive",
                silence="negative",
                face="not_applicable",
                ocr="not_applicable",
                object_="not_applicable",
            ),
        },
        {
            "id": "poster_face_ocr_object",
            "path": "members/poster_face_ocr_object_5s.mp4",
            "media_type": "video/mp4",
            "duration_seconds": 5.0,
            "source_ids": ["demo_poster"],
            "operation": "ffmpeg",
            "ffmpeg_args": [
                *common,
                "-loop",
                "1",
                "-framerate",
                "30",
                "-i",
                "@source/demo_poster",
                *silence_input,
                *_video_encode_args(),
                "@member/members/poster_face_ocr_object_5s.mp4",
            ],
            "expected": _truth(
                speech="negative",
                music="negative",
                silence="positive",
                face="positive",
                ocr="positive",
                object_="positive",
            ),
        },
    ]
    return sorted(specs, key=lambda item: str(item["path"]))


def _resolve_arguments(
    arguments: list[str],
    *,
    repo_root: Path,
    output_root: Path,
    source_specs: Mapping[str, Mapping[str, str]],
) -> list[str]:
    resolved: list[str] = []
    for argument in arguments:
        if argument.startswith("@source/"):
            source_id = argument.removeprefix("@source/")
            if source_id not in source_specs:
                raise FixturePackError(f"FFmpeg command references unknown source: {source_id}")
            source_path = _relative_path(source_specs[source_id]["path"], "source path")
            resolved.append(str(repo_root.joinpath(*source_path.parts)))
        elif argument.startswith("@member/"):
            member_path = _relative_path(argument.removeprefix("@member/"), "member path")
            resolved.append(str(output_root.joinpath(*member_path.parts)))
        else:
            resolved.append(argument)
    return resolved


def _source_receipts(
    *,
    repo_root: Path,
    source_specs: Mapping[str, Mapping[str, str]],
) -> tuple[list[dict[str, object]], dict[str, str]]:
    receipts: list[dict[str, object]] = []
    initial_hashes: dict[str, str] = {}
    for source_id in sorted(source_specs):
        spec = source_specs[source_id]
        relative = _relative_path(spec.get("path"), f"{source_id} source path")
        source_path = repo_root.joinpath(*relative.parts)
        if not source_path.is_file():
            raise FixturePackError(f"fixture source is missing: {source_id}")
        expected_hash = _expect_sha256(spec.get("sha256"), f"{source_id} source seal")
        actual_hash = _sha256(source_path)
        if actual_hash != expected_hash:
            raise FixturePackError(f"fixture source drift: {source_id}")
        initial_hashes[source_id] = actual_hash
        receipts.append(
            {
                "id": source_id,
                "path": relative.as_posix(),
                "size_bytes": source_path.stat().st_size,
                "sha256": actual_hash,
            }
        )
    return receipts, initial_hashes


def generate_fixture_pack(
    *,
    repo_root: Path,
    output_root: Path,
    ffmpeg_path: Path,
    source_specs: Mapping[str, Mapping[str, str]] | None = None,
    run_command: CommandRunner | None = None,
) -> Path:
    repo_root = repo_root.resolve()
    output_root = output_root.resolve()
    ffmpeg_path = ffmpeg_path.resolve()
    if output_root == repo_root or repo_root in output_root.parents:
        raise FixturePackError("fixture pack output must remain external to source control")
    if output_root.exists() and any(output_root.iterdir()):
        raise FixturePackError("fixture pack output root must be empty")
    if not ffmpeg_path.is_file():
        raise FixturePackError(f"FFmpeg executable is missing: {ffmpeg_path}")
    specs = source_specs or DEFAULT_SOURCE_SPECS
    sources, initial_source_hashes = _source_receipts(
        repo_root=repo_root,
        source_specs=specs,
    )
    runner = run_command or _default_runner
    version_result = runner([str(ffmpeg_path), "-version"], repo_root)
    if version_result.returncode != 0:
        raise FixturePackError("FFmpeg identity check failed")
    version_line = (version_result.stdout or "").splitlines()
    if not version_line:
        raise FixturePackError("FFmpeg identity check returned no version")

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "members").mkdir()
    members: list[dict[str, Any]] = []
    source_by_id = {str(item["id"]): item for item in sources}
    for spec in _member_specs():
        member_relative = _relative_path(spec["path"], "fixture member path")
        member_path = output_root.joinpath(*member_relative.parts)
        if spec["operation"] == "sealed_copy":
            source_id = str(spec["source_ids"][0])
            source_relative = _relative_path(source_by_id[source_id]["path"], "source path")
            shutil.copyfile(repo_root.joinpath(*source_relative.parts), member_path)
        else:
            arguments = list(spec["ffmpeg_args"])
            command = [
                str(ffmpeg_path),
                *_resolve_arguments(
                    arguments,
                    repo_root=repo_root,
                    output_root=output_root,
                    source_specs=specs,
                ),
            ]
            result = runner(command, repo_root)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "unknown error").strip()
                raise FixturePackError(f"FFmpeg failed for {spec['id']}: {detail}")
        if not member_path.is_file() or member_path.stat().st_size < 1:
            raise FixturePackError(f"fixture member was not produced: {spec['id']}")
        members.append(
            {
                "id": spec["id"],
                "path": member_relative.as_posix(),
                "media_type": spec["media_type"],
                "duration_seconds": spec["duration_seconds"],
                "source_ids": list(spec["source_ids"]),
                "operation": spec["operation"],
                "ffmpeg_args": list(spec["ffmpeg_args"]),
                "size_bytes": member_path.stat().st_size,
                "sha256": _sha256(member_path),
                "expected": dict(spec["expected"]),
            }
        )

    for source_id, initial_hash in initial_source_hashes.items():
        relative = _relative_path(specs[source_id]["path"], "source path")
        if _sha256(repo_root.joinpath(*relative.parts)) != initial_hash:
            raise FixturePackError(f"fixture source drift during generation: {source_id}")

    members.sort(key=lambda item: str(item["path"]))
    sources.sort(key=lambda item: str(item["id"]))
    members_sha256 = _canonical_sha256(members)
    sources_sha256 = _canonical_sha256(sources)
    tool = {
        "path_role": "explicit_ffmpeg_executable",
        "version": version_line[0],
        "size_bytes": ffmpeg_path.stat().st_size,
        "sha256": _sha256(ffmpeg_path),
    }
    pack_binding = {
        "schema": SCHEMA,
        "sources_sha256": sources_sha256,
        "members_sha256": members_sha256,
        "ffmpeg_sha256": tool["sha256"],
    }
    manifest = {
        "schema": SCHEMA,
        "status": "sealed",
        "argument_resolution": {
            "@source/<id>": "repo-relative path in sources",
            "@member/<path>": "pack-relative output path",
            "working_directory": "repo_root",
        },
        "tool": tool,
        "source_count": len(sources),
        "sources_sha256": sources_sha256,
        "sources": sources,
        "member_count": len(members),
        "members_sha256": members_sha256,
        "members": members,
        "fixture_pack_sha256": _canonical_sha256(pack_binding),
    }
    manifest_path = output_root / MANIFEST_NAME
    temporary = output_root / f".{MANIFEST_NAME}.tmp"
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    verify_fixture_pack(output_root)
    return manifest_path


def verify_fixture_pack(output_root: Path) -> dict[str, object]:
    output_root = output_root.resolve()
    manifest_path = output_root / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixturePackError("fixture pack manifest is unreadable") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise FixturePackError("fixture pack schema is unsupported")
    sources = manifest.get("sources")
    members = manifest.get("members")
    if not isinstance(sources, list) or not sources or manifest.get("source_count") != len(sources):
        raise FixturePackError("fixture source inventory is incomplete")
    if not isinstance(members, list) or not members or manifest.get("member_count") != len(members):
        raise FixturePackError("fixture member inventory is incomplete")
    source_ids = [str(item.get("id") or "") for item in sources if isinstance(item, dict)]
    member_paths = [str(item.get("path") or "") for item in members if isinstance(item, dict)]
    if (
        len(source_ids) != len(sources)
        or source_ids != sorted(source_ids)
        or len(source_ids) != len(set(source_ids))
    ):
        raise FixturePackError("fixture source IDs must be unique and sorted")
    if (
        len(member_paths) != len(members)
        or member_paths != sorted(member_paths)
        or len(member_paths) != len(set(member_paths))
    ):
        raise FixturePackError("fixture member paths must be unique and sorted")
    if _canonical_sha256(sources) != _expect_sha256(
        manifest.get("sources_sha256"), "fixture source inventory"
    ):
        raise FixturePackError("fixture source inventory digest mismatch")
    if _canonical_sha256(members) != _expect_sha256(
        manifest.get("members_sha256"), "fixture member inventory"
    ):
        raise FixturePackError("fixture member inventory digest mismatch")
    tool = manifest.get("tool")
    if not isinstance(tool, dict):
        raise FixturePackError("fixture FFmpeg identity is missing")
    ffmpeg_sha256 = _expect_sha256(tool.get("sha256"), "fixture FFmpeg identity")
    pack_binding = {
        "schema": SCHEMA,
        "sources_sha256": manifest["sources_sha256"],
        "members_sha256": manifest["members_sha256"],
        "ffmpeg_sha256": ffmpeg_sha256,
    }
    if _canonical_sha256(pack_binding) != _expect_sha256(
        manifest.get("fixture_pack_sha256"), "fixture pack binding"
    ):
        raise FixturePackError("fixture pack binding digest mismatch")

    declared_sources = set(source_ids)
    expected_files = {MANIFEST_NAME}
    for member in members:
        member_path = _relative_path(member.get("path"), "fixture member path")
        expected_files.add(member_path.as_posix())
        if not set(member.get("source_ids") or []).issubset(declared_sources):
            raise FixturePackError(f"fixture member references an unknown source: {member_path}")
        arguments = member.get("ffmpeg_args")
        if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
            raise FixturePackError(f"fixture member FFmpeg arguments are malformed: {member_path}")
        expected_truth = member.get("expected")
        if (
            not isinstance(expected_truth, dict)
            or set(expected_truth) != set(TRUTH_KEYS)
            or any(value not in TRUTH_VALUES for value in expected_truth.values())
        ):
            raise FixturePackError(f"fixture truth contract is malformed: {member_path}")
        file_path = output_root.joinpath(*member_path.parts)
        if not file_path.is_file() or file_path.stat().st_size != int(member.get("size_bytes") or -1):
            raise FixturePackError(f"fixture member size drift: {member_path}")
        if _sha256(file_path) != _expect_sha256(member.get("sha256"), f"fixture member {member_path}"):
            raise FixturePackError(f"fixture member SHA256 drift: {member_path}")
    actual_files = {
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise FixturePackError("fixture pack contains undeclared or missing files")
    return {
        "schema": SCHEMA,
        "status": "verified",
        "manifest_sha256": _sha256(manifest_path),
        "fixture_pack_sha256": manifest["fixture_pack_sha256"],
        "members_sha256": manifest["members_sha256"],
        "member_count": len(members),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.verify_only:
            result = verify_fixture_pack(args.output_root)
            print(json.dumps(result, sort_keys=True))
        else:
            print(
                generate_fixture_pack(
                    repo_root=args.repo_root,
                    output_root=args.output_root,
                    ffmpeg_path=args.ffmpeg,
                )
            )
    except (FixturePackError, OSError, ValueError) as exc:
        print(f"fixture pack failure: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
