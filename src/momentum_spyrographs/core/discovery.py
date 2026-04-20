from __future__ import annotations

from dataclasses import replace
import math

import numpy as np

from momentum_spyrographs.core.analysis_config import canonical_seed
from momentum_spyrographs.core.coherence import CoherenceMetrics, coherence_rank, compute_coherence_metrics
from momentum_spyrographs.core.models import (
    CreativeControls,
    PendulumSeed,
    PeriodicityStatus,
    SeedMetrics,
    SuggestionCandidate,
    TraceMetrics,
)
from momentum_spyrographs.core.project import simulate_projected_path


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def normalize_points_for_metrics(points: np.ndarray) -> np.ndarray:
    if len(points) == 0:
        return points
    centered = points - points.mean(axis=0)
    span = float(np.max(np.ptp(centered, axis=0)))
    if span <= 1e-9:
        return centered
    return centered / span


def compute_seed_energy(seed: PendulumSeed) -> float:
    delta = seed.theta1 - seed.theta2
    kinetic = 0.5 * (seed.mass1 + seed.mass2) * (seed.length1**2) * (seed.omega1**2)
    kinetic += 0.5 * seed.mass2 * (seed.length2**2) * (seed.omega2**2)
    kinetic += seed.mass2 * seed.length1 * seed.length2 * seed.omega1 * seed.omega2 * math.cos(delta)
    potential = -(seed.mass1 + seed.mass2) * seed.gravity * seed.length1 * math.cos(seed.theta1)
    potential -= seed.mass2 * seed.gravity * seed.length2 * math.cos(seed.theta2)
    return kinetic + potential


def compute_trace_turns(points: np.ndarray) -> float:
    if len(points) < 3:
        return 0.0
    centered = points - points.mean(axis=0)
    angles = np.unwrap(np.arctan2(centered[:, 1], centered[:, 0]))
    return float(np.sum(np.abs(np.diff(angles))) / (2.0 * math.pi))


def build_orbit_signature(points: np.ndarray, metrics: SeedMetrics) -> np.ndarray:
    normalized = normalize_points_for_metrics(points)
    if len(normalized) < 4:
        return np.zeros(24 * 3 + 4, dtype=np.float64)

    radii = np.linalg.norm(normalized, axis=1)
    radial_hist, _ = np.histogram(radii, bins=24, range=(0.0, max(1.0, float(np.max(radii)) + 1e-6)))

    angles = (np.arctan2(normalized[:, 1], normalized[:, 0]) + 2.0 * math.pi) % (2.0 * math.pi)
    angular_hist, _ = np.histogram(angles, bins=24, range=(0.0, 2.0 * math.pi))

    diffs = np.diff(normalized, axis=0)
    headings = np.unwrap(np.arctan2(diffs[:, 1], diffs[:, 0]))
    turns = np.diff(headings)
    turn_hist, _ = np.histogram(turns, bins=24, range=(-math.pi, math.pi))

    parts = []
    for hist in (radial_hist, angular_hist, turn_hist):
        hist = hist.astype(np.float64)
        total = hist.sum() or 1.0
        parts.append(hist / total)

    parts.append(
        np.array(
            [
                metrics.visual_symmetry_score,
                metrics.circularity_score,
                metrics.density_score,
                clamp01(metrics.turns_total / 24.0),
            ],
            dtype=np.float64,
        )
    )
    return np.concatenate(parts)


def compare_orbit_signatures(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-12:
        return 0.0
    return clamp01(float(np.dot(a, b) / denom))


def compute_seed_metrics(
    seed: PendulumSeed,
    points: np.ndarray,
    states: np.ndarray | None = None,
    *,
    divergence_score: float | None = None,
) -> SeedMetrics:
    normalized = normalize_points_for_metrics(points)
    energy = compute_seed_energy(seed)

    if divergence_score is None:
        coherence = compute_coherence_metrics(seed)
    else:
        coherence = CoherenceMetrics(divergence_score=divergence_score, coherence_rank=coherence_rank(divergence_score))

    if len(normalized) < 4:
        return SeedMetrics(
            energy=energy,
            chaos_score=0.0,
            trace_metrics=TraceMetrics(turns_total=compute_trace_turns(points)),
            coherence_metrics=coherence,
            periodicity_status=PeriodicityStatus.NOT_PROVEN,
        )

    radii = np.linalg.norm(normalized, axis=1)
    spans = np.ptp(normalized, axis=0)
    balance = clamp01(float(np.min(spans) / max(np.max(spans), 1e-9)))
    radial_consistency = clamp01(math.exp(-float(np.std(radii)) * 7.0))
    circularity = clamp01(0.68 * radial_consistency + 0.32 * balance)

    diffs = np.diff(normalized, axis=0)
    headings = np.unwrap(np.arctan2(diffs[:, 1], diffs[:, 0]))
    turns = np.diff(headings)
    chaos = clamp01(float(np.std(turns)) / 1.35) if len(turns) else 0.0

    bins = 18
    hist, _, _ = np.histogram2d(
        normalized[:, 0],
        normalized[:, 1],
        bins=bins,
        range=[[-0.7, 0.7], [-0.7, 0.7]],
    )
    occupancy = float(np.count_nonzero(hist)) / float(hist.size)
    density = clamp01(occupancy * 2.4)

    total = hist.sum() or 1.0
    rotated = np.flipud(np.fliplr(hist))
    mirrored = np.fliplr(hist)
    rot_delta = float(np.abs(hist - rotated).sum() / total)
    mirror_delta = float(np.abs(hist - mirrored).sum() / total)
    angles = (np.arctan2(normalized[:, 1], normalized[:, 0]) + 2.0 * math.pi) % (2.0 * math.pi)
    angular_hist, _ = np.histogram(angles, bins=24, range=(0.0, 2.0 * math.pi))
    angular_mean = float(np.mean(angular_hist)) or 1.0
    angular_balance = clamp01(math.exp(-float(np.std(angular_hist / angular_mean)) * 0.45))
    mirror_symmetry = clamp01(1.0 - min(rot_delta, mirror_delta))
    symmetry = clamp01(0.75 * angular_balance + 0.10 * mirror_symmetry + 0.15 * circularity)

    return SeedMetrics(
        energy=energy,
        chaos_score=chaos,
        trace_metrics=TraceMetrics(
            turns_total=compute_trace_turns(points),
            visual_symmetry_score=symmetry,
            circularity_score=circularity,
            density_score=density,
        ),
        coherence_metrics=coherence,
        periodicity_status=PeriodicityStatus.NOT_PROVEN,
    )


def describe_metrics(metrics: SeedMetrics) -> str:
    if metrics.coherence_rank > 0.82 and metrics.circularity_score > 0.74:
        return "Calm Orbit"
    if metrics.density_score > 0.7 and metrics.visual_symmetry_score > 0.55 and metrics.coherence_rank > 0.45:
        return "Dense Mandala"
    if metrics.chaos_score > 0.6 and metrics.density_score > 0.5:
        return "Wild Rosette"
    if metrics.circularity_score > 0.62 and metrics.density_score < 0.45:
        return "Soft Pretzel"
    if metrics.visual_symmetry_score > 0.6 and metrics.density_score > 0.45:
        return "Bright Floral"
    return "Unstable Lace" if metrics.chaos_score > 0.55 else "Ornate Orbit"


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _candidate_key(seed: PendulumSeed) -> tuple[float, float, float, float, str]:
    return (
        round(seed.theta1, 3),
        round(seed.theta2, 3),
        round(seed.omega1, 3),
        round(seed.omega2, 3),
        seed.space,
    )


def _with_motion(
    base_seed: PendulumSeed,
    *,
    theta1: float,
    theta2: float,
    omega1: float,
    omega2: float,
) -> PendulumSeed:
    return base_seed.with_updates(
        theta1=_clamp(theta1, -2.9, 2.9),
        theta2=_clamp(theta2, -2.9, 2.9),
        omega1=_clamp(omega1, -6.0, 6.0),
        omega2=_clamp(omega2, -6.0, 6.0),
    )


def _generate_candidate_seeds(base_seed: PendulumSeed, controls: CreativeControls) -> list[PendulumSeed]:
    energy_pref = (controls.motion_y + 1.0) / 2.0
    coherence_pref = (1.0 - controls.motion_x) / 2.0
    density_pref = (controls.shape_y + 1.0) / 2.0
    circular_pref = (1.0 - controls.shape_x) / 2.0
    chaos_pref = 1.0 - coherence_pref
    wild_pref = 1.0 - circular_pref

    omega_radius = 0.18 + 2.25 * energy_pref + 0.75 * chaos_pref
    angle_radius = 0.05 + 0.65 * wild_pref + 0.35 * density_pref + 0.25 * chaos_pref
    asymmetry = 0.08 + 0.95 * wild_pref + 0.35 * chaos_pref
    softness = 0.10 + 0.70 * coherence_pref

    family_seeds = [
        _with_motion(
            base_seed,
            theta1=(0.08 + 0.28 * circular_pref) * (0.9 + 0.1 * density_pref),
            theta2=-(0.08 + 0.28 * circular_pref) * (0.82 + 0.18 * coherence_pref),
            omega1=0.35 + omega_radius * (0.55 + 0.18 * circular_pref),
            omega2=-(0.30 + omega_radius * (0.45 + 0.24 * coherence_pref)),
        ),
        _with_motion(
            base_seed,
            theta1=angle_radius * (0.42 + 0.35 * density_pref),
            theta2=-angle_radius * (0.32 + 0.42 * wild_pref),
            omega1=omega_radius * (0.85 + 0.20 * density_pref),
            omega2=-(omega_radius * (0.18 + 0.65 * circular_pref)),
        ),
        _with_motion(
            base_seed,
            theta1=angle_radius * (0.75 + 0.22 * density_pref),
            theta2=angle_radius * (0.28 + 0.55 * asymmetry),
            omega1=omega_radius * (0.45 + 0.18 * coherence_pref),
            omega2=omega_radius * (0.92 + 0.28 * wild_pref),
        ),
        _with_motion(
            base_seed,
            theta1=-(angle_radius * (0.52 + 0.38 * wild_pref)),
            theta2=angle_radius * (0.82 + 0.22 * density_pref),
            omega1=-(omega_radius * (0.50 + 0.25 * softness)),
            omega2=omega_radius * (0.48 + 0.42 * chaos_pref),
        ),
    ]

    candidates: dict[tuple[float, float, float, float, str], PendulumSeed] = {}
    candidates[_candidate_key(base_seed)] = base_seed

    local_angle_step = 0.06 + 0.10 * wild_pref
    local_omega_step = 0.12 + 0.36 * chaos_pref + 0.18 * density_pref
    local_offsets = (
        (-1.0, 0.0, -1.0, 0.0),
        (1.0, 0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0, -1.0),
        (0.0, 1.0, 0.0, 1.0),
        (-1.0, 1.0, -1.0, 1.0),
        (1.0, -1.0, 1.0, -1.0),
    )
    for theta_dx, theta_dy, omega_dx, omega_dy in local_offsets:
        candidate = _with_motion(
            base_seed,
            theta1=base_seed.theta1 + theta_dx * local_angle_step,
            theta2=base_seed.theta2 + theta_dy * local_angle_step,
            omega1=base_seed.omega1 + omega_dx * local_omega_step,
            omega2=base_seed.omega2 + omega_dy * local_omega_step,
        )
        candidates[_candidate_key(candidate)] = candidate

    for family_seed in family_seeds:
        for theta_scale, omega_scale in ((0.9, 0.9), (1.0, 1.0), (1.1, 1.1)):
            candidate = _with_motion(
                base_seed,
                theta1=family_seed.theta1 * theta_scale,
                theta2=family_seed.theta2 * theta_scale,
                omega1=family_seed.omega1 * omega_scale,
                omega2=family_seed.omega2 * omega_scale,
            )
            candidates[_candidate_key(candidate)] = candidate

    return list(candidates.values())


def _score_target(metrics: SeedMetrics, controls: CreativeControls) -> float:
    circular_pref = (1.0 - controls.shape_x) / 2.0
    density_pref = (controls.shape_y + 1.0) / 2.0
    coherence_pref = (1.0 - controls.motion_x) / 2.0
    chaos_pref = (controls.motion_x + 1.0) / 2.0
    energy_pref = (controls.motion_y + 1.0) / 2.0
    symmetry_pref = 0.35 + 0.55 * circular_pref

    score = 0.0
    score += 2.8 * (1.0 - abs(metrics.circularity_score - circular_pref))
    score += 1.8 * (1.0 - abs(metrics.density_score - density_pref))
    score += 2.3 * (1.0 - abs(metrics.coherence_rank - coherence_pref))
    score += 1.2 * (1.0 - abs(metrics.chaos_score - chaos_pref))
    score += 1.0 * (1.0 - abs(metrics.energy_score - energy_pref))
    score += 1.2 * (1.0 - abs(metrics.visual_symmetry_score - symmetry_pref))
    score += 0.8 * metrics.circularity_score * circular_pref
    score += 0.6 * metrics.visual_symmetry_score * circular_pref
    score += 0.5 * metrics.coherence_rank * coherence_pref
    return score


def replace_seed_metrics(metrics: SeedMetrics, **kwargs: float) -> SeedMetrics:
    return replace(metrics, **kwargs)


def _normalize_energy_scores(metrics_by_seed: list[tuple[PendulumSeed, SeedMetrics, np.ndarray]]) -> None:
    energies = [metrics.energy for _, metrics, _ in metrics_by_seed]
    energy_min = min(energies)
    energy_max = max(energies)
    span = max(1e-9, energy_max - energy_min)
    for index, (seed, metrics, points) in enumerate(metrics_by_seed):
        normalized = clamp01((metrics.energy - energy_min) / span)
        metrics_by_seed[index] = (
            seed,
            replace_seed_metrics(metrics, energy_score=normalized),
            points,
        )


def build_suggestions(
    ranked: list[tuple[float, PendulumSeed, SeedMetrics, np.ndarray]],
    best_seed: PendulumSeed,
) -> tuple[SuggestionCandidate, ...]:
    suggestions: list[SuggestionCandidate] = []
    labels = [
        ("Nearest Circular", lambda item: item[2].circularity_score + 0.5 * item[2].coherence_rank),
        ("Nearest Dense", lambda item: item[2].density_score + 0.35 * item[2].symmetry_score),
        ("Nearest Calm", lambda item: item[2].coherence_rank + (1.0 - item[2].energy_score)),
        ("Nearest Ornate", lambda item: item[2].density_score + item[2].symmetry_score),
        ("Best Match", lambda item: item[0]),
    ]
    seen: set[tuple[float, float]] = {(best_seed.omega1, best_seed.omega2)}
    for label, selector in labels:
        ordered = sorted(ranked, key=selector, reverse=True)
        for _, seed, metrics, points in ordered:
            key = (seed.omega1, seed.omega2)
            if key in seen:
                continue
            suggestions.append(SuggestionCandidate(label=label, seed=seed, metrics=metrics, points=points))
            seen.add(key)
            break
    return tuple(suggestions[:6])


def search_creative_candidates(
    base_seed: PendulumSeed,
    controls: CreativeControls,
) -> tuple[PendulumSeed, SeedMetrics, np.ndarray, tuple[SuggestionCandidate, ...]]:
    preview_seed = canonical_seed(base_seed)
    candidates = _generate_candidate_seeds(preview_seed, controls)
    metrics_by_seed: list[tuple[PendulumSeed, SeedMetrics, np.ndarray]] = []
    for candidate in candidates:
        points, states = simulate_projected_path(candidate, max_points=900)
        metrics = compute_seed_metrics(candidate, points, states=states)
        metrics_by_seed.append((candidate, metrics, points))

    _normalize_energy_scores(metrics_by_seed)

    ranked = sorted(
        ((_score_target(metrics, controls), candidate, metrics, points) for candidate, metrics, points in metrics_by_seed),
        key=lambda item: item[0],
        reverse=True,
    )
    _, best_preview_seed, best_metrics, _ = ranked[0]
    best_seed = base_seed.with_updates(
        theta1=best_preview_seed.theta1,
        theta2=best_preview_seed.theta2,
        omega1=best_preview_seed.omega1,
        omega2=best_preview_seed.omega2,
        space=best_preview_seed.space,
    )
    best_points, _ = simulate_projected_path(canonical_seed(best_seed), max_points=1800)
    suggestions = build_suggestions(ranked, best_seed)
    return best_seed, best_metrics, best_points, suggestions
