from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtCore import Qt

from momentum_spyrographs.app.window import MainWindow
from momentum_spyrographs.app.widgets.pendulum_canvas import PendulumCanvas


class _FakeMouseEvent:
    def __init__(self, position: QPointF, button=Qt.MouseButton.LeftButton) -> None:
        self._position = position
        self._button = button

    def position(self) -> QPointF:
        return self._position

    def button(self):
        return self._button


class _FakeWheelEvent:
    def __init__(self, position: QPointF, delta_y: int) -> None:
        self._position = position
        self._delta_y = delta_y

    def position(self) -> QPointF:
        return self._position

    class _Angle:
        def __init__(self, value: int) -> None:
            self._value = value

        def y(self) -> int:
            return self._value

    def angleDelta(self):
        return self._Angle(self._delta_y)


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


def test_main_window_recomputes_preview_after_setup_change(qtbot, tmp_path) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.state.preview_payload is not None, timeout=5000)
    qtbot.waitUntil(lambda: window.map_panel._payload is not None and window.map_panel._payload.resolution_level >= 512, timeout=30000)
    assert window.map_panel._canvas._pixmap is not None
    window.setup_panel._energy_sliders[1].setValue(250)
    window.setup_panel._length_sliders[1].setValue(175)
    qtbot.waitUntil(
        lambda: window.state.preview_payload is not None
        and abs(window.state.preview_payload.selected_seed.omega1 - 2.5) < 1e-9,
        timeout=5000,
    )
    assert abs(window.state.seed.length1 - 1.75) < 1e-9
    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_side_panels_are_collapsible(qtbot, tmp_path) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    left_panel = window.centralWidget().widget(0).widget().layout().itemAt(0).widget()
    right_panel = window.centralWidget().widget(2).widget().layout().itemAt(0).widget()
    left_panel._toggle.click()
    right_panel._toggle.click()
    assert not left_panel._body.isVisible()
    assert not right_panel._body.isVisible()
    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_advanced_panel_expands_and_map_click_updates_seed(qtbot, tmp_path) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    window.setup_panel._toggle.click()
    assert window.setup_panel._content.isVisible()

    qtbot.waitUntil(lambda: window.map_panel._payload is not None and window.map_panel._payload.resolution_level >= 512, timeout=30000)
    map_rect = window.map_panel._canvas._map_rect()
    window.map_panel._canvas.mousePressEvent(_FakeMouseEvent(map_rect.center()))
    window.map_panel._canvas.mouseReleaseEvent(_FakeMouseEvent(map_rect.center()))
    qtbot.waitUntil(lambda: abs(window.state.seed.omega1) < 0.4 and abs(window.state.seed.omega2) < 0.4, timeout=5000)
    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_map_zoom_and_pan_update_viewport(qtbot, tmp_path) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.map_panel._payload is not None and window.map_panel._payload.resolution_level >= 512, timeout=30000)
    initial_span = window.state.map_viewport.span_omega1
    window.map_panel._zoom_in_button.click()
    qtbot.waitUntil(lambda: window.state.map_viewport.span_omega1 < initial_span, timeout=3000)

    map_rect = window.map_panel._canvas._map_rect()
    center = map_rect.center()
    window.map_panel._canvas.mousePressEvent(_FakeMouseEvent(center))
    window.map_panel._canvas.mouseMoveEvent(_FakeMouseEvent(center + QPointF(24.0, 0.0)))
    window.map_panel._canvas.mouseReleaseEvent(_FakeMouseEvent(center + QPointF(24.0, 0.0)))
    qtbot.waitUntil(lambda: abs(window.state.map_viewport.center_omega1) > 1e-6, timeout=3000)
    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()


def test_selection_only_map_update_reuses_cached_image(qtbot, tmp_path) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.map_panel._payload is not None and window.map_panel._payload.resolution_level >= 512, timeout=30000)
    before = window.map_panel._payload.image
    map_rect = window.map_panel._canvas._map_rect()
    window.map_panel._canvas.mousePressEvent(_FakeMouseEvent(map_rect.center()))
    window.map_panel._canvas.mouseReleaseEvent(_FakeMouseEvent(map_rect.center()))
    qtbot.waitUntil(lambda: window.map_panel._payload is not None and window.map_panel._payload.image is before, timeout=5000)
    window.preview_worker.shutdown()
    window.map_worker.shutdown()
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

    window.archive_current()
    assert window.store.list_presets() == []
    assert len(window.store.list_presets(include_archived=True)) == 1

    window.restore_current()
    assert len(window.store.list_presets()) == 1
    window.preview_worker.shutdown()
    window.map_worker.shutdown()
    window.maybe_save_changes = lambda: True
    window.close()
