import logging.handlers
import os
import time
import tempfile
from urllib.request import urlopen

import psutil

import imageio_ffmpeg

test_dir = tempfile.gettempdir()
test_url1 = "https://raw.githubusercontent.com/imageio/imageio-binaries/master/images/cockatoo.mp4"
test_url2 = "https://raw.githubusercontent.com/imageio/imageio-binaries/master/images/realshort.mp4"
test_file1 = os.path.join(test_dir, "cockatoo.mp4")
test_file2 = os.path.join(test_dir, "test.mp4")
test_file3 = os.path.join(test_dir, "realshort.mp4")
have_downloaded = False


def ensure_test_files():
    global have_downloaded
    if not have_downloaded:
        bb = urlopen(test_url1, timeout=5).read()
        with open(test_file1, "wb") as f:
            f.write(bb)
        bb = urlopen(test_url2, timeout=5).read()
        with open(test_file3, "wb") as f:
            f.write(bb)
        have_downloaded = True


class OurMemoryHandler(logging.handlers.MemoryHandler):
    pass


def no_warnings_allowed(f):
    logger = imageio_ffmpeg._utils.logger

    def wrapper():
        handler = OurMemoryHandler(99, logging.WARNING)
        logger.addHandler(handler)
        f()
        logger.removeHandler(handler)
        assert not handler.buffer

    wrapper.__name__ = f.__name__
    return wrapper


def get_ffmpeg_pids():
    time.sleep(0.01)
    pids = set()
    for p in psutil.process_iter():
        try:
            if "ffmpeg" in p.name().lower():
                pids.add(p.pid)
        except psutil.NoSuchProcess:
            pass
    return pids
