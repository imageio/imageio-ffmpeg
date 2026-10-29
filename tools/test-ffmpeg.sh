#!/usr/bin/env bash
# Smoke-test an ffmpeg executable the way imageio-ffmpeg uses it: encode test
# videos/audio with each available library encoder, then decode the frames
# through a raw video pipe and check the byte count.
#
# Usage: tools/test-ffmpeg.sh FFMPEG [REQUIRED_ENCODER...]
#   REQUIRED_ENCODER defaults to libx264 (imageio-ffmpeg's default codec).
#
# In GitHub Actions, the result is added to the job summary (labelled with
# $TEST_NAME, default "Smoke test") and failures are reported as annotations.
set -euo pipefail

ff=$1
shift
# Absolute, as some tests run in the temporary directory.
ff="$(cd "$(dirname "$ff")" && pwd)/$(basename "$ff")"
required=("${@:-libx264}")
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
passed=() skipped=()
summary_file="${GITHUB_STEP_SUMMARY:-}"
if [[ -n "$summary_file" ]] && command -v cygpath >/dev/null; then
    summary_file="$(cygpath -u "$summary_file")"
fi
summary() {
    if [[ -n "$summary_file" ]]; then
        printf '%s **%s** `%s`: %s\n\n' "$1" "${TEST_NAME:-Smoke test}" "$(basename "$ff")" "$2" \
            >> "$summary_file"
    fi
}
fail() {
    echo "FAIL: $*" >&2
    if [[ "${GITHUB_ACTIONS:-}" == true ]]; then
        echo "::error title=${TEST_NAME:-Smoke test} failed ($(basename "$ff"))::$*"
    fi
    summary "❌" "failed: $*"
    exit 1
}
export SVT_LOG=1  # only errors from SVT-AV1, which ignores ffmpeg's -v

version="$("$ff" -hide_banner -version)"
echo "${version%%$'\n'*}"
encoders="$("$ff" -hide_banner -encoders)"
for e in "${required[@]}"; do
    grep -qE "^ [^ ]+ $e " <<< "$encoders" || fail "missing required encoder $e"
done

w=128 h=96 n=10
for spec in "libx264 mp4" "libx265 mp4" "libvpx-vp9 webm" "libsvtav1 mkv" "libaom-av1 mkv" \
    "libtheora ogv" "mpeg4 avi"; do
    read -r codec ext <<< "$spec"
    grep -qE "^ [^ ]+ $codec " <<< "$encoders" || { echo "skip $codec (not available)"; skipped+=("$codec"); continue; }
    out="$tmp/$codec.$ext"
    extra=()
    # libaom's default speed is very slow.
    [[ $codec == libaom-av1 ]] && extra=(-cpu-used 8)
    "$ff" -nostdin -v error -f lavfi -i "testsrc=size=${w}x${h}:rate=10" -frames:v $n \
        -c:v "$codec" ${extra[@]+"${extra[@]}"} -pix_fmt yuv420p -y "$out" || fail "encoding with $codec"
    bytes=$("$ff" -nostdin -v error -i "$out" -f image2pipe -pix_fmt rgb24 -vcodec rawvideo - | wc -c)
    (( bytes == n * w * h * 3 )) || fail "$codec: decoded $bytes bytes, expected $((n * w * h * 3))"
    echo "ok   $codec ($ext)"
    passed+=("$codec")
done

if grep -qE "^ [^ ]+ libwebp " <<< "$encoders"; then
    out="$tmp/libwebp.webp"
    "$ff" -nostdin -v error -f lavfi -i "testsrc=size=${w}x${h}" -frames:v 1 -c:v libwebp -y "$out" \
        || fail "encoding with libwebp"
    bytes=$("$ff" -nostdin -v error -i "$out" -f image2pipe -pix_fmt rgb24 -vcodec rawvideo - | wc -c)
    (( bytes == w * h * 3 )) || fail "libwebp: decoded $bytes bytes, expected $((w * h * 3))"
    echo "ok   libwebp (webp)"
    passed+=("libwebp")
else
    echo "skip libwebp (not available)"; skipped+=("libwebp")
fi

# HAP needs libsnappy.
if grep -qE "^ [^ ]+ hap " <<< "$encoders"; then
    out="$tmp/hap.mov"
    "$ff" -nostdin -v error -f lavfi -i "testsrc=size=${w}x${h}:rate=10" -frames:v $n \
        -c:v hap -pix_fmt rgba -y "$out" || fail "encoding with hap"
    bytes=$("$ff" -nostdin -v error -i "$out" -f image2pipe -pix_fmt rgb24 -vcodec rawvideo - | wc -c)
    (( bytes == n * w * h * 3 )) || fail "hap: decoded $bytes bytes, expected $((n * w * h * 3))"
    echo "ok   hap (mov)"
    passed+=("hap")
else
    echo "skip hap (not available)"; skipped+=("hap")
fi

# codec, file extension, encoder options (speech codecs need specific sample rates)
for spec in "libmp3lame mp3" "libopus opus" "libvorbis ogg" "libspeex spx -ar 16000" \
    "libgsm gsm -ar 8000" "libopencore_amrnb amr -ar 8000 -b:a 12.2k" \
    "libvo_amrwbenc amr -ar 16000 -b:a 23.85k"; do
    read -r codec ext args <<< "$spec"
    read -ra args <<< "$args"
    grep -qE "^ [^ ]+ $codec " <<< "$encoders" || { echo "skip $codec (not available)"; skipped+=("$codec"); continue; }
    out="$tmp/$codec.$ext"
    "$ff" -nostdin -v error -f lavfi -i "sine=frequency=440:duration=1" -c:a "$codec" \
        ${args[@]+"${args[@]}"} -y "$out" || fail "encoding with $codec"
    "$ff" -nostdin -v error -i "$out" -f null - || fail "decoding $codec"
    echo "ok   $codec ($ext)"
    passed+=("$codec")
done

# Filters from external libraries, if built in. Relative paths: vid.stab's
# file options are not converted by MSYS for native Windows executables.
# vid.stab 1.1.1's packed-RGB code reads past the frame, so test with YUV.
filters="$("$ff" -hide_banner -filters)"
for spec in "zscale|-vf|zscale=w=64:h=48:filter=lanczos" \
    "vidstabdetect|-vf|format=yuv420p,vidstabdetect=result=vidstab.trf" \
    "vidstabtransform|-vf|format=yuv420p,vidstabtransform=input=vidstab.trf" \
    "aresample|-af|aresample=resampler=soxr:osr=22050" \
    "drawtext|-vf|null"; do
    IFS='|' read -r filter opt arg <<< "$spec"
    if ! grep -qE "^ [^ ]+ $filter " <<< "$filters"; then
        echo "skip $filter (not available)"; skipped+=("$filter"); continue
    fi
    if [[ $filter == aresample ]]; then
        grep -q -- '--enable-libsoxr' <<< "$version" || { echo "skip soxr (not available)"; skipped+=("soxr"); continue; }
        filter=soxr
        input=(-f lavfi -i "sine=frequency=440:duration=1")
    else
        input=(-f lavfi -i "testsrc=size=${w}x${h}:rate=10" -frames:v $n)
    fi
    # drawtext needs a font file (no fontconfig); only check that it is there.
    if [[ $filter != drawtext ]]; then
        (cd "$tmp" && "$ff" -nostdin -v error "${input[@]}" "$opt" "$arg" -f null -) \
            || fail "filter $filter"
    fi
    echo "ok   filter $filter"
    passed+=("$filter")
done

echo "All tests passed"
result="passed: $(IFS=,; echo "${passed[*]}" | sed 's/,/, /g')"
if ((${#skipped[@]})); then result+="; not available: $(IFS=,; echo "${skipped[*]}" | sed 's/,/, /g')"; fi
summary "✅" "$result"
