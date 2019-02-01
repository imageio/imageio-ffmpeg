import time
import threading


class LogCatcher(threading.Thread):
    """ Thread to keep reading from stderr so that the buffer does not
    fill up and stalls the ffmpeg process. On stderr a message is send
    on every few frames with some meta information. We only keep the
    last ones.
    """

    def __init__(self, file):
        self._file = file
        self._header = ""
        self._lines = []
        self._remainder = b""
        threading.Thread.__init__(self)
        self.setDaemon(True)  # do not let this thread hold up Python shutdown
        self._should_stop = False
        self.start()

    def stop_me(self):
        self._should_stop = True

    @property
    def header(self):
        """ Get header text. Empty string if the header is not yet parsed.
        """
        return self._header

    def get_text(self, timeout=0):
        """ Get the whole text written to stderr so far. To preserve
        memory, only the last 50 to 100 frames are kept.

        If a timeout is given, wait for this thread to finish. When
        something goes wrong, we stop ffmpeg and want a full report of
        stderr, but this thread might need a tiny bit more time.
        """

        # Wait?
        if timeout > 0:
            etime = time.time() + timeout
            while self.isAlive() and time.time() < etime:  # pragma: no cover
                time.sleep(0.01)
        # Return str
        lines = b"\n".join(self._lines)
        return self._header + "\n" + lines.decode("utf-8", "ignore")

    def run(self):

        # Create ref here so it still exists even if Py is shutting down
        limit_lines_local = limit_lines

        while not self._should_stop:
            time.sleep(0)
            # Read one line. Detect when closed, and exit
            try:
                line = self._file.read(20)
            except ValueError:  # pragma: no cover
                break
            if not line:
                break
            # Process to divide in lines
            line = line.replace(b"\r", b"\n").replace(b"\n\n", b"\n")
            lines = line.split(b"\n")
            lines[0] = self._remainder + lines[0]
            self._remainder = lines.pop(-1)
            # Process each line
            self._lines.extend(lines)
            if not self._header:
                if get_output_video_line(self._lines):
                    header = b"\n".join(self._lines)
                    self._header += header.decode("utf-8", "ignore")
            elif self._lines:
                self._lines = limit_lines_local(self._lines)


def get_output_video_line(lines):
    """Get the line that defines the video stream that ffmpeg outputs,
    and which we read.
    """
    in_output = False
    for line in lines:
        sline = line.lstrip()
        if sline.startswith(b"Output "):
            in_output = True
        elif in_output:
            if sline.startswith(b"Stream ") and b" Video:" in sline:
                return line


def limit_lines(lines, N=32):
    """ When number of lines > 2*N, reduce to N.
    """
    if len(lines) > 2 * N:
        lines = [b"... showing only last few lines ..."] + lines[-N:]
    return lines
