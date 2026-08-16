from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ambient_tv.normalize import (
    FFMPEG_TIMEOUT_SECONDS,
    PROBE_TIMEOUT_SECONDS,
    MediaProbe,
    cache_fingerprint,
    normalization_command,
    normalize_directory_files,
    parse_probe_json,
)


def test_cache_fingerprint_changes_when_source_changes(tmp_path: Path) -> None:
    source = tmp_path / "video.mp4"
    source.write_bytes(b"one")
    first = cache_fingerprint(source)

    source.write_bytes(b"two")
    second = cache_fingerprint(source)

    assert first != second


def test_parse_probe_json_extracts_video_and_audio_metadata(tmp_path: Path) -> None:
    source = tmp_path / "video.mp4"
    probe = parse_probe_json(
        source,
        json.dumps(
            {
                "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "pix_fmt": "yuv420p",
                        "width": 1920,
                        "height": 1080,
                        "avg_frame_rate": "30/1",
                    },
                    {
                        "codec_type": "audio",
                        "codec_name": "aac",
                        "sample_rate": "48000",
                        "channels": 2,
                    },
                ],
            }
        ),
    )

    assert probe.video_codec == "h264"
    assert probe.audio_codec == "aac"
    assert probe.fps == 30.0


def test_normalization_command_transcodes_to_shared_profile(tmp_path: Path) -> None:
    source = tmp_path / "video.mkv"
    output = tmp_path / "cache" / "video.mp4"
    probe = MediaProbe(
        container="matroska,webm",
        video_codec="hevc",
        pixel_format="yuv420p10le",
        width=3840,
        height=2160,
        fps=60,
        audio_codec="opus",
        audio_sample_rate=44100,
        audio_channels=6,
    )

    command = normalization_command(source, output, probe)

    assert command[:4] == ["ffmpeg", "-y", "-i", source.as_posix()]
    assert "-c:v" in command
    assert "libx264" in command
    assert "-c:a" in command
    assert "aac" in command
    assert output.as_posix() == command[-1]


def test_normalization_reuses_current_cache_and_removes_stale_files(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    cache = tmp_path / "cache"
    sources.mkdir()
    first = sources / "first.mp4"
    second = sources / "second.mp4"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    calls: list[list[str]] = []

    def runner(
        args: list[str], *, timeout: int, capture_output: bool, text: bool
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[0] == "ffprobe":
            assert timeout == PROBE_TIMEOUT_SECONDS
            stdout = json.dumps(
                {
                    "format": {"format_name": "matroska,webm"},
                    "streams": [
                        {
                            "codec_type": "video",
                            "codec_name": "hevc",
                            "pix_fmt": "yuv420p10le",
                            "width": 3840,
                            "height": 2160,
                            "avg_frame_rate": "60/1",
                        }
                    ],
                }
            )
            return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")
        assert timeout == FFMPEG_TIMEOUT_SECONDS
        Path(args[-1]).write_bytes(b"normalized")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    first_run = normalize_directory_files(
        sources=[first, second], cache_directory=cache, channel_id="city", runner=runner
    )
    ffmpeg_calls_after_first_run = [args for args in calls if args[0] == "ffmpeg"]

    assert len(first_run) == 2
    assert len(ffmpeg_calls_after_first_run) == 2

    calls.clear()
    normalize_directory_files(
        sources=[first, second], cache_directory=cache, channel_id="city", runner=runner
    )
    assert [args for args in calls if args[0] == "ffmpeg"] == []

    second.unlink()
    first.write_bytes(b"one updated")
    calls.clear()
    second_run = normalize_directory_files(
        sources=[first], cache_directory=cache, channel_id="city", runner=runner
    )

    active_names = {item.output.name for item in second_run}
    cache_names = {path.name for path in (cache / "city").iterdir()}
    assert len([args for args in calls if args[0] == "ffmpeg"]) == 1
    assert cache_names == active_names | {f"{next(iter(active_names))}.json", "manifest.json"}


def test_normalization_logs_progress_for_each_file_in_verbose_mode(
    tmp_path: Path, capsys
) -> None:
    source = tmp_path / "video.mkv"
    source.write_bytes(b"video")
    cache = tmp_path / "cache"
    calls: list[tuple[list[str], bool]] = []

    def runner(
        args: list[str], *, timeout: int, capture_output: bool, text: bool
    ) -> subprocess.CompletedProcess[str]:
        calls.append((args, capture_output))
        if args[0] == "ffprobe":
            stdout = json.dumps(
                {
                    "format": {"format_name": "matroska,webm"},
                    "streams": [
                        {
                            "codec_type": "video",
                            "codec_name": "hevc",
                            "pix_fmt": "yuv420p10le",
                            "width": 3840,
                            "height": 2160,
                            "avg_frame_rate": "60/1",
                        }
                    ],
                }
            )
            return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")
        Path(args[-1]).write_bytes(b"normalized")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    normalize_directory_files(
        sources=[source],
        cache_directory=cache,
        channel_id="night",
        runner=runner,
        verbose=True,
    )

    assert calls[1][0][0] == "ffmpeg"
    assert calls[1][1] is False
    output = capsys.readouterr().out
    assert "Normalizing" in output
    assert "night" in output
    assert "video.mkv" in output
