from __future__ import annotations

import numpy as np

from momentum_spyrographs.core.discovery import compute_seed_metrics, search_creative_candidates
from momentum_spyrographs.core.models import CreativeControls, PendulumSeed, PresetRecord, RenderSettings, create_preset_record
from momentum_spyrographs.core.presets import PresetStore
from momentum_spyrographs.core.project import simulate_projected_points
from momentum_spyrographs.core.render import write_gif, write_svg
from momentum_spyrographs.core.stability_map import sample_stability_map


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
    assert 0.0 <= metrics.stability_score <= 1.0
    assert len(suggestions) >= 3


def test_metrics_are_bounded() -> None:
    seed = PendulumSeed(duration=2.0, dt=0.02)
    points = simulate_projected_points(seed, max_points=120)
    metrics = compute_seed_metrics(seed, points)
    assert 0.0 <= metrics.circularity_score <= 1.0
    assert 0.0 <= metrics.density_score <= 1.0
    assert 0.0 <= metrics.stability_score <= 1.0


def test_stability_map_returns_color_grid_and_axes() -> None:
    payload = sample_stability_map(PendulumSeed(duration=6.0, dt=0.03), grid_size=9)
    assert payload.image.shape == (9, 9, 3)
    assert payload.periodicity.shape == (9, 9)
    assert payload.chaos.shape == (9, 9)
    assert payload.omega1_values.shape == (9,)
    assert payload.omega2_values.shape == (9,)


def test_preset_store_round_trip_archive_restore_and_migration(tmp_path) -> None:
    store = PresetStore(root=tmp_path)
    preset = create_preset_record(name="Orbit Study")
    saved = store.save_preset(preset)
    assert saved.thumbnail_path is not None

    loaded = store.load_preset(saved.id)
    assert loaded.name == "Orbit Study"
    assert store.list_presets()[0].id == saved.id

    legacy_seed = PendulumSeed().to_dict()
    legacy = PresetRecord.from_dict(
        {
            "id": "legacy",
            "name": "Legacy",
            "seed": legacy_seed,
            "render_settings": {
                "stroke_color": "#ffffff",
                "stroke_width": 3.0,
                "background_theme": "forest",
                "fadeout": 0.25,
            },
            "created_at": saved.created_at,
            "updated_at": saved.updated_at,
        }
    )
    assert legacy.render_settings.background_color == "#102a25"
    assert legacy.creative_controls == CreativeControls()

    store.archive_preset(saved.id)
    assert store.list_presets() == []
    assert store.list_presets(include_archived=True)[0].is_archived

    store.restore_preset(saved.id)
    restored = store.list_presets()[0]
    assert restored.id == saved.id
    assert not restored.is_archived


def test_svg_and_gif_export_support_styled_render_options(tmp_path) -> None:
    points = simulate_projected_points(PendulumSeed(duration=1.2, dt=0.01))
    svg_path = tmp_path / "sample.svg"
    gif_path = tmp_path / "sample.gif"
    render_settings = RenderSettings(
        background_mode="gradient",
        background_gradient_start="#09131d",
        background_gradient_end="#1b3b34",
        stroke_mode="gradient",
        stroke_gradient_start="#ff8844",
        stroke_gradient_end="#ffee88",
        fade_mode="gradient",
        fade_gradient_start="#09131d",
        fade_gradient_end="#ff8844",
        glow_enabled=True,
        glow_intensity=0.6,
        glow_radius=18.0,
    )
    write_svg(points, svg_path, width=512, height=512, render_settings=render_settings, fidelity="styled")
    write_gif(points, gif_path, width=360, height=360, frames=24, fps=18, render_settings=render_settings, fidelity="full_glow_raster")

    assert svg_path.exists()
    svg_text = svg_path.read_text(encoding="utf-8")
    assert "bgGradient" in svg_text
    assert "strokeGradient" in svg_text
    assert gif_path.exists()
    assert gif_path.stat().st_size > 0
