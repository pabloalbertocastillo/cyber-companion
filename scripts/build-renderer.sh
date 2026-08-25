#!/bin/sh

set -eu

repository=https://github.com/furudbat/wayland-vpets.git
commit=6475987f0dbebaef56b1db3e8997ea4c9cfd100e
source_dir=/data/Development/tools/wayland-vpets
build_dir=$source_dir/build-cyber-companion

if [ ! -d /data/Development/tools ]; then
    printf 'Missing directory: /data/Development/tools\n' >&2
    exit 1
fi

if [ ! -e "$source_dir" ]; then
    git clone --filter=blob:none "$repository" "$source_dir"
fi

if [ ! -d "$source_dir/.git" ]; then
    printf 'Refusing to use non-Git path: %s\n' "$source_dir" >&2
    exit 1
fi

configured_remote=$(git -C "$source_dir" remote get-url origin)
if [ "$configured_remote" != "$repository" ]; then
    printf 'Unexpected origin for %s: %s\n' "$source_dir" "$configured_remote" >&2
    exit 1
fi

if [ -n "$(git -C "$source_dir" status --porcelain)" ]; then
    printf 'Refusing to change a dirty upstream worktree: %s\n' "$source_dir" >&2
    exit 1
fi

git -C "$source_dir" fetch --depth 1 origin "$commit"
git -C "$source_dir" checkout --detach "$commit"

cmake \
    -S "$source_dir" \
    -B "$build_dir" \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_TESTING=OFF \
    -DSKIP_CPM=ON \
    -DFEATURE_MULTI_VERSIONS=OFF \
    -DFEATURE_CUSTOM_SPRITE_SHEETS=ON

cmake --build "$build_dir" --target bongocat --parallel

binary=$build_dir/bongocat
if [ ! -x "$binary" ]; then
    printf 'Build finished but expected binary is missing: %s\n' "$binary" >&2
    exit 1
fi

printf '\nRenderer built successfully:\n%s\n' "$binary"
"$binary" --version
