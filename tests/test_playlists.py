from __future__ import annotations

import random
from pathlib import Path

from ambient_tv.playlists import build_shuffle_sequence, render_ffconcat


def test_shuffle_sequence_avoids_round_boundary_duplicates() -> None:
    files = [Path("/media/a.mp4"), Path("/media/b.mp4"), Path("/media/c.mp4")]
    sequence = build_shuffle_sequence(files, rounds=8, rng=random.Random(4))

    assert len(sequence) == 24
    for index in range(3, len(sequence), 3):
        assert sequence[index] != sequence[index - 1]


def test_single_file_directory_sequence_allows_repetition() -> None:
    files = [Path("/media/a.mp4")]

    assert build_shuffle_sequence(files, rounds=3, rng=random.Random(1)) == files * 3


def test_render_ffconcat_escapes_single_quotes() -> None:
    rendered = render_ffconcat([Path("/media/bob's/video.mp4")])

    assert rendered == "ffconcat version 1.0\n\nfile '/media/bob'\\''s/video.mp4'\n"
