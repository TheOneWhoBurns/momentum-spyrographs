from __future__ import annotations

import math
from pathlib import Path
from typing import Union

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFilter

from momentum_spyrographs.core.models import RenderSettings


DEFAULT_BACKGROUND_THEME = "midnight"
DEFAULT_STROKE = "#ff9d76"
BACKGROUND_THEMES = {
    "midnight": "#0d1117",
    "paper": "#f4efe4",
    "forest": "#102a25",
}


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def reduce_points(points: np.ndarray, max_points: int) -> np.ndarray:
    if len(points) <= max_points:
        return points
    indices = np.linspace(0, len(points) - 1, max_points, dtype=int)
    return points[indices]


def background_color(theme_name: str) -> str:
    if theme_name.startswith("#"):
        return theme_name
    return BACKGROUND_THEMES.get(theme_name, BACKGROUND_THEMES[DEFAULT_BACKGROUND_THEME])


def normalize_points(
    points: np.ndarray,
    width: int,
    height: int,
    padding: float = 0.08,
) -> np.ndarray:
    mins = points.min(axis=0)
    maxs = points.max(axis=0)
    spans = np.maximum(maxs - mins, 1e-9)

    usable_width = width * (1.0 - 2.0 * padding)
    usable_height = height * (1.0 - 2.0 * padding)

    scale = min(usable_width / spans[0], usable_height / spans[1])
    centered = (points - (mins + maxs) / 2.0) * scale
    centered[:, 1] *= -1.0
    centered[:, 0] += width / 2.0
    centered[:, 1] += height / 2.0
    return centered


def svg_path(points: np.ndarray) -> str:
    commands = [f"M {points[0,0]:.2f} {points[0,1]:.2f}"]
    commands.extend(f"L {x:.2f} {y:.2f}" for x, y in points[1:])
    return " ".join(commands)


def _hex_to_rgba(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    r, g, b = ImageColor.getrgb(color)
    return (r, g, b, alpha)


def rgba_hex(color: tuple[int, int, int, int] | tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*color[:3])


def lerp_rgba(
    start: tuple[int, int, int, int],
    end: tuple[int, int, int, int],
    amount: float,
) -> tuple[int, int, int, int]:
    ratio = max(0.0, min(1.0, amount))
    return tuple(int(round(a + (b - a) * ratio)) for a, b in zip(start, end))


def interpolate_hex(start: str, end: str, amount: float, alpha: int = 255) -> tuple[int, int, int, int]:
    return lerp_rgba(_hex_to_rgba(start, alpha=alpha), _hex_to_rgba(end, alpha=alpha), amount)


def background_gradient_endpoints(width: int, height: int, angle_degrees: int) -> tuple[tuple[float, float], tuple[float, float]]:
    angle = math.radians(angle_degrees)
    dx = math.cos(angle)
    dy = math.sin(angle)
    length = max(width, height)
    cx = width / 2.0
    cy = height / 2.0
    return (
        (cx - dx * length / 2.0, cy - dy * length / 2.0),
        (cx + dx * length / 2.0, cy + dy * length / 2.0),
    )


def build_background_image(
    width: int,
    height: int,
    render_settings: RenderSettings,
    fidelity: str = "styled",
) -> Image.Image:
    if fidelity == "flat" or render_settings.background_mode == "solid":
        return Image.new("RGBA", (width, height), _hex_to_rgba(render_settings.background_color))

    start = np.array(_hex_to_rgba(render_settings.background_gradient_start), dtype=np.float32)
    end = np.array(_hex_to_rgba(render_settings.background_gradient_end), dtype=np.float32)
    angle = math.radians(render_settings.background_gradient_angle)
    x_values = np.linspace(-0.5, 0.5, width, dtype=np.float32)
    y_values = np.linspace(-0.5, 0.5, height, dtype=np.float32)
    xx, yy = np.meshgrid(x_values, y_values)
    projection = xx * math.cos(angle) + yy * math.sin(angle)
    projection -= projection.min()
    max_projection = float(projection.max()) or 1.0
    projection /= max_projection
    image_array = start + (end - start) * projection[..., None]
    return Image.fromarray(np.uint8(np.clip(image_array, 0, 255)), mode="RGBA")


def segment_style(
    render_settings: RenderSettings,
    progress_ratio: float,
    age_ratio: float,
    fidelity: str = "styled",
) -> tuple[int, int, int, int]:
    if fidelity == "flat" or render_settings.stroke_mode == "solid":
        color = _hex_to_rgba(render_settings.stroke_color)
    else:
        color = interpolate_hex(
            render_settings.stroke_gradient_start,
            render_settings.stroke_gradient_end,
            progress_ratio,
        )

    fade_strength = render_settings.fadeout * age_ratio
    if render_settings.fade_mode == "transparent" or fidelity == "flat":
        alpha = max(24, int(255 * (1.0 - fade_strength)))
        return (color[0], color[1], color[2], alpha)

    if render_settings.fade_mode == "color":
        fade_color = _hex_to_rgba(render_settings.fade_color)
        mixed = lerp_rgba(color, fade_color, fade_strength)
        alpha = max(48, int(255 * (1.0 - 0.55 * fade_strength)))
        return (mixed[0], mixed[1], mixed[2], alpha)

    fade_gradient = interpolate_hex(
        render_settings.fade_gradient_start,
        render_settings.fade_gradient_end,
        age_ratio,
    )
    mixed = lerp_rgba(color, fade_gradient, fade_strength)
    alpha = max(56, int(255 * (1.0 - 0.45 * fade_strength)))
    return (mixed[0], mixed[1], mixed[2], alpha)


def glow_color(render_settings: RenderSettings, progress_ratio: float) -> tuple[int, int, int, int]:
    if render_settings.glow_mode == "custom":
        return _hex_to_rgba(render_settings.glow_color)
    if render_settings.stroke_mode == "gradient":
        return interpolate_hex(
            render_settings.stroke_gradient_start,
            render_settings.stroke_gradient_end,
            progress_ratio,
        )
    return _hex_to_rgba(render_settings.stroke_color)


def render_static_image(
    points: np.ndarray,
    width: int,
    height: int,
    line_width: int,
    stroke_color: str,
    background: str,
) -> Image.Image:
    scaled = normalize_points(points, width, height)
    xy_points = [tuple(map(float, point)) for point in scaled]
    image = Image.new("RGBA", (width, height), _hex_to_rgba(background))
    draw = ImageDraw.Draw(image)
    draw.line(xy_points, fill=_hex_to_rgba(stroke_color), width=line_width)
    return image


def render_styled_frame(
    points: np.ndarray,
    width: int,
    height: int,
    render_settings: RenderSettings,
    progress: float = 1.0,
    fidelity: str = "styled",
    max_points: int = 4000,
) -> Image.Image:
    sampled = reduce_points(points, max_points)
    scaled = normalize_points(sampled, width, height)
    xy_points = [tuple(map(float, point)) for point in scaled]
    stop = max(2, int((len(xy_points) - 1) * max(0.0, min(1.0, progress))) + 1)

    image = build_background_image(width, height, render_settings, fidelity=fidelity)
    glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    line_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer, "RGBA")
    line_draw = ImageDraw.Draw(line_layer, "RGBA")
    pixel_width = max(1, int(round(render_settings.stroke_width)))

    for index in range(1, stop):
        progress_ratio = index / max(len(xy_points) - 1, 1)
        age_ratio = 1.0 - (index / max(stop - 1, 1))
        color = segment_style(render_settings, progress_ratio, age_ratio, fidelity=fidelity)
        segment = [xy_points[index - 1], xy_points[index]]
        if render_settings.glow_enabled and fidelity == "full_glow_raster":
            glow_rgba = glow_color(render_settings, progress_ratio)
            glow_alpha = int(255 * max(0.0, min(1.0, render_settings.glow_intensity)) * (1.0 - 0.45 * age_ratio))
            glow_draw.line(
                segment,
                fill=(glow_rgba[0], glow_rgba[1], glow_rgba[2], glow_alpha),
                width=max(pixel_width + int(render_settings.glow_radius * 1.35), pixel_width + 2),
            )
        line_draw.line(segment, fill=color, width=pixel_width)

    if render_settings.glow_enabled and fidelity == "full_glow_raster":
        blur_radius = max(1.0, render_settings.glow_radius / 2.4)
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        image = Image.alpha_composite(image, glow_layer)
    image = Image.alpha_composite(image, line_layer)
    return image


def _background_svg_fill(render_settings: RenderSettings, fidelity: str) -> tuple[str, str]:
    if fidelity == "flat" or render_settings.background_mode == "solid":
        return "", render_settings.background_color
    x1y1, x2y2 = background_gradient_endpoints(100, 100, render_settings.background_gradient_angle)
    defs = f"""
    <linearGradient id="bgGradient" gradientUnits="userSpaceOnUse" x1="{x1y1[0]:.2f}" y1="{x1y1[1]:.2f}" x2="{x2y2[0]:.2f}" y2="{x2y2[1]:.2f}">
      <stop offset="0%" stop-color="{render_settings.background_gradient_start}" />
      <stop offset="100%" stop-color="{render_settings.background_gradient_end}" />
    </linearGradient>
"""
    return defs, 'url(#bgGradient)'


def _stroke_svg_fill(render_settings: RenderSettings, fidelity: str, width: int, height: int) -> tuple[str, str]:
    if fidelity == "flat" or render_settings.stroke_mode == "solid":
        return "", render_settings.stroke_color
    defs = f"""
    <linearGradient id="strokeGradient" gradientUnits="userSpaceOnUse" x1="0" y1="{height}" x2="{width}" y2="0">
      <stop offset="0%" stop-color="{render_settings.stroke_gradient_start}" />
      <stop offset="100%" stop-color="{render_settings.stroke_gradient_end}" />
    </linearGradient>
"""
    return defs, 'url(#strokeGradient)'


def write_svg(
    points: np.ndarray,
    destination: Union[str, Path],
    width: int = 1600,
    height: int = 1600,
    stroke_width: float = 1.8,
    max_points: int = 12000,
    stroke_color: str = DEFAULT_STROKE,
    background: str | None = None,
    render_settings: RenderSettings | None = None,
    fidelity: str = "flat",
) -> Path:
    destination = Path(destination)
    ensure_parent(destination)
    sampled = reduce_points(points, max_points)
    scaled = normalize_points(sampled, width, height)
    path_data = svg_path(scaled)

    if render_settings is None:
        render_settings = RenderSettings(
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            background_color=background or BACKGROUND_THEMES[DEFAULT_BACKGROUND_THEME],
        )
    defs_bg, fill = _background_svg_fill(render_settings, fidelity)
    defs_stroke, stroke = _stroke_svg_fill(render_settings, fidelity, width, height)
    defs_block = ""
    if defs_bg or defs_stroke:
        defs_block = f"  <defs>{defs_bg}{defs_stroke}  </defs>\n"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
{defs_block}  <rect width="100%" height="100%" fill="{fill}" />
  <path d="{path_data}" fill="none" stroke="{stroke}" stroke-width="{render_settings.stroke_width:.2f}" stroke-linecap="round" stroke-linejoin="round" />
</svg>
"""
    destination.write_text(svg, encoding="utf-8")
    return destination


def write_gif(
    points: np.ndarray,
    destination: Union[str, Path],
    width: int = 1200,
    height: int = 1200,
    frames: int = 120,
    fps: int = 24,
    line_width: float = 2.0,
    max_points: int = 4000,
    stroke_color: str = DEFAULT_STROKE,
    background: str | None = None,
    fadeout: float = 0.35,
    animation_speed: float = 1.0,
    render_settings: RenderSettings | None = None,
    fidelity: str = "styled",
) -> Path:
    destination = Path(destination)
    ensure_parent(destination)
    if render_settings is None:
        render_settings = RenderSettings(
            stroke_color=stroke_color,
            stroke_width=line_width,
            background_color=background or BACKGROUND_THEMES[DEFAULT_BACKGROUND_THEME],
            fadeout=fadeout,
            animation_speed=animation_speed,
        )

    images: list[Image.Image] = []
    for frame_index in range(1, frames + 1):
        progress = frame_index / frames
        frame = render_styled_frame(
            points,
            width=width,
            height=height,
            render_settings=render_settings,
            progress=progress,
            fidelity=fidelity,
            max_points=max_points,
        )
        images.append(frame.convert("P", palette=Image.Palette.ADAPTIVE))

    duration = max(10, int(1000 / max(fps * max(animation_speed, 0.02), 1)))
    images[0].save(
        destination,
        save_all=True,
        append_images=images[1:],
        duration=duration,
        loop=0,
    )
    return destination


def render_thumbnail(
    points: np.ndarray,
    destination: Union[str, Path],
    width: int = 320,
    height: int = 320,
    line_width: float = 2.0,
    stroke_color: str = DEFAULT_STROKE,
    background: str | None = None,
    render_settings: RenderSettings | None = None,
) -> Path:
    destination = Path(destination)
    ensure_parent(destination)
    settings = render_settings or RenderSettings(
        stroke_color=stroke_color,
        stroke_width=line_width,
        background_color=background or BACKGROUND_THEMES[DEFAULT_BACKGROUND_THEME],
    )
    image = render_styled_frame(
        points,
        width=width,
        height=height,
        render_settings=settings,
        progress=1.0,
        fidelity="styled",
        max_points=1800,
    )
    image.convert("RGB").save(destination)
    return destination
