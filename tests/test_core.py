from __future__ import annotations

import numpy as np

from momentum_spyrographs.core.analysis_config import CANONICAL_DT, CANONICAL_WINDOW_SECONDS, canonical_seed
from momentum_spyrographs.core.coherence import compute_divergence_score
from momentum_spyrographs.core.discovery import (
    build_orbit_signature,
    compare_orbit_signatures,
    compute_seed_metrics,
    search_creative_candidates,
)
from momentum_spyrographs.core.map_tiles import RESOLUTION_LEVELS, default_viewport, structural_seed_key, visible_tiles
from momentum_spyrographs.core.models import (
    CreativeControls,
    ExplorationMapPayload,
    MapRequest,
    PendulumSeed,
    PeriodicityStatus,
    RegionSearchRequest,
)
from momentum_spyrographs.core.project import simulate_projected_points
from momentum_spyrographs.core.render import write_gif, write_svg
from momentum_spyrographs.core.stability_map import (
    _colorize_divergence,
    render_map_level,
    sample_stability_map,
    search_stable_minima,
)


def test_simulation_is_deterministic_and_has_expected_shape() -> None:
    seed = PendulumSeed(duration=1.2, dt=0.02, omega1=1.6, omega2=-0.2)
    points_a = simulate_projected_points(seed, max_points=80)
    points_b = simulate_projected_points(seed, max_points=80)
    assert points_a.shape == (61, 2)
    assert np.allclose(points_a, points_b)


def test_creative_search_returns_best_seed_metrics_and_suggestions() -> None:
    seed = PendulumSeed(duration=12.0, dt=0.02)
    controls = CreativeControls(shape_x=-0.7, shape_y=0.4, motion_x=-0.8, motion_y=-0.5)
    selected_seed, metrics, points, suggestions = search_creative_candidates(seed, controls)
    assert isinstance(selected_seed, PendulumSeed)
    assert points.shape[1] == 2
    assert metrics.periodicity_status == PeriodicityStatus.NOT_PROVEN
    assert len(suggestions) >= 3


def test_metrics_are_bounded_and_do_not_claim_periodicity() -> None:
    seed = canonical_seed(PendulumSeed(duration=2.0, dt=0.02))
    points = simulate_projected_points(seed, max_points=120)
    metrics = compute_seed_metrics(seed, points)
    assert 0.0 <= metrics.circularity_score <= 1.0
    assert 0.0 <= metrics.density_score <= 1.0
    assert 0.0 <= metrics.visual_symmetry_score <= 1.0
    assert 0.0 <= metrics.coherence_rank <= 1.0
    assert metrics.periodicity_status == PeriodicityStatus.NOT_PROVEN


def test_divergence_score_is_finite_for_normal_seed() -> None:
    seed = PendulumSeed(theta1=0.35, theta2=-0.3, omega1=1.4, omega2=-0.9)
    divergence = compute_divergence_score(seed)
    assert np.isfinite(divergence)
    assert divergence >= 0.0


def test_orbit_signature_prefers_closer_trace_family() -> None:
    reference = canonical_seed(PendulumSeed(theta1=0.60, theta2=-0.55, omega1=1.38, omega2=-1.14))
    similar = reference.with_updates(omega1=1.83, omega2=-1.52)
    different = canonical_seed(PendulumSeed())

    reference_points = simulate_projected_points(reference)
    similar_points = simulate_projected_points(similar)
    different_points = simulate_projected_points(different)

    reference_signature = build_orbit_signature(reference_points, compute_seed_metrics(reference, reference_points))
    similar_signature = build_orbit_signature(similar_points, compute_seed_metrics(similar, similar_points))
    different_signature = build_orbit_signature(different_points, compute_seed_metrics(different, different_points))

    similar_score = compare_orbit_signatures(reference_signature, similar_signature)
    different_score = compare_orbit_signatures(reference_signature, different_signature)
    assert similar_score > different_score + 0.1


def test_search_stable_minima_returns_markers_for_real_map_region() -> None:
    seed = PendulumSeed(theta1=0.60, theta2=-0.55, omega1=1.38, omega2=-1.14)
    analysis_seed = canonical_seed(seed)
    points = simulate_projected_points(analysis_seed)
    metrics = compute_seed_metrics(analysis_seed, points)
    payload = sample_stability_map(seed, grid_size=33)
    request = RegionSearchRequest(
        mode="viewport",
        payload=payload,
        reference_seed=seed,
        reference_points=points,
        reference_metrics=metrics,
        omega1_min=payload.viewport_omega1_min,
        omega1_max=payload.viewport_omega1_max,
        omega2_min=payload.viewport_omega2_min,
        omega2_max=payload.viewport_omega2_max,
    )

    result = search_stable_minima(request)

    assert result.markers
    assert result.status_text.startswith("Showing ")
    assert all(np.isfinite(marker.divergence_score) for marker in result.markers)
    assert all(marker.metrics.periodicity_status == PeriodicityStatus.NOT_PROVEN for marker in result.markers)


def test_search_stable_minima_returns_no_markers_when_box_has_no_finite_cells() -> None:
    payload = ExplorationMapPayload(
        image=np.zeros((8, 8, 3), dtype=np.uint8),
        divergence_grid=np.full((16, 16), np.inf, dtype=np.float32),
        overlay_seed=PendulumSeed(),
        selected_omega1=0.0,
        selected_omega2=0.0,
        viewport_omega1_min=-2.0,
        viewport_omega1_max=2.0,
        viewport_omega2_min=-2.0,
        viewport_omega2_max=2.0,
        resolution_level=8,
        exact_resolution_level=16,
        tile_size=8,
        pending_tiles=0,
        completed_tiles=1,
        minima_markers=tuple(),
    )
    seed = PendulumSeed()
    points = simulate_projected_points(canonical_seed(seed))
    metrics = compute_seed_metrics(canonical_seed(seed), points)
    request = RegionSearchRequest(
        mode="box",
        payload=payload,
        reference_seed=seed,
        reference_points=points,
        reference_metrics=metrics,
        omega1_min=-1.0,
        omega1_max=1.0,
        omega2_min=-1.0,
        omega2_max=1.0,
    )

    result = search_stable_minima(request)

    assert result.markers == tuple()
    assert result.status_text == "No stable minima found in box"


def test_stability_map_returns_color_grid_and_axes() -> None:
    payload = sample_stability_map(PendulumSeed(), grid_size=9)
    assert payload.image.shape == (9, 9, 3)
    assert payload.divergence_grid.shape == (18, 18)
    assert payload.viewport_omega1_min < payload.viewport_omega1_max
    assert payload.viewport_omega2_min < payload.viewport_omega2_max


def test_divergence_color_ramp_is_black_for_low_values_and_colored_for_high_values() -> None:
    low = _colorize_divergence(np.array([[0.0]], dtype=np.float32))
    high = _colorize_divergence(np.array([[6.0]], dtype=np.float32))
    assert float(low.mean()) < 1.0
    assert float(high.mean()) > 30.0


def test_structural_key_excludes_selected_start_speeds() -> None:
    seed_a = PendulumSeed(omega1=1.0, omega2=-2.0)
    seed_b = seed_a.with_updates(omega1=8.0, omega2=7.0)
    assert structural_seed_key(seed_a) == structural_seed_key(seed_b)


def test_render_map_level_returns_finite_payload_with_exact_grid() -> None:
    seed = PendulumSeed(theta1=0.4, theta2=-0.2)
    viewport = default_viewport(seed, pixel_size=64)
    request = MapRequest(
        seed=seed,
        viewport=viewport,
        structural_key=structural_seed_key(seed),
        selected_omega1=seed.omega1,
        selected_omega2=seed.omega2,
    )
    payload = render_map_level(request, resolution_level=64, tile_size=32)
    assert payload.image.shape == (64, 64, 3)
    assert payload.divergence_grid.shape == (128, 128)
    assert np.isfinite(payload.divergence_grid).any()


def test_final_map_level_uses_smaller_exact_grid_cap() -> None:
    seed = PendulumSeed()
    viewport = default_viewport(seed, pixel_size=RESOLUTION_LEVELS[-1])
    request = MapRequest(
        seed=seed,
        viewport=viewport,
        structural_key=structural_seed_key(seed),
        selected_omega1=seed.omega1,
        selected_omega2=seed.omega2,
    )
    payload = render_map_level(request, resolution_level=RESOLUTION_LEVELS[-1])
    assert payload.resolution_level == 512
    assert payload.exact_resolution_level == 512


def test_visible_tiles_cover_requested_level() -> None:
    viewport = default_viewport(PendulumSeed(), pixel_size=128)
    tiles = visible_tiles(viewport, resolution_level=128, tile_size=64)
    assert len(tiles) == 4


def test_svg_and_gif_exports_write_files(tmp_path) -> None:
    seed = PendulumSeed(theta1=0.4, theta2=-0.2, omega1=2.0, omega2=-1.5, duration=2.0, dt=0.02)
    svg_path = tmp_path / "sample.svg"
    gif_path = tmp_path / "sample.gif"
    points = simulate_projected_points(seed)

    write_svg(points, svg_path, width=600, height=600)
    write_gif(points, gif_path, width=240, height=240, frames=8, fps=8)

    assert svg_path.exists() and svg_path.read_text().lstrip().startswith("<svg")
    assert gif_path.exists() and gif_path.stat().st_size > 0


def test_canonical_analysis_constants_match_product_contract() -> None:
    assert CANONICAL_WINDOW_SECONDS == 24.0
    assert CANONICAL_DT == 0.02
