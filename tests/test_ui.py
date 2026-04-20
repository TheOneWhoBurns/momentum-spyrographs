from __future__ import annotations

from PySide6.QtCore import QPointF, Qt

from momentum_spyrographs.app.window import MainWindow
from momentum_spyrographs.app.widgets.pendulum_canvas import PendulumCanvas
from momentum_spyrographs.app.widgets.spirograph_preview import SpirographPreview
from momentum_spyrographs.core.analysis_config import canonical_seed
from momentum_spyrographs.core.discovery import compute_seed_metrics
from momentum_spyrographs.core.map_tiles import RESOLUTION_LEVELS
from momentum_spyrographs.core.models import (
    CreativeControls,
    PendulumSeed,
    PeriodicityStatus,
    PreviewDocument,
    PreviewPayload,
    RegionSearchMarker,
    RegionSearchResult,
    RenderSettings,
    SeedMetrics,
    TraceMetrics,
)
from momentum_spyrographs.core.project import simulate_projected_points

MAP_READY_TIMEOUT_MS = 60000


class _FakeMouseEvent:
    def __init__(self, position: QPointF, button=Qt.MouseButton.LeftButton) -> None:
        self._position = position
        self._button = button

    def position(self) -> QPointF:
        return self._position

    def button(self):
        return self._button


def _marker(seed: PendulumSeed, *, divergence: float = 0.8, similarity: float = 0.9) -> RegionSearchMarker:
    metrics = SeedMetrics(
        trace_metrics=TraceMetrics(
            turns_total=6.4,
            visual_symmetry_score=0.82,
            circularity_score=0.66,
            density_score=0.48,
        ),
        coherence_metrics=compute_seed_metrics(canonical_seed(seed), simulate_projected_points(canonical_seed(seed))).coherence_metrics,
        periodicity_status=PeriodicityStatus.NOT_PROVEN,
    )
    return RegionSearchMarker(
        seed=seed,
        score=1.0,
        pattern_similarity=similarity,
        divergence_score=divergence,
        metrics=metrics,
    )


def test_pendulum_canvas_drag_emits_updated_angles(qtbot) -> None:
    canvas = PendulumCanvas()
    canvas.resize(420, 320)
    qtbot.addWidget(canvas)
    canvas.show()
    _, bob1, _ = canvas._bob_positions()

    with qtbot.waitSignal(canvas.anglesChanged, timeout=1000) as signal:
        canvas.mousePressEvent(_FakeMouseEvent(bob1))
        canvas.mouseMoveEvent(_FakeMouseEvent(bob1 + QPointF(36.0, 20.0)))
        canvas.mouseReleaseEvent(_FakeMouseEvent(bob1 + QPointF(36.0, 20.0)))

    theta1, theta2 = signal.args
    assert theta1 != 0.0
    assert theta2 == canvas._seed.theta2


def test_pendulum_canvas_angle_convention_matches_geometry() -> None:
    origin = QPointF(10.0, 10.0)
    assert abs(PendulumCanvas._point_to_theta(origin, QPointF(10.0, 40.0))) < 1e-9
    assert abs(PendulumCanvas._point_to_theta(origin, QPointF(40.0, 10.0)) - 1.57079632679) < 1e-3
    assert abs(PendulumCanvas._point_to_theta(origin, QPointF(-20.0, 10.0)) + 1.57079632679) < 1e-3


def test_pendulum_canvas_total_visual_length_changes_with_shorter_arms(qtbot) -> None:
    canvas = PendulumCanvas()
    canvas.resize(420, 320)
    qtbot.addWidget(canvas)
    canvas.show()

    pivot_default, bob1_default, bob2_default = canvas._bob_positions()
    default_total = canvas._distance(pivot_default, bob1_default) + canvas._distance(bob1_default, bob2_default)

    canvas.set_seed(canvas._seed.with_updates(length1=0.5, length2=0.5))
    pivot_short, bob1_short, bob2_short = canvas._bob_positions()
    short_total = canvas._distance(pivot_short, bob1_short) + canvas._distance(bob1_short, bob2_short)

    assert short_total < default_total


def test_spirograph_preview_shows_trace_metrics_without_loop_claims(qtbot) -> None:
    preview = SpirographPreview()
    qtbot.addWidget(preview)
    preview.show()

    seed = canonical_seed(PendulumSeed(theta1=0.60, theta2=-0.55, omega1=1.38, omega2=-1.14))
    points = simulate_projected_points(seed)
    metrics = compute_seed_metrics(seed, points)
    payload = PreviewPayload(
        document=PreviewDocument(
            seed=seed,
            render_settings=RenderSettings(),
            creative_controls=CreativeControls(),
        ),
        selected_seed=seed,
        points=points,
        metrics=metrics,
    )

    preview.set_preview_payload(payload)

    text = preview._metrics_label.text()
    assert text.startswith("Turns ")
    assert "Visual symmetry" in text
    assert "Loop" not in text
    assert preview.canvas._reference_only


def test_spirograph_preview_animates_full_trace_once_then_returns_to_reference(qtbot) -> None:
    preview = SpirographPreview()
    qtbot.addWidget(preview)
    preview.show()

    seed = canonical_seed(PendulumSeed(theta1=0.60, theta2=-0.55, omega1=1.38, omega2=-1.14))
    points = simulate_projected_points(seed)
    metrics = compute_seed_metrics(seed, points)
    payload = PreviewPayload(
        document=PreviewDocument(
            seed=seed,
            render_settings=RenderSettings(animation_speed=10.0),
            creative_controls=CreativeControls(),
        ),
        selected_seed=seed,
        points=points,
        metrics=metrics,
    )

    preview.set_preview_payload(payload)
    preview.canvas.play()
    for _ in range(400):
        preview.canvas._advance()
        if preview.canvas._reference_only:
            break

    assert preview.canvas._reference_only
    assert preview.canvas._progress == 0.0


def test_main_window_recomputes_preview_after_setup_change(qtbot, tmp_path) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.state.preview_payload is not None, timeout=5000)
    qtbot.waitUntil(
        lambda: window.map_panel._payload is not None and window.map_panel._payload.resolution_level >= RESOLUTION_LEVELS[-1],
        timeout=MAP_READY_TIMEOUT_MS,
    )
    _, bob1, _ = window.setup_panel.pendulum_canvas._bob_positions()
    window.setup_panel.pendulum_canvas.mousePressEvent(_FakeMouseEvent(bob1))
    window.setup_panel.pendulum_canvas.mouseReleaseEvent(_FakeMouseEvent(bob1))
    window.setup_panel._arm_popover._speed_slider.setValue(250)
    window.setup_panel._arm_popover._length_slider.setValue(175)
    qtbot.waitUntil(
        lambda: window.state.preview_payload is not None
        and abs(window.state.preview_payload.selected_seed.omega1 - 2.5) < 1e-9,
        timeout=5000,
    )
    assert abs(window.state.seed.length1 - 1.75) < 1e-9
    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.loop_search_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_side_panels_are_collapsible(qtbot, tmp_path) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    assert not window._left_sidebar.expanded
    assert not window._right_sidebar.expanded

    window._left_sidebar.set_expanded(True)
    assert window._left_sidebar.expanded
    assert not window._right_sidebar.expanded

    window._right_sidebar.set_expanded(True)
    assert not window._left_sidebar.expanded
    assert window._right_sidebar.expanded

    window._right_sidebar.set_expanded(False)
    assert not window._left_sidebar.expanded
    assert not window._right_sidebar.expanded

    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.loop_search_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_arm_popover_edits_speed_and_length_and_map_click_updates_seed(qtbot, tmp_path) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    _, bob1, _ = window.setup_panel.pendulum_canvas._bob_positions()
    window.setup_panel.pendulum_canvas.mousePressEvent(_FakeMouseEvent(bob1))
    window.setup_panel.pendulum_canvas.mouseReleaseEvent(_FakeMouseEvent(bob1))
    assert window.setup_panel._arm_popover.isVisible()
    assert window.setup_panel._arm_popover.arm_index == 1

    window.setup_panel._arm_popover._speed_spin.setValue(-1.25)
    window.setup_panel._arm_popover._length_spin.setValue(1.65)
    qtbot.waitUntil(lambda: abs(window.state.seed.omega1 + 1.25) < 1e-9, timeout=5000)
    assert abs(window.state.seed.length1 - 1.65) < 1e-9

    qtbot.waitUntil(
        lambda: window.map_panel._payload is not None and window.map_panel._payload.resolution_level >= RESOLUTION_LEVELS[-1],
        timeout=MAP_READY_TIMEOUT_MS,
    )
    map_rect = window.map_panel._canvas._map_rect()
    window.map_panel._canvas.mousePressEvent(_FakeMouseEvent(map_rect.center()))
    window.map_panel._canvas.mouseReleaseEvent(_FakeMouseEvent(map_rect.center()))
    qtbot.waitUntil(lambda: abs(window.state.seed.omega1) < 0.4 and abs(window.state.seed.omega2) < 0.4, timeout=5000)
    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.loop_search_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_map_zoom_and_left_drag_pan_update_viewport(qtbot, tmp_path) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(
        lambda: window.map_panel._payload is not None and window.map_panel._payload.resolution_level >= RESOLUTION_LEVELS[-1],
        timeout=MAP_READY_TIMEOUT_MS,
    )
    initial_span = window.state.map_viewport.span_omega1
    window.map_panel._zoom_in_button.click()
    qtbot.waitUntil(lambda: window.state.map_viewport.span_omega1 < initial_span, timeout=3000)

    map_rect = window.map_panel._canvas._map_rect()
    center = map_rect.center()
    window.map_panel._canvas.mousePressEvent(_FakeMouseEvent(center, button=Qt.MouseButton.LeftButton))
    window.map_panel._canvas.mouseMoveEvent(_FakeMouseEvent(center + QPointF(24.0, 0.0), button=Qt.MouseButton.LeftButton))
    window.map_panel._canvas.mouseReleaseEvent(_FakeMouseEvent(center + QPointF(24.0, 0.0), button=Qt.MouseButton.LeftButton))
    qtbot.waitUntil(lambda: abs(window.state.map_viewport.center_omega1) > 1e-6, timeout=3000)
    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.loop_search_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_right_drag_box_search_updates_viewport_and_shows_markers_without_selection_change(qtbot, tmp_path, monkeypatch) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(
        lambda: window.map_panel._payload is not None and window.map_panel._payload.resolution_level >= RESOLUTION_LEVELS[-1],
        timeout=MAP_READY_TIMEOUT_MS,
    )
    initial_span = window.state.map_viewport.span_omega1
    previous_omega1 = window.state.seed.omega1
    previous_omega2 = window.state.seed.omega2
    map_rect = window.map_panel._canvas._map_rect()
    start = map_rect.center() - QPointF(60.0, 40.0)
    end = map_rect.center() + QPointF(60.0, 40.0)
    requests = []

    def fake_request_search(request) -> None:
        requests.append(request)
        window._handle_loop_search_started(1)
        marker_seed = window.state.seed.with_updates(
            omega1=(request.omega1_min + request.omega1_max) * 0.5,
            omega2=(request.omega2_min + request.omega2_max) * 0.5,
        )
        result = RegionSearchResult(
            mode=request.mode,
            omega1_min=request.omega1_min,
            omega1_max=request.omega1_max,
            omega2_min=request.omega2_min,
            omega2_max=request.omega2_max,
            markers=(_marker(marker_seed),),
            status_text="Showing 1 stable minima in box",
        )
        window._handle_loop_search_ready(1, result)

    monkeypatch.setattr(window.loop_search_worker, "request_search", fake_request_search)

    window.map_panel._canvas.mousePressEvent(_FakeMouseEvent(start, button=Qt.MouseButton.RightButton))
    window.map_panel._canvas.mouseMoveEvent(_FakeMouseEvent(end, button=Qt.MouseButton.RightButton))
    window.map_panel._canvas.mouseReleaseEvent(_FakeMouseEvent(end, button=Qt.MouseButton.RightButton))

    qtbot.waitUntil(lambda: len(requests) == 1, timeout=3000)
    qtbot.waitUntil(lambda: window.state.map_viewport.span_omega1 < initial_span, timeout=5000)
    request = requests[0]
    assert request.mode == "box"
    assert abs(window.state.seed.omega1 - previous_omega1) < 1e-9
    assert abs(window.state.seed.omega2 - previous_omega2) < 1e-9
    assert window.map_panel._hint.text() == "Showing 1 stable minima in box"
    assert len(window.map_panel._canvas._markers) == 1
    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.loop_search_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_clicking_marker_updates_seed_and_keeps_markers_visible(qtbot, tmp_path) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(
        lambda: window.map_panel._payload is not None and window.map_panel._payload.resolution_level >= RESOLUTION_LEVELS[-1],
        timeout=MAP_READY_TIMEOUT_MS,
    )
    marker = _marker(window.state.seed.with_updates(omega1=0.45, omega2=-0.55))
    window.map_panel.set_search_feedback("Showing 1 stable minima in box", (marker,))

    map_rect = window.map_panel._canvas._map_rect()
    marker_point = QPointF(
        window.map_panel._canvas._omega_to_x(marker.seed.omega1, map_rect),
        window.map_panel._canvas._omega_to_y(marker.seed.omega2, map_rect),
    )
    window.map_panel._canvas.mousePressEvent(_FakeMouseEvent(marker_point))
    window.map_panel._canvas.mouseReleaseEvent(_FakeMouseEvent(marker_point))

    qtbot.waitUntil(lambda: abs(window.state.seed.omega1 - 0.45) < 1e-9 and abs(window.state.seed.omega2 + 0.55) < 1e-9, timeout=5000)
    assert window.map_panel._hint.text() == "Showing 1 stable minima in box"
    assert len(window.map_panel._canvas._markers) == 1

    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.loop_search_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_selection_only_map_update_reuses_cached_image(qtbot, tmp_path) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(
        lambda: window.map_panel._payload is not None and window.map_panel._payload.resolution_level >= RESOLUTION_LEVELS[-1],
        timeout=MAP_READY_TIMEOUT_MS,
    )
    before = window.map_panel._payload.image
    map_rect = window.map_panel._canvas._map_rect()
    window.map_panel._canvas.mousePressEvent(_FakeMouseEvent(map_rect.center()))
    window.map_panel._canvas.mouseReleaseEvent(_FakeMouseEvent(map_rect.center()))
    qtbot.waitUntil(lambda: window.map_panel._payload is not None and window.map_panel._payload.image is before, timeout=5000)
    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.loop_search_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_find_stable_match_reuses_last_box_bounds_and_keeps_selection_on_no_markers(qtbot, tmp_path, monkeypatch) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(
        lambda: window.map_panel._payload is not None and window.map_panel._payload.resolution_level >= RESOLUTION_LEVELS[-1],
        timeout=MAP_READY_TIMEOUT_MS,
    )
    previous_omega1 = window.state.seed.omega1
    previous_omega2 = window.state.seed.omega2
    requests = []

    def fake_request_search(request) -> None:
        requests.append(request)
        window._handle_loop_search_started(len(requests))
        result = RegionSearchResult(
            mode=request.mode,
            omega1_min=request.omega1_min,
            omega1_max=request.omega1_max,
            omega2_min=request.omega2_min,
            omega2_max=request.omega2_max,
            markers=tuple(),
            status_text="No stable minima found in box",
        )
        window._handle_loop_search_ready(len(requests), result)

    monkeypatch.setattr(window.loop_search_worker, "request_search", fake_request_search)

    map_rect = window.map_panel._canvas._map_rect()
    start = map_rect.center() - QPointF(50.0, 36.0)
    end = map_rect.center() + QPointF(50.0, 36.0)
    window.map_panel._canvas.mousePressEvent(_FakeMouseEvent(start, button=Qt.MouseButton.RightButton))
    window.map_panel._canvas.mouseMoveEvent(_FakeMouseEvent(end, button=Qt.MouseButton.RightButton))
    window.map_panel._canvas.mouseReleaseEvent(_FakeMouseEvent(end, button=Qt.MouseButton.RightButton))

    qtbot.waitUntil(lambda: len(requests) == 1, timeout=3000)
    first_request = requests[0]
    assert first_request.mode == "box"
    assert abs(window.state.seed.omega1 - previous_omega1) < 1e-9
    assert abs(window.state.seed.omega2 - previous_omega2) < 1e-9
    assert window.map_panel._hint.text() == "No stable minima found in box"
    assert len(window.map_panel._canvas._markers) == 0

    window.map_panel._find_loop_button.click()
    qtbot.waitUntil(lambda: len(requests) == 2, timeout=3000)
    second_request = requests[1]
    assert second_request.mode == "box"
    assert second_request.omega1_min == first_request.omega1_min
    assert second_request.omega1_max == first_request.omega1_max
    assert second_request.omega2_min == first_request.omega2_min
    assert second_request.omega2_max == first_request.omega2_max
    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.loop_search_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_find_stable_match_uses_visible_viewport_when_no_box_exists(qtbot, tmp_path, monkeypatch) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(
        lambda: window.map_panel._payload is not None and window.map_panel._payload.resolution_level >= RESOLUTION_LEVELS[-1],
        timeout=MAP_READY_TIMEOUT_MS,
    )
    requests = []

    def fake_request_search(request) -> None:
        requests.append(request)
        window._handle_loop_search_started(len(requests))
        result = RegionSearchResult(
            mode=request.mode,
            omega1_min=request.omega1_min,
            omega1_max=request.omega1_max,
            omega2_min=request.omega2_min,
            omega2_max=request.omega2_max,
            markers=tuple(),
            status_text="No stable minima found in visible area",
        )
        window._handle_loop_search_ready(len(requests), result)

    monkeypatch.setattr(window.loop_search_worker, "request_search", fake_request_search)

    viewport = window.state.map_viewport
    window.map_panel._find_loop_button.click()
    qtbot.waitUntil(lambda: len(requests) == 1, timeout=3000)

    request = requests[0]
    assert request.mode == "viewport"
    assert request.omega1_min == viewport.omega1_min
    assert request.omega1_max == viewport.omega1_max
    assert request.omega2_min == viewport.omega2_min
    assert request.omega2_max == viewport.omega2_max
    assert window.map_panel._hint.text() == "No stable minima found in visible area"

    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.loop_search_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_clicking_map_point_keeps_markers_visible(qtbot, tmp_path) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(
        lambda: window.map_panel._payload is not None and window.map_panel._payload.resolution_level >= RESOLUTION_LEVELS[-1],
        timeout=MAP_READY_TIMEOUT_MS,
    )
    marker = _marker(window.state.seed.with_updates(omega1=0.25, omega2=-0.25))
    window.map_panel.set_search_feedback("Showing 1 stable minima in box", (marker,))

    map_rect = window.map_panel._canvas._map_rect()
    window.map_panel._canvas.mousePressEvent(_FakeMouseEvent(map_rect.center()))
    window.map_panel._canvas.mouseReleaseEvent(_FakeMouseEvent(map_rect.center()))

    qtbot.waitUntil(lambda: abs(window.state.seed.omega1) < 0.4 and abs(window.state.seed.omega2) < 0.4, timeout=5000)
    assert window.map_panel._hint.text() == "Showing 1 stable minima in box"
    assert len(window.map_panel._canvas._markers) == 1

    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.loop_search_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_main_window_save_archive_restore_flow(qtbot, tmp_path, monkeypatch) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    monkeypatch.setattr(
        "momentum_spyrographs.app.window.QInputDialog.getText",
        lambda *args, **kwargs: ("Saved Preset", True),
    )

    qtbot.waitUntil(lambda: window.state.preview_payload is not None, timeout=5000)
    assert window.save_current(save_as=True)
    assert len(window.store.list_presets()) == 1
    first_saved_id = window.state.current_preset.id

    window.setup_panel._emit_arm_velocity(1, 2.3)
    qtbot.waitUntil(lambda: window.state.is_dirty, timeout=3000)
    assert window.save_current()
    presets = window.store.list_presets()
    assert len(presets) == 2
    assert window.state.current_preset.id != first_saved_id
    assert window.state.current_preset.name == "Saved Preset v2"

    window.archive_current()
    assert len(window.store.list_presets()) == 1
    assert len(window.store.list_presets(include_archived=True)) == 2

    window.restore_current()
    assert len(window.store.list_presets()) == 2
    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.loop_search_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()
