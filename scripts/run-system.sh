#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
monitor="${CYBER_COMPANION_MONITOR:-}"
runtime_root="${XDG_RUNTIME_DIR:-}"

if [[ -z "$monitor" ]]; then
    echo "Select a monitor with CYBER_COMPANION_MONITOR." >&2
    exit 1
fi

if [[ -z "$runtime_root" || ! -d "$runtime_root" ]]; then
    echo "XDG_RUNTIME_DIR is missing or invalid." >&2
    exit 1
fi

if ! command -v playerctl >/dev/null 2>&1; then
    echo "playerctl is required for the MPRIS adapter." >&2
    exit 1
fi

runtime_dir="$runtime_root/cyber-companion"
runtime_config="$runtime_dir/wpets.conf"
runtime_state="$runtime_dir/state.json"
mkdir -p "$runtime_dir"
chmod 700 "$runtime_dir"
cp -- "$repo_root/config/wpets.conf.example" "$runtime_config"
chmod 600 "$runtime_config"

renderer_pid=""
controller_pid=""

cleanup() {
    set +e
    if [[ -n "$controller_pid" ]] && kill -0 "$controller_pid" 2>/dev/null; then
        kill "$controller_pid"
        wait "$controller_pid" 2>/dev/null
    fi
    if [[ -n "$renderer_pid" ]] && kill -0 "$renderer_pid" 2>/dev/null; then
        kill "$renderer_pid"
        wait "$renderer_pid" 2>/dev/null
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cd "$repo_root"

echo "Runtime config: $runtime_config"
echo "Runtime state:  $runtime_state"
echo "MPRIS media:    all players"

CYBER_COMPANION_CONFIG="$runtime_config" \
CYBER_COMPANION_MONITOR="$monitor" \
    ./scripts/run-renderer.sh &
renderer_pid=$!

# SIGUSR2 is the renderer's official reload signal. Give its signalfd and
# config watcher time to initialize before the controller sends the first one.
sleep 2
if ! kill -0 "$renderer_pid" 2>/dev/null; then
    wait "$renderer_pid"
    exit $?
fi

python3 -m cyber_companion.controller \
    --profiles "$repo_root/config/system-profiles.json" \
    --base-config "$repo_root/config/wpets.conf.example" \
    --runtime-config "$runtime_config" \
    --state-file "$runtime_state" \
    --renderer-pid "$renderer_pid" &
controller_pid=$!

set +e
wait -n "$renderer_pid" "$controller_pid"
status=$?
set -e
exit "$status"
