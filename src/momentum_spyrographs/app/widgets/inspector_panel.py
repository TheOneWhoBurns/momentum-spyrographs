from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
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


class _ArmPopover(QFrame):
    armSpeedChanged = Signal(int, float)
    armLengthChanged = Signal(int, float)
    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._syncing = False
        self._arm_index = 1
        self._title = QLabel("Arm 1", self)
        self._speed_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._speed_spin = QDoubleSpinBox(self)
        self._length_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._length_spin = QDoubleSpinBox(self)
        self._build_ui()
        self.hide()

    @property
    def arm_index(self) -> int:
        return self._arm_index

    def show_for_arm(
        self,
        arm_index: int,
        seed: PendulumSeed,
        *,
        anchor: QPoint,
        bounds: QWidget,
    ) -> None:
        self._arm_index = arm_index
        self._title.setText(f"Arm {arm_index}")
        self._sync_from_seed(seed)
        self.adjustSize()
        x_pos = anchor.x() + 18
        y_pos = anchor.y() - self.height() // 2
        x_pos = min(max(10, x_pos), max(10, bounds.width() - self.width() - 10))
        y_pos = min(max(10, y_pos), max(10, bounds.height() - self.height() - 10))
        self.move(x_pos, y_pos)
        self.show()
        self.raise_()

    def dismiss(self) -> None:
        if not self.isVisible():
            return
        self.hide()
        self.dismissed.emit()

    def _build_ui(self) -> None:
        self.setObjectName("inspectorSection")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._title.setObjectName("sectionTitle")

        self._speed_slider.setRange(-1000, 1000)
        self._speed_slider.setSingleStep(5)
        self._speed_slider.valueChanged.connect(self._sync_speed_from_slider)

        self._speed_spin.setRange(-10.0, 10.0)
        self._speed_spin.setDecimals(2)
        self._speed_spin.setSingleStep(0.05)
        self._speed_spin.setSuffix(" rad/s")
        self._speed_spin.valueChanged.connect(self._sync_speed_from_spin)

        self._length_slider.setRange(20, 300)
        self._length_slider.setSingleStep(2)
        self._length_slider.valueChanged.connect(self._sync_length_from_slider)

        self._length_spin.setRange(0.2, 3.0)
        self._length_spin.setDecimals(2)
        self._length_spin.setSingleStep(0.02)
        self._length_spin.setSuffix(" m")
        self._length_spin.valueChanged.connect(self._sync_length_from_spin)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.addWidget(QLabel("Speed", self), 0, 0)
        grid.addWidget(self._speed_slider, 0, 1)
        grid.addWidget(self._speed_spin, 0, 2)
        grid.addWidget(QLabel("Length", self), 1, 0)
        grid.addWidget(self._length_slider, 1, 1)
        grid.addWidget(self._length_spin, 1, 2)
        grid.setColumnStretch(1, 1)

        hint = QLabel("Signed speed replaces the old direction toggle.", self)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a9dba; font-size: 11px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self._title)
        layout.addLayout(grid)
        layout.addWidget(hint)

    def _sync_from_seed(self, seed: PendulumSeed) -> None:
        speed = seed.omega1 if self._arm_index == 1 else seed.omega2
        length = seed.length1 if self._arm_index == 1 else seed.length2
        self._syncing = True
        try:
            self._speed_slider.setValue(int(round(speed * 100.0)))
            self._speed_spin.setValue(speed)
            self._length_slider.setValue(int(round(length * 100.0)))
            self._length_spin.setValue(length)
        finally:
            self._syncing = False

    def _sync_speed_from_slider(self, slider_value: int) -> None:
        if self._syncing:
            return
        value = slider_value / 100.0
        self._syncing = True
        try:
            self._speed_spin.setValue(value)
        finally:
            self._syncing = False
        self.armSpeedChanged.emit(self._arm_index, value)

    def _sync_speed_from_spin(self, value: float) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            self._speed_slider.setValue(int(round(value * 100.0)))
        finally:
            self._syncing = False
        self.armSpeedChanged.emit(self._arm_index, value)

    def _sync_length_from_slider(self, slider_value: int) -> None:
        if self._syncing:
            return
        value = slider_value / 100.0
        self._syncing = True
        try:
            self._length_spin.setValue(value)
        finally:
            self._syncing = False
        self.armLengthChanged.emit(self._arm_index, value)

    def _sync_length_from_spin(self, value: float) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            self._length_slider.setValue(int(round(value * 100.0)))
        finally:
            self._syncing = False
        self.armLengthChanged.emit(self._arm_index, value)


class InspectorPanel(QWidget):
    seedChanged = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._syncing = False
        self._seed = PendulumSeed()
        self._speed_summary: dict[int, QLabel] = {}
        self._length_summary: dict[int, QLabel] = {}
        self.pendulum_canvas = PendulumCanvas(self)
        self._arm_popover = _ArmPopover(self)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.pendulum_canvas.setMinimumHeight(300)
        root.addWidget(self.pendulum_canvas, 1)

        hint = QLabel("Drag a bob to set angle. Click a bob to edit that arm's speed and length.", self)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a9dba; font-size: 12px;")
        root.addWidget(hint)

        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(10)
        for arm in (1, 2):
            summary_row.addWidget(self._arm_summary_card(arm), 1)
        root.addLayout(summary_row)

        self.pendulum_canvas.anglesChanged.connect(self._emit_pair)
        self.pendulum_canvas.armClicked.connect(self._show_arm_controls)
        self.pendulum_canvas.backgroundClicked.connect(self._hide_arm_controls)
        self._arm_popover.armSpeedChanged.connect(self._emit_arm_velocity)
        self._arm_popover.armLengthChanged.connect(self._emit_arm_length)
        self._arm_popover.dismissed.connect(lambda: self.pendulum_canvas.set_active_arm(None))

    def _arm_summary_card(self, arm_index: int) -> QWidget:
        card = QFrame(self)
        card.setObjectName("inspectorSection")

        title = QLabel(f"Arm {arm_index}", card)
        title.setObjectName("sectionTitle")

        speed_label = QLabel("Speed 0.00 rad/s", card)
        speed_label.setStyleSheet("font-weight: 600;")
        self._speed_summary[arm_index] = speed_label

        length_label = QLabel("Length 1.00 m", card)
        length_label.setStyleSheet("color: #b8c9e4;")
        self._length_summary[arm_index] = length_label

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        layout.addWidget(title)
        layout.addWidget(speed_label)
        layout.addWidget(length_label)
        return card

    def set_document(self, seed: PendulumSeed) -> None:
        self._syncing = True
        self._seed = seed
        try:
            self.pendulum_canvas.set_seed(seed)
            self._sync_summary(1, seed.omega1, seed.length1)
            self._sync_summary(2, seed.omega2, seed.length2)
            if self._arm_popover.isVisible():
                self._show_arm_controls(self._arm_popover.arm_index, self.pendulum_canvas.arm_anchor(self._arm_popover.arm_index))
        finally:
            self._syncing = False

    def _show_arm_controls(self, arm_index: int, anchor) -> None:
        self.pendulum_canvas.set_active_arm(arm_index)
        anchor_point = self.pendulum_canvas.mapTo(self, anchor.toPoint())
        self._arm_popover.show_for_arm(
            arm_index,
            self._seed,
            anchor=anchor_point,
            bounds=self,
        )

    def _hide_arm_controls(self) -> None:
        self._arm_popover.dismiss()

    def _sync_summary(self, arm_index: int, speed: float, length: float) -> None:
        self._speed_summary[arm_index].setText(f"Speed {speed:+.2f} rad/s")
        self._length_summary[arm_index].setText(f"Length {length:.2f} m")

    def _emit_pair(self, theta1: float, theta2: float) -> None:
        if self._syncing:
            return
        self.seedChanged.emit("theta1", theta1)
        self.seedChanged.emit("theta2", theta2)

    def _emit_arm_velocity(self, arm_index: int, speed: float) -> None:
        if self._syncing:
            return
        self.seedChanged.emit(ARM_FIELDS[arm_index], speed)

    def _emit_arm_length(self, arm_index: int, length: float) -> None:
        if self._syncing:
            return
        self.seedChanged.emit(LENGTH_FIELDS[arm_index], length)
