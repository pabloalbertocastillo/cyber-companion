#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source_image="$repo_root/assets/source/wisp/companion-wisp-master-v0.4.png"
build_dir="$repo_root/build/movement-v0.6"
rig_dir="$build_dir/rig"
atlas="$repo_root/assets/sprites/companion-wisp-movement-v0.6.png"
preview="$repo_root/assets/previews/companion-wisp-movement-v0.6.gif"

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

mkdir -p "$build_dir" "$rig_dir" "$(dirname -- "$atlas")" "$(dirname -- "$preview")"

# The approved master consists of three disconnected alpha components. At a
# 3% alpha threshold ImageMagick labels the body as 1 and the arms as 6 and 7.
# Extracting those components gives this preview a minimal deterministic 2D rig.
"${image_tool[@]}" "$source_image" -alpha extract -threshold 3% \
    -connected-components 4 "$rig_dir/labels.png"

extract_component() {
    local name="$1"
    local component_id="$2"
    local mask="$rig_dir/$name-mask.png"

    "${image_tool[@]}" "$rig_dir/labels.png" \
        -fx "abs(u*quantumrange-$component_id)<0.5?1:0" "$mask"
    "${image_tool[@]}" "$source_image" "$mask" \
        -alpha off -compose CopyOpacity -composite \
        -background none -alpha background "PNG32:$rig_dir/$name.png"
}

extract_component body 1
extract_component left-arm 6
extract_component right-arm 7

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

make_rig_frame() {
    local output="$1"
    local body_angle="$2"
    local arm_tuck="$3"
    local height="$4"
    local vertical_offset="$5"
    local stem="${output%.png}"

    # Arms pivot independently at their shoulders before the assembled rig is
    # tilted. Opposite local rotations draw both arms inward and then backward.
    "${image_tool[@]}" "$rig_dir/left-arm.png" -virtual-pixel transparent \
        -distort SRT "44,137 1 $arm_tuck 44,137" "${stem}-left.png"
    "${image_tool[@]}" "$rig_dir/right-arm.png" -virtual-pixel transparent \
        -distort SRT "146,137 1 -$arm_tuck 146,137" "${stem}-right.png"

    "${image_tool[@]}" -size 190x300 xc:none \
        "$rig_dir/body.png" -compose over -composite \
        "${stem}-left.png" -composite \
        "${stem}-right.png" -composite \
        -resize "95x${height}!" \
        -background none -rotate "$body_angle" \
        \( -size 256x192 xc:none \) +swap \
        -gravity Center -geometry "+0+${vertical_offset}" -composite \
        "PNG32:$output"
}

idle_heights=(150 152 154 153 151 149)

# Ease into the rotation instead of advancing by 30 degrees per frame. The
# arms progressively tuck by 18 degrees while the body reaches flight attitude.
start_angles=(0 8 22 42 66 86)
start_tucks=(0 4 9 14 18 18)

moving_angles=(88 90 92 94 92 90 88 86)
moving_tucks=(18 20 22 20 18 16 18 20)
moving_heights=(150 152 154 152 150 148 150 152)
moving_offsets=(-3 -4 -5 -4 -3 -2 -3 -4)

end_angles=(86 66 42 22 8 0)
end_tucks=(18 18 14 9 4 0)

idle_frames=()
for index in "${!idle_heights[@]}"; do
    frame="$build_dir/idle-$(printf '%02d' "$((index + 1))").png"
    make_idle_frame "$frame" "${idle_heights[$index]}"
    idle_frames+=("$frame")
done

start_frames=()
for index in "${!start_angles[@]}"; do
    frame="$build_dir/start-moving-$(printf '%02d' "$((index + 1))").png"
    if [ "$index" -eq 0 ]; then
        make_idle_frame "$frame" 150
    else
        make_rig_frame "$frame" "${start_angles[$index]}" \
            "${start_tucks[$index]}" 150 -3
    fi
    start_frames+=("$frame")
done

moving_frames=()
for index in "${!moving_angles[@]}"; do
    frame="$build_dir/moving-$(printf '%02d' "$((index + 1))").png"
    make_rig_frame "$frame" "${moving_angles[$index]}" \
        "${moving_tucks[$index]}" "${moving_heights[$index]}" \
        "${moving_offsets[$index]}"
    moving_frames+=("$frame")
done

end_frames=()
for index in "${!end_angles[@]}"; do
    frame="$build_dir/end-moving-$(printf '%02d' "$((index + 1))").png"
    if [ "$index" -eq $((${#end_angles[@]} - 1)) ]; then
        make_idle_frame "$frame" 150
    else
        make_rig_frame "$frame" "${end_angles[$index]}" \
            "${end_tucks[$index]}" 150 -3
    fi
    end_frames+=("$frame")
done

empty="$build_dir/empty.png"
"${image_tool[@]}" -size 256x192 xc:none "PNG32:$empty"

"${image_tool[@]}" "${idle_frames[@]}" "$empty" "$empty" +append \
    "PNG32:$build_dir/row-idle.png"
"${image_tool[@]}" "${start_frames[@]}" "$empty" "$empty" +append \
    "PNG32:$build_dir/row-start-moving.png"
"${image_tool[@]}" "${moving_frames[@]}" +append \
    "PNG32:$build_dir/row-moving.png"
"${image_tool[@]}" "${end_frames[@]}" "$empty" "$empty" +append \
    "PNG32:$build_dir/row-end-moving.png"

"${image_tool[@]}" \
    "$build_dir/row-idle.png" \
    "$build_dir/row-start-moving.png" \
    "$build_dir/row-moving.png" \
    "$build_dir/row-end-moving.png" \
    -append -strip "PNG32:$atlas"

preview_frames=(
    "${idle_frames[@]}"
    "${start_frames[@]}"
    "${moving_frames[@]}"
    "${moving_frames[@]}"
    "${moving_frames[@]}"
    "${end_frames[@]}"
    "${idle_frames[@]}"
)
"${image_tool[@]}" -delay 18 -dispose background \
    "${preview_frames[@]}" -loop 0 "$preview"

echo "Built: $atlas"
echo "Built: $preview"
