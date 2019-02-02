# styletest: ignore E501
""" Tests specific to parsing ffmpeg header.
"""

import os
from pytest import skip
from imageio_ffmpeg._parsing import cvsecs, limit_lines, parse_ffmpeg_header


if os.getenv("TRAVIS_OS_NAME") == "windows":
    skip(
        "Skip this on the Travis Windows run for now, see #408", allow_module_level=True
    )


def dedent(text, dedent=8):
    lines = [line[dedent:] for line in text.splitlines()]
    text = "\n".join(lines)
    return text.strip() + "\n"


def test_cvsecs():
    assert cvsecs(20) == 20
    assert cvsecs(2, 20) == (2 * 60) + 20
    assert cvsecs(2, 3, 20) == (2 * 3600) + (3 * 60) + 20


def test_limit_lines():
    lines = ["foo"] * 10
    assert len(limit_lines(lines)) == 10
    lines = ["foo"] * 50
    assert len(limit_lines(lines)) == 50  # < 2 * N
    lines = ["foo"] * 70 + ["bar"]
    lines2 = limit_lines(lines)
    assert len(lines2) == 33  # > 2 * N
    assert b"last few lines" in lines2[0]
    assert "bar" == lines2[-1]


def test_get_correct_fps1():
    # from issue imageio#262

    sample = dedent(
        r"""
        fmpeg version 3.2.2 Copyright (c) 2000-2016 the FFmpeg developers
        built with Apple LLVM version 8.0.0 (clang-800.0.42.1)
        configuration: --prefix=/usr/local/Cellar/ffmpeg/3.2.2 --enable-shared --enable-pthreads --enable-gpl --enable-version3 --enable-hardcoded-tables --enable-avresample --cc=clang --host-cflags= --host-ldflags= --enable-ffplay --enable-frei0r --enable-libass --enable-libfdk-aac --enable-libfreetype --enable-libmp3lame --enable-libopencore-amrnb --enable-libopencore-amrwb --enable-libopus --enable-librtmp --enable-libschroedinger --enable-libspeex --enable-libtheora --enable-libvorbis --enable-libvpx --enable-libx264 --enable-libxvid --enable-opencl --disable-lzma --enable-libopenjpeg --disable-decoder=jpeg2000 --extra-cflags=-I/usr/local/Cellar/openjpeg/2.1.2/include/openjpeg-2.1 --enable-nonfree --enable-vda
        libavutil      55. 34.100 / 55. 34.100
        libavcodec     57. 64.101 / 57. 64.101
        libavformat    57. 56.100 / 57. 56.100
        libavdevice    57.  1.100 / 57.  1.100
        libavfilter     6. 65.100 /  6. 65.100
        libavresample   3.  1.  0 /  3.  1.  0
        libswscale      4.  2.100 /  4.  2.100
        libswresample   2.  3.100 /  2.  3.100
        libpostproc    54.  1.100 / 54.  1.100
        Input #0, mov,mp4,m4a,3gp,3g2,mj2, from '/Users/echeng/video.mp4':
        Metadata:
            major_brand     : mp42
            minor_version   : 1
            compatible_brands: isom3gp43gp5
        Duration: 00:16:05.80, start: 0.000000, bitrate: 1764 kb/s
            Stream #0:0(eng): Audio: aac (LC) (mp4a / 0x6134706D), 8000 Hz, mono, fltp, 40 kb/s (default)
            Metadata:
            handler_name    : soun
            Stream #0:1(eng): Video: mpeg4 (Simple Profile) (mp4v / 0x7634706D), yuv420p, 640x480 [SAR 1:1 DAR 4:3], 1720 kb/s, 29.46 fps, 26.58 tbr, 90k tbn, 1k tbc (default)
            Metadata:
            handler_name    : vide
        Output #0, image2pipe, to 'pipe:':
        Metadata:
            major_brand     : mp42
            minor_version   : 1
            compatible_brands: isom3gp43gp5
            encoder         : Lavf57.56.100
            Stream #0:0(eng): Video: rawvideo (RGB[24] / 0x18424752), rgb24, 640x480 [SAR 1:1 DAR 4:3], q=2-31, 200 kb/s, 26.58 fps, 26.58 tbn, 26.58 tbc (default)
            Metadata:
            handler_name    : vide
            encoder         : Lavc57.64.101 rawvideo
        Stream mapping:
        """
    )

    info = parse_ffmpeg_header(sample)
    assert info["fps"] == 26.58


def test_get_correct_fps2():
    # from issue imageio#262

    sample = dedent(
        r"""
        ffprobe version 3.2.2 Copyright (c) 2007-2016 the FFmpeg developers
        built with Apple LLVM version 8.0.0 (clang-800.0.42.1)
        configuration: --prefix=/usr/local/Cellar/ffmpeg/3.2.2 --enable-shared --enable-pthreads --enable-gpl --enable-version3 --enable-hardcoded-tables --enable-avresample --cc=clang --host-cflags= --host-ldflags= --enable-ffplay --enable-frei0r --enable-libass --enable-libfdk-aac --enable-libfreetype --enable-libmp3lame --enable-libopencore-amrnb --enable-libopencore-amrwb --enable-libopus --enable-librtmp --enable-libschroedinger --enable-libspeex --enable-libtheora --enable-libvorbis --enable-libvpx --enable-libx264 --enable-libxvid --enable-opencl --disable-lzma --enable-libopenjpeg --disable-decoder=jpeg2000 --extra-cflags=-I/usr/local/Cellar/openjpeg/2.1.2/include/openjpeg-2.1 --enable-nonfree --enable-vda
        libavutil      55. 34.100 / 55. 34.100
        libavcodec     57. 64.101 / 57. 64.101
        libavformat    57. 56.100 / 57. 56.100
        libavdevice    57.  1.100 / 57.  1.100
        libavfilter     6. 65.100 /  6. 65.100
        libavresample   3.  1.  0 /  3.  1.  0
        libswscale      4.  2.100 /  4.  2.100
        libswresample   2.  3.100 /  2.  3.100
        libpostproc    54.  1.100 / 54.  1.100
        Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'video.mp4':
        Metadata:
            major_brand     : mp42
            minor_version   : 1
            compatible_brands: isom3gp43gp5
        Duration: 00:08:44.53, start: 0.000000, bitrate: 1830 kb/s
            Stream #0:0(eng): Audio: aac (LC) (mp4a / 0x6134706D), 8000 Hz, mono, fltp, 40 kb/s (default)
            Metadata:
            handler_name    : soun
            Stream #0:1(eng): Video: mpeg4 (Simple Profile) (mp4v / 0x7634706D), yuv420p, 640x480 [SAR 1:1 DAR 4:3], 1785 kb/s, 29.27 fps, 1k tbr, 90k tbn, 1k tbc (default)
            Metadata:
            handler_name    : vide
        """
    )

    info = parse_ffmpeg_header(sample)
    assert info["fps"] == 29.27


if __name__ == "__main__":
    test_cvsecs()
    test_limit_lines()
    test_get_correct_fps1()
    test_get_correct_fps2()
