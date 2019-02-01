import re

from ._utils import logger


def parse_ffmpeg_header(text):
    lines = text.splitlines()
    meta = {}

    # Get version
    ver = lines[0].split("version", 1)[-1].split("Copyright")[0]
    meta["ffmpeg_version"] = ver.strip() + " " + lines[1].strip()

    # get the output line that speaks about video
    videolines = [
        l for l in lines if l.lstrip().startswith("Stream ") and " Video: " in l
    ]
    line = videolines[0]

    # get the frame rate.
    # matches can be empty, see #171, assume nframes = inf
    # the regexp omits values of "1k tbr" which seems a specific edge-case #262
    # it seems that tbr is generally to be preferred #262
    matches = re.findall(r" ([0-9]+\.?[0-9]*) (tbr|fps)", line)
    fps = 0
    matches.sort(key=lambda x: x[1] == "tbr", reverse=True)
    if matches:
        fps = float(matches[0][0].strip())
    meta["fps"] = fps

    # get the size of the original stream, of the form 460x320 (w x h)
    match = re.search(" [0-9]*x[0-9]*(,| )", line)
    parts = line[match.start() : match.end() - 1].split("x")
    meta["source_size"] = tuple(map(int, parts))

    # get the size of what we receive, of the form 460x320 (w x h)
    line = videolines[-1]  # Pipe output
    match = re.search(" [0-9]*x[0-9]*(,| )", line)
    parts = line[match.start() : match.end() - 1].split("x")
    meta["size"] = tuple(map(int, parts))

    # Check the two sizes
    if meta["source_size"] != meta["size"]:
        logger.warning(
            "The frame size for reading %s is "
            "different from the source frame size %s."
            % (meta["size"], meta["source_size"])
        )

    # get duration (in seconds)
    line = [l for l in lines if "Duration: " in l][0]
    match = re.search(" [0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9]", line)
    if match is not None:
        hms = line[match.start() + 1 : match.end()].split(":")
        meta["duration"] = cvsecs(*hms)

    return meta


def cvsecs(*args):
    """ converts a time to second. Either cvsecs(min, secs) or
    cvsecs(hours, mins, secs).
    """
    if len(args) == 1:
        return float(args[0])
    elif len(args) == 2:
        return 60 * float(args[0]) + float(args[1])
    elif len(args) == 3:
        return 3600 * float(args[0]) + 60 * float(args[1]) + float(args[2])
