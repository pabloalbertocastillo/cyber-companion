#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
renderer_bin="${CYBER_COMPANION_RENDERER_BIN:-/data/Development/tools/wayland-vpets/build-cyber-companion/bongocat}"
config_file="${CYBER_COMPANION_CONFIG:-$repo_root/config/wpets.conf.example}"
monitor="${CYBER_COMPANION_MONITOR:-DP-2}"

if [ ! -x "$renderer_bin" ]; then
    echo "Renderer not found or not executable: $renderer_bin" >&2
    echo "Run ./scripts/build-renderer.sh first." >&2
    exit 1
fi

if [ ! -f "$config_file" ]; then
    echo "Configuration not found: $config_file" >&2
    exit 1
fi

if command -v pgrep >/dev/null 2>&1 && pgrep -x bongocat >/dev/null 2>&1; then
    echo "A bongocat process is already running." >&2
    echo "Stop the foreground process with Ctrl+C, then run this launcher again." >&2
    exit 1
fi

echo "Renderer: $renderer_bin"
echo "Config:   $config_file"
echo "Monitor:  $monitor"

exec "$renderer_bin" \
    --strict \
    --watch-config \
    --config "$config_file" \
    --monitor "$monitor"
