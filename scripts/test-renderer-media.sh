#!/bin/sh

set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
data_dir=${XDG_DATA_HOME:-"$HOME/.local/share"}
source_dir=${CYBER_COMPANION_UPSTREAM_SOURCE:-"$data_dir/cyber-companion/wayland-vpets"}

if [ ! -f "$source_dir/include/graphics/animation.h" ]; then
    printf 'Wayland V-Pets source not found: %s\n' "$source_dir" >&2
    exit 1
fi

grep -q 'MediaUpdate = (1u << 8u)' "$source_dir/include/graphics/animation.h"
grep -q 'media_active{false}' "$source_dir/include/platform/update_shared_memory.h"
grep -q 'Media playback %s' "$source_dir/src/platform/wayland.cpp"

test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT HUP INT TERM

${CXX:-c++} \
    -std=c++23 \
    -Wall -Wextra -Werror \
    -I"$source_dir/include" \
    "$repo_root/tests/renderer_media_test.cpp" \
    -o "$test_dir/renderer-media-test"

"$test_dir/renderer-media-test"
printf 'Renderer native-media state test: PASS\n'
