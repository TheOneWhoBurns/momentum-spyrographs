from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from momentum_spyrographs.core.models import StabilityMapPayload


def _as_qpixmap(image: np.ndarray) -> QPixmap:
    height, width, _ = image.shape
    qimage = QImage(image.data, width, height, image.strides[0], QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimage.copy())


class StabilityMapCanvas(QWidget):
    seedSelected = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._payload: StabilityMapPayload | None = None
        self._pixmap: QPixmap | None = None
        self._status = "Map pending"
        self._error = ""
        self.setMinimumHeight(280)

    def set_payload(self, payload: StabilityMapPayload | None) -> None:
        self._payload = payload
        self._pixmap = _as_qpixmap(payload.image) if payload is not None else None
        self._status = "Map ready"
        self._error = ""
        self.update()

    def set_status(self, status: str, error: str = "") -> None:
        labels = {
            "idle": "Map ready",
            "loading": "Building landscape",
            "error": error or "Map failed",
        }
        self._status = labels.get(status, status)
        self._error = error
        self.update()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self._payload is None:
            return
        map_rect = self._map_rect()
        if not map_rect.contains(event.position()):
            return
        omega1 = self._x_to_omega(event.position().x(), map_rect)
        omega2 = self._y_to_omega(event.position().y(), map_rect)
        self.seedSelected.emit(omega1, omega2)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        map_rect = self._map_rect()
        painter.fillRect(self.rect(), QColor("#111827"))
        painter.fillRect(map_rect, QColor("#0c1120"))

        if self._pixmap is not None:
            painter.drawPixmap(map_rect.toRect(), self._pixmap)
        else:
            painter.setPen(QColor("#dfe8f6"))
            painter.drawText(map_rect.toRect(), Qt.AlignmentFlag.AlignCenter, self._error or self._status)
            return

        painter.setPen(QPen(QColor(255, 255, 255, 50), 1))
        painter.drawRect(map_rect)

        for fraction in (0.25, 0.5, 0.75):
            x_value = map_rect.left() + map_rect.width() * fraction
            y_value = map_rect.top() + map_rect.height() * fraction
            painter.setPen(QPen(QColor(255, 255, 255, 24), 1, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(x_value, map_rect.top()), QPointF(x_value, map_rect.bottom()))
            painter.drawLine(QPointF(map_rect.left(), y_value), QPointF(map_rect.right(), y_value))

        if self._payload is not None:
            marker = QPointF(
                self._omega_to_x(self._payload.selected_omega1, map_rect),
                self._omega_to_y(self._payload.selected_omega2, map_rect),
            )
            self._paint_pendulum_overlay(painter, map_rect, marker)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawEllipse(marker, 6.0, 6.0)

        if self._status == "Building landscape":
            painter.setPen(QColor("#ff9d76"))
            painter.drawText(map_rect.adjusted(0, 0, -10, -10).toRect(), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, self._status)

    def _map_rect(self) -> QRectF:
        size = min(self.width() - 18.0, self.height() - 18.0)
        size = max(120.0, size)
        left = (self.width() - size) / 2.0
        top = (self.height() - size) / 2.0
        return QRectF(left, top, size, size)

    def _x_to_omega(self, x_value: float, rect: QRectF) -> float:
        assert self._payload is not None
        ratio = (x_value - rect.left()) / max(rect.width(), 1.0)
        return float(self._payload.omega1_values[0] + ratio * (self._payload.omega1_values[-1] - self._payload.omega1_values[0]))

    def _y_to_omega(self, y_value: float, rect: QRectF) -> float:
        assert self._payload is not None
        ratio = (y_value - rect.top()) / max(rect.height(), 1.0)
        return float(self._payload.omega2_values[-1] - ratio * (self._payload.omega2_values[-1] - self._payload.omega2_values[0]))

    def _omega_to_x(self, omega_value: float, rect: QRectF) -> float:
        assert self._payload is not None
        ratio = (omega_value - self._payload.omega1_values[0]) / max(self._payload.omega1_values[-1] - self._payload.omega1_values[0], 1e-9)
        return rect.left() + ratio * rect.width()

    def _omega_to_y(self, omega_value: float, rect: QRectF) -> float:
        assert self._payload is not None
        ratio = (self._payload.omega2_values[-1] - omega_value) / max(self._payload.omega2_values[-1] - self._payload.omega2_values[0], 1e-9)
        return rect.top() + ratio * rect.height()

    def _paint_pendulum_overlay(self, painter: QPainter, map_rect: QRectF, marker: QPointF) -> None:
        assert self._payload is not None
        seed = self._payload.overlay_seed
        max_span = max(seed.length1 + seed.length2, 1e-6)
        overlay_radius = map_rect.width() * 0.075
        scale = overlay_radius / max_span

        bob1_local = QPointF(
            seed.length1 * scale * np.sin(seed.theta1),
            seed.length1 * scale * np.cos(seed.theta1),
        )
        bob2_local = QPointF(
            bob1_local.x() + seed.length2 * scale * np.sin(seed.theta2),
            bob1_local.y() + seed.length2 * scale * np.cos(seed.theta2),
        )
        pivot = QPointF(marker.x() - bob2_local.x(), marker.y() - bob2_local.y())
        bob1 = QPointF(pivot.x() + bob1_local.x(), pivot.y() + bob1_local.y())
        bob2 = QPointF(pivot.x() + bob2_local.x(), pivot.y() + bob2_local.y())

        left = min(pivot.x(), bob1.x(), bob2.x())
        right = max(pivot.x(), bob1.x(), bob2.x())
        top = min(pivot.y(), bob1.y(), bob2.y())
        bottom = max(pivot.y(), bob1.y(), bob2.y())
        shift_x = 0.0
        shift_y = 0.0
        margin = 10.0
        if left < map_rect.left() + margin:
            shift_x = map_rect.left() + margin - left
        elif right > map_rect.right() - margin:
            shift_x = map_rect.right() - margin - right
        if top < map_rect.top() + margin:
            shift_y = map_rect.top() + margin - top
        elif bottom > map_rect.bottom() - margin:
            shift_y = map_rect.bottom() - margin - bottom
        if shift_x or shift_y:
            offset = QPointF(shift_x, shift_y)
            pivot = pivot + offset
            bob1 = bob1 + offset
            bob2 = bob2 + offset

        halo_pen = QPen(QColor(9, 14, 24, 180), 12)
        halo_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(halo_pen)
        painter.drawLine(pivot, bob1)
        painter.drawLine(bob1, bob2)

        rod_pen = QPen(QColor("#d7e4f8"), 3)
        rod_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(rod_pen)
        painter.drawLine(pivot, bob1)
        painter.drawLine(bob1, bob2)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ff9d76"))
        painter.drawEllipse(pivot, 6.0, 6.0)
        painter.setBrush(QColor("#73d2de"))
        painter.drawEllipse(bob1, 10.0, 10.0)
        painter.setBrush(QColor("#ffb36b"))
        painter.drawEllipse(bob2, 10.0, 10.0)


class StabilityMapWidget(QWidget):
    seedSelected = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._caption = QLabel("Warm colors = faster periodic return. Dark regions = more chaotic.", self)
        self._caption.setWordWrap(True)
        self._caption.setStyleSheet("color: #d9e7ff;")
        self._axis_hint = QLabel("Arm 1 start speed  <->  Arm 2 start speed", self)
        self._axis_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._axis_hint.setStyleSheet("color: #d7e4f8;")
        self._canvas = StabilityMapCanvas(self)
        self._canvas.seedSelected.connect(self.seedSelected.emit)
        self._build_ui()

    @property
    def _payload(self) -> StabilityMapPayload | None:
        return self._canvas._payload

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._caption)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(self._axis_hint)
        self.setMinimumHeight(320)

    def set_payload(self, payload: StabilityMapPayload | None) -> None:
        self._canvas.set_payload(payload)

    def set_status(self, status: str, error: str = "") -> None:
        self._canvas.set_status(status, error=error)
