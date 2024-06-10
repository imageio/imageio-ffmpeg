import platform
import struct

__version__ = "0.5.0"


def get_platform():
    bits = struct.calcsize("P") * 8
    if platform.system().lower().startswith("linux"):
        architecture = platform.machine()
        if architecture == "aarch64":
            return "linuxaarch64"
        return "linux{}".format(bits)
    elif platform.system().lower().startswith("freebsd"):
        return "freebsd{}".format(bits)
    elif platform.system().lower().startswith("win"):
        return "win{}".format(bits)
    elif platform.system().lower().startswith("cygwin"):
        return "win{}".format(bits)
    elif platform.system().lower().startswith("darwin"):
        if platform.processor().lower().startswith("arm"):  # Apple Silicon
            return "osx-arm{}".format(bits)
        else:
            return "osx-{}".format(bits)
    else:  # pragma: no cover
        return None


# The Linux static builds (https://johnvansickle.com/ffmpeg/) are build
# for Linux kernels 2.6.32 and up (at the time of writing, ffmpeg v4.1).
# This corresponds to CentOS 6. This means we should use manylinux2010 and not
# manylinux1.
# manylinux1: https://www.python.org/dev/peps/pep-0513
# manylinux2010: https://www.python.org/dev/peps/pep-0571


# Platform string -> ffmpeg filename
FNAME_PER_PLATFORM = {
    "osx-arm64": "ffmpeg-osx-arm64-v7.0", # Apple Silicon
    "osx64": "ffmpeg-osx-x86-v7.0",  # 10.9+
    "win32": "ffmpeg-win32-v4.2.2.exe",  # Windows 7+
    "win64": "ffmpeg-win64-v4.2.2.exe",
    # "linux32": "ffmpeg-linux32-v4.2.2",
    "linux64": "ffmpeg-linux64-v4.2.2",  # Kernel 3.2.0+
    "linuxaarch64": "ffmpeg-linuxaarch64-v4.2.2",
}

osxplats = "macosx_10_9_intel.macosx_10_9_x86_64"
osxarmplats = "macosx_11_0_arm64"

# Wheel tag -> platform string
WHEEL_BUILDS = {
    "py3-none-manylinux2010_x86_64": "linux64",
    "py3-none-manylinux2014_aarch64": "linuxaarch64",
    "py3-none-" + osxplats: "osx64",  # Apple Intel
    "py3-none-" + osxarmplats: "osx-arm64",  # Apple Silicon
    "py3-none-win32": "win32",
    "py3-none-win_amd64": "win64",
}
