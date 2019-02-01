import sys
import time
import signal
import subprocess

from ._utils import get_ffmpeg_exe, logger
from ._catchers import LogCatcher
from ._parsing import parse_ffmpeg_header, cvsecs


ISWIN = sys.platform.startswith("win")


exe = None


def _get_exe():
    global exe
    if exe is None:
        exe = get_ffmpeg_exe()
    return exe


def count_frames_and_secs(path):
    """ Get the exact number of frames and number of seconds for the given video file.
    Note that this operation can be relatively slow for large files.
    """
    # https://stackoverflow.com/questions/2017843/fetch-frame-count-with-ffmpeg

    cmd = [_get_exe(), "-i", path, "-map", "0:v:0", "-c", "copy", "-f", "null", "-"]
    out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=ISWIN)

    nframes = nsecs = None
    for line in reversed(out.splitlines()):
        if line.startswith(b"frame="):
            line = line.decode(errors="ignore")
            i = line.find("frame=")
            if i >= 0:
                s = line[i:].split("=", 1)[-1].lstrip().split(" ", 1)[0].strip()
                nframes = int(s)
            i = line.find("time=")
            if i >= 0:
                s = line[i:].split("=", 1)[-1].lstrip().split(" ", 1)[0].strip()
                nsecs = cvsecs(*s.split(":"))
            return nframes, nsecs
    raise RuntimeError("Could not get number of frames")


def read_frames(path, pix_fmt="rgb24", bpp=3, input_params=None, output_params=None):
    """ Create a generator to iterate over the frames in a video file.
    It first yields a small metadata dictionary. After that it yields
    frames until the end of the video is reached.
    
    This function makes no assumptions about the number of frames in
    the data. In part because this may depend on provided output args.
    If you want to know the number of frames in a video file, use
    count_frames_and_secs().
    
    Example:
    
        for frame in read_frames(path):
            print(len(frame))
    
    Parameters:
        path (str): the file to write to.
        pix_fmt (str): the pixel format the frames to be read.
        bpp (int): The number of bytes per pixel in the output. This depends on
            the given pix_fmt. Default is 3 (RGB).
        input_params (list): Additional ffmpeg input parameters.
        output_params (list): Additional ffmpeg output parameters.
    """

    # --- Prepare

    input_params = input_params or []
    output_params = output_params or []

    pre_output_params = ["-f", "image2pipe", "-pix_fmt", pix_fmt, "-vcodec", "rawvideo"]

    cmd = [_get_exe()]
    cmd += input_params + ["-i", path]
    cmd += pre_output_params + output_params + ["-"]

    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=ISWIN,
    )

    log_catcher = LogCatcher(p.stderr)

    try:

        # ----- Load meta data

        # Wait for the log catcher to get the meta information
        etime = time.time() + 10.0
        while (not log_catcher.header) and time.time() < etime:
            time.sleep(0.01)

        # Check whether we have the information
        if not log_catcher.header:
            self._terminate()
            # todo: ....
            if self.request._video:
                ffmpeg_err = (
                    "FFMPEG STDERR OUTPUT:\n" + self.log_catcher.get_text(0.1) + "\n"
                )
                if "darwin" in sys.platform:
                    if "Unknown input format: 'avfoundation'" in ffmpeg_err:
                        ffmpeg_err += (
                            "Try installing FFMPEG using "
                            "home brew to get a version with "
                            "support for cameras."
                        )
                raise IndexError(
                    "No video4linux camera at %s.\n\n%s"
                    % (self.request._video, ffmpeg_err)
                )
            else:
                err2 = self.log_catcher.get_text(0.2)
                fmt = "Could not load meta information\n=== stderr ===\n%s"
                raise IOError(fmt % err2)

        if "No such file or directory" in log_catcher.header:
            if self.request._video:
                raise IOError("Could not open stream %s." % path)
            else:  # pragma: no cover - this is checked by Request
                raise IOError("%s not found! Wrong path?" % path)

        meta = parse_ffmpeg_header(log_catcher.header)
        yield meta

        # ----- Read frames

        w, h = meta["size"]
        framesize = w * h * bpp
        framenr = 0

        while True:
            framenr += 1
            try:
                bb = bytes()
                while len(bb) < framesize:
                    extra_bytes = p.stdout.read(framesize - len(bb))
                    if not extra_bytes:
                        if len(bb) == 0:
                            return
                        else:
                            raise RuntimeError(
                                "End of file reached before full frame could be read."
                            )
                    bb += extra_bytes
            except Exception as err:
                err1 = str(err)
                err2 = log_catcher.get_text(0.4)
                fmt = "Could not read frame %i:\n%s\n=== stderr ===\n%s"
                raise RuntimeError(fmt % (framenr, err1, err2))
            yield bb

    finally:

        if p.poll() is None:

            # Ask ffmpeg to quit
            try:
                if sys.platform.startswith("win"):
                    p.communicate(b"q")
                else:
                    p.send_signal(signal.SIGINT)
            except Exception as err:
                logger.warning("Error while attempting stop ffmpeg: " + str(err))

            # Wait for it to stop
            etime = time.time() + 1.5
            while time.time() < etime and p.poll() is None:
                time.sleep(0.01)

            # Grr, we have to kill it
            if p.poll() is None:
                logger.warning("We had to kill ffmpeg to stop it.")
                p.kill()


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
    input_params=None,
    output_params=None,
):
    """ Create a generator to flush frames into a video file.
    
    Example:
    
        w = write_frames(path, size)
        w.send(None)  # seed the iterator
        for frame in frames:
            w.send(frame)
        w.close()
    
    Parameters:
        path (str): the file to write to.
        size (tuple): the width and height of the frames.
        pix_fmt_in (str): the pixel format of incoming frames.
            E.g. "gray", "gray8a", "rgb24", or "rgba".
        pix_fmt_out (str): the pixel format to store frames in. Default yuv420p".
        fps (float): The frames per second. Default 16.
        quality (float): A measure for quality between 0 and 10. Default 5.
            Ignored if bitrate is given.
        bitrate (float): The bitrate. Usually the defaults are pretty good.
        codec (str): The codec to use. Default "libx264" (or "msmpeg4" for .wmv).
        macro_block_size (int): You probably want to align the size of frames
            to this value to avoid image resizing. Default 16. Can also be set
            to None to avoid block alignment, though this is not recommended.
        ffmpeg_log_level (str): The ffmpeg logging level.
        input_params (list): Additional ffmpeg input parameters.
        output_params (list): Additional ffmpeg output parameters.
    
    """

    # --- Prepare

    input_params = input_params or []
    output_params = output_params or []

    # Get parameters
    # Note that H264 is a widespread and very good codec, but if we
    # do not specify a bitrate, we easily get crap results.
    sizestr = "%dx%d" % (size[0], size[1])
    default_codec = "libx264"
    if path.lower().endswith(".wmv"):
        # This is a safer default codec on windows to get videos that
        # will play in powerpoint and other apps. H264 is not always
        # available on windows.
        default_codec = "msmpeg4"
    codec = codec or default_codec
    # You may need to use -pix_fmt yuv420p for your output to work in
    # QuickTime and most other players. These players only supports
    # the YUV planar color space with 4:2:0 chroma subsampling for
    # H.264 video. Otherwise, depending on your source, ffmpeg may
    # output to a pixel format that may be incompatible with these
    # players. See
    # https://trac.ffmpeg.org/wiki/Encode/H.264#Encodingfordumbplayers

    # Get command
    cmd = [_get_exe(), "-y", "-f", "rawvideo", "-vcodec", "rawvideo", "-s", sizestr]
    cmd += ["-pix_fmt", pix_fmt_in, "-r", "%.02f" % fps] + input_params
    cmd += ["-i", "-"]
    cmd += ["-an", "-vcodec", codec, "-pix_fmt", pix_fmt_out]

    # Add fixed bitrate or variable bitrate compression flags
    if bitrate is not None:
        cmd += ["-b:v", str(bitrate)]
    elif quality is not None:  # If None, then we don't add anything
        if quality < 0 or quality > 10:
            raise ValueError("ffpmeg quality parameter must be between 0 and 10.")
        quality = 1 - quality / 10.0
        if codec == "libx264":
            # crf ranges 0 to 51, 51 being worst.
            quality = int(quality * 51)
            cmd += ["-crf", str(quality)]  # for h264
        else:  # Many codecs accept q:v
            # q:v range can vary, 1-31, 31 being worst
            # But q:v does not always have the same range.
            # May need a way to find range for any codec.
            quality = int(quality * 30) + 1
            cmd += ["-qscale:v", str(quality)]  # for others

    # Note, for most codecs, the image dimensions must be divisible by
    # 16 the default for the macro_block_size is 16. Check if image is
    # divisible, if not have ffmpeg upsize to nearest size and warn
    # user they should correct input image if this is not desired.
    if macro_block_size is not None and macro_block_size > 1:
        if size[0] % macro_block_size > 0 or size[1] % macro_block_size > 0:
            out_w = size[0]
            out_h = size[1]
            if size[0] % macro_block_size > 0:
                out_w += macro_block_size - (size[0] % macro_block_size)
            if size[1] % macro_block_size > 0:
                out_h += macro_block_size - (size[1] % macro_block_size)
            cmd += ["-vf", "scale={}:{}".format(out_w, out_h)]
            logger.warning(
                "IMAGEIO FFMPEG_WRITER WARNING: input image is not"
                " divisible by macro_block_size={}, resizing from {} "
                "to {} to ensure video compatibility with most codecs "
                "and players. To prevent resizing, make your input "
                "image divisible by the macro_block_size or set the "
                "macro_block_size to None (risking incompatibility). You "
                "may also see a FFMPEG warning concerning "
                "speedloss due to "
                "data not being aligned.".format(
                    macro_block_size, size[:2], (out_w, out_h)
                )
            )

    # Rather than redirect stderr to a pipe, just set minimal
    # output from ffmpeg by default. That way if there are warnings
    # the user will see them.
    cmd += ["-v", ffmpeg_log_level]
    cmd += output_params
    cmd.append(path)
    cmd_str = " ".join(cmd)
    if any(
        [level in ffmpeg_log_level for level in ("info", "verbose", "debug", "trace")]
    ):
        logger.info("RUNNING FFMPEG COMMAND: " + cmd_str)

    # Launch process
    p = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, shell=ISWIN
    )

    # For Windows, set `shell=True` in sp.Popen to prevent popup
    # of a command line window in frozen applications.
    # Note that directing stderr to a pipe on windows will cause ffmpeg
    # to hang if the buffer is not periodically cleared using
    # StreamCatcher or other means.

    # ----- Write frames

    try:

        # Just keep going until the generator.close() is called (raises GeneratorExit)
        while True:

            # Get frame
            bb = (yield)
            # framesize = size[0] * size[1] * depth * bpp
            # assert isinstance(bb, bytes), "Frame must be send as bytes"
            # assert len(bb) == framesize, "Frame must have width*height*depth*bpp bytes"
            # Actually, we accept anything that can be written to file.
            # This e.g. allows writing numpy arrays without having to make a copy ...

            # Write
            try:
                p.stdin.write(bb)
            except IOError as err:
                # Show the command and stderr from pipe
                msg = (
                    "{0:}\n\nFFMPEG COMMAND:\n{1:}\n\nFFMPEG STDERR "
                    "OUTPUT:\n".format(err, cmd_str)
                )
                raise IOError(msg)

    finally:

        if p.poll() is None:

            # Ask ffmpeg to quit - and finish writing the file
            try:
                p.stdin.close()
            except Exception as err:
                logger.warning("Error while attempting stop ffmpeg: " + str(err))
