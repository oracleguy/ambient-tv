from __future__ import annotations

from ambient_tv.models import AppConfig
from ambient_tv.urls import rtsp_url


def render_m3u(config: AppConfig) -> str:
    lines = ["#EXTM3U", ""]
    for channel in config.channels:
        if not channel.enabled:
            continue
        lines.append(f"#EXTINF:-1,{channel.name}")
        lines.append(rtsp_url(config, channel))
        lines.append("")
    return "\n".join(lines)
