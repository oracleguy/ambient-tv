from __future__ import annotations

from pathlib import Path

from ambient_tv.config import channel_source_path
from ambient_tv.media import media_mount_path
from ambient_tv.models import AppConfig, Channel

FFMPEG_IMAGE = "linuxserver/ffmpeg:latest"
MEDIAMTX_IMAGE = "bluenviron/mediamtx:latest"


def render_compose(config: AppConfig) -> str:
    lines: list[str] = [
        "services:",
        "  mediamtx:",
        f"    image: {MEDIAMTX_IMAGE}",
        "    restart: unless-stopped",
        "    ports:",
        f'      - "{config.network.rtsp_port}:8554"',
        "",
    ]
    for channel in config.channels:
        if not channel.enabled:
            continue
        lines.extend(render_channel_service(config, channel))
        lines.append("")
    return "\n".join(lines)


def render_channel_service(config: AppConfig, channel: Channel) -> list[str]:
    command = channel_command(config, channel)
    source_mount = f"{config.media.directory}:/media:ro"
    lines = [
        f"  channel-{channel.id}:",
        f"    image: {FFMPEG_IMAGE}",
        "    restart: unless-stopped",
        "    depends_on:",
        "      - mediamtx",
        "    volumes:",
        f"      - {quote_yaml(source_mount)}",
    ]
    if channel.is_directory:
        playlist_mount = f"{config.media.playlist_directory}:/playlists:ro"
        cache_mount = f"{config.media.cache_directory}:/cache:ro"
        lines.extend(
            [
                f"      - {quote_yaml(playlist_mount)}",
                f"      - {quote_yaml(cache_mount)}",
            ]
        )
    lines.extend(["    command:", *[f"      - {quote_yaml(arg)}" for arg in command]])
    return lines


def channel_command(config: AppConfig, channel: Channel) -> list[str]:
    publish_url = f"rtsp://mediamtx:8554/{channel.id}"
    if channel.file is not None:
        source = media_mount_path(channel_source_path(config, channel), config.media.directory)
        return ["-re", "-stream_loop", "-1", "-i", source, "-c", "copy", "-f", "rtsp", publish_url]

    playlist = Path("/playlists") / f"{channel.id}.ffconcat"
    return [
        "-re",
        "-stream_loop",
        "-1",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        playlist.as_posix(),
        "-c",
        "copy",
        "-f",
        "rtsp",
        publish_url,
    ]


def quote_yaml(value: object) -> str:
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
