from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ambient_tv.m3u import render_m3u
from ambient_tv.models import AppConfig, Channel
from ambient_tv.urls import rtsp_url

SITE_TEMPLATE_DIR = "templates/site"
STATIC_SITE_FILES = ("styles.css", "app.js", ".htaccess")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SiteChannel:
    id: str
    name: str
    description: str
    rtsp_url: str
    vlc_url: str
    poster_path: str | None


def render_site(config: AppConfig) -> dict[str, str]:
    return {
        "index.html": render_index(config),
        "channels.m3u": render_m3u(config),
    }


def write_site(config: AppConfig) -> None:
    output = config.site.output_directory
    output.mkdir(parents=True, exist_ok=True)
    for filename, content in render_site(config).items():
        (output / filename).write_text(content, encoding="utf-8")
    copy_static_site_assets(config, output)
    copy_poster_assets(config, output)


def render_index(config: AppConfig) -> str:
    template = template_environment(config).get_template("index.html.j2")
    return template.render(
        page_title=config.site.title,
        site=config.site,
        server=config.server,
        channels=[site_channel(config, channel) for channel in enabled_channels(config)],
    )


def template_environment(config: AppConfig) -> Environment:
    return Environment(
        loader=FileSystemLoader(template_search_paths(config)),
        autoescape=select_autoescape(("html", "xml", "j2")),
        keep_trailing_newline=True,
    )


def template_search_paths(config: AppConfig) -> list[Path]:
    paths = [config.root / SITE_TEMPLATE_DIR]
    bundled_templates = PROJECT_ROOT / SITE_TEMPLATE_DIR
    if bundled_templates not in paths:
        paths.append(bundled_templates)
    return paths


def enabled_channels(config: AppConfig) -> tuple[Channel, ...]:
    return tuple(channel for channel in config.channels if channel.enabled)


def site_channel(config: AppConfig, channel: Channel) -> SiteChannel:
    url = rtsp_url(config, channel)
    poster_path = f"assets/{Path(channel.poster).name}" if channel.poster else None
    return SiteChannel(
        id=channel.id,
        name=channel.name,
        description=channel.description or "Ambient video stream",
        rtsp_url=url,
        vlc_url=f"vlc://{url}",
        poster_path=poster_path,
    )


def copy_static_site_assets(config: AppConfig, output: Path) -> None:
    for filename in STATIC_SITE_FILES:
        shutil.copy2(template_asset_path(config, filename), output / filename)


def template_asset_path(config: AppConfig, filename: str) -> Path:
    for path in template_search_paths(config):
        candidate = path / filename
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Site template asset does not exist: {filename}")


def copy_poster_assets(config: AppConfig, output: Path) -> None:
    assets = output / "assets"
    for channel in config.channels:
        if not channel.poster:
            continue
        source = (config.media.directory / channel.poster).resolve()
        if not source.exists():
            continue
        assets.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, assets / source.name)
