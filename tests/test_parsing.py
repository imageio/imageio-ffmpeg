# styletest: ignore E501
"""
Tests specific to parsing ffmpeg header.
"""

from imageio_ffmpeg._parsing import cvsecs, limit_lines, parse_ffmpeg_header


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


def test_get_correct_rotation():
    # from issue imageio-ffmpeg#38

    sample = dedent(
        r"""
        ffmpeg version 4.2.2 Copyright (c) 2000-2019 the FFmpeg developers
          built with Apple clang version 11.0.0 (clang-1100.0.33.8)
          configuration: --enable-gpl --enable-version3 --enable-sdl2 --enable-fontconfig --enable-gnutls --enable-iconv --enable-libass --enable-libdav1d --enable-libbluray --enable-libfreetype --enable-libmp3lame --enable-libopencore-amrnb --enable-libopencore-amrwb --enable-libopenjpeg --enable-libopus --enable-libshine --enable-libsnappy --enable-libsoxr --enable-libtheora --enable-libtwolame --enable-libvpx --enable-libwavpack --enable-libwebp --enable-libx264 --enable-libx265 --enable-libxml2 --enable-libzimg --enable-lzma --enable-zlib --enable-gmp --enable-libvidstab --enable-libvorbis --enable-libvo-amrwbenc --enable-libmysofa --enable-libspeex --enable-libxvid --enable-libaom --enable-appkit --enable-avfoundation --enable-coreimage --enable-audiotoolbox
          libavutil      56. 31.100 / 56. 31.100
          libavcodec     58. 54.100 / 58. 54.100
          libavformat    58. 29.100 / 58. 29.100
          libavdevice    58.  8.100 / 58.  8.100
          libavfilter     7. 57.100 /  7. 57.100
          libswscale      5.  5.100 /  5.  5.100
          libswresample   3.  5.100 /  3.  5.100
          libpostproc    55.  5.100 / 55.  5.100
        Input #0, mov,mp4,m4a,3gp,3g2,mj2, from '/var/folders/82/6_ww__k94ms56ldtsph50pqc0000gn/T/imageio_sievk8ws':
          Metadata:
            major_brand     : mp42
            minor_version   : 0
            compatible_brands: isommp42
            creation_time   : 2020-06-18T12:31:32.000000Z
            com.android.version: 10
          Duration: 00:00:01.07, start: 0.000000, bitrate: 2661 kb/s
            Stream #0:0(eng): Video: h264 (High) (avc1 / 0x31637661), yuvj420p(pc, bt470bg/bt470bg/smpte170m), 720x480, 2636 kb/s, SAR 1:1 DAR 3:2, 30.01 fps, 120 tbr, 90k tbn, 180k tbc (default)
            Metadata:
              rotate          : 270
              creation_time   : 2020-06-18T12:31:32.000000Z
              handler_name    : VideoHandle
            Side data:
              displaymatrix: rotation of 90.00 degrees
        Stream mapping:
          Stream #0:0 -> #0:0 (h264 (native) -> rawvideo (native))
        Press [q] to stop, [?] for help
        [swscaler @ 0x7f95cd92da00] deprecated pixel format used, make sure you did set range correctly
        Output #0, image2pipe, to 'pipe:':
          Metadata:
            major_brand     : mp42
            minor_version   : 0
            compatible_brands: isommp42
            com.android.version: 10
            encoder         : Lavf58.29.100
            Stream #0:0(eng): Video: rawvideo (RGB[24] / 0x18424752), rgb24, 480x720 [SAR 1:1 DAR 2:3], q=2-31, 995328 kb/s, 120 fps, 120 tbn, 120 tbc (default)
        """
    )

    info = parse_ffmpeg_header(sample)
    assert info["rotate"] == 270


if __name__ == "__main__":
    test_cvsecs()
    test_limit_lines()
    test_get_correct_fps1()
    test_get_correct_fps2()
    test_get_correct_rotation()
