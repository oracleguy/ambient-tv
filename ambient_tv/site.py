from __future__ import annotations

import html
import shutil
from pathlib import Path

from ambient_tv.m3u import render_m3u
from ambient_tv.models import AppConfig, Channel
from ambient_tv.urls import rtsp_url


def render_site(config: AppConfig) -> dict[str, str]:
    return {
        "index.html": render_index(config),
        "styles.css": render_css(),
        "app.js": render_js(),
        "channels.m3u": render_m3u(config),
    }


def write_site(config: AppConfig) -> None:
    output = config.site.output_directory
    output.mkdir(parents=True, exist_ok=True)
    for filename, content in render_site(config).items():
        (output / filename).write_text(content, encoding="utf-8")
    copy_poster_assets(config, output)


def render_index(config: AppConfig) -> str:
    cards = "\n".join(
        render_channel_card(config, channel) for channel in config.channels if channel.enabled
    )
    title = escape(config.site.title)
    subtitle = escape(config.site.subtitle)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-header">
    <div>
      <p class="kicker">{escape(config.server.name)}</p>
      <h1>{title}</h1>
      <p class="subtitle">{subtitle}</p>
    </div>
    <a class="playlist-link" href="channels.m3u">Download M3U</a>
  </header>
  <main class="channel-grid" aria-label="Channels">
{cards}
  </main>
  <script src="app.js"></script>
</body>
</html>
"""


def render_channel_card(config: AppConfig, channel: Channel) -> str:
    url = rtsp_url(config, channel)
    poster = ""
    if channel.poster:
        poster_path = f"assets/{html.escape(Path(channel.poster).name, quote=True)}"
        poster = f'      <img src="{poster_path}" alt="" loading="lazy">\n'
    description = channel.description or "Ambient video stream"
    return f"""    <article class="channel-card">
      <div class="poster">
{poster}      </div>
      <div class="channel-body">
        <h2>{escape(channel.name)}</h2>
        <p>{escape(description)}</p>
        <label>
          <span>RTSP URL</span>
          <input readonly value="{escape(url)}">
        </label>
        <div class="actions">
          <button type="button" data-copy="{escape(url)}">Copy URL</button>
          <a href="vlc://{escape(url)}">Open in VLC</a>
        </div>
      </div>
    </article>"""


def render_css() -> str:
    return """*:where(:not(html, iframe, canvas, img, svg, video):not(svg *, symbol *)) {
  all: unset;
  display: revert;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

:root {
  color-scheme: dark;
  --bg: #101214;
  --panel: #1a1f23;
  --panel-strong: #222930;
  --text: #f3f7f8;
  --muted: #b7c2c7;
  --line: #354048;
  --accent: #8ed3c7;
  --accent-strong: #f4c96a;
  --shadow: 0 18px 50px rgb(0 0 0 / 0.28);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

body {
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
}

a,
button {
  cursor: pointer;
}

a:focus-visible,
button:focus-visible,
input:focus-visible {
  outline: 3px solid var(--accent-strong);
  outline-offset: 3px;
}

.site-header {
  display: flex;
  gap: 1.5rem;
  align-items: end;
  justify-content: space-between;
  padding: clamp(1.25rem, 4vw, 3rem);
  border-bottom: 1px solid var(--line);
}

.kicker {
  color: var(--accent);
  font-size: 0.85rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0;
}

h1 {
  margin-top: 0.35rem;
  font-size: clamp(2rem, 7vw, 4.5rem);
  font-weight: 800;
  letter-spacing: 0;
  line-height: 0.95;
}

.subtitle {
  margin-top: 0.7rem;
  color: var(--muted);
  font-size: clamp(1rem, 2vw, 1.2rem);
}

.playlist-link,
.actions > * {
  min-height: 2.75rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--accent);
  color: #08110f;
  font-weight: 800;
  padding: 0.75rem 1rem;
  white-space: nowrap;
}

.channel-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 21rem), 1fr));
  padding: clamp(1rem, 3vw, 2rem);
}

.channel-card {
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  box-shadow: var(--shadow);
}

.poster {
  aspect-ratio: 16 / 9;
  background: var(--panel-strong);
}

.poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.channel-body {
  display: grid;
  gap: 0.9rem;
  padding: 1rem;
}

h2 {
  font-size: 1.3rem;
  font-weight: 800;
}

p {
  color: var(--muted);
  line-height: 1.5;
}

label {
  display: grid;
  gap: 0.35rem;
}

label span {
  color: var(--muted);
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
}

input {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #0c0f11;
  color: var(--text);
  padding: 0.8rem;
  font: 0.95rem ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.actions a {
  background: transparent;
  color: var(--text);
  border: 1px solid var(--line);
}

@media (max-width: 640px) {
  .site-header {
    align-items: stretch;
    flex-direction: column;
  }

  .playlist-link,
  .actions > * {
    width: 100%;
  }
}
"""


def render_js() -> str:
    return """document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const value = button.getAttribute("data-copy");
    try {
      await navigator.clipboard.writeText(value);
      const previous = button.textContent;
      button.textContent = "Copied";
      window.setTimeout(() => {
        button.textContent = previous;
      }, 1800);
    } catch {
      const input = button.closest(".channel-card").querySelector("input");
      input.focus();
      input.select();
    }
  });
});
"""


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


def escape(value: str) -> str:
    return html.escape(value, quote=True)
