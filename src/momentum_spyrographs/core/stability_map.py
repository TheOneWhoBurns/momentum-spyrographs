from __future__ import annotations

import colorsys
import math
from typing import Callable

import numpy as np

from momentum_spyrographs.core.analysis_config import (
    CANONICAL_DT,
    CANONICAL_WINDOW_SECONDS,
    DIVERGENCE_COLOR_MAX,
    DIVERGENCE_COLOR_MIN,
    DIVERGENCE_DELTA_OMEGA1,
    DIVERGENCE_DELTA_OMEGA2,
    DIVERGENCE_DELTA_THETA1,
    DIVERGENCE_DELTA_THETA2,
    EXACT_GRID_CAP,
    EXACT_GRID_SCALE,
    MARKER_DEDUP_CELLS,
    MARKER_LIMIT,
    OMEGA_NORMALIZATION,
)
from momentum_spyrographs.core.discovery import (
    build_orbit_signature,
    compare_orbit_signatures,
    compute_seed_metrics,
)
from momentum_spyrographs.core.map_tiles import TILE_SIZE, default_viewport, visible_tiles
from momentum_spyrographs.core.models import (
    ExplorationMapPayload,
    MapRequest,
    MapViewport,
    PendulumSeed,
    RegionSearchMarker,
    RegionSearchRequest,
    RegionSearchResult,
)
from momentum_spyrographs.core.project import simulate_projected_path
from momentum_spyrographs.core.stability_kernel import compute_tile_divergence


def _hsv_to_rgb_array(hue: np.ndarray, saturation: np.ndarray, value: np.ndarray) -> np.ndarray:
    flat = np.empty((hue.size, 3), dtype=np.uint8)
    for index, (h, s, v) in enumerate(zip(hue.flat, saturation.flat, value.flat)):
        red, green, blue = colorsys.hsv_to_rgb(float(h), float(s), float(v))
        flat[index] = (int(red * 255), int(green * 255), int(blue * 255))
    return flat.reshape((*hue.shape, 3))


def _tile_axis_values(minimum: float, maximum: float, count: int, *, descending: bool = False) -> np.ndarray:
    step = (maximum - minimum) / max(count, 1)
    centers = minimum + (np.arange(count, dtype=np.float64) + 0.5) * step
    return centers[::-1] if descending else centers


def _pool_divergence_min(samples: np.ndarray, factor: int) -> np.ndarray:
    if factor <= 1:
        return samples
    height, width = samples.shape
    reshaped = samples.reshape(height // factor, factor, width // factor, factor)
    pooled = np.full((height // factor, width // factor), np.inf, dtype=np.float32)
    for row in range(height // factor):
        for col in range(width // factor):
            block = reshaped[row, :, col, :].reshape(-1)
            finite = block[np.isfinite(block)]
            if finite.size:
                pooled[row, col] = np.float32(np.min(finite))
    return pooled


def _colorize_divergence(divergence_grid: np.ndarray) -> np.ndarray:
    image = np.zeros((*divergence_grid.shape, 3), dtype=np.uint8)
    normalized = np.clip(
        (np.nan_to_num(divergence_grid, nan=DIVERGENCE_COLOR_MAX, posinf=DIVERGENCE_COLOR_MAX) - DIVERGENCE_COLOR_MIN)
        / max(DIVERGENCE_COLOR_MAX - DIVERGENCE_COLOR_MIN, 1e-9),
        0.0,
        1.0,
    )
    colored = normalized > 1e-6
    if not np.any(colored):
        return image
    hue = 0.70 - 0.63 * normalized[colored]
    saturation = 0.70 + 0.25 * normalized[colored]
    value = 0.12 + 0.74 * normalized[colored]
    image[colored] = _hsv_to_rgb_array(hue, saturation, value)
    return image


def omega_to_grid_index(payload: ExplorationMapPayload, omega1: float, omega2: float) -> tuple[int, int]:
    height, width = payload.divergence_grid.shape
    x_ratio = (omega1 - payload.viewport_omega1_min) / max(payload.viewport_omega1_max - payload.viewport_omega1_min, 1e-9)
    y_ratio = (payload.viewport_omega2_max - omega2) / max(payload.viewport_omega2_max - payload.viewport_omega2_min, 1e-9)
    col = int(np.clip(round(x_ratio * (width - 1)), 0, width - 1))
    row = int(np.clip(round(y_ratio * (height - 1)), 0, height - 1))
    return row, col


def grid_index_to_omega(payload: ExplorationMapPayload, row: int, col: int) -> tuple[float, float]:
    height, width = payload.divergence_grid.shape
    omega1 = payload.viewport_omega1_min + ((col + 0.5) / max(width, 1)) * (
        payload.viewport_omega1_max - payload.viewport_omega1_min
    )
    omega2 = payload.viewport_omega2_max - ((row + 0.5) / max(height, 1)) * (
        payload.viewport_omega2_max - payload.viewport_omega2_min
    )
    return float(omega1), float(omega2)


def _bounds_to_grid_window(
    payload: ExplorationMapPayload,
    *,
    omega1_a: float,
    omega1_b: float,
    omega2_a: float,
    omega2_b: float,
) -> tuple[int, int, int, int]:
    top_left_row, top_left_col = omega_to_grid_index(payload, min(omega1_a, omega1_b), max(omega2_a, omega2_b))
    bottom_right_row, bottom_right_col = omega_to_grid_index(payload, max(omega1_a, omega1_b), min(omega2_a, omega2_b))
    row_min = max(0, min(top_left_row, bottom_right_row))
    row_max = min(payload.divergence_grid.shape[0] - 1, max(top_left_row, bottom_right_row))
    col_min = max(0, min(top_left_col, bottom_right_col))
    col_max = min(payload.divergence_grid.shape[1] - 1, max(top_left_col, bottom_right_col))
    return row_min, row_max, col_min, col_max


def _local_minima_in_window(grid: np.ndarray, row_min: int, row_max: int, col_min: int, col_max: int) -> list[tuple[int, int, float]]:
    minima: list[tuple[int, int, float]] = []
    for row in range(row_min, row_max + 1):
        for col in range(col_min, col_max + 1):
            value = float(grid[row, col])
            if not math.isfinite(value):
                continue
            local_row_min = max(row_min, row - 1)
            local_row_max = min(row_max + 1, row + 2)
            local_col_min = max(col_min, col - 1)
            local_col_max = min(col_max + 1, col + 2)
            neighborhood = grid[local_row_min:local_row_max, local_col_min:local_col_max]
            finite_neighbors = neighborhood[np.isfinite(neighborhood)]
            if finite_neighbors.size == 0:
                continue
            if value <= float(np.min(finite_neighbors)) + 1e-9:
                minima.append((row, col, value))
    if minima:
        return minima

    window = grid[row_min : row_max + 1, col_min : col_max + 1]
    finite_mask = np.isfinite(window)
    if not np.any(finite_mask):
        return []
    masked = np.where(finite_mask, window, np.inf)
    flat_index = int(np.argmin(masked))
    local_row, local_col = np.unravel_index(flat_index, masked.shape)
    value = float(masked[local_row, local_col])
    return [(row_min + local_row, col_min + local_col, value)]


def _deduplicate_cells(candidates: list[tuple[int, int, float]], *, spacing: int = MARKER_DEDUP_CELLS) -> list[tuple[int, int, float]]:
    selected: list[tuple[int, int, float]] = []
    for row, col, divergence in sorted(candidates, key=lambda item: item[2]):
        if any(np.hypot(row - existing_row, col - existing_col) < spacing for existing_row, existing_col, _ in selected):
            continue
        selected.append((row, col, divergence))
    return selected


def _collect_candidate_cells(
    payload: ExplorationMapPayload,
    *,
    omega1_min: float,
    omega1_max: float,
    omega2_min: float,
    omega2_max: float,
    limit: int = 24,
) -> list[tuple[int, int, float]]:
    row_min, row_max, col_min, col_max = _bounds_to_grid_window(
        payload,
        omega1_a=omega1_min,
        omega1_b=omega1_max,
        omega2_a=omega2_min,
        omega2_b=omega2_max,
    )
    if row_max < row_min or col_max < col_min:
        return []
    raw_candidates = _local_minima_in_window(payload.divergence_grid, row_min, row_max, col_min, col_max)
    return _deduplicate_cells(raw_candidates)[:limit]


def _candidate_seed(reference_seed: PendulumSeed, *, omega1: float, omega2: float) -> PendulumSeed:
    return reference_seed.with_updates(
        omega1=omega1,
        omega2=omega2,
        duration=CANONICAL_WINDOW_SECONDS,
        dt=CANONICAL_DT,
    )


def _rank_markers(request: RegionSearchRequest, candidate_cells: list[tuple[int, int, float]]) -> tuple[RegionSearchMarker, ...]:
    if len(request.reference_points) < 8:
        return tuple()

    reference_signature = build_orbit_signature(request.reference_points, request.reference_metrics)
    markers: list[RegionSearchMarker] = []
    for row, col, divergence in candidate_cells:
        omega1, omega2 = grid_index_to_omega(request.payload, row, col)
        candidate_seed = _candidate_seed(request.reference_seed, omega1=omega1, omega2=omega2)
        points, states = simulate_projected_path(candidate_seed)
        if len(points) < 8:
            continue
        metrics = compute_seed_metrics(candidate_seed, points, states=states, divergence_score=divergence)
        signature = build_orbit_signature(points, metrics)
        pattern_similarity = compare_orbit_signatures(reference_signature, signature)
        score = (
            0.55 * pattern_similarity
            + 0.25 * metrics.coherence_rank
            + 0.15 * metrics.visual_symmetry_score
            + 0.05 * (1.0 - metrics.chaos_score)
        )
        markers.append(
            RegionSearchMarker(
                seed=request.reference_seed.with_updates(omega1=omega1, omega2=omega2),
                score=score,
                pattern_similarity=pattern_similarity,
                divergence_score=divergence,
                metrics=metrics,
            )
        )

    markers.sort(
        key=lambda marker: (
            marker.pattern_similarity,
            -marker.divergence_score,
            marker.metrics.visual_symmetry_score,
            -marker.metrics.chaos_score,
        ),
        reverse=True,
    )
    return tuple(markers[:MARKER_LIMIT])


def search_stable_minima(request: RegionSearchRequest) -> RegionSearchResult:
    candidate_cells = _collect_candidate_cells(
        request.payload,
        omega1_min=request.omega1_min,
        omega1_max=request.omega1_max,
        omega2_min=request.omega2_min,
        omega2_max=request.omega2_max,
        limit=max(MARKER_LIMIT * 2, 24),
    )
    markers = _rank_markers(request, candidate_cells)
    label = "box" if request.mode == "box" else "visible area"
    if markers:
        return RegionSearchResult(
            mode=request.mode,
            omega1_min=request.omega1_min,
            omega1_max=request.omega1_max,
            omega2_min=request.omega2_min,
            omega2_max=request.omega2_max,
            markers=markers,
            status_text=f"Showing {len(markers)} stable minima in {label}",
        )
    return RegionSearchResult(
        mode=request.mode,
        omega1_min=request.omega1_min,
        omega1_max=request.omega1_max,
        omega2_min=request.omega2_min,
        omega2_max=request.omega2_max,
        markers=tuple(),
        status_text=f"No stable minima found in {label}",
    )


def render_map_level(
    request: MapRequest,
    *,
    resolution_level: int,
    tile_size: int = TILE_SIZE,
    progress_callback: Callable[[int, int], None] | None = None,
) -> ExplorationMapPayload:
    viewport = request.viewport.with_updates(pixel_width=resolution_level, pixel_height=resolution_level)
    exact_resolution = min(resolution_level * EXACT_GRID_SCALE, EXACT_GRID_CAP)
    pooling_factor = max(exact_resolution // max(resolution_level, 1), 1)

    image = np.zeros((resolution_level, resolution_level, 3), dtype=np.uint8)
    divergence_grid = np.full((exact_resolution, exact_resolution), np.inf, dtype=np.float32)

    tiles = visible_tiles(viewport, resolution_level=resolution_level, tile_size=tile_size)
    total_tiles = len(tiles)
    for tile_index, tile in enumerate(tiles, start=1):
        sample_width = tile.pixel_width * pooling_factor
        sample_height = tile.pixel_height * pooling_factor
        omega1_values = _tile_axis_values(tile.omega1_min, tile.omega1_max, sample_width)
        omega2_values = _tile_axis_values(tile.omega2_min, tile.omega2_max, sample_height, descending=True)
        tile_divergence = compute_tile_divergence(
            omega1_values,
            omega2_values,
            request.seed.theta1,
            request.seed.theta2,
            request.seed.length1,
            request.seed.length2,
            request.seed.mass1,
            request.seed.mass2,
            request.seed.gravity,
            CANONICAL_WINDOW_SECONDS,
            CANONICAL_DT,
            DIVERGENCE_DELTA_THETA1,
            DIVERGENCE_DELTA_THETA2,
            DIVERGENCE_DELTA_OMEGA1,
            DIVERGENCE_DELTA_OMEGA2,
            OMEGA_NORMALIZATION,
        )

        exact_y_slice = slice(tile.pixel_y * pooling_factor, (tile.pixel_y + tile.pixel_height) * pooling_factor)
        exact_x_slice = slice(tile.pixel_x * pooling_factor, (tile.pixel_x + tile.pixel_width) * pooling_factor)
        divergence_grid[exact_y_slice, exact_x_slice] = tile_divergence

        display_tile = _pool_divergence_min(tile_divergence, pooling_factor)
        y_slice = slice(tile.pixel_y, tile.pixel_y + tile.pixel_height)
        x_slice = slice(tile.pixel_x, tile.pixel_x + tile.pixel_width)
        image[y_slice, x_slice] = _colorize_divergence(display_tile)
        if progress_callback is not None:
            progress_callback(tile_index, total_tiles)

    return ExplorationMapPayload(
        image=image,
        divergence_grid=divergence_grid,
        overlay_seed=request.seed,
        selected_omega1=request.selected_omega1,
        selected_omega2=request.selected_omega2,
        viewport_omega1_min=viewport.omega1_min,
        viewport_omega1_max=viewport.omega1_max,
        viewport_omega2_min=viewport.omega2_min,
        viewport_omega2_max=viewport.omega2_max,
        resolution_level=resolution_level,
        exact_resolution_level=exact_resolution,
        tile_size=tile_size,
        pending_tiles=0,
        completed_tiles=total_tiles,
        minima_markers=tuple(),
    )


def sample_stability_map(
    seed: PendulumSeed,
    *,
    grid_size: int = 41,
    velocity_limit: float | None = None,
) -> ExplorationMapPayload:
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


search_matching_loop = search_stable_minima
