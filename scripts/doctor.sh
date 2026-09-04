#!/bin/sh

set -u

ok=0
required_missing=0
optional_missing=0

check_required_command() {
    if command -v "$1" >/dev/null 2>&1; then
        printf '[OK]   %-14s %s\n' "$1" "$(command -v "$1")"
        ok=$((ok + 1))
    else
        printf '[MISS] %-14s %s\n' "$1" "$2"
        required_missing=$((required_missing + 1))
    fi
}

check_optional_command() {
    if command -v "$1" >/dev/null 2>&1; then
        printf '[OK]   %-14s %s\n' "$1" "$(command -v "$1")"
        ok=$((ok + 1))
    else
        printf '[OPT]  %-14s %s\n' "$1" "$2"
        optional_missing=$((optional_missing + 1))
    fi
}

printf 'Cyber Companion doctor\n\n'

check_required_command hyprctl 'required for Hyprland integration'
check_required_command make 'required to build Wayland V-Pets'
check_required_command pkg-config 'required to locate Wayland libraries'
check_required_command python3 'required to build Wisp Visual v0.12'
check_optional_command playerctl 'required by the current MPRIS system launcher'
check_optional_command virsh 'planned Windows VM adapter'

if command -v python3 >/dev/null 2>&1; then
    if pillow_version=$(python3 -c 'import PIL; print(PIL.__version__)' 2>/dev/null); then
        printf '[OK]   %-14s %s\n' Pillow "$pillow_version"
        ok=$((ok + 1))
    else
        printf '[MISS] %-14s required at build time for Wisp Visual v0.12\n' Pillow
        required_missing=$((required_missing + 1))
    fi
fi

if command -v cmake >/dev/null 2>&1; then
    cmake_version=$(cmake --version | sed -n '1s/.* //p')
    cmake_major=${cmake_version%%.*}
    cmake_rest=${cmake_version#*.}
    cmake_minor=${cmake_rest%%.*}
    if [ "$cmake_major" -gt 3 ] || { [ "$cmake_major" -eq 3 ] && [ "$cmake_minor" -ge 24 ]; }; then
        printf '[OK]   %-14s %s (>= 3.24)\n' cmake "$cmake_version"
        ok=$((ok + 1))
    else
        printf '[MISS] %-14s %s; version 3.24 or newer is required\n' cmake "$cmake_version"
        required_missing=$((required_missing + 1))
    fi
else
    printf '[MISS] %-14s required to build Wayland V-Pets\n' cmake
    required_missing=$((required_missing + 1))
fi

compiler_ok=0
if command -v gcc >/dev/null 2>&1; then
    gcc_version=$(gcc -dumpfullversion -dumpversion)
    gcc_major=${gcc_version%%.*}
    if [ "$gcc_major" -ge 15 ]; then
        printf '[OK]   %-14s %s (>= 15)\n' gcc "$gcc_version"
        compiler_ok=1
        ok=$((ok + 1))
    else
        printf '[OLD]  %-14s %s; upstream requires GCC 15 or newer\n' gcc "$gcc_version"
    fi
fi

if command -v clang >/dev/null 2>&1; then
    clang_version=$(clang -dumpversion)
    clang_major=${clang_version%%.*}
    if [ "$clang_major" -ge 19 ]; then
        printf '[OK]   %-14s %s (>= 19)\n' clang "$clang_version"
        compiler_ok=1
        ok=$((ok + 1))
    else
        printf '[OLD]  %-14s %s; upstream requires Clang 19 or newer\n' clang "$clang_version"
    fi
fi

if [ "$compiler_ok" -eq 0 ]; then
    printf '[MISS] A supported compiler is required: GCC >= 15 or Clang >= 19\n'
    required_missing=$((required_missing + 1))
fi

printf '\nSession: %s\n' "${XDG_SESSION_TYPE:-unknown}"

if [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
    printf '[OK]   Hyprland session detected\n'
    ok=$((ok + 1))
else
    printf '[MISS] Hyprland session not detected\n'
    required_missing=$((required_missing + 1))
fi

for module in wayland-client libudev; do
    if module_version=$(pkg-config --modversion "$module" 2>/dev/null); then
        printf '[OK]   %s %s\n' "$module" "$module_version"
        ok=$((ok + 1))
    else
        printf '[MISS] %s development metadata\n' "$module"
        required_missing=$((required_missing + 1))
    fi
done

printf '\nMonitors:\n'
if command -v hyprctl >/dev/null 2>&1; then
    hyprctl monitors 2>/dev/null | sed -n 's/^Monitor /  /p'
fi

printf '\nResult: %s passed, %s required missing, %s optional missing.\n' \
    "$ok" "$required_missing" "$optional_missing"

if [ "$required_missing" -gt 0 ]; then
    exit 1
fi
