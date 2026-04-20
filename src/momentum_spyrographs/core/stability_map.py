from __future__ import annotations

import colorsys
from typing import Callable

import numpy as np

from momentum_spyrographs.core.map_tiles import TILE_SIZE, default_viewport, visible_tiles
from momentum_spyrographs.core.models import MapRequest, MapViewport, PendulumSeed, StabilityMapPayload
from momentum_spyrographs.core.stability_kernel import compute_tile_metrics


def _clamp01(value: np.ndarray | float) -> np.ndarray | float:
    return np.clip(value, 0.0, 1.0)


def map_simulation_params(seed: PendulumSeed) -> tuple[float, float]:
    return min(seed.duration, 6.0), max(seed.dt, 0.08)


def _hsv_to_rgb_array(hue: np.ndarray, saturation: np.ndarray, value: np.ndarray) -> np.ndarray:
    flat = np.empty((hue.size, 3), dtype=np.uint8)
    for index, (h, s, v) in enumerate(zip(hue.flat, saturation.flat, value.flat)):
        red, green, blue = colorsys.hsv_to_rgb(float(h), float(s), float(v))
        flat[index] = (int(red * 255), int(green * 255), int(blue * 255))
    return flat.reshape((*hue.shape, 3))


def _colorize_tile(periodicity: np.ndarray, chaos: np.ndarray, phase: np.ndarray) -> np.ndarray:
    periodic_mask = periodicity > 0.065
    hue = np.where(
        periodic_mask,
        (0.02 + 0.95 * phase + 0.12 * (1.0 - chaos)) % 1.0,
        0.63 + 0.10 * (1.0 - chaos),
    )
    saturation = np.where(
        periodic_mask,
        0.84 - 0.18 * chaos,
        0.35 + 0.25 * (1.0 - chaos),
    )
    value = np.where(
        periodic_mask,
        0.28 + 0.72 * periodicity,
        0.02 + 0.16 * (1.0 - chaos),
    )
    return _hsv_to_rgb_array(_clamp01(hue), _clamp01(saturation), _clamp01(value))


def _tile_axis_values(minimum: float, maximum: float, count: int, *, descending: bool = False) -> np.ndarray:
    step = (maximum - minimum) / max(count, 1)
    centers = minimum + (np.arange(count, dtype=np.float64) + 0.5) * step
    return centers[::-1] if descending else centers


def render_map_level(
    request: MapRequest,
    *,
    resolution_level: int,
    tile_size: int = TILE_SIZE,
    progress_callback: Callable[[int, int], None] | None = None,
) -> StabilityMapPayload:
    viewport = request.viewport.with_updates(pixel_width=resolution_level, pixel_height=resolution_level)
    duration, dt = map_simulation_params(request.seed)
    omega_scale = max(2.0, 0.5 * max(viewport.span_omega1, viewport.span_omega2))

    image = np.zeros((resolution_level, resolution_level, 3), dtype=np.uint8)
    periodicity = np.zeros((resolution_level, resolution_level), dtype=np.float32)
    chaos = np.ones((resolution_level, resolution_level), dtype=np.float32)

    tiles = visible_tiles(viewport, resolution_level=resolution_level, tile_size=tile_size)
    total_tiles = len(tiles)
    for tile_index, tile in enumerate(tiles, start=1):
        omega1_values = _tile_axis_values(tile.omega1_min, tile.omega1_max, tile.pixel_width)
        omega2_values = _tile_axis_values(
            tile.omega2_min,
            tile.omega2_max,
            tile.pixel_height,
            descending=True,
        )
        tile_periodicity, tile_chaos, tile_phase = compute_tile_metrics(
            omega1_values,
            omega2_values,
            request.seed.theta1,
            request.seed.theta2,
            request.seed.length1,
            request.seed.length2,
            request.seed.mass1,
            request.seed.mass2,
            request.seed.gravity,
            duration,
            dt,
            omega_scale,
        )
        y_slice = slice(tile.pixel_y, tile.pixel_y + tile.pixel_height)
        x_slice = slice(tile.pixel_x, tile.pixel_x + tile.pixel_width)
        periodicity[y_slice, x_slice] = tile_periodicity
        chaos[y_slice, x_slice] = tile_chaos
        image[y_slice, x_slice] = _colorize_tile(tile_periodicity, tile_chaos, tile_phase)
        if progress_callback is not None:
            progress_callback(tile_index, total_tiles)

    return StabilityMapPayload(
        image=image,
        periodicity=periodicity,
        chaos=chaos,
        overlay_seed=request.seed,
        selected_omega1=request.selected_omega1,
        selected_omega2=request.selected_omega2,
        viewport_omega1_min=viewport.omega1_min,
        viewport_omega1_max=viewport.omega1_max,
        viewport_omega2_min=viewport.omega2_min,
        viewport_omega2_max=viewport.omega2_max,
        resolution_level=resolution_level,
        tile_size=tile_size,
        pending_tiles=0,
        completed_tiles=total_tiles,
    )


def sample_stability_map(
    seed: PendulumSeed,
    *,
    grid_size: int = 41,
    velocity_limit: float | None = None,
) -> StabilityMapPayload:
    if velocity_limit is None:
        viewport = default_viewport(seed, pixel_size=grid_size)
    else:
        viewport = MapViewport(
            center_omega1=0.0,
            center_omega2=0.0,
            span_omega1=velocity_limit * 2.0,
            span_omega2=velocity_limit * 2.0,
            pixel_width=grid_size,
            pixel_height=grid_size,
        )
    request = MapRequest(
        seed=seed,
        viewport=viewport,
        structural_key=(),
        selected_omega1=seed.omega1,
        selected_omega2=seed.omega2,
    )
    return render_map_level(request, resolution_level=grid_size, tile_size=min(TILE_SIZE, grid_size))
