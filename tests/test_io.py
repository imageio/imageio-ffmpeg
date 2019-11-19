import os
import types
import tempfile
import time
from urllib.request import urlopen

from pytest import skip, raises

import imageio_ffmpeg


if os.getenv("TRAVIS_OS_NAME") == "windows":
    skip(
        "Skip this on the Travis Windows run for now, see #408", allow_module_level=True
    )


test_dir = tempfile.gettempdir()
test_url1 = "https://raw.githubusercontent.com/imageio/imageio-binaries/master/images/cockatoo.mp4"
test_url2 = "https://raw.githubusercontent.com/imageio/imageio-binaries/master/images/realshort.mp4"
test_file1 = os.path.join(test_dir, "cockatoo.mp4")
test_file2 = os.path.join(test_dir, "test.mp4")
test_file3 = os.path.join(test_dir, "realshort.mp4")


def setup_module():
    bb = urlopen(test_url1, timeout=5).read()
    with open(test_file1, "wb") as f:
        f.write(bb)
    bb = urlopen(test_url2, timeout=5).read()
    with open(test_file3, "wb") as f:
        f.write(bb)


def test_ffmpeg_version():
    version = imageio_ffmpeg.get_ffmpeg_version()
    print("ffmpeg version", version)
    assert version > "3.0"


def test_read_nframes():
    nframes, nsecs = imageio_ffmpeg.count_frames_and_secs(test_file1)
    assert nframes == 280
    assert 13.80 < nsecs < 13.99


def test_reading1():

    # Calling returns a generator
    gen = imageio_ffmpeg.read_frames(test_file1)
    assert isinstance(gen, types.GeneratorType)

    # First yield is a meta dict
    meta = gen.__next__()
    assert isinstance(meta, dict)
    for key in ("size", "fps", "duration"):
        assert key in meta

    # Read frames
    framesize = meta["size"][0] * meta["size"][1] * 3
    assert framesize == 1280 * 720 * 3
    count = 0
    for frame in gen:
        assert isinstance(frame, bytes) and len(frame) == framesize
        count += 1

    assert count == 280


def test_reading2():
    # Same as 1, but using other pixel format

    gen = imageio_ffmpeg.read_frames(test_file1, pix_fmt="gray", bpp=1)
    meta = gen.__next__()
    framesize = meta["size"][0] * meta["size"][1] * 1
    assert framesize == 1280 * 720 * 1

    count = 0
    for frame in gen:
        count += 1
        assert isinstance(frame, bytes) and len(frame) == framesize

    assert count == 280


def test_reading3():
    # Same as 1, but using other fps

    gen = imageio_ffmpeg.read_frames(test_file1, output_params=["-r", "5.0"])
    meta = gen.__next__()
    framesize = meta["size"][0] * meta["size"][1] * 3
    assert framesize == 1280 * 720 * 3

    count = 0
    for frame in gen:
        count += 1
        assert isinstance(frame, bytes) and len(frame) == framesize

    assert 50 < count < 100  # because smaller fps, same duration


def test_reading4():
    # Same as 1, but wrong, using an insane bpp, to invoke eof halfway a frame

    gen = imageio_ffmpeg.read_frames(test_file1, bpp=13)
    gen.__next__()  # == meta

    with raises(RuntimeError) as info:
        for frame in gen:
            pass
    msg = str(info.value).lower()
    assert "end of file reached before full frame could be read" in msg
    assert "ffmpeg version" in msg  # The log is included


def test_reading5():
    # Same as 1, but using other pixel format and bits_per_pixel
    bits_per_pixel = 12
    bits_per_bytes = 8
    gen = imageio_ffmpeg.read_frames(test_file3, pix_fmt="yuv420p", bits_per_pixel=bits_per_pixel)

    meta = gen.__next__()
    assert isinstance(meta, dict)
    for key in ("size", "fps", "duration"):
        assert key in meta

    # Read frames
    framesize = meta["size"][0] * meta["size"][1] * bits_per_pixel / bits_per_bytes
    assert framesize == 320 * 240 * bits_per_pixel / bits_per_bytes
    count = 0
    for frame in gen:
        assert isinstance(frame, bytes) and len(frame) == framesize
        count += 1

    assert count == 36


def test_reading_invalid_video():
    """
    Check whether invalid video is
    handled correctly without timeouts
    """
    # empty file as an example of invalid video
    _, test_invalid_file = tempfile.mkstemp(dir=test_dir)
    gen = imageio_ffmpeg.read_frames(test_invalid_file)

    start = time.time()
    with raises(OSError):
        gen.__next__()
    end = time.time()

    # check if metadata extraction doesn't hang
    # for a timeout period
    assert end - start < 1, "Metadata extraction hangs"


def test_write1():

    for n in (1, 9, 14, 279, 280, 281):

        # Prepare for writing
        gen = imageio_ffmpeg.write_frames(test_file2, (64, 64))
        assert isinstance(gen, types.GeneratorType)
        gen.send(None)  # seed

        # Write n frames
        for i in range(n):
            data = bytes([min(255, 100 + i * 10)] * 64 * 64 * 3)
            gen.send(data)
        gen.close()

        # Check that number of frames is correct
        nframes, nsecs = imageio_ffmpeg.count_frames_and_secs(test_file2)
        assert nframes == n

        # Check again by actually reading
        gen2 = imageio_ffmpeg.read_frames(test_file2)
        gen2.__next__()  # == meta
        count = 0
        for frame in gen2:
            count += 1
        assert count == n


def test_write_pix_fmt_in():

    sizes = []
    for pixfmt, bpp in [("gray", 1), ("rgb24", 3), ("rgba", 4)]:
        # Prepare for writing
        gen = imageio_ffmpeg.write_frames(test_file2, (64, 64), pix_fmt_in=pixfmt)
        gen.send(None)  # seed
        for i in range(9):
            data = bytes([min(255, 100 + i * 10)] * 64 * 64 * bpp)
            gen.send(data)
        gen.close()
        with open(test_file2, "rb") as f:
            sizes.append(len(f.read()))
        # Check nframes
        nframes, nsecs = imageio_ffmpeg.count_frames_and_secs(test_file2)
        assert nframes == 9

    assert sizes[0] <= sizes[1] <= sizes[2]


def test_write_pix_fmt_out():

    sizes = []
    for pixfmt in ["gray", "yuv420p"]:
        # Prepare for writing
        gen = imageio_ffmpeg.write_frames(test_file2, (64, 64), pix_fmt_out=pixfmt)
        gen.send(None)  # seed
        for i in range(9):
            data = bytes([min(255, 100 + i * 10)] * 64 * 64 * 3)
            gen.send(data)
        gen.close()
        with open(test_file2, "rb") as f:
            sizes.append(len(f.read()))
        # Check nframes
        nframes, nsecs = imageio_ffmpeg.count_frames_and_secs(test_file2)
        assert nframes == 9

    assert sizes[0] < sizes[1]


def test_write_wmv():
    # Switch to MS friendly codec when writing .wmv files

    for ext, codec in [("", "h264"), (".wmv", "msmpeg4")]:
        fname = test_file2 + ext
        gen = imageio_ffmpeg.write_frames(fname, (64, 64))
        gen.send(None)  # seed
        for i in range(9):
            data = bytes([min(255, 100 + i * 10)] * 64 * 64 * 3)
            gen.send(data)
        gen.close()
        #
        meta = imageio_ffmpeg.read_frames(fname).__next__()
        assert meta["codec"].startswith(codec)


def test_write_quality():

    sizes = []
    for quality in [2, 5, 9]:
        # Prepare for writing
        gen = imageio_ffmpeg.write_frames(test_file2, (64, 64), quality=quality)
        gen.send(None)  # seed
        for i in range(9):
            data = bytes([min(255, 100 + i * 10)] * 64 * 64 * 3)
            gen.send(data)
        gen.close()
        with open(test_file2, "rb") as f:
            sizes.append(len(f.read()))
        # Check nframes
        nframes, nsecs = imageio_ffmpeg.count_frames_and_secs(test_file2)
        assert nframes == 9

    assert sizes[0] < sizes[1] < sizes[2]


def test_write_bitrate():

    # Mind that we send uniform images, so the difference is marginal

    sizes = []
    for bitrate in ["1k", "10k", "100k"]:
        # Prepare for writing
        gen = imageio_ffmpeg.write_frames(test_file2, (64, 64), bitrate=bitrate)
        gen.send(None)  # seed
        for i in range(9):
            data = bytes([min(255, 100 + i * 10)] * 64 * 64 * 3)
            gen.send(data)
        gen.close()
        with open(test_file2, "rb") as f:
            sizes.append(len(f.read()))
        # Check nframes
        nframes, nsecs = imageio_ffmpeg.count_frames_and_secs(test_file2)
        assert nframes == 9

    assert sizes[0] < sizes[1] < sizes[2]


def test_write_macro_block_size():

    frame_sizes = []
    for mbz in [None, 10]:  # None is default == 16
        # Prepare for writing
        gen = imageio_ffmpeg.write_frames(test_file2, (40, 50), macro_block_size=mbz)
        gen.send(None)  # seed
        for i in range(9):
            data = bytes([min(255, 100 + i * 10)] * 40 * 50 * 3)
            gen.send(data)
        gen.close()
        # Check nframes
        nframes, nsecs = imageio_ffmpeg.count_frames_and_secs(test_file2)
        assert nframes == 9
        # Check size
        meta = imageio_ffmpeg.read_frames(test_file2).__next__()
        frame_sizes.append(meta["size"])

    assert frame_sizes[0] == (48, 64)
    assert frame_sizes[1] == (40, 50)


def test_write_big_frames():
    """Test that we give ffmpeg enough time to finish."""
    try:
        import numpy as np
    except ImportError:
        return skip("Missing 'numpy' test dependency")

    n = 9

    def _write_frames(pixfmt, bpp, tout):
        gen = imageio_ffmpeg.write_frames(
            test_file2, (2048, 2048), pix_fmt_in=pixfmt, ffmpeg_timeout=tout
        )
        gen.send(None)  # seed
        for i in range(n):
            data = (255 * np.random.rand(2048 * 2048 * bpp)).astype(np.uint8)
            data = bytes(data)
            gen.send(data)
        gen.close()

    # Short timeout is not enough time
    # Note that on Windows, if we wait a bit before calling count_frames_and_secs(),
    # it *does* work. Probably because killing a process on Windows is not instant (?)
    # and ffmpeg is able to still process the frames.
    _write_frames("rgb24", 3, 1.0)
    raises(RuntimeError, imageio_ffmpeg.count_frames_and_secs, test_file2)

    _write_frames("gray", 1, 15.0)
    nframes, nsecs = imageio_ffmpeg.count_frames_and_secs(test_file2)
    assert nframes == n

    _write_frames("rgb24", 3, 15.0)
    nframes, nsecs = imageio_ffmpeg.count_frames_and_secs(test_file2)
    assert nframes == n

    _write_frames("rgba", 4, 15.0)
    nframes, nsecs = imageio_ffmpeg.count_frames_and_secs(test_file2)
    assert nframes == n


if __name__ == "__main__":
    setup_module()
    test_ffmpeg_version()
    test_read_nframes()
    test_reading1()
    test_reading2()
    test_reading3()
    test_reading4()
    test_reading_invalid_video()
    test_write1()
    test_write_pix_fmt_in()
    test_write_pix_fmt_out()
    test_write_wmv()
    test_write_quality()
    test_write_bitrate()
    test_write_macro_block_size()
    test_write_big_frames()
