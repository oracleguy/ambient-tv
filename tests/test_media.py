from __future__ import annotations

from pathlib import Path

from ambient_tv.media import scan_video_directory


def test_scan_video_directory_filters_and_sorts_supported_files(tmp_path: Path) -> None:
    directory = tmp_path / "media"
    directory.mkdir()
    (directory / "b.MKV").write_bytes(b"fake")
    (directory / "a.mp4").write_bytes(b"fake")
    (directory / "notes.txt").write_text("ignore", encoding="utf-8")

    paths = scan_video_directory(directory)

    assert [path.name for path in paths] == ["a.mp4", "b.MKV"]
