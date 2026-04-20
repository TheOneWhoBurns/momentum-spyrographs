from __future__ import annotations

from PySide6.QtCore import QPointF

from momentum_spyrographs.app.window import MainWindow
from momentum_spyrographs.app.widgets.pendulum_canvas import PendulumCanvas


class _FakeMouseEvent:
    def __init__(self, position: QPointF) -> None:
        self._position = position

    def position(self) -> QPointF:
        return self._position


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


def test_main_window_recomputes_preview_after_setup_change(qtbot, tmp_path) -> None:
    window = MainWindow(preset_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.state.preview_payload is not None, timeout=5000)
    window.setup_panel._energy_sliders[1].setValue(250)
    qtbot.waitUntil(
        lambda: window.state.preview_payload is not None
        and abs(window.state.preview_payload.selected_seed.omega1 - 2.5) < 1e-9,
        timeout=5000,
    )
    window.preview_worker.shutdown()
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
    window.maybe_save_changes = lambda: True
    window.close()
