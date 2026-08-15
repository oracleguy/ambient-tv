from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from ambient_tv.compose import render_compose
from ambient_tv.config import channel_source_path, load_config
from ambient_tv.errors import AmbientTvError
from ambient_tv.media import media_mount_path, scan_video_directory
from ambient_tv.models import AppConfig, Channel
from ambient_tv.normalize import cache_container_path, normalize_directory_files
from ambient_tv.playlists import build_shuffle_sequence, write_ffconcat
from ambient_tv.publish import publish_site
from ambient_tv.site import write_site


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        run(args)
    except AmbientTvError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except Exception:
        if args.verbose:
            raise
        print("Error: unexpected failure. Rerun with --verbose for a traceback.", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Ambient TV runtime files")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--no-normalize", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def run(args: argparse.Namespace) -> None:
    print("Loading configuration")
    config = load_config(args.config)

    print("Validating channels")
    if args.check:
        print("Check complete")
        return

    use_normalized_media = not args.no_normalize
    if use_normalized_media:
        print("Probing media")
        print("Normalizing media")

    print("Generating playlists")
    generate_playlists(config, normalize=use_normalized_media)

    print("Generating Compose configuration")
    write_compose(config)

    print("Generating static site")
    write_site(config)

    if args.no_publish or config.site.publish_directory is None:
        print("Publishing static site skipped")
    else:
        print("Publishing static site")
        publish_site(
            config.site.output_directory,
            config.site.publish_directory,
            repo_root=config.root,
        )

    print("Complete")


def generate_playlists(config: AppConfig, *, normalize: bool = True) -> None:
    for channel in config.channels:
        if channel.enabled and channel.is_directory:
            generate_channel_playlist(config, channel, normalize=normalize)


def generate_channel_playlist(
    config: AppConfig, channel: Channel, *, normalize: bool = True
) -> None:
    source_dir = channel_source_path(config, channel)
    files = scan_video_directory(source_dir)
    if normalize:
        normalized = normalize_directory_files(
            sources=files,
            cache_directory=config.media.cache_directory,
            channel_id=channel.id,
        )
        playlist_inputs = [
            cache_container_path(config.media.cache_directory, item.output) for item in normalized
        ]
    else:
        playlist_inputs = [Path(media_mount_path(path, config.media.directory)) for path in files]
    sequence = build_shuffle_sequence(
        playlist_inputs, rounds=channel.shuffle_rounds, rng=random.Random()
    )
    container_paths = [Path(path) for path in sequence]
    write_ffconcat(config.media.playlist_directory / f"{channel.id}.ffconcat", container_paths)


def write_compose(config: AppConfig) -> None:
    compose_path = config.root / "compose.yaml"
    compose_path.write_text(render_compose(config), encoding="utf-8")
