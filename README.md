# Ambient TV

Ambient TV is a lightweight, self-hosted system for turning local video files into always-on ambient network streams.

It is designed for a headless Ubuntu server and intended for use with clients such as VLC on televisions, tablets, phones, and desktop computers.

The project uses:

- Docker Compose for runtime orchestration
- MediaMTX as the RTSP streaming server
- FFmpeg for looping and publishing video streams
- A Python generator for producing Docker Compose configuration, playlists, and a static website
- Apache or another existing web server for serving the generated static site

The system is intentionally generator-driven rather than managed through a runtime web application. Configuration changes are made in a local config file, then applied by rerunning the generator.

## Goals

Ambient TV should:

- Stream one or more always-on ambient video channels over the local network
- Support single-file looping channels
- Support directory-based channels containing multiple videos
- Randomize directory-based playlists across multiple rounds
- Avoid unnecessary runtime transcoding
- Generate an M3U playlist for easy use in VLC
- Generate a polished, responsive static website for browsing streams
- Publish the generated website to a configurable Apache document directory
- Keep runtime services simple, durable, and easy to inspect
- Be easy to back up, version, and recreate from Git

## Non-goals

The first version does not need:

- A runtime administrative web application
- Authentication or user accounts
- Hot reloading when media directories change
- Direct manipulation of Docker from a web application
- Live upload or deletion of video files through the browser
- Automatic discovery through DLNA or SAP

Automatic discovery may be considered later. For the first version, users can open the generated M3U playlist or manually add RTSP URLs in VLC.

## High-level architecture

```text
config.toml
    |
    v
generate.py
    |
    +--> compose.yaml
    +--> generated site files
    +--> channels.m3u
    +--> ffconcat playlists
    +--> normalized media cache

Docker Compose
    |
    +--> MediaMTX
    +--> one FFmpeg container per channel

Apache
    |
    +--> generated static website
    +--> channels.m3u

VLC clients
    |
    +--> rtsp://server:8554/<channel-id>
```

## Channel modes

### Single-file mode

A single video file is streamed continuously on a loop.

Example:

```toml
[[channels]]
id = "ocean"
name = "Ocean"
file = "ocean.mp4"
description = "Rolling waves and coastal ambience"
poster = "posters/ocean.jpg"
```

The generated FFmpeg command should resemble:

```bash
ffmpeg \
  -re \
  -stream_loop -1 \
  -i /media/ocean.mp4 \
  -c copy \
  -f rtsp \
  rtsp://mediamtx:8554/ocean
```

### Directory mode

A channel may reference a directory containing multiple video files.

Example:

```toml
[[channels]]
id = "city"
name = "Night City"
directory = "city"
shuffle_rounds = 6
description = "Rainy streets, traffic, and skyline views"
poster = "posters/city.jpg"
```

The generator should:

1. Scan the configured directory for supported video files.
2. Probe each file with `ffprobe`.
3. Normalize or remux files when necessary.
4. Generate several independently shuffled rounds.
5. Prevent the same file from appearing at the boundary between two rounds when possible.
6. Write an FFmpeg concat playlist.
7. Run one persistent FFmpeg process using stream copy.

With 10 to 15 hours of source material and six shuffled rounds, the full generated sequence will run for approximately 60 to 90 hours before repeating.

## Media normalization

Directory-based channels may contain files with different codecs, resolutions, frame rates, audio formats, or timestamp behavior.

To keep runtime CPU and energy use low, media should be normalized once and cached rather than transcoded continuously.

The normalization cache should:

- Store one normalized output per source file
- Reuse cached files when the source and normalization settings have not changed
- Reprocess files when the source changes
- Remove stale cached outputs when source files are removed
- Avoid transcoding when a file is already compatible
- Remux when only the container or timestamps need adjustment
- Transcode only when required

A reasonable default target profile is:

- H.264 video
- AAC audio
- 1920x1080 maximum output resolution, preserving aspect ratio
- 30 fps
- 48 kHz stereo audio
- `yuv420p` pixel format

Exact defaults may evolve during implementation, but all normalized files used in a concat playlist must have compatible stream layouts.

## Suggested repository layout

```text
ambient-tv/
├── README.md
├── AGENTS.md
├── config.toml
├── generate.py
├── Makefile
├── compose.yaml                 # generated
├── media/
│   ├── ocean.mp4
│   └── city/
│       ├── rainy-street.mp4
│       ├── skyline.mp4
│       └── traffic.mp4
├── assets/
│   ├── logo.svg
│   ├── favicon.png
│   └── posters/
│       ├── ocean.jpg
│       └── city.jpg
├── templates/
│   ├── compose.yaml.j2
│   ├── index.html.j2
│   ├── styles.css.j2
│   ├── app.js.j2
│   └── channels.m3u.j2
└── generated/
    ├── site/
    │   ├── index.html
    │   ├── styles.css
    │   ├── app.js
    │   ├── channels.m3u
    │   └── assets/
    ├── playlists/
    │   └── city.ffconcat
    └── cache/
        └── city/
```

Generated files may be excluded from Git if they can be reproduced safely. The config, source code, templates, and documentation should remain versioned.

## Configuration design

A suggested initial configuration:

```toml
[server]
name = "Ambient TV"

[network]
stream_host = "ambient-tv.local"
rtsp_port = 8554

[site]
title = "Ambient TV"
subtitle = "Always-on ambient channels"
base_url = "http://ambient-tv.local/ambient"
publish_directory = "/var/www/html/ambient"
theme = "dark"

[media]
directory = "./media"
cache_directory = "./generated/cache"
playlist_directory = "./generated/playlists"

[[channels]]
id = "ocean"
name = "Ocean"
file = "ocean.mp4"
description = "Rolling waves and coastal ambience"
poster = "posters/ocean.jpg"

[[channels]]
id = "city"
name = "Night City"
directory = "city"
shuffle_rounds = 6
description = "Rainy streets, traffic, and skyline views"
poster = "posters/city.jpg"
```

Rules:

- `file` and `directory` are mutually exclusive.
- Every channel must specify exactly one of them.
- Channel IDs must be URL-safe and unique.
- `shuffle_rounds` applies only to directory channels.
- Disabled channels may be supported later through an optional `enabled` field.
- Paths should be resolved relative to the repository root unless explicitly documented otherwise.

## Generated Docker Compose configuration

The generator should produce:

- One MediaMTX service
- One FFmpeg service per channel
- Shared service configuration through YAML extension fields and anchors where useful
- Read-only media and generated playlist mounts
- `restart: unless-stopped`
- Explicit dependency on MediaMTX
- No unnecessary published ports besides the RTSP port

An existing Apache server will serve the static website, so the Compose stack does not need an Nginx or Caddy container.

The generated Compose file should be validated with:

```bash
docker compose config --quiet
```

## Static website

The generated website should feel like a modern media application rather than an infrastructure status page.

Requirements:

- Responsive layout for phones, tablets, and desktops
- Mobile-first design
- Crisp typography and spacing
- Dark theme by default
- Strong contrast and accessible controls
- Channel cards with poster images
- Channel name and description
- Copyable RTSP URL
- “Open in VLC” action where supported
- Global M3U playlist link
- Large touch targets
- Graceful behavior when custom `vlc://` URLs are unsupported
- Minimal JavaScript
- No runtime framework or backend dependency

The generated site should be written to a temporary or staging directory first, then synchronized to the configured publish directory only after successful generation.

Recommended publishing approach:

```bash
rsync -a --delete generated/site/ /var/www/html/ambient/
```

The generator should not partially overwrite the live site if an earlier generation step fails.

## Generated M3U playlist

The site should publish a playlist containing all enabled channels.

Example:

```m3u
#EXTM3U

#EXTINF:-1,Ocean
rtsp://ambient-tv.local:8554/ocean

#EXTINF:-1,Night City
rtsp://ambient-tv.local:8554/city
```

The playlist URL should be visible prominently on the static site.

## Expected workflow

After editing `config.toml` or changing media files:

```bash
python3 generate.py
docker compose config --quiet
docker compose up -d --remove-orphans
```

A Makefile may wrap these commands:

```makefile
apply:
	python3 generate.py
	docker compose config --quiet
	docker compose up -d --remove-orphans

stop:
	docker compose down

logs:
	docker compose logs -f
```

## Validation and safety

The generator should fail clearly before modifying the live site or Compose output when:

- Required configuration sections are missing
- A channel has both `file` and `directory`
- A channel has neither `file` nor `directory`
- Channel IDs are duplicated or unsafe
- A source file or directory does not exist
- A directory contains no supported videos
- `ffprobe`, `ffmpeg`, Docker, or required Python dependencies are unavailable
- The configured publish directory is unsafe or not writable
- Media normalization fails
- Generated Compose configuration is invalid

Avoid destructive operations outside explicitly configured generated, cache, and publish directories.

## Future ideas

Possible later enhancements include:

- SAP announcements for VLC network discovery
- DLNA integration
- QR codes for stream and playlist URLs
- Optional channel enable/disable flags
- Per-channel normalization profiles
- Hardware-accelerated transcoding
- Better health reporting
- Stream thumbnails or previews
- A generated JSON channel catalog

These are intentionally outside the initial implementation unless they emerge naturally from the core design.
