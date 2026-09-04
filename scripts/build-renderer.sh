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
media_patch=$repo_root/$CYBER_COMPANION_MEDIA_PATCH
config_patch=$repo_root/$CYBER_COMPANION_CONFIG_PATCH
system_patch=$repo_root/$CYBER_COMPANION_SYSTEM_PATCH
system_atlas=$repo_root/assets/sprites/companion-wisp-system-v0.12.png

# The atlas is a local build artifact. Visual v2 renders all source geometry,
# lighting and state effects deterministically before the renderer is built.
if [ ! -f "$system_atlas" ]; then
    printf 'Generating Wisp Visual v0.12 atlas...\n'
    "$repo_root/scripts/build-wisp-v2.py" --atlas-only
fi

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

verify_patch() {
    patch_file=$1
    expected_sha256=$2
    if [ ! -f "$patch_file" ]; then
        printf 'Missing renderer patch: %s\n' "$patch_file" >&2
        exit 1
    fi
    actual_patch_sha256=$(sha256sum "$patch_file" | awk '{print $1}')
    if [ "$actual_patch_sha256" != "$expected_sha256" ]; then
        printf 'Renderer patch checksum mismatch: %s\n' "$patch_file" >&2
        exit 1
    fi
}

verify_patch "$alpha_patch" "$CYBER_COMPANION_PATCH_SHA256"
verify_patch "$media_patch" "$CYBER_COMPANION_MEDIA_PATCH_SHA256"
verify_patch "$config_patch" "$CYBER_COMPANION_CONFIG_PATCH_SHA256"
verify_patch "$system_patch" "$CYBER_COMPANION_SYSTEM_PATCH_SHA256"

current_commit=$(git -C "$source_dir" rev-parse HEAD)
if [ "$current_commit" != "$commit" ]; then
    if [ -n "$(git -C "$source_dir" status --porcelain)" ]; then
        printf 'Refusing to switch a dirty upstream worktree: %s\n' "$source_dir" >&2
        exit 1
    fi
    git -C "$source_dir" fetch --depth 1 origin "$commit"
    git -C "$source_dir" checkout --detach "$commit"
fi

apply_patch_once() {
    patch_file=$1
    patch_name=$2
    if git -C "$source_dir" apply --check "$patch_file" >/dev/null 2>&1; then
        git -C "$source_dir" apply "$patch_file"
    elif git -C "$source_dir" apply --reverse --check "$patch_file" >/dev/null 2>&1; then
        printf 'Renderer %s patch is already applied.\n' "$patch_name"
    else
        printf 'Upstream worktree conflicts with the %s patch: %s\n' "$patch_name" "$source_dir" >&2
        exit 1
    fi
}

apply_patch_once "$alpha_patch" "alpha"
apply_patch_once "$media_patch" "media-signal"
apply_patch_once "$config_patch" "config-validation"
apply_patch_once "$system_patch" "system-presence"

worktree_status=$(git -C "$source_dir" status --porcelain --untracked-files=no)
expected_status=' M include/graphics/animation.h
 M include/platform/update_shared_memory.h
 M src/config/config.cpp
 M src/core/main.cpp
 M src/graphics/animation.cpp
 M src/graphics/drawing_images.cpp
 M src/platform/wayland.cpp'
if [ "$worktree_status" != "$expected_status" ]; then
    printf 'Upstream worktree differs from the expected patched files:\n%s\n' "$worktree_status" >&2
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
