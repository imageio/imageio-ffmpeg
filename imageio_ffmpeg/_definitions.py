import sys
import platform


__version__ = "0.6.0"


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
    machine = platform.machine()

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


# The Linux static builds (https://johnvansickle.com/ffmpeg/) are build
# for Linux kernels 3.2.0 and up (at the time of writing, ffmpeg v7.0.2).
# This corresponds to Ubuntu 12.04 / Debian 7. I'm not entirely sure'
# what manylinux matches that, but I think manylinux2014 should be safe.


# Platform string -> ffmpeg filename
FNAME_PER_PLATFORM = {
    "macos-aarch64": "ffmpeg-macos-aarch64-v7.1",
    "macos-x86_64": "ffmpeg-macos-x86_64-v7.1",  # 10.9+
    "windows-x86_64": "ffmpeg-win-x86_64-v7.1.exe",
    "windows-i686": "ffmpeg-win32-v4.2.2.exe",  # Windows 7+
    "linux-aarch64": "ffmpeg-linux-aarch64-v7.0.2",  # Kernel 3.2.0+
    "linux-x86_64": "ffmpeg-linux-x86_64-v7.0.2",
}

osxplats = "macosx_10_9_intel.macosx_10_9_x86_64"
osxarmplats = "macosx_11_0_arm64"

# Wheel tag -> platform string
WHEEL_BUILDS = {
    "py3-none-manylinux2014_x86_64": "linux-x86_64",
    "py3-none-manylinux2014_aarch64": "linux-aarch64",
    "py3-none-" + osxplats: "macos-x86_64",
    "py3-none-" + osxarmplats: "macos-aarch64",
    "py3-none-win32": "windows-i686",
    "py3-none-win_amd64": "windows-x86_64",
}
