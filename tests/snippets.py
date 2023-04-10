"""
Snippets of code that are hard to bring under test, but that can be
used to manually test the behavior of imageip-ffmpeg in certain
use-cases. Some may depend on imageio.
"""

# %%  Write a series of large frames

# In earlier versions of imageio-ffmpeg, the ffmpeg process was given a timeout
# to complete, but this timeout must be longer for longer movies. The default
# is now to wait for ffmpeg.

import os

import numpy as np

import imageio_ffmpeg

ims = [
    np.random.uniform(0, 255, size=(1000, 1000, 3)).astype(np.uint8) for i in range(10)
]

filename = os.path.expanduser("~/Desktop/foo.mp4")
w = imageio_ffmpeg.write_frames(filename, (1000, 1000), ffmpeg_timeout=0)
w.send(None)
for i in range(200):
    w.send(ims[i % 10])
    print(i)
w.close()


# %% Behavior of KeyboardInterrupt / Ctrl+C

import os

import imageio_ffmpeg

filename = os.path.expanduser("~/.imageio/images/cockatoo.mp4")
reader = imageio_ffmpeg.read_frames(filename)

meta = reader.__next__()

try:
    input("Do a manual KeyboardInterrupt now [Ctrl]+[c]")
    # Note: Raising an error with code won't trigger the original error.
except BaseException as err:
    print(err)
    print("out1", len(reader.__next__()))
    print("out2", len(reader.__next__()))

print("closing")
reader.close()
print("closed")
