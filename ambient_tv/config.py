from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - only used by local Python < 3.11
    import tomli as tomllib

from ambient_tv.errors import ConfigError
from ambient_tv.media import SUPPORTED_VIDEO_EXTENSIONS, scan_video_directory
from ambient_tv.models import (
    AppConfig,
    Channel,
    MediaConfig,
    NetworkConfig,
    ServerConfig,
    SiteConfig,
)
from ambient_tv.publish import assert_safe_publish_directory

CHANNEL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def load_config(path: Path) -> AppConfig:
    config_path = path.expanduser().resolve()
    if not config_path.exists():
        raise ConfigError(f"Configuration file does not exist: {path}")

    with config_path.open("rb") as file:
        raw = tomllib.load(file)

    root = config_path.parent
    return parse_config(raw, root=root)


def parse_config(raw: dict[str, Any], *, root: Path) -> AppConfig:
    require_sections(raw, "server", "network", "site", "media")
    channels_raw = raw.get("channels")
    if not isinstance(channels_raw, list) or not channels_raw:
        raise ConfigError("Configuration must include at least one [[channels]] entry")

    media_raw = require_mapping(raw["media"], "media")
    site_raw = require_mapping(raw["site"], "site")

    media = MediaConfig(
        directory=resolve_config_path(root, require_str(media_raw, "directory", "media")),
        cache_directory=resolve_config_path(
            root, require_str(media_raw, "cache_directory", "media")
        ),
        playlist_directory=resolve_config_path(
            root, require_str(media_raw, "playlist_directory", "media")
        ),
    )
    site = SiteConfig(
        title=require_str(site_raw, "title", "site"),
        subtitle=str(site_raw.get("subtitle", "")),
        base_url=require_str(site_raw, "base_url", "site").rstrip("/"),
        output_directory=resolve_config_path(
            root, str(site_raw.get("output_directory", "./generated/site"))
        ),
        publish_directory=parse_optional_path(root, site_raw.get("publish_directory")),
        theme=str(site_raw.get("theme", "dark")),
    )
    network_raw = require_mapping(raw["network"], "network")
    server_raw = require_mapping(raw["server"], "server")
    network = NetworkConfig(
        stream_host=require_str(network_raw, "stream_host", "network"),
        rtsp_port=require_int(network_raw, "rtsp_port", "network"),
    )
    server = ServerConfig(name=require_str(server_raw, "name", "server"))
    channels = tuple(parse_channel(item, index) for index, item in enumerate(channels_raw, start=1))

    config = AppConfig(
        root=root,
        server=server,
        network=network,
        site=site,
        media=media,
        channels=channels,
    )
    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    seen_ids: set[str] = set()
    for channel in config.channels:
        if channel.id in seen_ids:
            raise ConfigError(f"Duplicate channel id: {channel.id}")
        seen_ids.add(channel.id)
        if not CHANNEL_ID_RE.fullmatch(channel.id):
            raise ConfigError(
                f"Invalid channel id '{channel.id}'. Use lowercase letters, numbers, and hyphens."
            )
        if channel.shuffle_rounds < 1:
            raise ConfigError(f"Channel '{channel.id}' shuffle_rounds must be a positive integer")

        source = channel_source_path(config, channel)
        if not source.exists():
            raise ConfigError(f"Channel '{channel.id}' source path does not exist: {source}")
        if channel.file and not source.is_file():
            raise ConfigError(f"Channel '{channel.id}' file source is not a file: {source}")
        if channel.directory:
            if not source.is_dir():
                raise ConfigError(
                    f"Channel '{channel.id}' directory source is not a directory: {source}"
                )
            if not scan_video_directory(source):
                extensions = ", ".join(sorted(SUPPORTED_VIDEO_EXTENSIONS))
                raise ConfigError(
                    f"Channel '{channel.id}' directory contains no supported videos "
                    f"({extensions}): {source}"
                )

    assert_generated_path(config.root, config.media.cache_directory, "media.cache_directory")
    assert_generated_path(config.root, config.media.playlist_directory, "media.playlist_directory")
    assert_generated_path(config.root, config.site.output_directory, "site.output_directory")
    if config.site.publish_directory is not None:
        assert_safe_publish_directory(config.site.publish_directory, repo_root=config.root)


def parse_channel(raw: Any, index: int) -> Channel:
    data = require_mapping(raw, f"channels[{index}]")
    channel_id = require_str(data, "id", f"channels[{index}]")
    has_file = "file" in data
    has_directory = "directory" in data
    if has_file == has_directory:
        raise ConfigError(f"Channel '{channel_id}' must contain exactly one of file or directory")
    shuffle_rounds = data.get("shuffle_rounds", 1)
    if not isinstance(shuffle_rounds, int):
        raise ConfigError(f"Channel '{channel_id}' shuffle_rounds must be an integer")
    return Channel(
        id=channel_id,
        name=str(data.get("name", channel_id)),
        file=str(data["file"]) if has_file else None,
        directory=str(data["directory"]) if has_directory else None,
        shuffle_rounds=shuffle_rounds,
        description=str(data.get("description", "")),
        poster=str(data["poster"]) if data.get("poster") else None,
        enabled=bool(data.get("enabled", True)),
    )


def channel_source_path(config: AppConfig, channel: Channel) -> Path:
    relative = channel.file if channel.file is not None else channel.directory
    if relative is None:
        raise ConfigError(f"Channel '{channel.id}' has no source path")
    return (config.media.directory / relative).resolve()


def require_sections(raw: dict[str, Any], *sections: str) -> None:
    missing = [section for section in sections if section not in raw]
    if missing:
        raise ConfigError(f"Missing required section(s): {', '.join(missing)}")


def require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"Section [{name}] must be a table")
    return value


def require_str(data: dict[str, Any], key: str, section: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"[{section}] {key} must be a non-empty string")
    return value


def require_int(data: dict[str, Any], key: str, section: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise ConfigError(f"[{section}] {key} must be an integer")
    return value


def resolve_config_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def parse_optional_path(root: Path, value: Any) -> Path | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ConfigError("[site] publish_directory must be a string when set")
    return resolve_config_path(root, value)


def assert_generated_path(root: Path, path: Path, label: str) -> None:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path == resolved_root:
        raise ConfigError(f"{label} cannot be the repository root")
    if not resolved_path.is_relative_to(resolved_root):
        raise ConfigError(f"{label} must resolve inside the repository: {resolved_path}")
