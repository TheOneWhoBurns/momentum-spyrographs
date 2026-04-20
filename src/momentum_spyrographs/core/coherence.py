from __future__ import annotations

import math

import numpy as np

from momentum_spyrographs.core.analysis_config import (
    CANONICAL_DT,
    CANONICAL_WINDOW_SECONDS,
    DIVERGENCE_COLOR_MAX,
    DIVERGENCE_DELTA_OMEGA1,
    DIVERGENCE_DELTA_OMEGA2,
    DIVERGENCE_DELTA_THETA1,
    DIVERGENCE_DELTA_THETA2,
    OMEGA_NORMALIZATION,
    canonical_seed,
)
from momentum_spyrographs.core.models import CoherenceMetrics, PendulumSeed
from momentum_spyrographs.core.sim import simulate


def _wrap_pi(values: np.ndarray) -> np.ndarray:
    return (values + math.pi) % (2.0 * math.pi) - math.pi


def state_distance_series(states_a: np.ndarray, states_b: np.ndarray) -> np.ndarray:
    delta = states_a - states_b
    wrapped_theta1 = _wrap_pi(delta[:, 0])
    wrapped_theta2 = _wrap_pi(delta[:, 1])
    omega1 = delta[:, 2] / OMEGA_NORMALIZATION
    omega2 = delta[:, 3] / OMEGA_NORMALIZATION
    return np.sqrt(wrapped_theta1**2 + wrapped_theta2**2 + omega1**2 + omega2**2)


def divergence_score_from_states(states_a: np.ndarray, states_b: np.ndarray) -> float:
    if len(states_a) == 0 or len(states_b) == 0:
        return float("inf")
    distances = state_distance_series(states_a, states_b)
    if len(distances) == 0 or not np.isfinite(distances).all():
        return float("inf")
    d0 = float(distances[0])
    if not math.isfinite(d0) or d0 <= 0.0:
        return float("inf")
    dmax = float(np.max(distances))
    if not math.isfinite(dmax) or dmax <= 0.0:
        return float("inf")
    return float(math.log10(max(dmax / d0, 1.0)))


def coherence_rank(divergence_score: float) -> float:
    if not math.isfinite(divergence_score):
        return 0.0
    return max(0.0, min(1.0, 1.0 - (divergence_score / DIVERGENCE_COLOR_MAX)))


def twin_seed(seed: PendulumSeed) -> PendulumSeed:
    return seed.with_updates(
        theta1=seed.theta1 + DIVERGENCE_DELTA_THETA1,
        theta2=seed.theta2 + DIVERGENCE_DELTA_THETA2,
        omega1=seed.omega1 + DIVERGENCE_DELTA_OMEGA1,
        omega2=seed.omega2 + DIVERGENCE_DELTA_OMEGA2,
        duration=CANONICAL_WINDOW_SECONDS,
        dt=CANONICAL_DT,
    )


def compute_divergence_score(seed: PendulumSeed) -> float:
    analysis_seed = canonical_seed(seed)
    _, states = simulate(analysis_seed.to_config())
    _, twin_states = simulate(twin_seed(analysis_seed).to_config())
    return divergence_score_from_states(states, twin_states)


def compute_coherence_metrics(seed: PendulumSeed) -> CoherenceMetrics:
    divergence_score = compute_divergence_score(seed)
    return CoherenceMetrics(
        divergence_score=divergence_score,
        coherence_rank=coherence_rank(divergence_score),
    )
