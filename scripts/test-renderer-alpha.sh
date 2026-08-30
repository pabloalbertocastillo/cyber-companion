#!/bin/sh

set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
data_dir=${XDG_DATA_HOME:-"$HOME/.local/share"}
source_dir=${CYBER_COMPANION_UPSTREAM_SOURCE:-"$data_dir/cyber-companion/wayland-vpets"}

if [ ! -f "$source_dir/src/graphics/drawing_images.cpp" ]; then
    printf 'Wayland V-Pets source not found: %s\n' "$source_dir" >&2
    exit 1
fi

test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT HUP INT TERM

${CXX:-c++} \
    -std=c++23 \
    -Wall -Wextra -Werror \
    -I"$source_dir/include" \
    "$source_dir/src/graphics/drawing_images.cpp" \
    "$repo_root/tests/renderer_alpha_test.cpp" \
    -o "$test_dir/renderer-alpha-test"

"$test_dir/renderer-alpha-test"
printf 'Renderer premultiplied-alpha test: PASS\n'
