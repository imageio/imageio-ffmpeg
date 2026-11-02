import sys
import platform

__version__ = "0.7.0"


def get_platform():
    # get_os_string and get_arch are taken from wgpu-py
    return _get_os_string() + "-" + _get_arch()


def _get_os_string():
    if sys.platform.startswith("win"):
        return "windows"
    elif sys.platform.startswith("darwin"):
        return "macos"
    elif sys.platform.startswith("linux"):
        return "linux"
    else:
        return sys.platform


def _get_arch():
    # See e.g.: https://stackoverflow.com/questions/45124888
    is_64_bit = sys.maxsize > 2**32
    machine = platform.machine().lower()  # e.g. "ARM64" on Windows

    if machine == "armv7l":
        # Raspberry pi
        detected_arch = "armv7"
    elif is_64_bit and machine.startswith(("arm", "aarch64")):
        # Includes MacOS M1, arm linux, ...
        detected_arch = "aarch64"
    elif is_64_bit:
        detected_arch = "x86_64"
    else:
        detected_arch = "i686"
    return detected_arch


# The binaries are downloaded from the sources pinned in
# tools/ffmpeg-sources.json (see tools/download_ffmpeg.py, which also updates
# the file names below). The wheel tags must match the requirements of the
# binaries, which `invoke check-binaries` verifies:
# * Linux (BtbN): glibc 2.28+ (manylinux_2_28), kernel 4.18+.
# * macOS x86_64 (evermeet.cx): macOS 10.13+; aarch64 (osxexperts): 12.0+.


# Platform string -> ffmpeg filename
FNAME_PER_PLATFORM = {
    "macos-aarch64": "ffmpeg-macos-aarch64-v9.0",
    "macos-x86_64": "ffmpeg-macos-x86_64-v9.0.2",
    "windows-x86_64": "ffmpeg-win-x86_64-v9.0.2.exe",
    "windows-aarch64": "ffmpeg-win-aarch64-v9.0.1.exe",
    "windows-i686": "ffmpeg-win32-v4.2.2.exe",  # Windows 7+
    "linux-aarch64": "ffmpeg-linux-aarch64-v9.0.2",
    "linux-x86_64": "ffmpeg-linux-x86_64-v9.0.2",
}

# Wheel tag -> platform string
WHEEL_BUILDS = {
    "py3-none-manylinux_2_28_x86_64": "linux-x86_64",
    "py3-none-manylinux_2_28_aarch64": "linux-aarch64",
    "py3-none-macosx_10_13_x86_64": "macos-x86_64",
    "py3-none-macosx_12_0_arm64": "macos-aarch64",
    "py3-none-win32": "windows-i686",
    "py3-none-win_amd64": "windows-x86_64",
    "py3-none-win_arm64": "windows-aarch64",
}
