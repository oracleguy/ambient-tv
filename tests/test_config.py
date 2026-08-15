from __future__ import annotations

from pathlib import Path

import pytest

from ambient_tv.config import load_config
from ambient_tv.errors import ConfigError, PublishError


def write_config(root: Path, body: str) -> Path:
    path = root / "config.toml"
    path.write_text(body, encoding="utf-8")
    return path


def base_config(root: Path, channels: str) -> str:
    media = root / "media"
    return f"""
[server]
name = "Ambient TV"

[network]
stream_host = "ambient-tv.local"
rtsp_port = 8554

[site]
title = "Ambient TV"
subtitle = "Always-on channels"
base_url = "http://ambient-tv.local/ambient"
output_directory = "./generated/site"

[media]
directory = "{media}"
cache_directory = "./generated/cache"
playlist_directory = "./generated/playlists"

{channels}
"""


@pytest.fixture
def media_root(tmp_path: Path) -> Path:
    media = tmp_path / "media"
    media.mkdir()
    return media


def test_loads_valid_single_file_config(tmp_path: Path, media_root: Path) -> None:
    (media_root / "ocean.mp4").write_bytes(b"fake")
    config_path = write_config(
        tmp_path,
        base_config(
            tmp_path,
            """
[[channels]]
id = "ocean"
name = "Ocean"
file = "ocean.mp4"
""",
        ),
    )

    config = load_config(config_path)

    assert config.channels[0].id == "ocean"
    assert config.media.directory == media_root.resolve()


def test_requires_expected_sections(tmp_path: Path) -> None:
    config_path = write_config(tmp_path, "[server]\nname = 'Ambient TV'\n")

    with pytest.raises(ConfigError, match="Missing required section"):
        load_config(config_path)


def test_rejects_file_and_directory_together(tmp_path: Path, media_root: Path) -> None:
    (media_root / "ocean.mp4").write_bytes(b"fake")
    (media_root / "city").mkdir()
    config_path = write_config(
        tmp_path,
        base_config(
            tmp_path,
            """
[[channels]]
id = "bad"
file = "ocean.mp4"
directory = "city"
""",
        ),
    )

    with pytest.raises(ConfigError, match="exactly one"):
        load_config(config_path)


def test_rejects_duplicate_channel_ids(tmp_path: Path, media_root: Path) -> None:
    (media_root / "one.mp4").write_bytes(b"fake")
    (media_root / "two.mp4").write_bytes(b"fake")
    config_path = write_config(
        tmp_path,
        base_config(
            tmp_path,
            """
[[channels]]
id = "ocean"
file = "one.mp4"

[[channels]]
id = "ocean"
file = "two.mp4"
""",
        ),
    )

    with pytest.raises(ConfigError, match="Duplicate channel id"):
        load_config(config_path)


@pytest.mark.parametrize("channel_id", ["Ocean", "night_city", "-city", "city/one"])
def test_rejects_invalid_channel_ids(
    tmp_path: Path, media_root: Path, channel_id: str
) -> None:
    (media_root / "ocean.mp4").write_bytes(b"fake")
    config_path = write_config(
        tmp_path,
        base_config(
            tmp_path,
            f"""
[[channels]]
id = "{channel_id}"
file = "ocean.mp4"
""",
        ),
    )

    with pytest.raises(ConfigError, match="Invalid channel id"):
        load_config(config_path)


def test_directory_channel_requires_supported_media(tmp_path: Path, media_root: Path) -> None:
    empty = media_root / "empty"
    empty.mkdir()
    (empty / "notes.txt").write_text("nope", encoding="utf-8")
    config_path = write_config(
        tmp_path,
        base_config(
            tmp_path,
            """
[[channels]]
id = "empty"
directory = "empty"
""",
        ),
    )

    with pytest.raises(ConfigError, match="no supported videos"):
        load_config(config_path)


def test_rejects_unsafe_publish_directory(tmp_path: Path, media_root: Path) -> None:
    (media_root / "ocean.mp4").write_bytes(b"fake")
    body = base_config(
        tmp_path,
        """
[[channels]]
id = "ocean"
file = "ocean.mp4"
""",
    ).replace('output_directory = "./generated/site"', 'publish_directory = "/"')
    config_path = write_config(tmp_path, body)

    with pytest.raises(PublishError, match="unsafe publish"):
        load_config(config_path)
