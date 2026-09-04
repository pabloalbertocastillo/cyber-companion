"""Animation model and visual constants for Wisp Visual v2."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

CELL_WIDTH = 256
CELL_HEIGHT = 192
COLUMNS = 24
ROWS = 7
SUPERSAMPLE = 4
SAFE_ZONE = (20, 12, 236, 180)
TAU = math.tau

STATE_ORDER = (
    "idle",
    "start_working",
    "working",
    "end_working",
    "start_moving",
    "moving",
    "end_moving",
)

ARMOR_0 = (3, 8, 18, 255)
ARMOR_1 = (8, 20, 36, 255)
ARMOR_2 = (16, 39, 58, 255)
ARMOR_3 = (44, 78, 100, 255)
OUTLINE = (2, 6, 14, 236)
CYAN = (68, 245, 255, 255)
TEAL = (23, 224, 190, 255)
LIME = (153, 255, 73, 255)
VIOLET = (191, 86, 255, 255)
WHITE = (235, 255, 255, 255)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def smoothstep(value: float) -> float:
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


def ease_in_out(value: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * clamp(value))


def lerp(left: float, right: float, position: float) -> float:
    return left + (right - left) * position


def mix_color(
    left: Sequence[int],
    right: Sequence[int],
    position: float,
    alpha: int | None = None,
) -> tuple[int, int, int, int]:
    position = clamp(position)
    rgb = tuple(
        round(lerp(float(left[index]), float(right[index]), position))
        for index in range(3)
    )
    mixed_alpha = (
        int(alpha)
        if alpha is not None
        else round(lerp(float(left[3]), float(right[3]), position))
    )
    return *rgb, mixed_alpha


def periodic_gaussian(position: float, center: float, width: float) -> float:
    distance = min(abs(position - center), 1.0 - abs(position - center))
    return math.exp(-0.5 * (distance / width) ** 2)


def cubic_bezier(
    first: tuple[float, float],
    second: tuple[float, float],
    third: tuple[float, float],
    fourth: tuple[float, float],
    steps: int = 36,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index in range(steps + 1):
        position = index / steps
        inverse = 1.0 - position
        x = (
            inverse**3 * first[0]
            + 3.0 * inverse * inverse * position * second[0]
            + 3.0 * inverse * position * position * third[0]
            + position**3 * fourth[0]
        )
        y = (
            inverse**3 * first[1]
            + 3.0 * inverse * inverse * position * second[1]
            + 3.0 * inverse * position * position * third[1]
            + position**3 * fourth[1]
        )
        points.append((x, y))
    return points


def regular_polygon(
    center_x: float,
    center_y: float,
    radius: float,
    sides: int,
    rotation: float = -math.pi / 2.0,
) -> list[tuple[float, float]]:
    return [
        (
            center_x + radius * math.cos(rotation + index * TAU / sides),
            center_y + radius * math.sin(rotation + index * TAU / sides),
        )
        for index in range(sides)
    ]


@dataclass(frozen=True)
class Pose:
    bob_y: float = 0.0
    tilt: float = 0.0
    scale_y: float = 1.0
    left_upper: float = 132.0
    left_fore: float = 105.0
    right_upper: float = 48.0
    right_fore: float = 75.0
    core: float = 0.55
    aura: float = 0.42
    rings: float = 0.18
    particles: float = 0.25
    tail_wave: float = 0.0
    eye_open: float = 1.0
    data: float = 0.0
    media: float = 0.0
    scan: float = -1.0
    accent: float = 0.0


def blend_pose(source: Pose, destination: Pose, position: float) -> Pose:
    position = smoothstep(position)
    return Pose(
        **{
            name: lerp(getattr(source, name), getattr(destination, name), position)
            for name in Pose.__dataclass_fields__
        }
    )


def idle_pose(position: float) -> Pose:
    pulse = 0.5 + 0.5 * math.sin(TAU * position - math.pi / 2.0)
    blink = max(
        periodic_gaussian(position, 0.71, 0.025),
        0.78 * periodic_gaussian(position, 0.77, 0.018),
    )
    return Pose(
        bob_y=-1.6 - 2.0 * math.sin(TAU * position),
        tilt=0.9 * math.sin(TAU * position + 0.5),
        scale_y=1.0 + 0.012 * math.sin(TAU * position - 0.7),
        left_upper=132.0 + 4.2 * math.sin(TAU * position + 0.8),
        left_fore=105.0 + 3.2 * math.sin(TAU * position + 1.7),
        right_upper=48.0 - 4.0 * math.sin(TAU * position + 0.4),
        right_fore=75.0 - 3.4 * math.sin(TAU * position + 1.2),
        core=0.48 + 0.16 * pulse,
        aura=0.38 + 0.09 * pulse,
        rings=0.13 + 0.07 * pulse,
        particles=0.22,
        tail_wave=math.sin(TAU * position),
        eye_open=1.0 - 0.93 * blink,
        accent=0.03,
    )


def working_pose(position: float) -> Pose:
    beat = 0.5 + 0.5 * math.sin(TAU * 2.0 * position)
    sway = math.sin(TAU * position)
    return Pose(
        bob_y=-3.0 - 3.2 * beat,
        tilt=2.2 * sway,
        scale_y=1.0 + 0.025 * beat,
        left_upper=lerp(208.0, 118.0, 0.5 + 0.5 * math.sin(TAU * position)),
        left_fore=lerp(
            235.0,
            85.0,
            0.5 + 0.5 * math.sin(TAU * position + 0.6),
        ),
        right_upper=lerp(
            332.0,
            62.0,
            0.5 + 0.5 * math.sin(TAU * position + math.pi),
        ),
        right_fore=lerp(
            305.0,
            95.0,
            0.5 + 0.5 * math.sin(TAU * position + math.pi + 0.6),
        ),
        core=0.86 + 0.14 * beat,
        aura=0.60 + 0.18 * beat,
        rings=0.62 + 0.22 * beat,
        particles=0.68 + 0.18 * beat,
        tail_wave=1.2 * math.sin(TAU * position + 0.4),
        eye_open=1.0,
        media=1.0,
        accent=0.65 + 0.25 * beat,
    )


def busy_pose(position: float) -> Pose:
    pulse = 0.5 + 0.5 * math.sin(TAU * 3.0 * position)
    return Pose(
        bob_y=-2.4 - 1.5 * math.sin(TAU * position),
        tilt=0.6 * math.sin(TAU * position),
        scale_y=1.0 + 0.012 * math.sin(TAU * 2.0 * position),
        left_upper=161.0 + 5.0 * math.sin(TAU * position),
        left_fore=27.0 + 7.0 * math.sin(TAU * 2.0 * position + 0.7),
        right_upper=19.0 - 5.0 * math.sin(TAU * position),
        right_fore=153.0 - 7.0 * math.sin(TAU * 2.0 * position + 0.7),
        core=0.78 + 0.20 * pulse,
        aura=0.52 + 0.11 * pulse,
        rings=0.45 + 0.18 * pulse,
        particles=0.58,
        tail_wave=0.75 * math.sin(TAU * 1.5 * position),
        eye_open=0.92,
        data=1.0,
        scan=position,
        accent=0.18,
    )


def pose_for(state: str, frame: int, frames: int = COLUMNS) -> Pose:
    looping = state in {"idle", "working", "moving"}
    position = frame / frames if looping else frame / (frames - 1)
    if state == "idle":
        return idle_pose(position)
    if state == "working":
        return working_pose(position)
    if state == "moving":
        return busy_pose(position)
    if state == "start_working":
        return blend_pose(idle_pose(0.0), working_pose(0.0), ease_in_out(position))
    if state == "end_working":
        return blend_pose(working_pose(0.0), idle_pose(0.0), ease_in_out(position))
    if state == "start_moving":
        return blend_pose(idle_pose(0.0), busy_pose(0.0), ease_in_out(position))
    if state == "end_moving":
        return blend_pose(busy_pose(0.0), idle_pose(0.0), ease_in_out(position))
    raise ValueError(f"Unknown Wisp state: {state}")
