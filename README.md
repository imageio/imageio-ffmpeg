# imageio-ffmpeg
FFMPEG functionality for imageio

The purpose of this project is to take care of some of the difficulty
of imageio's ffmpeg plugin. It takes care of producing platform-specific
wheels that include the binary executables of ffmpeg. These
can then be installed (and updated, and uninstalled) easily with pip.

(For those interested, the actual binaries are on https://github.com/imageio/imageio-binaries.)

Maybe the purpose ends there. Though I think I'll also move some of the actual
wrapping here, and thus make imageio a bit lighter. This repo can then
also be used by itself.
