from __future__ import annotations

from ambient_tv.models import AppConfig, Channel


def rtsp_url(config: AppConfig, channel: Channel, *, host: str | None = None) -> str:
    stream_host = host or config.network.stream_host
    return f"rtsp://{stream_host}:{config.network.rtsp_port}/{channel.id}"
