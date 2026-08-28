#!/bin/sh

set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
lock_file=$repo_root/UPSTREAM.lock
. "$lock_file"
repository=$WAYLAND_VPETS_REPOSITORY
commit=$WAYLAND_VPETS_COMMIT
data_dir=${XDG_DATA_HOME:-"$HOME/.local/share"}
source_dir=${CYBER_COMPANION_UPSTREAM_SOURCE:-"$data_dir/cyber-companion/wayland-vpets"}
build_dir=$source_dir/build-cyber-companion
alpha_patch=$repo_root/$CYBER_COMPANION_PATCH

if [ ! -e "$source_dir" ]; then
    mkdir -p "$(dirname -- "$source_dir")"
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

if [ ! -f "$alpha_patch" ]; then
    printf 'Missing renderer patch: %s\n' "$alpha_patch" >&2
    exit 1
fi

actual_patch_sha256=$(sha256sum "$alpha_patch" | awk '{print $1}')
if [ "$actual_patch_sha256" != "$CYBER_COMPANION_PATCH_SHA256" ]; then
    printf 'Renderer patch checksum mismatch: %s\n' "$alpha_patch" >&2
    exit 1
fi

current_commit=$(git -C "$source_dir" rev-parse HEAD)
if [ "$current_commit" != "$commit" ]; then
    if [ -n "$(git -C "$source_dir" status --porcelain)" ]; then
        printf 'Refusing to switch a dirty upstream worktree: %s\n' "$source_dir" >&2
        exit 1
    fi
    git -C "$source_dir" fetch --depth 1 origin "$commit"
    git -C "$source_dir" checkout --detach "$commit"
fi

if git -C "$source_dir" apply --check "$alpha_patch"; then
    git -C "$source_dir" apply "$alpha_patch"
elif git -C "$source_dir" apply --reverse --check "$alpha_patch"; then
    printf 'Renderer alpha patch is already applied.\n'
else
    printf 'Upstream worktree contains changes outside the expected renderer patch: %s\n' "$source_dir" >&2
    exit 1
fi

worktree_status=$(git -C "$source_dir" status --porcelain --untracked-files=normal)
if [ "$worktree_status" != " M src/graphics/drawing_images.cpp" ]; then
    printf 'Upstream worktree differs from the one expected patched file:\n%s\n' "$worktree_status" >&2
    exit 1
fi

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
