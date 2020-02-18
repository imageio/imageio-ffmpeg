""" Invoke tasks for imageio-ffmpeg
"""

import os
import sys
import shutil
import importlib
import subprocess
from urllib.request import urlopen

from invoke import task

# ---------- Per project config ----------

NAME = "imageio-ffmpeg"
LIBNAME = NAME.replace("-", "_")
PY_PATHS = [LIBNAME, "tests", "tasks.py", "setup.py"]  # for linting/formatting

# ----------------------------------------

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if not os.path.isdir(os.path.join(ROOT_DIR, LIBNAME)):
    sys.exit("package NAME seems to be incorrect.")


@task
def test(ctx, cover=False):
    """Perform unit tests. Use --cover to open a webbrowser to show coverage.
    """
    cmd = [sys.executable, "-m", "pytest", "tests"]
    cmd += ["--cov=" + LIBNAME, "--cov-report=term", "--cov-report=html"]
    ret_code = subprocess.call(cmd, cwd=ROOT_DIR)
    if ret_code:
        sys.exit(ret_code)
    if cover:
        import webbrowser

        webbrowser.open(os.path.join(ROOT_DIR, "htmlcov", "index.html"))


@task
def lint(ctx):
    """ Validate the code style (e.g. undefined names)
    """
    try:
        importlib.import_module("flake8")
    except ImportError:
        sys.exit("You need to ``pip install flake8`` to lint")

    print("Checking linting errors with flake8:")

    # We use flake8 with minimal settings
    # http://pep8.readthedocs.io/en/latest/intro.html#error-codes
    cmd = [sys.executable, "-m", "flake8"] + PY_PATHS + ["--select=F,E11"]
    ret_code = subprocess.call(cmd, cwd=ROOT_DIR)
    if ret_code == 0:
        print("No linting errors found")
    else:
        sys.exit(ret_code)


@task
def checkformat(ctx):
    """ Check whether the code adheres to the style rules. Use autoformat to fix.
    """
    print("Checking format with black (also see invoke autoformat):")
    black_wrapper(False)


@task
def autoformat(ctx):
    """ Automatically format the code (using black).
    """
    print("Auto-formatting with black:")
    black_wrapper(True)


@task
def clean(ctx):
    """ Clean the repo of temp files etc.
    """
    for root, dirs, files in os.walk(ROOT_DIR):
        for dname in dirs:
            if dname in (
                "__pycache__",
                ".cache",
                "htmlcov",
                ".hypothesis",
                ".pytest_cache",
                "dist",
                "build",
                LIBNAME + ".egg-info",
            ):
                shutil.rmtree(os.path.join(root, dname))
                print("Removing", dname)
        for fname in files:
            if fname.endswith((".pyc", ".pyo")) or fname in (".coverage"):
                os.remove(os.path.join(root, fname))
                print("Removing", fname)


##


@task
def get_ffmpeg_binary(ctx):
    """ Download/copy ffmpeg binary for local development.
    """
    # Get ffmpeg fname
    sys.path.insert(0, os.path.join(ROOT_DIR, "imageio_ffmpeg"))
    try:
        from _definitions import FNAME_PER_PLATFORM, get_platform
    finally:
        sys.path.pop(0)
    fname = FNAME_PER_PLATFORM[get_platform()]

    # Clear
    clear_binaries_dir(os.path.join(ROOT_DIR, "imageio_ffmpeg", "binaries"))

    # Use local if we can (faster)
    source_dir = os.path.abspath(
        os.path.join(ROOT_DIR, "..", "imageio-binaries", "ffmpeg")
    )
    if os.path.isdir(source_dir):
        copy_binaries(os.path.join(ROOT_DIR, "imageio_ffmpeg", "binaries"), fname)
        return

    # Download from Github
    base_url = "https://github.com/imageio/imageio-binaries/raw/master/ffmpeg/"
    filename = os.path.join(ROOT_DIR, "imageio_ffmpeg", "binaries", fname)
    print("Downloading", fname, "...", end="")
    with urlopen(base_url + fname, timeout=5) as f1:
        with open(filename, "wb") as f2:
            shutil.copyfileobj(f1, f2)
    # Mark executable
    os.chmod(filename, os.stat(filename).st_mode | 64)
    print("done")


@task
def build(ctx):
    """ Build packages for different platforms. Dont release yet.
    """

    # Get version and more
    sys.path.insert(0, os.path.join(ROOT_DIR, "imageio_ffmpeg"))
    try:
        from _definitions import __version__, FNAME_PER_PLATFORM, WHEEL_BUILDS
    finally:
        sys.path.pop(0)

    # Clear up any build artifacts
    clean(ctx)

    # Clear binaries, we don't want them in the reference release
    clear_binaries_dir(
        os.path.abspath(os.path.join(ROOT_DIR, "imageio_ffmpeg", "binaries"))
    )

    # Now build a universal wheel
    print("Using setup.py to generate wheel... ", end="")
    subprocess.check_output(
        [sys.executable, "setup.py", "sdist", "bdist_wheel"], cwd=ROOT_DIR
    )
    print("done")

    # Prepare
    dist_dir = os.path.join(ROOT_DIR, "dist")
    fname = "imageio_ffmpeg-" + __version__ + "-py3-none-any.whl"
    packdir = "imageio_ffmpeg-" + __version__
    infodir = "imageio_ffmpeg-" + __version__ + ".dist-info"
    wheelfile = os.path.join(dist_dir, packdir, infodir, "WHEEL")
    assert os.path.isfile(os.path.join(dist_dir, fname))

    # Unpack
    print("Unpacking ... ", end="")
    subprocess.check_output(
        [sys.executable, "-m", "wheel", "unpack", fname], cwd=dist_dir
    )
    os.remove(os.path.join(dist_dir, packdir, infodir, "RECORD"))
    print("done")

    # Build for different platforms
    for wheeltag, platform in WHEEL_BUILDS.items():
        ffmpeg_fname = FNAME_PER_PLATFORM[platform]

        # Edit
        print("Edit for {} ({})".format(platform, wheeltag))
        copy_binaries(
            os.path.join(dist_dir, packdir, "imageio_ffmpeg", "binaries"), ffmpeg_fname
        )
        make_platform_specific(wheelfile, wheeltag)

        # Pack
        print("Pack ... ", end="")
        subprocess.check_output(
            [sys.executable, "-m", "wheel", "pack", packdir], cwd=dist_dir
        )
        print("done")

    # Clean up
    os.remove(os.path.join(dist_dir, fname))
    shutil.rmtree(os.path.join(dist_dir, packdir))

    # Show overview
    print("Dist folder:")
    for fname in sorted(os.listdir(dist_dir)):
        s = os.stat(os.path.join(dist_dir, fname)).st_size
        print("  {:0.0f} KiB  {}".format(s / 2 ** 10, fname))
    if sys.platform.startswith("win"):
        print("Note that the exes for Linux/OSX are not chmodded properly!")


@task
def release(ctx):
    """ Release the packages to Pypi!
    """
    dist_dir = os.path.join(ROOT_DIR, "dist")
    if not os.path.isdir(dist_dir):
        sys.exit("Dist directory does not exist. Build first?")

    print("This is what you are about to upload:")
    for fname in sorted(os.listdir(dist_dir)):
        s = os.stat(os.path.join(dist_dir, fname)).st_size
        print("  {:0.0f} KiB  {}".format(s / 2 ** 10, fname))

    while True:
        x = input("Are you sure you want to upload now? [Y/N]: ")
        if x.upper() == "N":
            return
        elif x.upper() == "Y":
            break

    if sys.platform.startswith("win"):
        sys.exit("Cannot release from Windows: the exes wont be chmodded properly!")

    subprocess.check_call([sys.executable, "-m", "twine", "upload", "dist/*"])


@task
def update_readme(ctx):
    """Update readme to include the latest API docs.
    """
    text = open(os.path.join(ROOT_DIR, "README.md"), "rb").read().decode()
    text = text.split("\n## API\n")[0] + "\n## API\n\n"

    import inspect
    import imageio_ffmpeg

    for func in (
        imageio_ffmpeg.read_frames,
        imageio_ffmpeg.write_frames,
        imageio_ffmpeg.count_frames_and_secs,
        imageio_ffmpeg.get_ffmpeg_exe,
        imageio_ffmpeg.get_ffmpeg_version,
    ):
        source = inspect.getsourcelines(func)[0]
        stripped = [x.strip() for x in source]
        end = stripped.index('"""', stripped.index('"""') + 1) + 1
        text += "```py\n" + "".join(source[:end]) + "```\n\n"

    with open(os.path.join(ROOT_DIR, "README.md"), "wb") as f:
        f.write(text.encode())


##


def black_wrapper(writeback):
    """ Helper function to invoke black programatically.
    """

    check = [] if writeback else ["--check"]
    exclude = "|".join(["cangivefilenameshere"])
    sys.argv[1:] = check + ["--exclude", exclude, ROOT_DIR]

    import black

    black.main()


def clear_binaries_dir(target_dir):
    assert os.path.isdir(target_dir)
    for fname in os.listdir(target_dir):
        if fname != "README.md":
            print("Removing", fname, "...", end="")
            os.remove(os.path.join(target_dir, fname))
            print("done")


def copy_binaries(target_dir, fname):
    # Get source dir - the imageio-binaries repo must be present
    source_dir = os.path.abspath(
        os.path.join(ROOT_DIR, "..", "imageio-binaries", "ffmpeg")
    )
    if not os.path.isdir(source_dir):
        sys.exit("Need to clone imageio-binaries next to this repo to do a release!")

    clear_binaries_dir(target_dir)
    print("Copying", fname, "...", end="")
    filename = os.path.join(target_dir, fname)
    shutil.copy2(os.path.join(source_dir, fname), filename)
    # Mark as exe. This does not actually do anything on Windows.
    os.chmod(filename, os.stat(filename).st_mode | 64)
    print("done")


def make_platform_specific(filename, tag):
    with open(filename, "rb") as f:
        text = f.read().decode()

    lines = []
    for line in text.splitlines():
        if line.startswith("Root-Is-Purelib:"):
            line = "Root-Is-Purelib: true"
        elif line.startswith("Tag:"):
            line = "Tag: " + tag
        lines.append(line)
    text = "\n".join(lines).strip() + "\n"
    with open(filename, "wb") as f:
        f.write(text.encode())
