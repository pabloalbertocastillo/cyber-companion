#!/bin/sh

set -u

ok=0
warn=0

check_command() {
    if command -v "$1" >/dev/null 2>&1; then
        printf '[OK]   %-14s %s\n' "$1" "$(command -v "$1")"
        ok=$((ok + 1))
    else
        printf '[MISS] %-14s %s\n' "$1" "$2"
        warn=$((warn + 1))
    fi
}

printf 'Cyber Companion doctor\n\n'

check_command hyprctl 'required for Hyprland integration'
check_command cmake 'required to build Wayland V-Pets'
check_command make 'required to build Wayland V-Pets'
check_command pkg-config 'required to locate Wayland libraries'
check_command gcc 'upstream currently requires GCC 15 or newer'
check_command clang 'Clang 19 or newer can be used instead of GCC'
check_command playerctl 'planned MPRIS adapter'
check_command virsh 'planned Windows VM adapter'

printf '\nSession: %s\n' "${XDG_SESSION_TYPE:-unknown}"

if [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
    printf '[OK]   Hyprland session detected\n'
    ok=$((ok + 1))
else
    printf '[MISS] Hyprland session not detected\n'
    warn=$((warn + 1))
fi

if wayland_version=$(pkg-config --modversion wayland-client 2>/dev/null); then
    printf '[OK]   wayland-client %s\n' "$wayland_version"
    ok=$((ok + 1))
else
    printf '[MISS] wayland-client development metadata\n'
    warn=$((warn + 1))
fi

printf '\nMonitors:\n'
if command -v hyprctl >/dev/null 2>&1; then
    hyprctl monitors 2>/dev/null | sed -n 's/^Monitor /  /p'
fi

printf '\nResult: %s checks passed, %s items need review.\n' "$ok" "$warn"

if [ "$warn" -gt 0 ]; then
    exit 1
fi
