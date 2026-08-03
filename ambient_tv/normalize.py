from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

CACHE_VERSION = "1"
MANIFEST_NAME = "manifest.json"
PROBE_TIMEOUT_SECONDS = 30
FFMPEG_TIMEOUT_SECONDS = 60 * 60 * 6


class CommandRunner(Protocol):
    def __call__(
        self, args: list[str], *, timeout: int, capture_output: bool, text: bool
    ) -> subprocess.CompletedProcess[str]: ...


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


@dataclass(frozen=True)
class MediaProbe:
    container: str
    video_codec: str
    pixel_format: str | None
    width: int
    height: int
    fps: float | None
    audio_codec: str | None
    audio_sample_rate: int | None
    audio_channels: int | None


@dataclass(frozen=True)
class NormalizedMedia:
    source: Path
    output: Path
    fingerprint: str
    action: str


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


def cached_output_path(
    cache_directory: Path,
    channel_id: str,
    source: Path,
    profile: NormalizationProfile | None = None,
) -> Path:
    return cache_directory / channel_id / f"{cache_fingerprint(source, profile)}.mp4"


def cache_container_path(cache_directory: Path, output: Path) -> Path:
    relative = output.resolve().relative_to(cache_directory.resolve())
    return Path("/cache") / relative


def normalize_directory_files(
    *,
    sources: list[Path],
    cache_directory: Path,
    channel_id: str,
    profile: NormalizationProfile | None = None,
    runner: CommandRunner = subprocess.run,
) -> list[NormalizedMedia]:
    selected_profile = profile or NormalizationProfile()
    channel_cache = cache_directory / channel_id
    channel_cache.mkdir(parents=True, exist_ok=True)

    normalized: list[NormalizedMedia] = []
    for source in sources:
        probe = probe_media(source, runner=runner)
        fingerprint = cache_fingerprint(source, selected_profile)
        output = channel_cache / f"{fingerprint}.mp4"
        action = normalization_action(probe, selected_profile)
        if not cached_output_is_valid(output, source, fingerprint, selected_profile, action):
            run_normalization(source, output, probe, selected_profile, runner=runner)
            write_sidecar(output, source, fingerprint, selected_profile, action)
        normalized.append(
            NormalizedMedia(source=source, output=output, fingerprint=fingerprint, action=action)
        )

    write_manifest(channel_cache, normalized)
    remove_stale_cache_files(channel_cache, {item.output.name for item in normalized})
    return normalized


def probe_media(source: Path, *, runner: CommandRunner = subprocess.run) -> MediaProbe:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        source.as_posix(),
    ]
    result = runner(command, timeout=PROBE_TIMEOUT_SECONDS, capture_output=True, text=True)
    if result.returncode != 0:
        from ambient_tv.errors import MediaError

        raise MediaError(f"ffprobe failed for {source}: {result.stderr.strip()}")
    return parse_probe_json(source, result.stdout)


def parse_probe_json(source: Path, text: str) -> MediaProbe:
    from ambient_tv.errors import MediaError

    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise MediaError(f"ffprobe returned invalid JSON for {source}") from error

    streams = data.get("streams")
    if not isinstance(streams, list):
        raise MediaError(f"ffprobe returned no streams for {source}")

    video = first_stream(streams, "video")
    if video is None:
        raise MediaError(f"No video stream found in {source}")
    audio = first_stream(streams, "audio")
    format_data = data.get("format") if isinstance(data.get("format"), dict) else {}

    return MediaProbe(
        container=str(format_data.get("format_name", "")),
        video_codec=str(video.get("codec_name", "")),
        pixel_format=str(video["pix_fmt"]) if video.get("pix_fmt") else None,
        width=int(video.get("width", 0)),
        height=int(video.get("height", 0)),
        fps=parse_rate(str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "")),
        audio_codec=str(audio.get("codec_name")) if audio and audio.get("codec_name") else None,
        audio_sample_rate=parse_int(audio.get("sample_rate")) if audio else None,
        audio_channels=parse_int(audio.get("channels")) if audio else None,
    )


def first_stream(streams: list[Any], codec_type: str) -> dict[str, Any] | None:
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == codec_type:
            return stream
    return None


def parse_rate(value: str) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        denominator_value = float(denominator)
        if denominator_value == 0:
            return None
        return float(numerator) / denominator_value
    return float(value)


def parse_int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def normalization_action(probe: MediaProbe, profile: NormalizationProfile) -> str:
    if probe_matches_profile(probe, profile) and "mp4" in probe.container.split(","):
        return "remux"
    return "transcode"


def probe_matches_profile(probe: MediaProbe, profile: NormalizationProfile) -> bool:
    return (
        probe.video_codec == profile.video_codec
        and probe.audio_codec == profile.audio_codec
        and probe.pixel_format == profile.pixel_format
        and probe.width == profile.max_width
        and probe.height == profile.max_height
        and probe.fps == float(profile.fps)
        and probe.audio_sample_rate == profile.audio_sample_rate
        and probe.audio_channels == profile.audio_channels
    )


def cached_output_is_valid(
    output: Path,
    source: Path,
    fingerprint: str,
    profile: NormalizationProfile,
    action: str,
) -> bool:
    sidecar = sidecar_path(output)
    if not output.is_file() or not sidecar.is_file():
        return False
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return data == sidecar_payload(source, fingerprint, profile, action)


def run_normalization(
    source: Path,
    output: Path,
    probe: MediaProbe,
    profile: NormalizationProfile,
    *,
    runner: CommandRunner = subprocess.run,
) -> None:
    from ambient_tv.errors import MediaError

    output.parent.mkdir(parents=True, exist_ok=True)
    command = normalization_command(source, output, probe, profile)
    result = runner(command, timeout=FFMPEG_TIMEOUT_SECONDS, capture_output=True, text=True)
    if result.returncode != 0:
        raise MediaError(f"ffmpeg failed for {source}: {result.stderr.strip()}")


def normalization_command(
    source: Path,
    output: Path,
    probe: MediaProbe,
    profile: NormalizationProfile | None = None,
) -> list[str]:
    selected_profile = profile or NormalizationProfile()
    base = ["ffmpeg", "-y", "-i", source.as_posix()]
    if normalization_action(probe, selected_profile) == "remux":
        return [
            *base,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            output.as_posix(),
        ]

    video_filter = (
        f"scale={selected_profile.max_width}:{selected_profile.max_height}:"
        "force_original_aspect_ratio=decrease,"
        f"pad={selected_profile.max_width}:{selected_profile.max_height}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={selected_profile.fps},setsar=1,format={selected_profile.pixel_format}"
    )
    command = [*base]
    if probe.audio_codec is None:
        command.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=stereo:sample_rate={selected_profile.audio_sample_rate}",
            ]
        )
    command.extend(
        [
            "-map",
            "0:v:0",
            "-map",
            "1:a:0" if probe.audio_codec is None else "0:a:0",
            "-vf",
            video_filter,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            selected_profile.audio_codec,
            "-ar",
            str(selected_profile.audio_sample_rate),
            "-ac",
            str(selected_profile.audio_channels),
            "-b:a",
            "160k",
            "-shortest",
            "-movflags",
            "+faststart",
            output.as_posix(),
        ]
    )
    return command


def write_sidecar(
    output: Path, source: Path, fingerprint: str, profile: NormalizationProfile, action: str
) -> None:
    sidecar_path(output).write_text(
        json.dumps(sidecar_payload(source, fingerprint, profile, action), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def sidecar_payload(
    source: Path, fingerprint: str, profile: NormalizationProfile, action: str
) -> dict[str, Any]:
    return {
        "cache_version": CACHE_VERSION,
        "source": str(source.resolve()),
        "fingerprint": fingerprint,
        "profile": asdict(profile),
        "action": action,
    }


def sidecar_path(output: Path) -> Path:
    return output.with_suffix(output.suffix + ".json")


def write_manifest(channel_cache: Path, normalized: list[NormalizedMedia]) -> None:
    payload = {
        "cache_version": CACHE_VERSION,
        "files": [
            {
                "source": str(item.source.resolve()),
                "output": item.output.name,
                "fingerprint": item.fingerprint,
                "action": item.action,
            }
            for item in normalized
        ],
    }
    (channel_cache / MANIFEST_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def remove_stale_cache_files(channel_cache: Path, active_outputs: set[str]) -> None:
    keep = set(active_outputs)
    keep.update(f"{name}.json" for name in active_outputs)
    keep.add(MANIFEST_NAME)
    for path in channel_cache.iterdir():
        if path.is_file() and path.name not in keep:
            path.unlink()
