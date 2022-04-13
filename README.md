# imageio-ffmpeg

[![Build Status](https://github.com/imageio/imageio-ffmpeg/workflows/CI/badge.svg)](https://github.com/imageio/imageio-ffmpeg/actions)
[![PyPI Version](https://img.shields.io/pypi/v/imageio-ffmpeg.svg)](https://pypi.python.org/pypi/imageio-ffmpeg/)

FFMPEG wrapper for Python

## Purpose

The purpose of this project is to provide a simple and reliable ffmpeg
wrapper for working with video files. It implements two simple generator
functions for reading and writing data from/to ffmpeg, which reliably
terminate the ffmpeg process when done. It also takes care of publishing
platform-specific wheels that include the binary ffmpeg executables.

This library is used as the basis for the
[imageio](https://github.com/imageio/imageio)
[ffmpeg plugin](https://imageio.readthedocs.io/en/stable/format_ffmpeg.html),
but it can also be used by itself. Imageio provides a higher level API,
and adds support for e.g. cameras and seeking.


## Installation

This library works with any version of Python 3.5+ (including Pypy).
There are no further dependencies. The wheels on Pypi include the ffmpeg
executable for all common platforms (Windows 7+, Linux kernel 2.6.32+,
OSX 10.9+). Install using:

```
$ pip install --upgrade imageio-ffmpeg
```

(On Linux you may want to first `pip install -U pip`, since pip 19 is needed to detect the `manylinux2010` wheels.)

If you're using a Conda environment: the conda package does not include
the ffmpeg executable, but instead depends on the `ffmpeg` package from
`conda-forge`. Install using:

```
$ conda install imageio-ffmpeg -c conda-forge
```

If you don't want to install the included ffmpeg, you can use pip with
`--no-binary` or conda with `--no-deps`. Then use the
`IMAGEIO_FFMPEG_EXE` environment variable if needed.


## Example usage

The `imageio_ffmpeg` library provides low level functionality to read
and write video data, using Python generators:


```py

# Read a video file
reader = read_frames(path)
meta = reader.__next__()  # meta data, e.g. meta["size"] -> (width, height)
for frame in reader:
    ... # each frame is a bytes object

# Write a video file
writer = write_frames(path, size)  # size is (width, height)
writer.send(None)  # seed the generator
for frame in frames:
    writer.send(frame)
writer.close()  # don't forget this
```

(Also see the API section further down.)


## How it works

This library calls ffmpeg in a subprocess, and video frames are
communicated over pipes. This is certainly not the fastest way to
use ffmpeg, but it makes it possible to wrap ffmpeg with pure Python,
making distribution and installation *much* easier. And probably
the code itself too. In contrast, [PyAV](https://github.com/mikeboers/PyAV)
wraps ffmpeg at the C level.

Note that because of how `imageio-ffmpeg` works, `read_frames()` and
`write_frames()` only accept file names, and not file (like) objects.



## imageio-ffmpeg for enterprise

Available as part of the Tidelift Subscription

The maintainers of imageio-ffmpeg and thousands of other packages are working with Tidelift to deliver commercial support and maintenance for the open source dependencies you use to build your applications. Save time, reduce risk, and improve code health, while paying the maintainers of the exact dependencies you use. [Learn more.](https://tidelift.com/subscription/pkg/pypi-imageio-ffmpeg?utm_source=pypi-imageio-ffmpeg&utm_medium=referral&utm_campaign=enterprise&utm_term=repo)


## Security contact information

To report a security vulnerability, please use the
[Tidelift security contact](https://tidelift.com/security).
Tidelift will coordinate the fix and disclosure.


## Environment variables

The library can be configured at runtime by setting the following environment
variables:
* `IMAGEIO_FFMPEG_EXE=[file name]` -- override the ffmpeg executable;
* `IMAGEIO_FFMPEG_NO_PREVENT_SIGINT=1` -- don't prevent propagation of SIGINT
  to the ffmpeg process.


## API

```py
def read_frames(
    path,
    pix_fmt="rgb24",
    bpp=None,
    input_params=None,
    output_params=None,
    bits_per_pixel=None,
):
    """
    Create a generator to iterate over the frames in a video file.

    It first yields a small metadata dictionary that contains:

    * ffmpeg_version: the ffmpeg version in use (as a string).
    * codec: a hint about the codec used to encode the video, e.g. "h264".
    * source_size: the width and height of the encoded video frames.
    * size: the width and height of the frames that will be produced.
    * fps: the frames per second. Can be zero if it could not be detected.
    * duration: duration in seconds. Can be zero if it could not be detected.

    After that, it yields frames until the end of the video is reached. Each
    frame is a bytes object.

    This function makes no assumptions about the number of frames in
    the data. For one because this is hard to predict exactly, but also
    because it may depend on the provided output_params. If you want
    to know the number of frames in a video file, use count_frames_and_secs().
    It is also possible to estimate the number of frames from the fps and
    duration, but note that even if both numbers are present, the resulting
    value is not always correct.

    Example:

        gen = read_frames(path)
        meta = gen.__next__()
        for frame in gen:
            print(len(frame))

    Parameters:
        path (str): the filename of the file to read from.
        pix_fmt (str): the pixel format of the frames to be read.
            The default is "rgb24" (frames are uint8 RGB images).
        input_params (list): Additional ffmpeg input command line parameters.
        output_params (list): Additional ffmpeg output command line parameters.
        bits_per_pixel (int): The number of bits per pixel in the output frames.
            This depends on the given pix_fmt. Default is 24 (RGB)
        bpp (int): DEPRECATED, USE bits_per_pixel INSTEAD. The number of bytes per pixel in the output frames.
            This depends on the given pix_fmt. Some pixel formats like yuv420p have 12 bits per pixel
            and cannot be set in bytes as integer. For this reason the bpp argument is deprecated.
    """
```

```py
def write_frames(
    path,
    size,
    pix_fmt_in="rgb24",
    pix_fmt_out="yuv420p",
    fps=16,
    quality=5,
    bitrate=None,
    codec=None,
    macro_block_size=16,
    ffmpeg_log_level="warning",
    ffmpeg_timeout=None,
    input_params=None,
    output_params=None,
    audio_path=None,
    audio_codec=None,
):
    """
    Create a generator to write frames (bytes objects) into a video file.

    The frames are written by using the generator's `send()` method. Frames
    can be anything that can be written to a file. Typically these are
    bytes objects, but c-contiguous Numpy arrays also work.

    Example:

        gen = write_frames(path, size)
        gen.send(None)  # seed the generator
        for frame in frames:
            gen.send(frame)
        gen.close()  # don't forget this

    Parameters:
        path (str): the filename to write to.
        size (tuple): the width and height of the frames.
        pix_fmt_in (str): the pixel format of incoming frames.
            E.g. "gray", "gray8a", "rgb24", or "rgba". Default "rgb24".
        pix_fmt_out (str): the pixel format to store frames. Default yuv420p".
        fps (float): The frames per second. Default 16.
        quality (float): A measure for quality between 0 and 10. Default 5.
            Ignored if bitrate is given.
        bitrate (str): The bitrate, e.g. "192k". The defaults are pretty good.
        codec (str): The codec. Default "libx264" for .mp4 (if available from
            the ffmpeg executable) or "msmpeg4" for .wmv.
        macro_block_size (int): You probably want to align the size of frames
            to this value to avoid image resizing. Default 16. Can be set
            to 1 to avoid block alignment, though this is not recommended.
        ffmpeg_log_level (str): The ffmpeg logging level. Default "warning".
        ffmpeg_timeout (float): Timeout in seconds to wait for ffmpeg process
            to finish. Value of 0 or None will wait forever (default). The time that
            ffmpeg needs depends on CPU speed, compression, and frame size.
        input_params (list): Additional ffmpeg input command line parameters.
        output_params (list): Additional ffmpeg output command line parameters.
        audio_path (str): A input file path for encoding with an audio stream.
            Default None, no audio.
        audio_codec (str): The audio codec to use if audio_path is provided.
            "copy" will try to use audio_path's audio codec without re-encoding.
            Default None, but some formats must have certain codecs specified.
    """
```

```py
def count_frames_and_secs(path):
    """
    Get the number of frames and number of seconds for the given video
    file. Note that this operation can be quite slow for large files.

    Disclaimer: I've seen this produce different results from actually reading
    the frames with older versions of ffmpeg (2.x). Therefore I cannot say
    with 100% certainty that the returned values are always exact.
    """
```

```py
def get_ffmpeg_exe():
    """
    Get the ffmpeg executable file. This can be the binary defined by
    the IMAGEIO_FFMPEG_EXE environment variable, the binary distributed
    with imageio-ffmpeg, an ffmpeg binary installed with conda, or the
    system ffmpeg (in that order). A RuntimeError is raised if no valid
    ffmpeg could be found.
    """
```

```py
def get_ffmpeg_version():
    """
    Get the version of the used ffmpeg executable (as a string).
    """
```

