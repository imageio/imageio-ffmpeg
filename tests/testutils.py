import logging.handlers

import psutil

import imageio_ffmpeg


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
    pids = set()
    for p in psutil.process_iter():
        if "ffmpeg" in p.name().lower():
            pids.add(p.pid)
    return pids
