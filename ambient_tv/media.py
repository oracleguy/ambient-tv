from __future__ import annotations

from pathlib import Path

SUPPORTED_VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".mov", ".webm", ".m4v"})


def is_supported_video(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS


def scan_video_directory(directory: Path) -> list[Path]:
    return sorted(
        (path.resolve() for path in directory.iterdir() if is_supported_video(path)),
        key=lambda path: path.name.lower(),
    )


def media_mount_path(source: Path, media_root: Path) -> str:
    relative = source.resolve().relative_to(media_root.resolve())
    return "/media/" + relative.as_posix()
