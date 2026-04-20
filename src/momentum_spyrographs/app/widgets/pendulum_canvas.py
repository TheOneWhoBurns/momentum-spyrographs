from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from momentum_spyrographs.core.models import PendulumSeed


class PendulumCanvas(QWidget):
    anglesChanged = Signal(float, float)
    armClicked = Signal(int, object)
    backgroundClicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._seed = PendulumSeed()
        self._press_target: int | None = None
        self._drag_target: int | None = None
        self._press_position: QPointF | None = None
        self._active_arm: int | None = None
        self.setMinimumHeight(260)
        self.setMouseTracking(True)

    def set_seed(self, seed: PendulumSeed) -> None:
        self._seed = seed
        self.update()

    def set_active_arm(self, arm_index: int | None) -> None:
        if self._active_arm == arm_index:
            return
        self._active_arm = arm_index
        self.update()

    def arm_anchor(self, arm_index: int) -> QPointF:
        _, bob1, bob2 = self._bob_positions()
        return bob1 if arm_index == 1 else bob2

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        arm = self._hit_test_arm(event.position())
        self._press_target = arm
        self._drag_target = None
        self._press_position = event.position()
        if arm is None:
            self.backgroundClicked.emit()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._press_target is None or self._press_position is None:
            return
        if self._drag_target is None and self._distance(event.position(), self._press_position) > 6.0:
            self._drag_target = self._press_target
        if self._drag_target is None:
            return
        pivot, bob1, _ = self._bob_positions()
        if self._drag_target == 1:
            theta1 = self._point_to_theta(pivot, event.position())
            self.anglesChanged.emit(theta1, self._seed.theta2)
        else:
            theta2 = self._point_to_theta(bob1, event.position())
            self.anglesChanged.emit(self._seed.theta1, theta2)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_target is None and self._press_target is not None:
            self.armClicked.emit(self._press_target, self.arm_anchor(self._press_target))
        del event
        self._press_target = None
        self._drag_target = None
        self._press_position = None

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0a0f1c"))

        pivot, bob1, bob2 = self._bob_positions()
        rod_pen = QPen(QColor("#d7e4f8"), 3)
        rod_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(rod_pen)
        painter.drawLine(pivot, bob1)
        painter.drawLine(bob1, bob2)

        guide_pen = QPen(QColor(255, 255, 255, 70), 1, Qt.PenStyle.DashLine)
        painter.setPen(guide_pen)
        painter.drawLine(QPointF(pivot.x(), 24), QPointF(pivot.x(), self.height() - 24))
        painter.drawLine(bob1, QPointF(bob1.x(), self.height() - 16))

        painter.setBrush(QColor("#ff9d76"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(pivot.x() - 7, pivot.y() - 7, 14, 14))

        painter.setBrush(QColor("#73d2de"))
        painter.drawEllipse(QRectF(bob1.x() - 16, bob1.y() - 16, 32, 32))
        painter.setBrush(QColor("#ffb36b"))
        painter.drawEllipse(QRectF(bob2.x() - 18, bob2.y() - 18, 36, 36))

        if self._active_arm is not None:
            active_center = bob1 if self._active_arm == 1 else bob2
            active_radius = 18 if self._active_arm == 1 else 20
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#ffb38f"), 2))
            painter.drawEllipse(active_center, active_radius, active_radius)

        painter.setPen(QColor("#eaf1ff"))
        painter.drawText(18, 28, "Drag a bob to set angle. Click a bob to edit that arm.")

    def _geometry(self) -> tuple[QPointF, float, float]:
        reference_total = max(2.4, self._seed.length1 + self._seed.length2)
        scale = min(self.width() * 0.30, self.height() * 0.60) / reference_total
        pivot = QPointF(self.width() / 2.0, self.height() * 0.16)
        return pivot, self._seed.length1 * scale, self._seed.length2 * scale

    def _bob_positions(self) -> tuple[QPointF, QPointF, QPointF]:
        pivot, l1, l2 = self._geometry()
        bob1 = QPointF(
            pivot.x() + l1 * math.sin(self._seed.theta1),
            pivot.y() + l1 * math.cos(self._seed.theta1),
        )
        bob2 = QPointF(
            bob1.x() + l2 * math.sin(self._seed.theta2),
            bob1.y() + l2 * math.cos(self._seed.theta2),
        )
        return pivot, bob1, bob2

    @staticmethod
    def _point_to_theta(origin: QPointF, point: QPointF) -> float:
        return math.atan2(point.x() - origin.x(), point.y() - origin.y())

    @staticmethod
    def _distance(a: QPointF, b: QPointF) -> float:
        return math.hypot(a.x() - b.x(), a.y() - b.y())

    def _hit_test_arm(self, point: QPointF) -> int | None:
        _, bob1, bob2 = self._bob_positions()
        if self._distance(point, bob1) <= 18:
            return 1
        if self._distance(point, bob2) <= 20:
            return 2
        return None
