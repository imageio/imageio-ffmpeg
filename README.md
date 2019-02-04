# imageio-ffmpeg

[![Build Status](https://travis-ci.org/imageio/imageio-ffmpeg.svg?branch=master)](https://travis-ci.org/imageio/imageio-ffmpeg)

FFMPEG wrapper for Python

## Purpose

The purpose of this project is to provide a simple and reliable ffmpeg
wrapper for working with video files. It takes care of producing
platform-specific wheels that include the binary executables of ffmpeg.
These can then be installed (and updated or uninstalled) easily with pip.

It also provides simple generator functions for reading and writing data
from/to ffmpeg, which reliably terminate the ffmpeg process when done.

This library is used as the basis for the
[imageio](https://github.com/imageio/imageio) ffmpeg plugin, but it can
be used by itself just fine.


## Usage

The `imageio_ffmpeg` library provides low level functionality to read
and write video data, using Python generators:


```py

# Read a video file
reader = read_frames(path)
meta = reader.__next__()  # meta data, like frame size
for frame in reader:
    ... # each frame is a bytes object

# Write a video file
writer = write_frames(path, size)
writer.send(None)  # seed the generator
for frame in frames:
    writer.send(frame)
writer.close()  # don't forget this
```


## Requirements and installation

This library works with any version of Python v3.4 and up (also Pypy).
There are no further dependencies. It should also work on any platform.
For common platforms (Windows, Linux, OSX), the wheels on Pypi include
the ffmpeg executable.

Install with

```
$ pip install imageio-binaries
```


## How it works

This library calls ffmpeg in a subprocess, and video frames are
communicated over pipes. This is certainly not the fastest way to
use ffmpeg, but it makes it possible to wrap ffmpeg with pure Python,
making distribution and installation *much* easier. And probably
the code itself too. In contrast, [PyAV](https://github.com/mikeboers/PyAV)
wraps ffmpeg at the C level.


## API

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
def read_frames(path, pix_fmt="rgb24", bpp=3, input_params=None, output_params=None):
    """
    Create a generator to iterate over the frames in a video file.
    
    It first yields a small metadata dictionary that contains:
    
    * ffmpeg_version: the ffmpeg version is use (as a string).
    * codec: a hint about the codec used to encode the video, e.g. "h264"
    * source_size: the width and height of the encoded video frames
    * size: the width and height of the frames that will be produced
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
        path (str): the file to write to.
        pix_fmt (str): the pixel format the frames to be read.
        bpp (int): The number of bytes per pixel in the output.
            This depends on the given pix_fmt. Default is 3 (RGB).
        input_params (list): Additional ffmpeg input parameters.
        output_params (list): Additional ffmpeg output parameters.
    """
```



```py
def write_frames(path, size, pix_fmt_in="rgb24", pix_fmt_out="yuv420p", fps=16,
                 quality=5, bitrate=None, codec=None, macro_block_size=16,
                 ffmpeg_log_level="warning",
                 input_params=None, output_params=None):
    """
    Create a generator to write frames (bytes objects) into a video file.
    
    Example:
    
        gen = write_frames(path, size)
        gen.send(None)  # seed the generator
        for frame in frames:
            gen.send(frame)
        gen.close()  # don't forget this
    
    Parameters:
        path (str): the file to write to.
        size (tuple): the width and height of the frames.
        pix_fmt_in (str): the pixel format of incoming frames.
            E.g. "gray", "gray8a", "rgb24", or "rgba". Default "rgb24".
        pix_fmt_out (str): the pixel format to store frames. Default yuv420p".
        fps (float): The frames per second. Default 16.
        quality (float): A measure for quality between 0 and 10. Default 5.
            Ignored if bitrate is given.
        bitrate (str): The bitrate, e.g. "192k". The defaults are pretty good.
        codec (str): The codec. Default "libx264" (or "msmpeg4" for .wmv).
        macro_block_size (int): You probably want to align the size of frames
            to this value to avoid image resizing. Default 16. Can be set
            to 1 to avoid block alignment, though this is not recommended.
        ffmpeg_log_level (str): The ffmpeg logging level.
        input_params (list): Additional ffmpeg input parameters.
        output_params (list): Additional ffmpeg output parameters.
    """
```
