#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source_image="$repo_root/assets/source/wisp/companion-wisp-master-v0.4.png"
build_dir="$repo_root/build/idle-v0.4"
atlas="$repo_root/assets/sprites/companion-wisp-idle-v0.4.png"
preview="$repo_root/assets/previews/companion-wisp-idle-v0.4.gif"

if command -v magick >/dev/null 2>&1; then
    image_tool=(magick)
elif command -v convert >/dev/null 2>&1; then
    image_tool=(convert)
else
    echo "ImageMagick is required to rebuild the idle preview." >&2
    exit 1
fi

if [ ! -f "$source_image" ]; then
    echo "Canonical source image not found: $source_image" >&2
    exit 1
fi

mkdir -p "$build_dir" "$(dirname -- "$atlas")" "$(dirname -- "$preview")"

# Width remains fixed. Height changes around the fixed y=168 tail pivot.
heights=(150 152 154 153 151 149)
frames=()

for index in "${!heights[@]}"; do
    height="${heights[$index]}"
    top=$((168 - height))
    frame="$build_dir/idle-$(printf '%02d' "$((index + 1))").png"
    "${image_tool[@]}" "$source_image" \
        -resize "95x${height}!" \
        \( -size 256x192 xc:none \) +swap \
        -gravity North -geometry "+0+${top}" -composite \
        "PNG32:$frame"
    frames+=("$frame")
done

"${image_tool[@]}" "${frames[@]}" +append "PNG32:$atlas"
"${image_tool[@]}" -delay 16 -dispose background "${frames[@]}" -loop 0 "$preview"

echo "Built: $atlas"
echo "Built: $preview"
