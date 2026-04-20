from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from momentum_spyrographs.app.widgets.pendulum_canvas import PendulumCanvas
from momentum_spyrographs.core.models import PendulumSeed


ARM_FIELDS = {
    1: "omega1",
    2: "omega2",
}

LENGTH_FIELDS = {
    1: "length1",
    2: "length2",
}


class InspectorPanel(QWidget):
    seedChanged = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._syncing = False
        self._direction_boxes: dict[int, QComboBox] = {}
        self._energy_sliders: dict[int, QSlider] = {}
        self._energy_labels: dict[int, QLabel] = {}
        self._length_sliders: dict[int, QSlider] = {}
        self._length_labels: dict[int, QLabel] = {}
        self.pendulum_canvas = PendulumCanvas(self)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # Left: pendulum canvas
        self.pendulum_canvas.setMinimumSize(140, 140)
        root.addWidget(self.pendulum_canvas, 1)

        # Right: compact arm grid
        controls = QVBoxLayout()
        controls.setSpacing(6)

        arm_frame = QFrame(self)
        arm_frame.setObjectName("inspectorSection")
        grid = QGridLayout(arm_frame)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setSpacing(4)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(4, 1)

        for col, text in [(1, "Dir"), (2, "Speed"), (4, "Length")]:
            lbl = QLabel(text, arm_frame)
            lbl.setStyleSheet("color: #6b83a8; font-size: 10px;")
            grid.addWidget(lbl, 0, col)

        for row, arm in enumerate([1, 2], start=1):
            title = QLabel(f"Arm {arm}", arm_frame)
            title.setStyleSheet("color: #ffb38f; font-weight: 600; font-size: 12px;")
            grid.addWidget(title, row, 0)

            direction = QComboBox(arm_frame)
            direction.addItem("\u21bb CW", 1.0)
            direction.addItem("\u21ba CCW", -1.0)
            direction.setFixedWidth(78)
            direction.setToolTip("Rotation direction")
            direction.currentTextChanged.connect(lambda _t, a=arm: self._emit_arm_velocity(a))
            self._direction_boxes[arm] = direction
            grid.addWidget(direction, row, 1)

            e_slider = QSlider(Qt.Orientation.Horizontal, arm_frame)
            e_slider.setRange(0, 1000)
            e_slider.setToolTip("Angular velocity \u2014 how fast this arm spins")
            e_slider.valueChanged.connect(lambda v, a=arm: self._update_energy_label(a, v))
            e_slider.valueChanged.connect(lambda _v, a=arm: self._emit_arm_velocity(a))
            self._energy_sliders[arm] = e_slider
            grid.addWidget(e_slider, row, 2)

            e_label = QLabel("0.00", arm_frame)
            e_label.setFixedWidth(34)
            self._energy_labels[arm] = e_label
            grid.addWidget(e_label, row, 3)

            l_slider = QSlider(Qt.Orientation.Horizontal, arm_frame)
            l_slider.setRange(20, 300)
            l_slider.setToolTip("Physical length of this arm")
            l_slider.valueChanged.connect(lambda v, a=arm: self._update_length_label(a, v))
            l_slider.valueChanged.connect(lambda _v, a=arm: self._emit_arm_length(a))
            self._length_sliders[arm] = l_slider
            grid.addWidget(l_slider, row, 4)

            l_label = QLabel("1.00", arm_frame)
            l_label.setFixedWidth(34)
            self._length_labels[arm] = l_label
            grid.addWidget(l_label, row, 5)

        controls.addWidget(arm_frame)
        controls.addStretch(1)

        root.addLayout(controls, 1)
        self.pendulum_canvas.anglesChanged.connect(self._emit_pair)

    def set_document(self, seed: PendulumSeed) -> None:
        self._syncing = True
        try:
            self.pendulum_canvas.set_seed(seed)
            self._set_arm_motion(1, seed.omega1)
            self._set_arm_motion(2, seed.omega2)
            self._set_arm_length(1, seed.length1)
            self._set_arm_length(2, seed.length2)
        finally:
            self._syncing = False

    def _set_arm_motion(self, arm_index: int, omega: float) -> None:
        direction = self._direction_boxes[arm_index]
        slider = self._energy_sliders[arm_index]
        slider.setValue(min(1000, int(round(abs(omega) * 100))))
        direction.setCurrentIndex(0 if omega >= 0 else 1)
        self._update_energy_label(arm_index, slider.value())

    def _set_arm_length(self, arm_index: int, length: float) -> None:
        slider = self._length_sliders[arm_index]
        slider.setValue(min(300, max(20, int(round(length * 100)))))
        self._update_length_label(arm_index, slider.value())

    def _emit_pair(self, theta1: float, theta2: float) -> None:
        if self._syncing:
            return
        self.seedChanged.emit("theta1", theta1)
        self.seedChanged.emit("theta2", theta2)

    def _emit_arm_velocity(self, arm_index: int) -> None:
        if self._syncing:
            return
        direction = float(self._direction_boxes[arm_index].currentData())
        energy = self._energy_sliders[arm_index].value() / 100.0
        self.seedChanged.emit(ARM_FIELDS[arm_index], direction * energy)

    def _update_energy_label(self, arm_index: int, slider_value: int) -> None:
        self._energy_labels[arm_index].setText(f"{slider_value / 100.0:.2f}")

    def _emit_arm_length(self, arm_index: int) -> None:
        if self._syncing:
            return
        self.seedChanged.emit(LENGTH_FIELDS[arm_index], self._length_sliders[arm_index].value() / 100.0)

    def _update_length_label(self, arm_index: int, slider_value: int) -> None:
        self._length_labels[arm_index].setText(f"{slider_value / 100.0:.2f}")
