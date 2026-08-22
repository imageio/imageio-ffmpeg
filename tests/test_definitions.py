import struct
import sys

import pytest

import imageio_ffmpeg
from imageio_ffmpeg import _definitions


@pytest.mark.parametrize("machine", ["ARM64", "arm64", "aarch64", "AARCH64"])
def test_get_arch_normalizes_aarch64(monkeypatch, machine):
    monkeypatch.setattr(_definitions.platform, "machine", lambda: machine)

    assert _definitions._get_arch() == "aarch64"


def test_windows_arm64_mappings():
    platform = "windows-aarch64"

    assert _definitions.FNAME_PER_PLATFORM[platform].endswith(".exe")
    assert _definitions.WHEEL_BUILDS["py3-none-win_arm64"] == platform


@pytest.mark.skipif(
    sys.platform != "win32" or _definitions._get_arch() != "aarch64",
    reason="requires native Windows ARM64",
)
def test_bundled_executable_is_arm64():
    try:
        executable = imageio_ffmpeg.get_ffmpeg_exe()
    except RuntimeError:
        pytest.skip("no bundled executable in the source tree")

    with open(executable, "rb") as file:
        assert file.read(2) == b"MZ"
        file.seek(0x3C)
        pe_offset = struct.unpack("<I", file.read(4))[0]
        file.seek(pe_offset)
        assert file.read(4) == b"PE\0\0"
        machine = struct.unpack("<H", file.read(2))[0]

    assert machine == 0xAA64
