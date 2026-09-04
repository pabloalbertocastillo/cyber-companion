"""Supersampled compositing primitives for Wisp Visual v2."""

from __future__ import annotations

import math
from typing import Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .model import (
    CELL_HEIGHT,
    CELL_WIDTH,
    SAFE_ZONE,
    SUPERSAMPLE,
    Pose,
    clamp,
    mix_color,
)


class Canvas:
    """Logical 256x192 canvas rendered at a higher internal resolution."""

    def __init__(self, pose: Pose):
        self.pose = pose
        self.size = (CELL_WIDTH * SUPERSAMPLE, CELL_HEIGHT * SUPERSAMPLE)
        self.image = Image.new("RGBA", self.size, (0, 0, 0, 0))
        self.root = (128.0, 98.0)

    def point(self, x: float, y: float) -> tuple[int, int]:
        root_x, root_y = self.root
        y = root_y + (y - root_y) * self.pose.scale_y
        angle = math.radians(self.pose.tilt)
        delta_x = x - root_x
        delta_y = y - root_y
        transformed_x = (
            root_x
            + delta_x * math.cos(angle)
            - delta_y * math.sin(angle)
        )
        transformed_y = (
            root_y
            + delta_x * math.sin(angle)
            + delta_y * math.cos(angle)
            + self.pose.bob_y
        )
        return round(transformed_x * SUPERSAMPLE), round(
            transformed_y * SUPERSAMPLE
        )

    @staticmethod
    def raw_point(x: float, y: float) -> tuple[int, int]:
        return round(x * SUPERSAMPLE), round(y * SUPERSAMPLE)

    def layer(self) -> Image.Image:
        return Image.new("RGBA", self.size, (0, 0, 0, 0))

    def composite(self, layer: Image.Image) -> None:
        self.image = Image.alpha_composite(self.image, layer)

    def polygon_mask(self, points: Sequence[tuple[float, float]]) -> Image.Image:
        mask = Image.new("L", self.size, 0)
        ImageDraw.Draw(mask).polygon([self.point(*point) for point in points], fill=255)
        return mask


def fill_gradient(
    mask: Image.Image,
    top: Sequence[int],
    bottom: Sequence[int],
) -> Image.Image:
    width, height = mask.size
    gradient = Image.new("RGBA", (1, height))
    pixels = gradient.load()
    for y in range(height):
        pixels[0, y] = mix_color(top, bottom, y / max(1, height - 1))
    gradient = gradient.resize((width, height))
    gradient.putalpha(mask)
    return gradient


def add_glow(
    destination: Image.Image,
    mask: Image.Image,
    color: Sequence[int],
    radius: float,
    strength: float = 1.0,
) -> None:
    if strength <= 0.0:
        return
    blurred = mask.filter(ImageFilter.GaussianBlur(radius * SUPERSAMPLE))
    alpha = blurred.point(lambda value: round(value * clamp(strength)))
    glow = Image.new("RGBA", destination.size, (*color[:3], 0))
    glow.putalpha(alpha)
    destination.alpha_composite(glow)


def line_mask(
    size: tuple[int, int],
    points: Sequence[tuple[int, int]],
    width: float,
) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).line(
        points,
        fill=255,
        width=max(1, round(width * SUPERSAMPLE)),
        joint="curve",
    )
    return mask


def draw_polyline(
    layer: Image.Image,
    points: Sequence[tuple[int, int]],
    fill: Sequence[int],
    width: float,
) -> None:
    ImageDraw.Draw(layer).line(
        points,
        fill=tuple(fill),
        width=max(1, round(width * SUPERSAMPLE)),
        joint="curve",
    )


def finish_frame(image: Image.Image) -> Image.Image:
    """Downsample cleanly and feather alpha to zero at the renderer safe zone."""

    frame = image.resize((CELL_WIDTH, CELL_HEIGHT), Image.Resampling.LANCZOS)

    inner = Image.new("L", frame.size, 0)
    left, top, right, bottom = SAFE_ZONE
    ImageDraw.Draw(inner).rectangle(
        (left + 2, top + 2, right - 3, bottom - 3),
        fill=255,
    )
    feather = inner.filter(ImageFilter.GaussianBlur(1.25))

    hard_clip = Image.new("L", frame.size, 0)
    ImageDraw.Draw(hard_clip).rectangle(
        (left, top, right - 1, bottom - 1),
        fill=255,
    )
    safe_alpha = ImageChops.multiply(feather, hard_clip)
    frame.putalpha(ImageChops.multiply(frame.getchannel("A"), safe_alpha))
    return frame
