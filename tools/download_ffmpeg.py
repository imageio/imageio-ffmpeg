#!/usr/bin/env python3
"""Download the ffmpeg executables that are shipped in the imageio-ffmpeg wheels.

    download_ffmpeg.py fetch [--platforms LIST] [--out DIR]
    download_ffmpeg.py check
    download_ffmpeg.py update [--platforms LIST] [--out DIR]

fetch   Download the binaries pinned in tools/ffmpeg-sources.json, verify them
        against the pinned SHA-256 hashes and extract the ffmpeg executable.
        LIST is "current" (default: the platform of this machine), "all" or a
        comma-separated list of platforms.
check   Compare the pinned versions with the newest upstream releases.
update  Download the newest upstream releases, verify them against what the
        upstream publishes (checksums, GPG signature), and pin them in
        tools/ffmpeg-sources.json and imageio_ffmpeg/_definitions.py.
        LIST is "outdated" (default), "all" or a comma-separated list.

Upstream sources (preferring GitHub releases where available):

    linux-*          https://github.com/BtbN/FFmpeg-Builds (gpl, release branch;
                     static except for glibc >= 2.28). Only month-end builds
                     are used, as BtbN deletes daily builds after 14 days.
    windows-x86_64   https://github.com/GyanD/codexffmpeg (release mirror of
                     https://www.gyan.dev/ffmpeg/builds/, essentials)
    windows-aarch64  https://github.com/BtbN/FFmpeg-Builds (gpl, release branch)
    macos-x86_64     https://evermeet.cx/ffmpeg/ (GPG-signed, see tools/keys/)
    macos-aarch64    https://www.osxexperts.net/ (evermeet.cx has no ARM builds)
    windows-i686     no upstream builds anymore; the old binary from
                     https://github.com/imageio/imageio-binaries is pinned.

When run in GitHub Actions, results are also written to the job summary.
Only the Python standard library is used (plus gpgv for `update`).
"""

import argparse
import base64
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
MANIFEST = TOOLS_DIR / "ffmpeg-sources.json"
DEFINITIONS = ROOT / "imageio_ffmpeg" / "_definitions.py"
DEFAULT_OUT = ROOT / "ffmpeg-downloads"

GHA = os.environ.get("GITHUB_ACTIONS") == "true"
UA = {"User-Agent": "imageio-ffmpeg-build"}


# --- Helpers ------------------------------------------------------------------


def get(url, headers=None, attempts=5):
    """GET url, retrying transient errors (connection, TLS, timeouts, 408/429/5xx)."""
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            # Client errors other than rate limiting will not go away.
            if (e.code < 500 and e.code not in (408, 429)) or attempt == attempts:
                raise
            error = e
        except (urllib.error.URLError, OSError) as e:
            if attempt == attempts:
                raise
            error = e
        print(
            f"  attempt {attempt} for {url} failed ({error}), "
            f"retrying in {attempt * 10} s",
            flush=True,
        )
        time.sleep(attempt * 10)


def github_api(path):
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    return json.loads(get("https://api.github.com/" + path, headers))


def vkey(version):
    """Sort key for dotted numeric versions."""
    return tuple(int(x) for x in re.findall(r"\d+", version))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def fail(msg, platform=None):
    if GHA:
        title = "ffmpeg download failed" + (f" ({platform})" if platform else "")
        print(f"::error title={title}::{msg}", flush=True)
    sys.exit(msg)


def write_summary(text):
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text + "\n")


def get_platform():
    sys.path.insert(0, str(DEFINITIONS.parent))
    try:
        from _definitions import get_platform
    finally:
        sys.path.pop(0)
    return get_platform()


# --- Upstream sources ---------------------------------------------------------
# Each latest_* function returns a dict with: version, url, source, member
# (regex for the ffmpeg executable inside the archive) and checksums: a list of
# (description, sha256 hex) that the download must match. Optionally
# signature: (url of a detached GPG signature, key file, primary key fingerprint).

EVERMEET_KEY = (
    TOOLS_DIR / "keys" / "evermeet-0x1A660874.asc",
    "20F6EA3E0CFD6B4C53447A73476C4B611A660874",
)

# (release tag, target) of BtbN builds that are known to be broken.
BTBN_BROKEN = {
    # Crashes on start (0xC0000005), probably what BtbN/FFmpeg-Builds@9acad4a
    # fixed: "llvm-strip --strip-unneeded strips needed sections from PE files".
    ("autobuild-2026-09-30-13-08", "winarm64"),
}


def github_digest(asset):
    """The SHA-256 that GitHub computed when the release asset was uploaded."""
    digest = asset.get("digest") or ""
    if not digest.startswith("sha256:"):
        raise RuntimeError(f"no GitHub digest for {asset['name']}")
    return ("GitHub asset digest", digest.split(":", 1)[1])


def latest_btbn(target):
    # Dated releases have assets named after `git describe` of the release
    # branch, e.g. ffmpeg-n9.0.2-17-g2a571b6068-winarm64-gpl-9.0.zip (Windows)
    # or ...-linux64-gpl-9.0.tar.xz (Linux). Daily releases are deleted after
    # 14 days, the last build of each month is kept for two years.
    windows = target.startswith("win")
    ext, exe = (r"\.zip", r"\.exe") if windows else (r"\.tar\.xz", "")
    pattern = re.compile(
        r"ffmpeg-n(\d+\.\d+(?:\.\d+)?)-\d+-g[0-9a-f]+-"
        + target
        + r"-gpl-\d+\.\d+"
        + ext
        + "$"
    )
    for rel in github_api("repos/BtbN/FFmpeg-Builds/releases?per_page=40"):
        m = re.match(r"autobuild-(\d{4})-(\d\d)-(\d\d)-", rel["tag_name"])
        if not m:
            continue
        day = datetime.date(*map(int, m.groups()))
        if (day + datetime.timedelta(days=1)).month == day.month:
            continue  # not a month-end build
        if (rel["tag_name"], target) in BTBN_BROKEN:
            continue
        assets = {a["name"]: a for a in rel["assets"]}
        found = [
            (vkey(m.group(1)), m.group(1), name)
            for name in assets
            if (m := pattern.match(name))
        ]
        if not found:
            continue
        _, version, name = max(found)
        sums = get(assets["checksums.sha256"]["browser_download_url"]).decode()
        sha = next(line.split()[0] for line in sums.splitlines() if line.endswith(name))
        return dict(
            version=version,
            url=assets[name]["browser_download_url"],
            checksums=[
                ("BtbN checksums.sha256", sha),
                github_digest(assets[name]),
            ],
            member=r"/bin/ffmpeg" + exe + "$",
            source=f"BtbN/FFmpeg-Builds {rel['tag_name']}",
        )
    raise RuntimeError(f"no BtbN {target} month-end release found")


def latest_gyan():
    # GyanD/codexffmpeg mirrors the gyan.dev release builds as GitHub releases
    # tagged with the version (other tags are git master builds).
    version = get("https://www.gyan.dev/ffmpeg/builds/release-version")
    version = version.decode().strip()
    rel = github_api(f"repos/GyanD/codexffmpeg/releases/tags/{version}")
    name = f"ffmpeg-{version}-essentials_build.zip"
    asset = next((a for a in rel["assets"] if a["name"] == name), None)
    if asset is None:
        raise RuntimeError(f"{name} not found in GyanD/codexffmpeg {version}")
    # Cross-check with the checksum published on gyan.dev itself.
    gyan_url = f"https://www.gyan.dev/ffmpeg/builds/packages/{name}.sha256"
    gyan_sha = get(gyan_url).decode().split()[0]
    return dict(
        version=version,
        url=asset["browser_download_url"],
        checksums=[("gyan.dev .sha256", gyan_sha), github_digest(asset)],
        member=r"/bin/ffmpeg\.exe$",
        source=f"GyanD/codexffmpeg {version} (gyan.dev essentials)",
    )


def latest_evermeet():
    info = json.loads(get("https://evermeet.cx/ffmpeg/info/ffmpeg/release"))
    zip_ = info["download"]["zip"]
    return dict(
        version=info["version"],
        url=zip_["url"],
        checksums=[],
        signature=(zip_["sig"], *EVERMEET_KEY),
        member=r"^ffmpeg$",
        source="evermeet.cx",
    )


def latest_osxexperts(kind):
    html = get("https://www.osxexperts.net/").decode("utf-8", "replace")
    label = "Apple Silicon" if kind == "arm" else "Intel"
    m = re.search(
        r'href="(https://www\.osxexperts\.net/ffmpeg\d+'
        + kind
        + r'\.zip)"[^>]*>\s*Download ffmpeg ([\d.]+) \('
        + label,
        html,
    )
    if not m:
        raise RuntimeError(f"no ffmpeg ({label}) download found on osxexperts.net")
    return dict(
        version=m.group(2),
        url=m.group(1),
        checksums=[],
        member=r"(^|/)ffmpeg$",
        source="osxexperts.net",
    )


SOURCES = {
    "linux-x86_64": lambda: latest_btbn("linux64"),
    "linux-aarch64": lambda: latest_btbn("linuxarm64"),
    "macos-x86_64": latest_evermeet,
    "macos-aarch64": lambda: latest_osxexperts("arm"),
    "windows-x86_64": latest_gyan,
    "windows-aarch64": lambda: latest_btbn("winarm64"),
}


# --- Pins ---------------------------------------------------------------------


def load_manifest():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def save_manifest(manifest):
    text = json.dumps(dict(sorted(manifest.items())), indent=2) + "\n"
    MANIFEST.write_text(text, encoding="utf-8", newline="\n")


def output_name(platform, version):
    os_, arch = platform.split("-", 1)
    if os_ == "windows":
        return f"ffmpeg-win-{arch}-v{version}.exe"
    return f"ffmpeg-{platform}-v{version}"


def update_definitions(platform, fname):
    """Point FNAME_PER_PLATFORM in _definitions.py to the new file."""
    text = DEFINITIONS.read_text(encoding="utf-8")
    pattern = re.compile(r'^(\s*"' + re.escape(platform) + r'":\s*")[^"]*(")', re.M)
    text, n = pattern.subn(lambda m: m.group(1) + fname + m.group(2), text)
    if n != 1:
        raise RuntimeError(f"{platform} not found in FNAME_PER_PLATFORM")
    DEFINITIONS.write_text(text, encoding="utf-8", newline="\n")


def select(arg, choices, default_selection):
    if arg == "all":
        return list(choices)
    if arg in ("current", "outdated"):
        return default_selection
    names = [p.strip() for p in arg.split(",") if p.strip()]
    unknown = set(names) - set(choices)
    if unknown:
        sys.exit(
            f"unknown platform(s): {', '.join(sorted(unknown))}; "
            f"known: {', '.join(choices)}"
        )
    return names


def extract(data, url, member_re):
    if not member_re:
        return data  # the download is the executable itself
    member_re = re.compile(member_re)
    if url.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = [
                n for n in z.namelist() if member_re.search(n) and "__MACOSX" not in n
            ]
            if len(names) == 1:
                return z.read(names[0])
    else:
        with tarfile.open(fileobj=io.BytesIO(data)) as t:
            names = [
                m for m in t.getmembers() if m.isfile() and member_re.search(m.name)
            ]
            if len(names) == 1:
                return t.extractfile(names[0]).read()
    raise RuntimeError(f"expected one ffmpeg executable in {url}, found {names}")


def verify_signature(data, sig_url, keyfile, fingerprint):
    """Check a detached GPG signature with gpgv against a key pinned in the repo."""
    gpgv = os.environ.get("GPGV") or shutil.which("gpgv")
    if not gpgv:
        raise RuntimeError(
            "gpgv is needed to verify the download; install GnuPG or set GPGV"
        )
    # gpgv only reads binary keyrings, so strip the ASCII armor (and its CRC line).
    text = Path(keyfile).read_text().replace("\r\n", "\n")
    armored = text.split("-----BEGIN PGP PUBLIC KEY BLOCK-----")[1]
    body = armored.split("\n\n", 1)[1].split("-----END")[0]
    key = base64.b64decode(
        "".join(line for line in body.split() if not line.startswith("="))
    )
    with tempfile.TemporaryDirectory() as tmp:
        files = {"key.gpg": key, "data": data, "data.sig": get(sig_url)}
        for name, content in files.items():
            Path(tmp, name).write_bytes(content)
        r = subprocess.run(
            [gpgv, "--status-fd", "1", "--keyring", "./key.gpg", "data.sig", "data"],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
    # VALIDSIG <signing key fpr> ... <primary key fpr>
    valid = [
        line.split()[2:]
        for line in r.stdout.splitlines()
        if line.startswith("[GNUPG:] VALIDSIG ")
    ]
    if r.returncode or not any(fingerprint in fields for fields in valid):
        raise RuntimeError(
            f"GPG signature check failed for {sig_url}:\n{r.stdout}{r.stderr}"
        )


def write_exe(out, fname, exe):
    target = Path(out) / fname
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(exe)
    target.chmod(target.stat().st_mode | 0o755)
    return target


# --- Commands -----------------------------------------------------------------


def fetch(platforms="current", out=DEFAULT_OUT):
    """Download the pinned binaries for the given platforms into out.

    Returns a dict platform -> path of the executable. Files that are already
    present with the pinned hash are not downloaded again.
    """
    manifest = load_manifest()
    current = get_platform()
    if platforms == "current" and current not in manifest:
        sys.exit(f"no ffmpeg binary is available for this platform ({current})")
    selected = select(platforms, list(manifest), [current])
    rows = ["| File | Size | Source | SHA-256 |", "|---|---|---|---|"]
    result = {}
    for platform in selected:
        pin = manifest[platform]
        target = Path(out) / pin["file"]
        if target.is_file() and sha256(target.read_bytes()) == pin["exe_sha256"]:
            print(f"{target.name} is up to date")
            result[platform] = target
            continue
        print(f"Downloading {platform} ffmpeg {pin['version']}", flush=True)
        print(f"  {pin['url']}", flush=True)
        data = get(pin["url"])
        if sha256(data) != pin["sha256"]:
            fail(
                f"SHA-256 mismatch for {pin['url']}: "
                f"{sha256(data)} != {pin['sha256']} (pinned)",
                platform,
            )
        exe = extract(data, pin["url"], pin.get("member"))
        if sha256(exe) != pin["exe_sha256"]:
            fail(f"SHA-256 mismatch for the executable in {pin['url']}", platform)
        target = write_exe(out, pin["file"], exe)
        size = f"{len(exe) / 2**20:.1f} MiB"
        print(f"  -> {target} ({size}, SHA-256 verified)")
        rows.append(f"| `{target.name}` | {size} | {pin['source']} | `{sha256(exe)}` |")
        result[platform] = target
    if len(rows) > 2:
        write_summary("## Downloaded ffmpeg binaries\n\n" + "\n".join(rows))
    return result


def check():
    """Compare the pins with the newest upstream versions.

    Returns (upstream info per platform, list of outdated platforms).
    """
    manifest = load_manifest()
    upstream = {}
    outdated = []
    rows = ["| Platform | Pinned | Upstream | Source |", "|---|---|---|---|"]
    for platform in sorted(set(SOURCES) | set(manifest)):
        pinned = manifest.get(platform, {}).get("version", "-")
        if platform not in SOURCES:
            rows.append(f"| {platform} | {pinned} | - | no upstream build |")
            continue
        try:
            upstream[platform] = info = SOURCES[platform]()
        except Exception as e:  # report and continue with the other sources
            rows.append(f"| {platform} | {pinned} | error | {e} |")
            continue
        newer = platform not in manifest or vkey(info["version"]) > vkey(pinned)
        if newer:
            outdated.append(platform)
        rows.append(
            f"| {platform} | {pinned} | {info['version']}"
            f"{' **(newer)**' if newer else ''} | [{info['source']}]({info['url']}) |"
        )
    report = "\n".join(rows)
    print(report)
    print("\nOutdated:", ", ".join(outdated) or "nothing")
    write_summary("## Upstream ffmpeg builds\n\n" + report)
    return upstream, outdated


def update(platforms="outdated", out=DEFAULT_OUT):
    """Pin the newest upstream builds for the given platforms."""
    upstream, outdated = check()
    selected = select(platforms, list(SOURCES), outdated)
    manifest = load_manifest()
    for platform in selected:
        info = upstream.get(platform) or fail(f"no upstream info for {platform}")
        print(f"\nDownloading {platform} ffmpeg {info['version']}", flush=True)
        print(f"  {info['url']}", flush=True)
        data = get(info["url"])
        actual = sha256(data)
        verified = []
        for what, expected in info["checksums"]:
            if actual != expected.lower():
                fail(f"{what} mismatch for {info['url']}: {actual} != {expected}")
            verified.append(f"SHA-256 matches {what}")
        if info.get("signature"):
            try:
                verify_signature(data, *info["signature"])
            except RuntimeError as e:
                fail(str(e), platform)
            verified.append("GPG signature verified")
        if not verified:
            print(f"  WARNING: {info['source']} publishes no checksum or signature")
        verified = "; ".join(verified) or "nothing published upstream"
        print(f"  {verified}")
        fname = output_name(platform, info["version"])
        exe = extract(data, info["url"], info["member"])
        target = write_exe(out, fname, exe)
        print(f"  -> {target} ({len(exe) / 2**20:.1f} MiB)")
        manifest[platform] = dict(
            file=fname,
            version=info["version"],
            source=info["source"],
            url=info["url"],
            sha256=actual,
            verified=verified,
            member=info["member"],
            exe_sha256=sha256(exe),
        )
        save_manifest(manifest)
        update_definitions(platform, fname)
    if selected:
        print("\nUpdated tools/ffmpeg-sources.json and imageio_ffmpeg/_definitions.py.")
        print("Check that WHEEL_BUILDS still fits (invoke check-binaries).")


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("command", choices=["fetch", "check", "update"])
    p.add_argument("--platforms", default=None)
    p.add_argument("--out", default=str(DEFAULT_OUT))
    args = p.parse_args()
    if args.command == "fetch":
        fetch(args.platforms or "current", args.out)
    elif args.command == "check":
        check()
    else:
        update(args.platforms or "outdated", args.out)


if __name__ == "__main__":
    main()
