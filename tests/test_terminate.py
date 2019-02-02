"""
Tests specifically for ensuring that we dont have daemon ffmpeg processes.
"""

import os
import gc
import psutil
import tempfile
from urllib.request import urlopen

import imageio_ffmpeg

test_dir = tempfile.gettempdir()
test_url = "https://raw.githubusercontent.com/imageio/imageio-binaries/master/images/cockatoo.mp4"
test_file1 = os.path.join(test_dir, "cockatoo.mp4")
test_file2 = os.path.join(test_dir, "test.mp4")

N = 2  # number of times to perform each test


def get_ffmpeg_pids():
    pids = set()
    for p in psutil.process_iter():
        if "ffmpeg" in p.name().lower():
            pids.add(p.pid)
    return pids


def setup_module():
    bb = urlopen(test_url, timeout=5).read()
    with open(test_file1, "wb") as f:
        f.write(bb)


def test_reader_close():

    for i in range(N):
        pids0 = get_ffmpeg_pids()
        r = imageio_ffmpeg.read_frames(test_file1)
        pids1 = get_ffmpeg_pids().difference(pids0)  # generator has not started
        r.__next__()  # == meta
        pids2 = get_ffmpeg_pids().difference(pids0)  # now ffmpeg is running
        r.close()
        pids3 = get_ffmpeg_pids().difference(pids0)  # now its not

        assert len(pids1) == 0
        assert len(pids2) == 1
        assert len(pids3) == 0


def test_reader_del():

    for i in range(N):
        pids0 = get_ffmpeg_pids()
        r = imageio_ffmpeg.read_frames(test_file1)
        pids1 = get_ffmpeg_pids().difference(pids0)  # generator has not started
        r.__next__()  # == meta
        pids2 = get_ffmpeg_pids().difference(pids0)  # now ffmpeg is running
        del r
        gc.collect()
        pids3 = get_ffmpeg_pids().difference(pids0)  # now its not

        assert len(pids1) == 0
        assert len(pids2) == 1
        assert len(pids3) == 0


def test_write_close():

    for i in range(N):
        pids0 = get_ffmpeg_pids()
        w = imageio_ffmpeg.write_frames(test_file2, (64, 64))
        pids1 = get_ffmpeg_pids().difference(pids0)  # generator has not started
        w.send(None)
        w.send(b"x" * 64 * 64 * 3)
        pids2 = get_ffmpeg_pids().difference(pids0)  # now ffmpeg is running
        w.close()
        pids3 = get_ffmpeg_pids().difference(pids0)  # now its not

        assert len(pids1) == 0
        assert len(pids2) == 1
        assert len(pids3) == 0


def test_write_del():

    for i in range(N):
        pids0 = get_ffmpeg_pids()
        w = imageio_ffmpeg.write_frames(test_file2, (64, 64))
        pids1 = get_ffmpeg_pids().difference(pids0)  # generator has not started
        w.send(None)
        w.send(b"x" * 64 * 64 * 3)
        pids2 = get_ffmpeg_pids().difference(pids0)  # now ffmpeg is running
        del w
        gc.collect()
        pids3 = get_ffmpeg_pids().difference(pids0)  # now its not

        assert len(pids1) == 0
        assert len(pids2) == 1
        assert len(pids3) == 0


if __name__ == "__main__":
    setup_module()
    test_reader_close()
    test_reader_del()
    test_write_close()
    test_write_del()
