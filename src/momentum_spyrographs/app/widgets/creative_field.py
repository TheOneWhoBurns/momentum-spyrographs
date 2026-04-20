from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class CreativeField(QWidget):
    valueChanged = Signal(float, float)

    def __init__(
        self,
        title: str,
        left_label: str,
        right_label: str,
        top_label: str,
        bottom_label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.title = title
        self.left_label = left_label
        self.right_label = right_label
        self.top_label = top_label
        self.bottom_label = bottom_label
        self._x = 0.0
        self._y = 0.0
        self._dragging = False
        self.setMinimumSize(220, 180)
        self.setMouseTracking(True)

    def set_value(self, x_value: float, y_value: float) -> None:
        self._x = max(-1.0, min(1.0, float(x_value)))
        self._y = max(-1.0, min(1.0, float(y_value)))
        self.update()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self._dragging = True
        self._apply_position(event.position())

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging:
            self._apply_position(event.position())

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._dragging = False
        self._apply_position(event.position())

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#101622"))

        pad = self._field_rect()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#162133"))
        painter.drawRoundedRect(pad, 18, 18)

        painter.setPen(QPen(QColor(255, 255, 255, 35), 1))
        painter.drawLine(QPointF(pad.center().x(), pad.top()), QPointF(pad.center().x(), pad.bottom()))
        painter.drawLine(QPointF(pad.left(), pad.center().y()), QPointF(pad.right(), pad.center().y()))
        painter.drawRoundedRect(pad, 18, 18)

        point = self._value_to_point(self._x, self._y)
        painter.setBrush(QColor("#ff9d76"))
        painter.setPen(QPen(QColor("#fff1e8"), 2))
        painter.drawEllipse(QRectF(point.x() - 8, point.y() - 8, 16, 16))

        painter.setPen(QColor("#ffb38f"))
        painter.drawText(QRectF(0, 8, self.width(), 24), Qt.AlignmentFlag.AlignHCenter, self.title)
        painter.setPen(QColor("#dfe8f6"))
        painter.drawText(QRectF(10, pad.center().y() - 10, 80, 20), Qt.AlignmentFlag.AlignLeft, self.left_label)
        painter.drawText(QRectF(self.width() - 90, pad.center().y() - 10, 80, 20), Qt.AlignmentFlag.AlignRight, self.right_label)
        painter.drawText(QRectF(0, pad.top() + 10, self.width(), 20), Qt.AlignmentFlag.AlignHCenter, self.top_label)
        painter.drawText(QRectF(0, pad.bottom() - 26, self.width(), 20), Qt.AlignmentFlag.AlignHCenter, self.bottom_label)

    def _field_rect(self) -> QRectF:
        return QRectF(24.0, 40.0, self.width() - 48.0, self.height() - 72.0)

    def _value_to_point(self, x_value: float, y_value: float) -> QPointF:
        pad = self._field_rect()
        x_pos = pad.left() + (x_value + 1.0) * 0.5 * pad.width()
        y_pos = pad.bottom() - (y_value + 1.0) * 0.5 * pad.height()
        return QPointF(x_pos, y_pos)

    def _apply_position(self, point: QPointF) -> None:
        pad = self._field_rect()
        x_pos = max(pad.left(), min(pad.right(), point.x()))
        y_pos = max(pad.top(), min(pad.bottom(), point.y()))
        x_value = ((x_pos - pad.left()) / max(pad.width(), 1.0)) * 2.0 - 1.0
        y_value = ((pad.bottom() - y_pos) / max(pad.height(), 1.0)) * 2.0 - 1.0
        self._x = x_value
        self._y = y_value
        self.valueChanged.emit(self._x, self._y)
        self.update()
