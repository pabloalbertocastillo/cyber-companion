"""Deterministic, layered Wisp Visual v2 renderer."""

from __future__ import annotations

import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .model import (
    ARMOR_0,
    ARMOR_1,
    ARMOR_2,
    ARMOR_3,
    COLUMNS,
    CYAN,
    LIME,
    OUTLINE,
    SUPERSAMPLE,
    TAU,
    TEAL,
    VIOLET,
    WHITE,
    cubic_bezier,
    lerp,
    mix_color,
    pose_for,
    regular_polygon,
)
from .primitives import (
    Canvas,
    add_glow,
    draw_polyline,
    fill_gradient,
    finish_frame,
    line_mask,
)


def draw_tail(canvas: Canvas, phase: float) -> None:
    pose = canvas.pose
    start = canvas.point(128, 117)
    end = canvas.raw_point(128, 169)
    wave = pose.tail_wave
    controls = (
        start,
        canvas.raw_point(113 + 5 * wave, 133 + pose.bob_y * 0.35),
        canvas.raw_point(145 - 6 * wave, 151 + pose.bob_y * 0.14),
        end,
    )
    points = [
        (round(x), round(y))
        for x, y in cubic_bezier(*controls, steps=42)
    ]

    glow_layer = canvas.layer()
    outer = line_mask(canvas.size, points, 10)
    add_glow(glow_layer, outer, CYAN, 8, 0.28 + pose.aura * 0.24)
    add_glow(glow_layer, outer, TEAL, 3.5, 0.34 + pose.aura * 0.22)
    canvas.composite(glow_layer)

    tail = canvas.layer()
    draw_polyline(tail, points, (6, 35, 51, 205), 9)
    draw_polyline(tail, points, (21, 157, 169, 190), 5.4)
    filament = mix_color(
        TEAL,
        LIME,
        0.32 + 0.2 * math.sin(phase),
        230,
    )
    draw_polyline(tail, points, filament, 2.2)
    draw_polyline(tail, points, (224, 255, 248, 210), 0.75)
    canvas.composite(tail)

    beads = canvas.layer()
    draw = ImageDraw.Draw(beads)
    for index in range(4):
        position = (index / 4 + phase / TAU) % 1.0
        point_index = min(len(points) - 1, round(position * (len(points) - 1)))
        x, y = points[point_index]
        radius = (1.1 + 0.5 * math.sin(phase + index)) * SUPERSAMPLE
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=(220, 255, 245, 220),
        )
    add_glow(beads, beads.getchannel("A"), LIME, 2.4, 0.55)
    canvas.composite(beads)


def draw_holographic_rings(canvas: Canvas, phase: float) -> None:
    pose = canvas.pose
    if pose.rings < 0.02:
        return

    layer = canvas.layer()
    draw = ImageDraw.Draw(layer)
    center_y = (105 + pose.bob_y) * SUPERSAMPLE
    for index, (width, height, alpha, offset) in enumerate(
        ((84, 24, 120, 0.0), (63, 18, 95, 1.7))
    ):
        bounds = (
            (128 - width / 2) * SUPERSAMPLE,
            center_y - height / 2 * SUPERSAMPLE,
            (128 + width / 2) * SUPERSAMPLE,
            center_y + height / 2 * SUPERSAMPLE,
        )
        start = (phase * 70 + offset * 90) % 360
        span = 150 + 80 * pose.rings
        color = mix_color(CYAN, VIOLET, pose.accent, round(alpha * pose.rings))
        draw.arc(
            bounds,
            start=start,
            end=start + span,
            fill=color,
            width=max(1, round((1.1 + index * 0.35) * SUPERSAMPLE)),
        )
        draw.arc(
            bounds,
            start=start + 190,
            end=start + 190 + span * 0.58,
            fill=(*TEAL[:3], round(alpha * 0.62 * pose.rings)),
            width=max(1, round(0.8 * SUPERSAMPLE)),
        )

    glow = layer.getchannel("A").filter(
        ImageFilter.GaussianBlur(2.2 * SUPERSAMPLE)
    )
    bloom = Image.new("RGBA", canvas.size, (*CYAN[:3], 0))
    bloom.putalpha(glow.point(lambda value: round(value * 0.34)))
    canvas.composite(bloom)
    canvas.composite(layer)


def limb_points(
    canvas: Canvas,
    shoulder: tuple[float, float],
    upper_angle: float,
    forearm_angle: float,
    upper_length: float = 31,
    forearm_length: float = 27,
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    shoulder_x, shoulder_y = shoulder
    upper_radians = math.radians(upper_angle)
    elbow_x = shoulder_x + upper_length * math.cos(upper_radians)
    elbow_y = shoulder_y + upper_length * math.sin(upper_radians)
    forearm_radians = math.radians(forearm_angle)
    hand_x = elbow_x + forearm_length * math.cos(forearm_radians)
    hand_y = elbow_y + forearm_length * math.sin(forearm_radians)
    return (
        canvas.point(shoulder_x, shoulder_y),
        canvas.point(elbow_x, elbow_y),
        canvas.point(hand_x, hand_y),
    )


def draw_arm(canvas: Canvas, side: str) -> None:
    pose = canvas.pose
    left = side == "left"
    shoulder = (97, 90) if left else (159, 90)
    upper = pose.left_upper if left else pose.right_upper
    forearm = pose.left_fore if left else pose.right_fore
    shoulder_point, elbow_point, hand_point = limb_points(
        canvas,
        shoulder,
        upper,
        forearm,
    )

    layer = canvas.layer()
    draw = ImageDraw.Draw(layer)
    path = [shoulder_point, elbow_point, hand_point]
    draw.line(
        path,
        fill=OUTLINE,
        width=round(12 * SUPERSAMPLE),
        joint="curve",
    )
    draw.line(
        path,
        fill=ARMOR_2,
        width=round(8 * SUPERSAMPLE),
        joint="curve",
    )
    draw.line(
        path,
        fill=(52, 91, 112, 230),
        width=round(3.2 * SUPERSAMPLE),
        joint="curve",
    )
    seam = mix_color(CYAN, VIOLET, pose.accent, 235)
    draw.line(
        path,
        fill=seam,
        width=round(1.25 * SUPERSAMPLE),
        joint="curve",
    )

    for joint, radius in (
        (shoulder_point, 5.6),
        (elbow_point, 5.2),
        (hand_point, 6.0),
    ):
        outer_radius = radius * SUPERSAMPLE
        draw.ellipse(
            (
                joint[0] - outer_radius,
                joint[1] - outer_radius,
                joint[0] + outer_radius,
                joint[1] + outer_radius,
            ),
            fill=OUTLINE,
        )
        shell_radius = (radius - 1.3) * SUPERSAMPLE
        draw.ellipse(
            (
                joint[0] - shell_radius,
                joint[1] - shell_radius,
                joint[0] + shell_radius,
                joint[1] + shell_radius,
            ),
            fill=ARMOR_1,
        )
        emitter_radius = 1.55 * SUPERSAMPLE
        draw.ellipse(
            (
                joint[0] - emitter_radius,
                joint[1] - emitter_radius,
                joint[0] + emitter_radius,
                joint[1] + emitter_radius,
            ),
            fill=seam,
        )

    hand_angle = math.radians(forearm)
    normal = (-math.sin(hand_angle), math.cos(hand_angle))
    forward = (math.cos(hand_angle), math.sin(hand_angle))
    for offset in (-1, 0, 1):
        start_x = hand_point[0] + normal[0] * offset * 2.3 * SUPERSAMPLE
        start_y = hand_point[1] + normal[1] * offset * 2.3 * SUPERSAMPLE
        length = 4.5 + (1.5 if offset == 0 else 0.0)
        end_x = start_x + forward[0] * length * SUPERSAMPLE
        end_y = start_y + forward[1] * length * SUPERSAMPLE
        draw.line(
            [(start_x, start_y), (end_x, end_y)],
            fill=(*seam[:3], 190),
            width=max(1, round(0.8 * SUPERSAMPLE)),
        )

    glow = canvas.layer()
    add_glow(
        glow,
        layer.getchannel("A"),
        seam,
        2.7,
        0.22 + 0.18 * pose.aura,
    )
    canvas.composite(glow)
    canvas.composite(layer)


def draw_body(canvas: Canvas) -> None:
    pose = canvas.pose

    aura_mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(aura_mask).ellipse(
        (
            72 * SUPERSAMPLE,
            (20 + pose.bob_y) * SUPERSAMPLE,
            184 * SUPERSAMPLE,
            (133 + pose.bob_y) * SUPERSAMPLE,
        ),
        fill=round(170 * pose.aura),
    )
    aura_mask = aura_mask.filter(
        ImageFilter.GaussianBlur((11 + 4 * pose.aura) * SUPERSAMPLE)
    )
    aura_color = mix_color(TEAL, CYAN, 0.55, 0)
    aura = Image.new("RGBA", canvas.size, (*aura_color[:3], 0))
    aura.putalpha(aura_mask.point(lambda value: round(value * 0.46)))
    canvas.composite(aura)

    torso_points = (
        (101, 82),
        (111, 72),
        (145, 72),
        (155, 82),
        (149, 119),
        (137, 132),
        (119, 132),
        (107, 119),
    )
    torso_mask = canvas.polygon_mask(torso_points)
    outline_mask = torso_mask.filter(ImageFilter.MaxFilter(4 * SUPERSAMPLE + 1))
    outline_only = ImageChops.subtract(outline_mask, torso_mask)
    outline = Image.new("RGBA", canvas.size, OUTLINE)
    outline.putalpha(outline_only.point(lambda value: round(value * 0.94)))
    canvas.composite(outline)
    canvas.composite(fill_gradient(torso_mask, ARMOR_3, ARMOR_0))

    details = canvas.layer()
    draw = ImageDraw.Draw(details)
    draw.polygon(
        [
            canvas.point(105, 86),
            canvas.point(116, 80),
            canvas.point(115, 117),
            canvas.point(108, 116),
        ],
        fill=(12, 55, 72, 170),
    )
    draw.polygon(
        [
            canvas.point(151, 86),
            canvas.point(140, 80),
            canvas.point(141, 117),
            canvas.point(148, 116),
        ],
        fill=(12, 55, 72, 170),
    )
    draw.line(
        [canvas.point(111, 77), canvas.point(128, 84), canvas.point(145, 77)],
        fill=(*CYAN[:3], 150),
        width=round(1.2 * SUPERSAMPLE),
        joint="curve",
    )
    draw.line(
        [canvas.point(116, 121), canvas.point(128, 128), canvas.point(140, 121)],
        fill=(*TEAL[:3], 125),
        width=round(0.85 * SUPERSAMPLE),
    )
    for x in (112, 144):
        draw.line(
            [canvas.point(x, 88), canvas.point(x + (2 if x < 128 else -2), 112)],
            fill=(100, 240, 255, 80),
            width=max(1, round(0.55 * SUPERSAMPLE)),
        )
    canvas.composite(details)

    neck = canvas.layer()
    draw = ImageDraw.Draw(neck)
    draw.rounded_rectangle(
        (*canvas.point(116, 67), *canvas.point(140, 87)),
        radius=7 * SUPERSAMPLE,
        fill=OUTLINE,
    )
    draw.rounded_rectangle(
        (*canvas.point(119, 69), *canvas.point(137, 85)),
        radius=5 * SUPERSAMPLE,
        fill=ARMOR_1,
    )
    canvas.composite(neck)

    crown = canvas.layer()
    draw = ImageDraw.Draw(crown)
    crown_edge = mix_color(CYAN, LIME, 0.18, 180)
    fins = (
        ((95, 52), (88, 28), (109, 42)),
        ((161, 52), (168, 28), (147, 42)),
        ((109, 40), (112, 20), (121, 38)),
        ((147, 40), (144, 20), (135, 38)),
    )
    for fin in fins:
        points = [canvas.point(*point) for point in fin]
        draw.polygon(points, fill=OUTLINE)
        draw.line(
            points,
            fill=crown_edge,
            width=max(1, round(0.9 * SUPERSAMPLE)),
            joint="curve",
        )
    canvas.composite(crown)

    head_mask = Image.new("L", canvas.size, 0)
    draw = ImageDraw.Draw(head_mask)
    hover = pose.bob_y
    draw.rounded_rectangle(
        (
            91 * SUPERSAMPLE,
            (31 + hover) * SUPERSAMPLE,
            165 * SUPERSAMPLE,
            (83 + hover) * SUPERSAMPLE,
        ),
        radius=22 * SUPERSAMPLE,
        fill=255,
    )
    draw.polygon(
        [
            canvas.point(94, 58),
            canvas.point(103, 78),
            canvas.point(118, 87),
            canvas.point(138, 87),
            canvas.point(153, 78),
            canvas.point(162, 58),
        ],
        fill=255,
    )
    expanded = head_mask.filter(ImageFilter.MaxFilter(4 * SUPERSAMPLE + 1))
    border = ImageChops.subtract(expanded, head_mask)
    border_image = Image.new("RGBA", canvas.size, OUTLINE)
    border_image.putalpha(border)
    canvas.composite(border_image)
    canvas.composite(fill_gradient(head_mask, (31, 63, 82, 255), ARMOR_0))

    helmet = canvas.layer()
    draw = ImageDraw.Draw(helmet)
    draw.line(
        [
            canvas.point(100, 49),
            canvas.point(111, 38),
            canvas.point(128, 34),
            canvas.point(145, 38),
            canvas.point(156, 49),
        ],
        fill=(95, 150, 169, 130),
        width=round(0.9 * SUPERSAMPLE),
        joint="curve",
    )
    draw.arc(
        (
            94 * SUPERSAMPLE,
            (34 + hover) * SUPERSAMPLE,
            162 * SUPERSAMPLE,
            (82 + hover) * SUPERSAMPLE,
        ),
        198,
        342,
        fill=(*CYAN[:3], 120),
        width=max(1, round(1.0 * SUPERSAMPLE)),
    )
    draw.line(
        [canvas.point(104, 76), canvas.point(117, 84)],
        fill=(*TEAL[:3], 100),
        width=max(1, round(0.8 * SUPERSAMPLE)),
    )
    draw.line(
        [canvas.point(152, 76), canvas.point(139, 84)],
        fill=(*TEAL[:3], 100),
        width=max(1, round(0.8 * SUPERSAMPLE)),
    )
    canvas.composite(helmet)

    visor_mask = Image.new("L", canvas.size, 0)
    draw = ImageDraw.Draw(visor_mask)
    visor_points = [
        canvas.point(101, 51),
        canvas.point(111, 43),
        canvas.point(145, 43),
        canvas.point(155, 51),
        canvas.point(148, 68),
        canvas.point(108, 68),
    ]
    draw.polygon(visor_points, fill=255)
    canvas.composite(fill_gradient(visor_mask, (4, 16, 30, 245), (7, 34, 45, 235)))

    visor_edge = canvas.layer()
    draw = ImageDraw.Draw(visor_edge)
    draw.line(
        visor_points + [visor_points[0]],
        fill=(*CYAN[:3], 120),
        width=max(1, round(0.85 * SUPERSAMPLE)),
        joint="curve",
    )

    eye_center_y = lerp(58.0, 60.0, 1.0 - pose.eye_open)
    eye_height = max(0.45, 2.6 * pose.eye_open)
    eye_color = mix_color(CYAN, LIME, 0.20 + 0.18 * pose.accent, 245)
    eye_mask = Image.new("L", canvas.size, 0)
    draw = ImageDraw.Draw(eye_mask)
    eye_shapes = (
        ((111, 56), (124, 55), (121, 60), (110, 61)),
        ((145, 56), (132, 55), (135, 60), (146, 61)),
    )
    for shape in eye_shapes:
        points = []
        for x, y in shape:
            transformed_y = eye_center_y + (y - 58.0) * (eye_height / 2.6)
            points.append(canvas.point(x, transformed_y))
        draw.polygon(points, fill=255)
    eye_glow = canvas.layer()
    add_glow(eye_glow, eye_mask, eye_color, 3.0, 0.65)
    canvas.composite(eye_glow)
    eyes = Image.new("RGBA", canvas.size, eye_color)
    eyes.putalpha(eye_mask)
    canvas.composite(eyes)
    canvas.composite(visor_edge)

    core_center = canvas.point(128, 101)
    core_layer = canvas.layer()
    draw = ImageDraw.Draw(core_layer)
    core_color = mix_color(CYAN, LIME, 0.42 + 0.18 * pose.accent, 255)
    for radius, alpha in ((15, 40), (11, 70), (8, 130)):
        mask = Image.new("L", canvas.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        scaled_radius = radius * SUPERSAMPLE
        mask_draw.ellipse(
            (
                core_center[0] - scaled_radius,
                core_center[1] - scaled_radius,
                core_center[0] + scaled_radius,
                core_center[1] + scaled_radius,
            ),
            fill=round(alpha * pose.core),
        )
        add_glow(core_layer, mask, core_color, radius * 0.7, pose.core)

    outer_hexagon = [
        (round(x * SUPERSAMPLE), round(y * SUPERSAMPLE))
        for x, y in regular_polygon(
            core_center[0] / SUPERSAMPLE,
            core_center[1] / SUPERSAMPLE,
            9.2,
            6,
        )
    ]
    inner_hexagon = [
        (round(x * SUPERSAMPLE), round(y * SUPERSAMPLE))
        for x, y in regular_polygon(
            core_center[0] / SUPERSAMPLE,
            core_center[1] / SUPERSAMPLE,
            5.8,
            6,
        )
    ]
    draw.polygon(outer_hexagon, fill=OUTLINE)
    draw.line(
        outer_hexagon + [outer_hexagon[0]],
        fill=(*core_color[:3], 230),
        width=round(1.5 * SUPERSAMPLE),
        joint="curve",
    )
    draw.polygon(
        inner_hexagon,
        fill=(*core_color[:3], round(190 + 60 * pose.core)),
    )
    center_radius = 2.1 * SUPERSAMPLE
    draw.ellipse(
        (
            core_center[0] - center_radius,
            core_center[1] - center_radius,
            core_center[0] + center_radius,
            core_center[1] + center_radius,
        ),
        fill=WHITE,
    )
    canvas.composite(core_layer)


def draw_state_effects(canvas: Canvas, phase: float) -> None:
    pose = canvas.pose
    layer = canvas.layer()
    draw = ImageDraw.Draw(layer)
    accent = mix_color(CYAN, VIOLET, pose.accent, 230)

    if pose.media > 0.01:
        for index in range(6):
            angle = phase + index * TAU / 6
            radius = 47 + 5 * math.sin(phase * 2 + index)
            x, y = canvas.point(
                128 + radius * math.cos(angle),
                98 + 0.42 * radius * math.sin(angle),
            )
            diamond_radius = (
                1.6 + 1.0 * (0.5 + 0.5 * math.sin(phase * 2 + index))
            ) * SUPERSAMPLE
            draw.polygon(
                [
                    (x, y - diamond_radius),
                    (x + diamond_radius, y),
                    (x, y + diamond_radius),
                    (x - diamond_radius, y),
                ],
                fill=(*accent[:3], round(150 * pose.media)),
            )
        for index in range(3):
            x = 117 + index * 11
            height = 4 + 10 * (
                0.5 + 0.5 * math.sin(phase * 2 + index * 1.4)
            )
            first = canvas.point(x, 123 - height / 2)
            second = canvas.point(x + 4, 123 + height / 2)
            draw.rounded_rectangle(
                (*first, *second),
                radius=1.4 * SUPERSAMPLE,
                fill=(*accent[:3], round(135 * pose.media)),
            )

    if pose.data > 0.01:
        for index in range(8):
            angle = phase * 1.6 + index * TAU / 8
            radius = 52 + 4 * math.sin(phase + index)
            x, y = canvas.point(
                128 + radius * math.cos(angle),
                96 + 0.48 * radius * math.sin(angle),
            )
            tangent = angle + math.pi / 2
            delta_x = math.cos(tangent) * 3.2 * SUPERSAMPLE
            delta_y = math.sin(tangent) * 3.2 * SUPERSAMPLE
            normal_x = -math.sin(tangent) * 1.2 * SUPERSAMPLE
            normal_y = math.cos(tangent) * 1.2 * SUPERSAMPLE
            draw.polygon(
                [
                    (x - delta_x - normal_x, y - delta_y - normal_y),
                    (x + delta_x - normal_x, y + delta_y - normal_y),
                    (x + delta_x + normal_x, y + delta_y + normal_y),
                    (x - delta_x + normal_x, y - delta_y + normal_y),
                ],
                fill=(*TEAL[:3], round(120 * pose.data)),
            )
        scan_y = 47 + 20 * pose.scan
        draw.line(
            [canvas.point(105, scan_y), canvas.point(151, scan_y)],
            fill=(*LIME[:3], round(170 * pose.data)),
            width=max(1, round(0.8 * SUPERSAMPLE)),
        )

    for index in range(7):
        angle = phase * (0.45 + 0.07 * index) + index * 2.399963
        radius = 39 + 8 * ((index * 37) % 7) / 6
        x, y = canvas.point(
            128 + radius * math.cos(angle),
            91 + 0.72 * radius * math.sin(angle),
        )
        particle_radius = (
            0.55 + 0.7 * ((index * 53) % 5) / 4
        ) * SUPERSAMPLE
        color = mix_color(
            TEAL,
            LIME,
            (index % 3) / 3,
            round(
                (45 + 110 * pose.particles)
                * (0.72 + 0.28 * math.sin(angle) ** 2)
            ),
        )
        draw.ellipse(
            (
                x - particle_radius,
                y - particle_radius,
                x + particle_radius,
                y + particle_radius,
            ),
            fill=color,
        )

    bloom = canvas.layer()
    add_glow(bloom, layer.getchannel("A"), accent, 2.6, 0.38)
    canvas.composite(bloom)
    canvas.composite(layer)


def render_frame(state: str, frame: int) -> Image.Image:
    pose = pose_for(state, frame)
    canvas = Canvas(pose)
    looping = state in {"idle", "working", "moving"}
    position = frame / COLUMNS if looping else frame / (COLUMNS - 1)
    phase = TAU * (position % 1.0)

    draw_tail(canvas, phase)
    draw_holographic_rings(canvas, phase)
    draw_arm(canvas, "left")
    draw_body(canvas)
    draw_arm(canvas, "right")
    draw_state_effects(canvas, phase)
    return finish_frame(canvas.image)
