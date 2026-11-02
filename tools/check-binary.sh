#!/usr/bin/env bash
# Report the platform baseline of ffmpeg executables and check that they are
# self-contained, using `file` and `llvm-readobj` (works for ELF, Mach-O and PE
# from any host).
#
# Usage: tools/check-binary.sh [--max-macos VERSION] [--max-glibc VERSION]
#                              [--max-size-mib N] FILE...
#
# Checks (non-zero exit on failure):
#   * the architecture matches the one in the file name (ffmpeg-<os>-<arch>-...)
#   * the file is smaller than --max-size-mib (GitHub rejects files over 100 MiB
#     in git, release assets may be up to 2 GiB)
#   * Linux: fully static, or linked only against glibc's own libraries (and
#     libgcc_s); newest required GLIBC_* symbol version <= --max-glibc
#   * macOS: only system libraries/frameworks; minimum macOS <= --max-macos
#   * Windows: only Windows system DLLs are imported
set -euo pipefail

MAX_MACOS=""
MAX_GLIBC=""
MAX_SIZE_MIB=""
while [[ "${1:-}" == --* ]]; do
    case "$1" in
        --max-macos) MAX_MACOS=$2 ;;
        --max-glibc) MAX_GLIBC=$2 ;;
        --max-size-mib) MAX_SIZE_MIB=$2 ;;
        *) echo "unknown option $1" >&2; exit 2 ;;
    esac
    shift 2
done
[[ $# -gt 0 ]] || { echo "usage: $0 [--max-macos VERSION] [--max-glibc VERSION] [--max-size-mib N] FILE..." >&2; exit 2; }

READOBJ="${LLVM_READOBJ:-$(command -v llvm-readobj || true)}"
if [[ -z "$READOBJ" ]]; then
    READOBJ="$(ls /usr/bin/llvm-readobj-* /usr/lib/llvm*/bin/llvm-readobj 2>/dev/null | sort -V | tail -n1 || true)"
fi
[[ -x "$READOBJ" ]] || { echo "llvm-readobj not found (install llvm)" >&2; exit 2; }

# Libraries that are part of glibc itself (plus libgcc_s, which every glibc
# system has), i.e. what a manylinux wheel may depend on without bundling.
GLIBC_LIBS='^(ld-linux[-a-z0-9_.]*\.so\.[0-9]+|(libc|libm|libmvec|libdl|libpthread|librt|libresolv|libutil|libgcc_s)\.so\.[0-9]+)$'

WIN_SYSTEM_DLLS='^(api-ms-win-.*|advapi32|avicap32|avrt|bcrypt|bcryptprimitives|cfgmgr32|comctl32|comdlg32|crypt32|d2d1|d3d9|d3d11|d3d12|d3dcompiler_47|dnsapi|dwmapi|dwrite|dxgi|dxva2|evr|gdi32|gdiplus|imm32|iphlpapi|kernel32|mf|mfplat|mfreadwrite|msimg32|msvcrt|ncrypt|normaliz|ntdll|ole32|oleaut32|opengl32|powrprof|propsys|psapi|rpcrt4|secur32|setupapi|shell32|shlwapi|ucrtbase|user32|userenv|uxtheme|version|vfw32|windowscodecs|winmm|wintrust|ws2_32|wsock32)\.dll$'

version_le() { [[ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n1)" == "$1" ]]; }

failed=0
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    printf '### Platform baseline\n\n| File | Size (MiB) | Type | Baseline | Status |\n|---|---|---|---|---|\n' >> "$GITHUB_STEP_SUMMARY"
fi

for f in "$@"; do
    name="$(basename "$f")"
    desc="$(file -b "$f")"
    size=$(wc -c < "$f")
    libs="$("$READOBJ" --needed-libs "$f" | sed -n '/NeededLibraries \[/,/^\]/p' | sed '1d;$d;s/^ *//')"
    errors=()
    baseline=""

    case "$name" in
        *-x86_64-*) arch_re='x86-64|x86_64' ;;
        *-aarch64-*) arch_re='aarch64|arm64' ;;
        *-i686-*) arch_re='80386|i386' ;;
        *) arch_re='' ;;
    esac
    if [[ -n "$arch_re" ]] && ! grep -qiE "$arch_re" <<< "$desc"; then
        errors+=("architecture does not match file name")
    fi
    if [[ -n "$MAX_SIZE_MIB" ]] && (( size >= MAX_SIZE_MIB * 1024 * 1024 )); then
        errors+=("larger than $MAX_SIZE_MIB MiB")
    fi

    case "$desc" in
        ELF*)
            kernel="$(grep -oE ', for GNU/Linux [0-9.]+' <<< "$desc" | sed 's/, for GNU\/Linux / (kernel >= /;s/$/)/' || true)"
            if [[ -z "$libs" ]]; then
                baseline="static$kernel"
            else
                bad="$(grep -vE "$GLIBC_LIBS" <<< "$libs" || true)"
                [[ -z "$bad" ]] || errors+=("non-glibc libraries: $(echo $bad)")
                versions="$("$READOBJ" --version-info "$f" | grep -oE 'GLIBC_([0-9.]+|PRIVATE)' | sort -u || true)"
                glibc="$(grep -oE '[0-9]+(\.[0-9]+)+' <<< "$versions" | sort -V | tail -n1 || true)"
                baseline="glibc >= ${glibc:-unknown}$kernel"
                # Private glibc interfaces are not covered by its ABI guarantee.
                if grep -q PRIVATE <<< "$versions"; then baseline+=", uses GLIBC_PRIVATE"; fi
                if [[ -n "$MAX_GLIBC" ]] && ! version_le "${glibc:-999}" "$MAX_GLIBC"; then
                    errors+=("requires glibc ${glibc:-unknown}, more than $MAX_GLIBC")
                fi
            fi
            ;;
        Mach-O*)
            bad="$(grep -vE '^(/usr/lib/|/System/Library/)' <<< "$libs" || true)"
            [[ -z "$bad" ]] || errors+=("non-system libraries: $(echo $bad)")
            minos="$("$READOBJ" --macho-version-min "$f" | awk '/Version:/ {print $2; exit}')"
            baseline="macOS >= ${minos:-unknown}"
            if [[ -n "$MAX_MACOS" ]] && ! version_le "${minos:-999}" "$MAX_MACOS"; then
                errors+=("requires macOS $minos, more than $MAX_MACOS")
            fi
            ;;
        PE*)
            bad="$(grep -viE "$WIN_SYSTEM_DLLS" <<< "$libs" || true)"
            [[ -z "$bad" ]] || errors+=("non-system DLLs: $(echo $bad)")
            crt="static CRT"
            grep -qiE '^msvcrt\.dll$' <<< "$libs" && crt="msvcrt"
            grep -qiE '^(ucrtbase|api-ms-win-crt-)' <<< "$libs" && crt="UCRT"
            subsys="$("$READOBJ" --file-headers "$f" | awk '/MajorSubsystemVersion/ {ma=$2} /MinorSubsystemVersion/ {mi=$2} END {print ma "." mi}')"
            baseline="PE subsystem $subsys, $crt"
            ;;
        *)
            errors+=("unknown executable type")
            ;;
    esac

    echo "== $name"
    echo "   $desc"
    echo "   size: $((size / 1024 / 1024)) MiB; baseline: $baseline"
    echo "   needs: $(echo ${libs:-nothing})"
    status=OK
    for e in "${errors[@]}"; do
        echo "   ERROR: $e"
        status="FAILED: ${errors[*]}"
        failed=1
    done
    if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
        printf '| %s | %s | %s | %s | %s |\n' "$name" "$((size / 1024 / 1024))" \
            "${desc%%,*}" "$baseline" "$status" >> "$GITHUB_STEP_SUMMARY"
    fi
done
exit $failed
