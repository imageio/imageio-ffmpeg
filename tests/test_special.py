""" Tests more special use-cases.
"""

import gc
import queue
import threading

from testutils import ensure_test_files, test_file1

import imageio_ffmpeg


def setup_module():
    ensure_test_files()


def make_iterator(q, n):
    for i in range(n):
        gen = imageio_ffmpeg.read_frames(test_file1)
        gen.__next__()  # meta data
        q.put(gen.__next__())  # first frame


def test_threading():
    # See issue #20

    num_threads = 16
    num_frames = 5

    q = queue.Queue()
    threads = []
    for i in range(num_threads):
        t = threading.Thread(target=make_iterator, args=(q, num_frames))
        t.daemon = True
        t.start()
        threads.append(t)

    for i in range(num_threads * num_frames):
        print(i, end=" ")
        gc.collect()  # this seems to help invoke the segfault earlier
        q.get(timeout=20)


if __name__ == "__main__":
    setup_module()
    test_threading()
