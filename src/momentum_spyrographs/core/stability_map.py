from __future__ import annotations

import colorsys

import numpy as np

from momentum_spyrographs.core.discovery import clamp01, compute_seed_metrics
from momentum_spyrographs.core.models import PendulumSeed, StabilityMapPayload
from momentum_spyrographs.core.project import project_points
from momentum_spyrographs.core.sim import simulate


def _state_embedding(states: np.ndarray, omega_scale: float) -> np.ndarray:
    theta1 = states[:, 0]
    theta2 = states[:, 1]
    omega1 = states[:, 2] / omega_scale
    omega2 = states[:, 3] / omega_scale
    return np.column_stack(
        (
            np.sin(theta1),
            np.cos(theta1),
            np.sin(theta2),
            np.cos(theta2),
            omega1,
            omega2,
        )
    )


def _periodicity_score(states: np.ndarray, omega_scale: float) -> float:
    embedding = _state_embedding(states, omega_scale)
    lag_min = max(12, len(embedding) // 18)
    distances = np.linalg.norm(embedding[lag_min:] - embedding[0], axis=1)
    hits = np.where(distances < 0.16)[0]
    if hits.size == 0:
        return 0.0
    return clamp01(1.0 - ((hits[0] + lag_min) / max(len(embedding) - 1, 1)))


def _map_color(periodicity: float, chaos: float, density: float) -> tuple[int, int, int]:
    if periodicity > 0.08:
        hue = (0.12 + 0.76 * (1.0 - periodicity)) % 1.0
        saturation = 0.82 - 0.18 * chaos
        value = 0.72 + 0.25 * (1.0 - chaos)
    else:
        hue = 0.62 - 0.08 * (1.0 - chaos)
        saturation = 0.40 + 0.18 * density
        value = 0.05 + 0.38 * (1.0 - chaos) * (0.65 + 0.35 * density)
    red, green, blue = colorsys.hsv_to_rgb(hue, clamp01(saturation), clamp01(value))
    return int(red * 255), int(green * 255), int(blue * 255)


def sample_stability_map(
    seed: PendulumSeed,
    *,
    grid_size: int = 21,
    velocity_limit: float | None = None,
) -> StabilityMapPayload:
    velocity_span = velocity_limit or max(3.0, min(6.0, max(abs(seed.omega1), abs(seed.omega2), 2.4) + 1.2))
    omega1_values = np.linspace(-velocity_span, velocity_span, grid_size, dtype=np.float64)
    omega2_values = np.linspace(-velocity_span, velocity_span, grid_size, dtype=np.float64)

    image = np.zeros((grid_size, grid_size, 3), dtype=np.uint8)
    periodicity = np.zeros((grid_size, grid_size), dtype=np.float32)
    chaos = np.zeros((grid_size, grid_size), dtype=np.float32)
    omega_scale = max(1.5, velocity_span)

    preview_seed = seed.with_updates(
        duration=min(seed.duration, 12.0),
        dt=max(seed.dt, 0.05),
        space="trace",
    )

    for row_index, omega2 in enumerate(reversed(omega2_values)):
        for col_index, omega1 in enumerate(omega1_values):
            candidate = preview_seed.with_updates(omega1=float(omega1), omega2=float(omega2))
            _, states = simulate(candidate.to_config())
            points = project_points(states, candidate, "trace")
            if len(points) > 420:
                sample_indices = np.linspace(0, len(points) - 1, 420, dtype=int)
                metric_points = points[sample_indices]
            else:
                metric_points = points
            metrics = compute_seed_metrics(candidate, metric_points)
            periodic = max(
                _periodicity_score(states, omega_scale),
                metrics.closure_score * (1.0 - 0.55 * metrics.chaos_score),
            )
            chaoticness = clamp01(max(metrics.chaos_score, 1.0 - metrics.stability_score))
            periodicity[row_index, col_index] = periodic
            chaos[row_index, col_index] = chaoticness
            image[row_index, col_index] = _map_color(periodic, chaoticness, metrics.density_score)

    return StabilityMapPayload(
        omega1_values=omega1_values,
        omega2_values=omega2_values,
        image=image,
        periodicity=periodicity,
        chaos=chaos,
        selected_omega1=seed.omega1,
        selected_omega2=seed.omega2,
    )
