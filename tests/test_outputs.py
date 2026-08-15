from __future__ import annotations

from pathlib import Path

from ambient_tv.compose import channel_command, render_compose
from ambient_tv.config import load_config
from ambient_tv.m3u import render_m3u
from ambient_tv.site import write_site


def make_config(tmp_path: Path):
    media = tmp_path / "media"
    city = media / "city"
    city.mkdir(parents=True)
    (media / "ocean.mp4").write_bytes(b"fake")
    (city / "rain.mp4").write_bytes(b"fake")
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
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

[[channels]]
id = "ocean"
name = "Ocean"
file = "ocean.mp4"

[[channels]]
id = "city"
name = "Night City"
directory = "city"
shuffle_rounds = 2
""",
        encoding="utf-8",
    )
    return load_config(config_path)


def test_m3u_uses_channel_order_and_public_host(tmp_path: Path) -> None:
    config = make_config(tmp_path)

    assert render_m3u(config) == (
        "#EXTM3U\n\n"
        "#EXTINF:-1,Ocean\n"
        "rtsp://ambient-tv.local:8554/ocean\n\n"
        "#EXTINF:-1,Night City\n"
        "rtsp://ambient-tv.local:8554/city\n"
    )


def test_compose_contains_mediamtx_and_channel_services(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    rendered = render_compose(config)

    assert "  mediamtx:" in rendered
    assert "  channel-ocean:" in rendered
    assert "  channel-city:" in rendered
    assert '"8554:8554"' in rendered
    assert "rtsp://mediamtx:8554/ocean" in rendered


def test_directory_channel_command_uses_concat_playlist(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    command = channel_command(config, config.channels[1])

    assert "-f" in command
    assert "concat" in command
    assert "/playlists/city.ffconcat" in command


def test_write_site_renders_html_and_copies_static_assets(tmp_path: Path) -> None:
    config = make_config(tmp_path)

    write_site(config)

    output = config.site.output_directory
    index_html = (output / "index.html").read_text(encoding="utf-8")
    assert index_html.startswith("<!doctype html>")
    assert "rtsp://ambient-tv.local:8554/ocean" in index_html
    assert (output / "styles.css").exists()
    assert (output / "app.js").exists()
    assert (output / "channels.m3u").exists()
