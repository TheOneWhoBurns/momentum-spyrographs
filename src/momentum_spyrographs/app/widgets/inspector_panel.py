from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from momentum_spyrographs.app.widgets.pendulum_canvas import PendulumCanvas
from momentum_spyrographs.core.models import PendulumSeed


ARM_FIELDS = {
    1: "omega1",
    2: "omega2",
}


class InspectorPanel(QWidget):
    seedChanged = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._syncing = False
        self._spin_boxes: dict[str, QDoubleSpinBox] = {}
        self._direction_boxes: dict[int, QComboBox] = {}
        self._energy_sliders: dict[int, QSlider] = {}
        self._energy_labels: dict[int, QLabel] = {}
        self._space_combo = QComboBox(self)
        self.pendulum_canvas = PendulumCanvas(self)
        self._toggle = QToolButton(self)
        self._content = QWidget(self)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.pendulum_canvas.setMinimumHeight(300)
        layout.addWidget(self.pendulum_canvas)

        arm_row = QHBoxLayout()
        arm_row.setSpacing(10)
        arm_row.addWidget(self._arm_group(1), 1)
        arm_row.addWidget(self._arm_group(2), 1)
        layout.addLayout(arm_row)

        self._toggle.setText("Advanced Physics")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(False)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.ArrowType.RightArrow)
        self._toggle.toggled.connect(self._set_expanded)
        layout.addWidget(self._toggle)

        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        form_frame = QFrame(self._content)
        form_layout = QFormLayout(form_frame)
        form_layout.addRow("Projection", self._space_combo)
        self._space_combo.addItems(["trace", "momentum", "omega", "angle"])
        self._space_combo.currentTextChanged.connect(self._emit_space)

        for key, minimum, maximum, step, decimals in [
            ("theta1", -6.3, 6.3, 0.01, 3),
            ("theta2", -6.3, 6.3, 0.01, 3),
            ("omega1", -10.0, 10.0, 0.01, 3),
            ("omega2", -10.0, 10.0, 0.01, 3),
            ("length1", 0.1, 5.0, 0.05, 2),
            ("length2", 0.1, 5.0, 0.05, 2),
            ("mass1", 0.1, 10.0, 0.1, 2),
            ("mass2", 0.1, 10.0, 0.1, 2),
            ("gravity", 0.1, 30.0, 0.1, 2),
            ("duration", 1.0, 240.0, 1.0, 1),
            ("dt", 0.001, 0.1, 0.001, 3),
        ]:
            box = QDoubleSpinBox(form_frame)
            box.setRange(minimum, maximum)
            box.setSingleStep(step)
            box.setDecimals(decimals)
            box.valueChanged.connect(lambda value, name=key: self._emit_seed(name, value))
            self._spin_boxes[key] = box
            form_layout.addRow(key.replace("theta", "theta ").replace("omega", "omega ").title(), box)
        content_layout.addWidget(form_frame)

        self._content.setVisible(False)
        layout.addWidget(self._content)
        self.pendulum_canvas.anglesChanged.connect(self._emit_pair)

    def _arm_group(self, arm_index: int) -> QWidget:
        group = QGroupBox(f"Arm {arm_index}", self)
        form = QFormLayout(group)

        direction = QComboBox(group)
        direction.addItem("Clockwise", 1.0)
        direction.addItem("Counterclockwise", -1.0)
        direction.currentTextChanged.connect(lambda _text, arm=arm_index: self._emit_arm_velocity(arm))
        self._direction_boxes[arm_index] = direction

        energy_slider = QSlider(Qt.Orientation.Horizontal, group)
        energy_slider.setRange(0, 600)
        energy_slider.valueChanged.connect(lambda value, arm=arm_index: self._update_energy_label(arm, value))
        energy_slider.valueChanged.connect(lambda _value, arm=arm_index: self._emit_arm_velocity(arm))
        self._energy_sliders[arm_index] = energy_slider

        energy_label = QLabel("0.00", group)
        self._energy_labels[arm_index] = energy_label

        energy_row = QWidget(group)
        energy_layout = QHBoxLayout(energy_row)
        energy_layout.setContentsMargins(0, 0, 0, 0)
        energy_layout.addWidget(energy_slider, 1)
        energy_layout.addWidget(energy_label)

        form.addRow("Direction", direction)
        form.addRow("Energy", energy_row)
        return group

    def set_document(self, seed: PendulumSeed) -> None:
        self._syncing = True
        try:
            self.pendulum_canvas.set_seed(seed)
            self._space_combo.setCurrentText(seed.space)
            for key, box in self._spin_boxes.items():
                box.setValue(float(getattr(seed, key)))
            self._set_arm_motion(1, seed.omega1)
            self._set_arm_motion(2, seed.omega2)
        finally:
            self._syncing = False

    def _set_expanded(self, expanded: bool) -> None:
        self._toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self._content.setVisible(expanded)

    def _set_arm_motion(self, arm_index: int, omega: float) -> None:
        direction = self._direction_boxes[arm_index]
        slider = self._energy_sliders[arm_index]
        slider.setValue(min(600, int(round(abs(omega) * 100))))
        direction.setCurrentIndex(0 if omega >= 0 else 1)
        self._update_energy_label(arm_index, slider.value())

    def _emit_pair(self, theta1: float, theta2: float) -> None:
        if self._syncing:
            return
        self.seedChanged.emit("theta1", theta1)
        self.seedChanged.emit("theta2", theta2)

    def _emit_space(self, value: str) -> None:
        if not self._syncing:
            self.seedChanged.emit("space", value)

    def _emit_seed(self, key: str, value: object) -> None:
        if not self._syncing:
            self.seedChanged.emit(key, value)

    def _emit_arm_velocity(self, arm_index: int) -> None:
        if self._syncing:
            return
        direction = float(self._direction_boxes[arm_index].currentData())
        energy = self._energy_sliders[arm_index].value() / 100.0
        self.seedChanged.emit(ARM_FIELDS[arm_index], direction * energy)

    def _update_energy_label(self, arm_index: int, slider_value: int) -> None:
        self._energy_labels[arm_index].setText(f"{slider_value / 100.0:.2f}")
