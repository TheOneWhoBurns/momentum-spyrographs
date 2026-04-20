from __future__ import annotations

import numpy as np

from momentum_spyrographs.core.models import PendulumSeed
from momentum_spyrographs.core.sim import simulate


def generalized_momenta(
    states: np.ndarray,
    config: PendulumSeed,
) -> tuple[np.ndarray, np.ndarray]:
    theta1 = states[:, 0]
    theta2 = states[:, 1]
    omega1 = states[:, 2]
    omega2 = states[:, 3]
    delta = theta1 - theta2

    p1 = (
        (config.mass1 + config.mass2) * config.length1 * config.length1 * omega1
        + config.mass2
        * config.length1
        * config.length2
        * omega2
        * np.cos(delta)
    )
    p2 = (
        config.mass2 * config.length2 * config.length2 * omega2
        + config.mass2
        * config.length1
        * config.length2
        * omega1
        * np.cos(delta)
    )
    return p1, p2


def project_points(states: np.ndarray, config: PendulumSeed, space: str) -> np.ndarray:
    if space == "momentum":
        x_values, y_values = generalized_momenta(states, config)
    elif space == "omega":
        x_values, y_values = states[:, 2], states[:, 3]
    elif space == "angle":
        x_values = np.unwrap(states[:, 0])
        y_values = np.unwrap(states[:, 1])
    elif space == "trace":
        theta1 = states[:, 0]
        theta2 = states[:, 1]
        x1 = config.length1 * np.sin(theta1)
        y1 = -config.length1 * np.cos(theta1)
        x_values = x1 + config.length2 * np.sin(theta2)
        y_values = y1 - config.length2 * np.cos(theta2)
    else:
        raise ValueError(f"Unsupported space: {space}")

    return np.column_stack((x_values, y_values))


def simulate_projected_points(
    seed: PendulumSeed,
    max_points: int | None = None,
) -> np.ndarray:
    _, states = simulate(seed.to_config())
    points = project_points(states, seed, seed.space)
    finite_mask = np.isfinite(points).all(axis=1)
    points = points[finite_mask]
    if max_points is not None and len(points) > max_points:
        indices = np.linspace(0, len(points) - 1, max_points, dtype=int)
        return points[indices]
    return points
