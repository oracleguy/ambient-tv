from __future__ import annotations

import random
from pathlib import Path


def build_shuffle_sequence(
    files: list[Path], *, rounds: int, rng: random.Random | None = None
) -> list[Path]:
    if rounds < 1:
        raise ValueError("rounds must be positive")
    if not files:
        raise ValueError("files must not be empty")

    randomizer = rng or random.Random()
    sequence: list[Path] = []
    for _ in range(rounds):
        round_files = list(files)
        randomizer.shuffle(round_files)
        if len(round_files) > 1 and sequence and round_files[0] == sequence[-1]:
            round_files.append(round_files.pop(0))
        sequence.extend(round_files)
    return sequence


def ffconcat_escape(path: Path) -> str:
    text = path.as_posix()
    return text.replace("\\", "\\\\").replace("'", "'\\''")


def render_ffconcat(paths: list[Path]) -> str:
    lines = ["ffconcat version 1.0", ""]
    lines.extend(f"file '{ffconcat_escape(path)}'" for path in paths)
    return "\n".join(lines) + "\n"


def write_ffconcat(path: Path, entries: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_ffconcat(entries), encoding="utf-8")
