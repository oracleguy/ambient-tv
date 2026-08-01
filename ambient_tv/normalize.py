from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

CACHE_VERSION = "1"


@dataclass(frozen=True)
class NormalizationProfile:
    video_codec: str = "h264"
    audio_codec: str = "aac"
    pixel_format: str = "yuv420p"
    max_width: int = 1920
    max_height: int = 1080
    fps: int = 30
    audio_sample_rate: int = 48000
    audio_channels: int = 2


def cache_fingerprint(source: Path, profile: NormalizationProfile | None = None) -> str:
    selected_profile = profile or NormalizationProfile()
    stat = source.stat()
    payload = {
        "cache_version": CACHE_VERSION,
        "path": str(source.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "profile": asdict(selected_profile),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def cached_output_path(cache_directory: Path, channel_id: str, source: Path) -> Path:
    return cache_directory / channel_id / f"{cache_fingerprint(source)}{source.suffix.lower()}"
