#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source_image="$repo_root/assets/source/wisp/companion-wisp-master-v0.4.png"
build_dir="$repo_root/build/movement-v0.5"
atlas="$repo_root/assets/sprites/companion-wisp-movement-v0.5.png"
preview="$repo_root/assets/previews/companion-wisp-movement-v0.5.gif"

if command -v magick >/dev/null 2>&1; then
    image_tool=(magick)
elif command -v convert >/dev/null 2>&1; then
    image_tool=(convert)
else
    echo "ImageMagick is required to rebuild the movement preview." >&2
    exit 1
fi

if [ ! -f "$source_image" ]; then
    echo "Canonical source image not found: $source_image" >&2
    exit 1
fi

mkdir -p "$build_dir" "$(dirname -- "$atlas")" "$(dirname -- "$preview")"

make_frame() {
    local output="$1"
    local angle="$2"
    local height="$3"

    "${image_tool[@]}" "$source_image" \
        -resize "95x${height}!" \
        -background none -rotate "$angle" \
        \( -size 256x192 xc:none \) +swap \
        -gravity Center -geometry '+0-3' -composite \
        "PNG32:$output"
}

make_idle_frame() {
    local output="$1"
    local height="$2"
    local top=$((168 - height))

    "${image_tool[@]}" "$source_image" \
        -resize "95x${height}!" \
        \( -size 256x192 xc:none \) +swap \
        -gravity North -geometry "+0+${top}" -composite \
        "PNG32:$output"
}

idle_heights=(150 152 154 153 151 149)
start_angles=(0 30 60 82)
moving_angles=(86 88 90 92 94 92 90 88)
moving_heights=(150 152 154 152 150 148 150 152)
end_angles=(86 60 30 0)

idle_frames=()
for index in "${!idle_heights[@]}"; do
    frame="$build_dir/idle-$(printf '%02d' "$((index + 1))").png"
    make_idle_frame "$frame" "${idle_heights[$index]}"
    idle_frames+=("$frame")
done

start_frames=()
for index in "${!start_angles[@]}"; do
    frame="$build_dir/start-moving-$(printf '%02d' "$((index + 1))").png"
    make_frame "$frame" "${start_angles[$index]}" 150
    start_frames+=("$frame")
done

moving_frames=()
for index in "${!moving_angles[@]}"; do
    frame="$build_dir/moving-$(printf '%02d' "$((index + 1))").png"
    make_frame "$frame" "${moving_angles[$index]}" "${moving_heights[$index]}"
    moving_frames+=("$frame")
done

end_frames=()
for index in "${!end_angles[@]}"; do
    frame="$build_dir/end-moving-$(printf '%02d' "$((index + 1))").png"
    make_frame "$frame" "${end_angles[$index]}" 150
    end_frames+=("$frame")
done

empty="$build_dir/empty.png"
"${image_tool[@]}" -size 256x192 xc:none "PNG32:$empty"

"${image_tool[@]}" "${idle_frames[@]}" "$empty" "$empty" +append "PNG32:$build_dir/row-idle.png"
"${image_tool[@]}" "${start_frames[@]}" "$empty" "$empty" "$empty" "$empty" +append \
    "PNG32:$build_dir/row-start-moving.png"
"${image_tool[@]}" "${moving_frames[@]}" +append "PNG32:$build_dir/row-moving.png"
"${image_tool[@]}" "${end_frames[@]}" "$empty" "$empty" "$empty" "$empty" +append \
    "PNG32:$build_dir/row-end-moving.png"

"${image_tool[@]}" \
    "$build_dir/row-idle.png" \
    "$build_dir/row-start-moving.png" \
    "$build_dir/row-moving.png" \
    "$build_dir/row-end-moving.png" \
    -append "PNG32:$atlas"

preview_frames=("${start_frames[@]}" "${moving_frames[@]}" "${moving_frames[@]}" "${end_frames[@]}" "${idle_frames[@]}")
"${image_tool[@]}" -delay 16 -dispose background "${preview_frames[@]}" -loop 0 "$preview"

echo "Built: $atlas"
echo "Built: $preview"
