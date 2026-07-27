from __future__ import annotations

from pathlib import Path

import pytest
import typer

from cli.run_ingestion import (
    _filter_scenes_by_index,
    _filter_scenes_by_selection,
    _parse_scene_indices,
    _select_ingest_videos,
)


def test_select_ingest_videos_uses_only_explicit_file(tmp_path: Path) -> None:
    selected = tmp_path / "selected.mp4"
    unselected = tmp_path / "unselected.mp4"
    selected.write_bytes(b"selected")
    unselected.write_bytes(b"unselected")

    root, videos = _select_ingest_videos(None, selected)

    assert root == tmp_path.resolve()
    assert videos == [selected.resolve()]


def test_select_ingest_videos_rejects_ambiguous_or_invalid_file(tmp_path: Path) -> None:
    selected = tmp_path / "selected.mp4"
    selected.write_bytes(b"selected")
    unsupported = tmp_path / "not-video.txt"
    unsupported.write_text("not video", encoding="utf-8")

    with pytest.raises(typer.BadParameter, match="mutually exclusive"):
        _select_ingest_videos(tmp_path, selected)
    with pytest.raises(typer.BadParameter, match="Input file not found"):
        _select_ingest_videos(None, tmp_path / "missing.mp4")
    with pytest.raises(typer.BadParameter, match="Unsupported input file type"):
        _select_ingest_videos(None, unsupported)


def test_select_ingest_videos_preserves_directory_glob_mode(tmp_path: Path) -> None:
    mp4 = tmp_path / "b.mp4"
    mov = tmp_path / "a.mov"
    ignored = tmp_path / "ignore.txt"
    mp4.write_bytes(b"mp4")
    mov.write_bytes(b"mov")
    ignored.write_text("ignore", encoding="utf-8")

    root, videos = _select_ingest_videos(tmp_path, None)

    assert root == tmp_path.resolve()
    assert videos == [mp4.resolve(), mov.resolve()]


def test_explicit_file_selection_keeps_scene_index_filter_precise() -> None:
    scenes = [{"index": 0}, {"index": 1}, {"index": 2}, {"index": 3}]

    assert _filter_scenes_by_index(scenes, 2, 2) == [{"index": 2}]


def test_exact_scene_indices_select_only_requested_scenes_in_detector_order() -> None:
    scenes = [{"index": 8}, {"index": 2}, {"index": 5}, {"index": 1}]

    indices = _parse_scene_indices("5,2,8")

    assert indices == (2, 5, 8)
    assert _filter_scenes_by_selection(scenes, None, None, indices) == [
        {"index": 8},
        {"index": 2},
        {"index": 5},
    ]


def test_exact_scene_indices_fail_when_detector_does_not_return_the_locked_scope() -> None:
    with pytest.raises(typer.BadParameter, match="not detected"):
        _filter_scenes_by_selection([{"index": 2}], None, None, (2, 5))


@pytest.mark.parametrize("value", ["", "2,,3", "-1", "2,2", "two"])
def test_exact_scene_indices_reject_ambiguous_selection(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        _parse_scene_indices(value)
