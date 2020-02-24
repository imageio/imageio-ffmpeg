"""
Tests specifically for ensuring that we dont have daemon ffmpeg processes.
We should also run this test as a script, so we can confirm that ffmpeg
quits nicely (instead of being killed).
"""

import gc

import imageio_ffmpeg

from testutils import no_warnings_allowed, get_ffmpeg_pids
from testutils import ensure_test_files, test_file1, test_file2


N = 2  # number of times to perform each test


def setup_module():
    ensure_test_files()


@no_warnings_allowed
def test_ffmpeg_version():
    version = imageio_ffmpeg.get_ffmpeg_version()
    print("ffmpeg version", version)
    assert version > "3.0"


@no_warnings_allowed
def test_reader_done():

    for i in range(N):
        pids0 = get_ffmpeg_pids()
        r = imageio_ffmpeg.read_frames(test_file1)
        pids1 = get_ffmpeg_pids().difference(pids0)  # generator has not started
        r.__next__()  # == meta
        pids2 = get_ffmpeg_pids().difference(pids0)  # now ffmpeg is running
        for frame in r:
            pass
        pids3 = get_ffmpeg_pids().difference(pids0)  # now its not

        assert len(pids1) == 0
        assert len(pids2) == 1
        assert len(pids3) == 0


@no_warnings_allowed
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


@no_warnings_allowed
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


@no_warnings_allowed
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


@no_warnings_allowed
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
    test_ffmpeg_version()
    test_reader_done()
    test_reader_close()
    test_reader_del()
    test_write_close()
    test_write_del()
