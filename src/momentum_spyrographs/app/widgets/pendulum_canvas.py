from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from momentum_spyrographs.core.models import PendulumSeed


class PendulumCanvas(QWidget):
    anglesChanged = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._seed = PendulumSeed()
        self._drag_target: str | None = None
        self.setMinimumHeight(280)
        self.setMouseTracking(True)

    def set_seed(self, seed: PendulumSeed) -> None:
        self._seed = seed
        self.update()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        _, bob1, bob2 = self._bob_positions()
        if self._distance(event.position(), bob1) <= 16:
            self._drag_target = "bob1"
        elif self._distance(event.position(), bob2) <= 16:
            self._drag_target = "bob2"

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_target is None:
            return
        pivot, bob1, _ = self._bob_positions()
        if self._drag_target == "bob1":
            theta1 = self._point_to_theta(pivot, event.position())
            self.anglesChanged.emit(theta1, self._seed.theta2)
        else:
            theta2 = self._point_to_theta(bob1, event.position())
            self.anglesChanged.emit(self._seed.theta1, theta2)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        del event
        self._drag_target = None

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#101622"))

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
        painter.drawEllipse(QRectF(bob1.x() - 14, bob1.y() - 14, 28, 28))
        painter.setBrush(QColor("#ffb36b"))
        painter.drawEllipse(QRectF(bob2.x() - 14, bob2.y() - 14, 28, 28))

        painter.setPen(QColor("#eaf1ff"))
        painter.drawText(18, 28, "Drag the bobs to set initial angles")

    def _geometry(self) -> tuple[QPointF, float, float]:
        total_length = max(self._seed.length1 + self._seed.length2, 0.1)
        scale = min(self.width() * 0.34, self.height() * 0.62) / total_length
        pivot = QPointF(self.width() / 2.0, self.height() * 0.18)
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
