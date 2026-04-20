from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from momentum_spyrographs.core.models import MapViewport, PendulumSeed


TILE_SIZE = 32
RESOLUTION_LEVELS = (128, 256, 512)


@dataclass(frozen=True)
class TileSpec:
    tile_x: int
    tile_y: int
    pixel_x: int
    pixel_y: int
    pixel_width: int
    pixel_height: int
    omega1_min: float
    omega1_max: float
    omega2_min: float
    omega2_max: float


def structural_seed_key(
    seed: PendulumSeed,
    *,
    map_duration: float | None = None,
    map_dt: float | None = None,
) -> tuple[float, ...]:
    duration = map_duration if map_duration is not None else min(seed.duration, 6.0)
    dt = map_dt if map_dt is not None else max(seed.dt, 0.08)
    return (
        round(seed.theta1, 6),
        round(seed.theta2, 6),
        round(seed.length1, 6),
        round(seed.length2, 6),
        round(seed.mass1, 6),
        round(seed.mass2, 6),
        round(seed.gravity, 6),
        round(duration, 6),
        round(dt, 6),
    )


def default_velocity_span(seed: PendulumSeed) -> float:
    return max(4.0, min(12.0, max(abs(seed.omega1), abs(seed.omega2), 2.5) + 2.5))


def default_viewport(seed: PendulumSeed, *, pixel_size: int = 512) -> MapViewport:
    span = default_velocity_span(seed) * 2.0
    return MapViewport(
        center_omega1=0.0,
        center_omega2=0.0,
        span_omega1=span,
        span_omega2=span,
        pixel_width=pixel_size,
        pixel_height=pixel_size,
    )


def pan_viewport(viewport: MapViewport, *, delta_omega1: float, delta_omega2: float) -> MapViewport:
    return viewport.with_updates(
        center_omega1=viewport.center_omega1 + delta_omega1,
        center_omega2=viewport.center_omega2 + delta_omega2,
    )


def zoom_viewport(
    viewport: MapViewport,
    *,
    zoom_factor: float,
    focus_omega1: float | None = None,
    focus_omega2: float | None = None,
) -> MapViewport:
    clamped_factor = min(2.5, max(0.4, zoom_factor))
    next_span_omega1 = min(40.0, max(1.0, viewport.span_omega1 / clamped_factor))
    next_span_omega2 = min(40.0, max(1.0, viewport.span_omega2 / clamped_factor))
    if focus_omega1 is None or focus_omega2 is None:
        return viewport.with_updates(span_omega1=next_span_omega1, span_omega2=next_span_omega2)

    focus_x_ratio = (focus_omega1 - viewport.omega1_min) / max(viewport.span_omega1, 1e-9)
    focus_y_ratio = (focus_omega2 - viewport.omega2_min) / max(viewport.span_omega2, 1e-9)
    next_min_omega1 = focus_omega1 - focus_x_ratio * next_span_omega1
    next_min_omega2 = focus_omega2 - focus_y_ratio * next_span_omega2
    return viewport.with_updates(
        center_omega1=next_min_omega1 + 0.5 * next_span_omega1,
        center_omega2=next_min_omega2 + 0.5 * next_span_omega2,
        span_omega1=next_span_omega1,
        span_omega2=next_span_omega2,
    )


def visible_tiles(
    viewport: MapViewport,
    *,
    resolution_level: int,
    tile_size: int = TILE_SIZE,
) -> tuple[TileSpec, ...]:
    x_count = int(ceil(resolution_level / tile_size))
    y_count = int(ceil(resolution_level / tile_size))
    omega_per_pixel_x = viewport.span_omega1 / resolution_level
    omega_per_pixel_y = viewport.span_omega2 / resolution_level
    tiles: list[TileSpec] = []
    for tile_y in range(y_count):
        for tile_x in range(x_count):
            pixel_x = tile_x * tile_size
            pixel_y = tile_y * tile_size
            pixel_width = min(tile_size, resolution_level - pixel_x)
            pixel_height = min(tile_size, resolution_level - pixel_y)
            omega1_min = viewport.omega1_min + pixel_x * omega_per_pixel_x
            omega1_max = omega1_min + pixel_width * omega_per_pixel_x
            omega2_max = viewport.omega2_max - pixel_y * omega_per_pixel_y
            omega2_min = omega2_max - pixel_height * omega_per_pixel_y
            tiles.append(
                TileSpec(
                    tile_x=tile_x,
                    tile_y=tile_y,
                    pixel_x=pixel_x,
                    pixel_y=pixel_y,
                    pixel_width=pixel_width,
                    pixel_height=pixel_height,
                    omega1_min=omega1_min,
                    omega1_max=omega1_max,
                    omega2_min=omega2_min,
                    omega2_max=omega2_max,
                )
            )
    center_x = resolution_level / 2.0
    center_y = resolution_level / 2.0
    return tuple(
        sorted(
            tiles,
            key=lambda spec: (
                abs((spec.pixel_x + 0.5 * spec.pixel_width) - center_x)
                + abs((spec.pixel_y + 0.5 * spec.pixel_height) - center_y),
                spec.tile_y,
                spec.tile_x,
            ),
        )
    )
