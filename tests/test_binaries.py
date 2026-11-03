"""
Check that the pinned ffmpeg binaries match the package definitions.
"""

import json
import os

import pytest

from imageio_ffmpeg import _definitions
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


@pytest.mark.parametrize(
    "interpreter_platform, expected",
    [
        ("win-amd64", "windows-x86_64"),
        ("win-arm64", "windows-aarch64"),
        ("win32", "windows-i686"),
    ],
)
def test_windows_platform_follows_interpreter(
    monkeypatch, interpreter_platform, expected
):
    # The host machine is ARM64, but e.g. x64 Python runs under emulation and
    # gets the win_amd64 wheel, which only contains the x86_64 binary.
    monkeypatch.setattr(_definitions.sys, "platform", "win32")
    monkeypatch.setattr(_definitions.platform, "machine", lambda: "ARM64")
    monkeypatch.setattr(
        _definitions.sysconfig, "get_platform", lambda: interpreter_platform
    )
    assert _definitions.get_platform() == expected
