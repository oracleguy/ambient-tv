from __future__ import annotations

from pathlib import Path

from ambient_tv.normalize import cache_fingerprint


def test_cache_fingerprint_changes_when_source_changes(tmp_path: Path) -> None:
    source = tmp_path / "video.mp4"
    source.write_bytes(b"one")
    first = cache_fingerprint(source)

    source.write_bytes(b"two")
    second = cache_fingerprint(source)

    assert first != second
