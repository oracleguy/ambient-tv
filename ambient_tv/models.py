from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServerConfig:
    name: str


@dataclass(frozen=True)
class NetworkConfig:
    stream_host: str
    rtsp_port: int


@dataclass(frozen=True)
class SiteConfig:
    title: str
    subtitle: str
    base_url: str
    output_directory: Path
    publish_directory: Path | None
    theme: str


@dataclass(frozen=True)
class MediaConfig:
    directory: Path
    cache_directory: Path
    playlist_directory: Path


@dataclass(frozen=True)
class Channel:
    id: str
    name: str
    file: str | None
    directory: str | None
    shuffle_rounds: int
    description: str
    poster: str | None
    enabled: bool = True

    @property
    def is_directory(self) -> bool:
        return self.directory is not None


@dataclass(frozen=True)
class AppConfig:
    root: Path
    server: ServerConfig
    network: NetworkConfig
    site: SiteConfig
    media: MediaConfig
    channels: tuple[Channel, ...]
