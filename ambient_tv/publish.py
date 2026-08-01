from __future__ import annotations

import shutil
from pathlib import Path

from ambient_tv.errors import PublishError

UNSAFE_PUBLISH_PATHS = {Path("/"), Path("/var"), Path("/var/www")}


def assert_safe_publish_directory(path: Path, *, repo_root: Path) -> None:
    resolved = path.resolve()
    if resolved in UNSAFE_PUBLISH_PATHS:
        raise PublishError(f"Refusing unsafe publish directory: {resolved}")
    if resolved == repo_root.resolve():
        raise PublishError("Refusing to publish into the repository root")
    if resolved.is_relative_to(repo_root.resolve()):
        raise PublishError(f"Refusing to publish into the repository tree: {resolved}")


def publish_site(staging: Path, destination: Path, *, repo_root: Path) -> None:
    assert_safe_publish_directory(destination, repo_root=repo_root)
    if not staging.exists():
        raise PublishError(f"Site staging directory does not exist: {staging}")
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / ".ambient-tv-generated"
    if any(destination.iterdir()) and not marker.exists():
        raise PublishError(
            f"Publish directory is not marked as generated: {destination}. "
            "Create .ambient-tv-generated there once if this target is intentional."
        )
    marker.touch()
    for item in destination.iterdir():
        if item.name == marker.name:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    for item in staging.iterdir():
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
