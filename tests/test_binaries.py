"""
Check that the pinned ffmpeg binaries match the package definitions.
"""

import json
import os

from imageio_ffmpeg._definitions import FNAME_PER_PLATFORM, WHEEL_BUILDS

MANIFEST = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "tools", "ffmpeg-sources.json"
)


def test_manifest_matches_definitions():
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    assert set(manifest) == set(FNAME_PER_PLATFORM)
    for platform, pin in manifest.items():
        assert pin["file"] == FNAME_PER_PLATFORM[platform]
        assert len(pin["sha256"]) == 64
        assert len(pin["exe_sha256"]) == 64
    assert set(WHEEL_BUILDS.values()) <= set(manifest)
