# AGENTS.md

## Project purpose

Build a generator-driven ambient video streaming system for a headless Ubuntu server.

The repository should produce:

- A Docker Compose file
- One MediaMTX service
- One FFmpeg publisher service per channel
- FFmpeg concat playlists for directory-based channels
- A normalized media cache where required
- A responsive static website
- An M3U playlist
- Published static files in a configurable Apache document directory

Read `README.md` before making architectural changes.

## Core design constraints

1. The runtime should remain simple.
2. Do not build a long-running administrative web application.
3. Do not give the static site permission to alter Docker, configuration, or host files.
4. Configuration changes are applied by rerunning the generator.
5. Media directories do not require hot reload.
6. Prefer one persistent FFmpeg publisher per channel.
7. Avoid restarting FFmpeg between individual files in a directory channel.
8. Avoid continuous transcoding when normalization can be performed once.
9. Do not combine an entire directory into one monolithic generated video.
10. Keep all generated outputs reproducible from source configuration and media.

## Preferred implementation language

Use Python 3.11 or newer.

Prefer the standard library when practical. `tomllib` should be used for reading TOML configuration.

Third-party dependencies are acceptable when they clearly improve maintainability. Good candidates include:

- Jinja2 for templates
- PyYAML or ruamel.yaml for YAML generation, if templates are not used
- pytest for tests

Keep the dependency set small and document it.

## Source configuration

Use `config.toml` as the human-edited source of truth.

Expected sections:

- `[server]`
- `[network]`
- `[site]`
- `[media]`
- one or more `[[channels]]`

A channel must contain exactly one of:

- `file`
- `directory`

Example:

```toml
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

Validation requirements:

- Channel IDs must be unique.
- Channel IDs must be URL-safe.
- Channel IDs should match `^[a-z0-9][a-z0-9-]*$` unless there is a strong reason to broaden this.
- `file` and `directory` are mutually exclusive.
- Source paths must exist.
- Directory channels must contain at least one supported video.
- `shuffle_rounds` must be a positive integer.
- All configured output directories must resolve safely.

## Supported media

Start with common video extensions:

- `.mp4`
- `.mkv`
- `.mov`
- `.webm`
- `.m4v`

Extension checks are only a first filter. Use `ffprobe` to determine whether files are valid and usable.

## Directory channel behavior

For each directory-based channel:

1. Enumerate supported files deterministically before shuffling.
2. Probe each file.
3. Determine whether it can be used directly, remuxed, or must be transcoded.
4. Store normalized files individually in a cache.
5. Generate the configured number of shuffled rounds.
6. Prevent the first file of a round from matching the final file of the prior round when there is more than one source file.
7. Write one `.ffconcat` playlist.
8. Configure one persistent FFmpeg publisher to loop the complete generated playlist.

A directory with only one file is valid. In that case, boundary repetition is unavoidable and should not be treated as an error.

Shuffle behavior does not need to change at runtime. Regenerating the project may produce a new order.

The generator may support an optional shuffle seed later, but it is not required initially.

## Normalization strategy

The objective is low runtime CPU use.

Use this decision order:

1. Use the original file directly when it already matches the required stream profile and is safe for concat playback.
2. Remux without re-encoding when codecs and stream properties are compatible but the container or timestamps are unsuitable.
3. Transcode once when stream properties are incompatible.

Do not transcode continuously in the running channel container unless there is no practical alternative.

Recommended default normalized profile:

- H.264 video
- AAC audio
- `yuv420p`
- no more than 1920x1080
- preserved aspect ratio
- 30 fps
- 48 kHz stereo audio

Treat this profile as an implementation default, not an immutable contract. Keep it centralized in code or configuration.

Cache invalidation should account for:

- Source path
- Source file size
- Source modification time
- Relevant normalization settings
- Generator cache version

A sidecar metadata file or manifest is acceptable.

Never overwrite source media.

## FFmpeg and FFprobe execution

Use `subprocess.run` or `subprocess.Popen` without `shell=True`.

Requirements:

- Pass arguments as arrays.
- Capture stderr for actionable errors.
- Use explicit timeouts for probing operations.
- Include the source path in error messages.
- Avoid exposing secrets or unrelated environment variables in logs.
- Make command construction testable independently from command execution.

Generated FFmpeg services should use one persistent publisher per channel.

Single-file channels should use the equivalent of:

```text
-re -stream_loop -1 -i <file> -c copy -f rtsp rtsp://mediamtx:8554/<id>
```

Directory channels should use the concat demuxer, loop the complete generated playlist, and use stream copy.

Use RTSP over TCP for publishing if that proves more reliable in the container network.

## Docker Compose generation

Generate `compose.yaml` from templates or structured data.

Expected services:

- `mediamtx`
- one channel service per configured channel

Use stable, readable service names such as:

```text
channel-ocean
channel-city
```

Use shared YAML extension fields and anchors when they improve readability, but do not make the generated output obscure.

Channel services should:

- use a maintained FFmpeg image
- use `restart: unless-stopped`
- depend on MediaMTX
- mount media read-only
- mount generated playlists and cache read-only
- publish to MediaMTX by service name over the Compose network
- avoid host networking unless there is a demonstrated need

MediaMTX should publish only the ports required by clients, initially RTSP port 8554.

Do not include a web server container. Apache already exists on the host.

After generation, validate Compose with:

```bash
docker compose config --quiet
```

The generator may invoke validation directly or leave it to `make apply`, but validation must be part of the documented workflow.

## Static site

Generate a polished, modern, responsive static website.

Design requirements:

- Mobile-first
- Responsive card grid
- One column on small phones
- Multiple columns on wider screens
- Dark theme by default
- High contrast
- Visible focus states
- Keyboard accessible controls
- Semantic HTML
- Large touch targets
- Minimal JavaScript
- No frontend framework unless clearly justified
- No external CDN dependency required for core functionality

Each channel card should include:

- Poster image when configured
- Channel name
- Description
- RTSP URL
- Copy URL action
- Open in VLC action where supported

The page should also include a prominent link to the generated M3U playlist.

Do not rely solely on the `vlc://` protocol. It may not work on every client. The RTSP URL and M3U link must always be available.

Prefer system fonts or locally stored assets. Do not require Google Fonts or other third-party services.

## Static site publishing

The site output directory and live Apache publish directory are separate concepts.

Recommended flow:

1. Render the complete site into a staging directory.
2. Verify all expected files exist.
3. Synchronize the staging directory into `site.publish_directory`.
4. Use delete semantics so removed generated files are cleaned up.

An `rsync -a --delete` style operation is preferred.

Publishing must not occur if generation or validation fails.

Safety requirements:

- Refuse obviously unsafe publish paths such as `/`, `/var`, `/var/www`, or the repository root.
- Resolve paths before comparing them.
- Only delete files inside the configured publish directory.
- Consider requiring a marker file in the publish directory before allowing delete synchronization.
- Never delete outside generated, cache, staging, or explicitly configured publish directories.

If permission is denied, fail with a clear message rather than attempting privilege escalation.

Do not invoke `sudo` from Python.

## M3U generation

Generate `channels.m3u` for all enabled channels.

Use the configured public stream host and RTSP port.

Example:

```m3u
#EXTM3U

#EXTINF:-1,Ocean
rtsp://ambient-tv.local:8554/ocean
```

Keep ordering consistent with the channel order in `config.toml`.

## Templates

Prefer separate templates under `templates/` for:

- Compose YAML
- HTML
- CSS
- JavaScript
- M3U

Generated output should not contain development-only comments or template artifacts.

Keep generated files readable enough for troubleshooting.

## Command-line interface

A reasonable initial interface:

```bash
python3 generate.py
```

Optional flags may include:

```text
--config PATH
--no-publish
--no-normalize
--check
--verbose
```

`--check` should validate configuration and planned outputs without modifying files.

Do not add flags until they have clear behavior and tests.

## Logging and errors

Use clear, concise console output.

Suggested stages:

```text
Loading configuration
Validating channels
Probing media
Normalizing media
Generating playlists
Generating Compose configuration
Generating static site
Publishing static site
Complete
```

Errors should state:

- What failed
- Which channel or file was involved
- The relevant external command output
- What the user can do next

Avoid full Python tracebacks for expected user errors. Preserve tracebacks for unexpected failures when verbose mode is enabled.

## Testing expectations

Use pytest.

At minimum, test:

- TOML parsing
- Required section validation
- Mutual exclusivity of `file` and `directory`
- Duplicate and invalid channel IDs
- Directory scanning
- Supported extension filtering
- Shuffle round generation
- Boundary duplicate avoidance
- Single-file directory behavior
- FFconcat escaping
- M3U generation
- Compose service generation
- URL construction
- Safe publish path checks
- Cache fingerprint generation
- No-op reuse of valid cached outputs

External commands should be wrapped so tests can mock them.

Include at least one integration-style fixture with temporary directories and fake media metadata.

## Code quality

- Use type hints throughout.
- Prefer dataclasses for validated configuration models.
- Keep parsing, validation, probing, normalization, rendering, and publishing in separate modules or clearly separated functions.
- Avoid a single monolithic `generate.py` once implementation grows.
- Use `pathlib.Path` for filesystem operations.
- Format with Ruff or Black.
- Lint with Ruff.
- Keep functions small and testable.
- Document non-obvious FFmpeg behavior.

A likely package structure:

```text
ambient_tv/
├── __init__.py
├── cli.py
├── config.py
├── models.py
├── media.py
├── normalize.py
├── playlists.py
├── compose.py
├── site.py
└── publish.py
```

A thin root-level `generate.py` may call the package CLI.

## Git hygiene

Do not commit source media unless intentionally desired.

The default `.gitignore` should probably exclude:

```text
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
generated/cache/
generated/playlists/
generated/site/
compose.yaml
```

Whether to ignore `compose.yaml` and generated site files should be documented. Prefer ignoring them when they are fully reproducible.

Do not ignore templates, config examples, source code, or documentation.

Provide a `config.example.toml`. Avoid committing host-specific `config.toml` values if they expose private hostnames or filesystem layouts.

## Security posture

This is intended for a trusted home network, but apply reasonable defaults:

- Do not mount the Docker socket.
- Do not run containers as privileged.
- Do not expose unnecessary ports.
- Use read-only mounts where possible.
- Do not execute values from TOML through a shell.
- Do not accept arbitrary template paths from untrusted config.
- Do not allow channel IDs to become filesystem traversal paths.
- Do not allow generated output paths to escape configured roots.
- Do not add a runtime control API in the first version.

## Scope discipline

Implement the smallest complete version first:

1. Parse and validate config.
2. Support one single-file channel.
3. Generate Compose, M3U, and static site.
4. Add directory channels and shuffled concat playlists.
5. Add probing and normalization cache.
6. Add safe Apache publishing.
7. Add tests and polish.

Do not prematurely add:

- User accounts
- Database storage
- Docker socket access
- Runtime file watchers
- Live media uploads
- DLNA
- SAP announcements
- Hardware transcoding
- Complex frontend frameworks

Those can be considered only after the core workflow is working reliably.

## Definition of done for v1

Version 1 is complete when a user can:

1. Clone the repository on Ubuntu.
2. Create `config.toml` from an example.
3. Add a single video channel and a directory channel.
4. Run the generator.
5. Start the stack with Docker Compose.
6. Open the generated M3U playlist in VLC.
7. Browse the responsive static site from a phone or desktop.
8. Play each generated RTSP stream.
9. Regenerate after adding or removing media.
10. Observe low steady-state CPU use when streams are using normalized cached media and stream copy.
