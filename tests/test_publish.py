from __future__ import annotations

from pathlib import Path

import pytest

from ambient_tv.errors import PublishError
from ambient_tv.publish import publish_site


def test_publish_refuses_unmarked_non_empty_directory(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "index.html").write_text("new", encoding="utf-8")
    destination = tmp_path / "public"
    destination.mkdir()
    (destination / "old.html").write_text("old", encoding="utf-8")

    with pytest.raises(PublishError, match="not marked"):
        publish_site(staging, destination, repo_root=tmp_path / "repo")


def test_publish_replaces_files_in_marked_directory(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "index.html").write_text("new", encoding="utf-8")
    destination = tmp_path / "public"
    destination.mkdir()
    (destination / ".ambient-tv-generated").touch()
    (destination / "old.html").write_text("old", encoding="utf-8")

    publish_site(staging, destination, repo_root=tmp_path / "repo")

    assert not (destination / "old.html").exists()
    assert (destination / "index.html").read_text(encoding="utf-8") == "new"
