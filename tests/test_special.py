""" Tests more special use-cases.
"""

import gc
import queue
import threading

import imageio_ffmpeg

from testutils import ensure_test_files, test_file1


def setup_module():
    ensure_test_files()


def test_threading():
    # See issue #20

    num_threads = 16
    num_frames = 5

    def make_iterator(q, n):
        for i in range(n):
            gen = imageio_ffmpeg.read_frames(test_file1)
            gen.__next__()  # meta data
            q.put(gen.__next__())  # first frame

    q = queue.Queue()
    threads = []
    for i in range(num_threads):
        t = threading.Thread(target=make_iterator, args=(q, num_frames))
        t.daemon = True
        t.start()
        threads.append(t)

    for i in range(num_threads * num_frames):
        print(i, end=" ")
        q.get()
        gc.collect()  # this seems to help invoke the segfault earlier


if __name__ == "__main__":
    # setup_module()
    test_threading()
