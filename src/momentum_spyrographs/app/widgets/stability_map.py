from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from momentum_spyrographs.core.map_tiles import (
    default_viewport,
    pan_viewport,
    viewport_from_bounds,
    zoom_viewport,
)
from momentum_spyrographs.core.models import ExplorationMapPayload, MapViewport, PendulumSeed, RegionSearchMarker


def _as_qpixmap(image: np.ndarray) -> QPixmap:
    height, width, _ = image.shape
    qimage = QImage(image.data, width, height, image.strides[0], QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimage.copy())


class StabilityMapCanvas(QWidget):
    seedSelected = Signal(float, float)
    viewportChanged = Signal(object)
    boxSearchRequested = Signal(float, float, float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._payload: StabilityMapPayload | None = None
        self._pixmap: QPixmap | None = None
        self._status = "Map pending"
        self._error = ""
        self._viewport = default_viewport(PendulumSeed())
        self._press_position: QPointF | None = None
        self._selection_rect: QRectF | None = None
        self._interaction_mode: str | None = None
        self._pan_origin: MapViewport | None = None
        self._markers: tuple[RegionSearchMarker, ...] = tuple()
        self.setMinimumHeight(160)
        self.setMouseTracking(True)

    def set_payload(self, payload: ExplorationMapPayload | None) -> None:
        self._payload = payload
        if payload is not None:
            self._pixmap = _as_qpixmap(payload.image)
            self._viewport = MapViewport(
                center_omega1=0.5 * (payload.viewport_omega1_min + payload.viewport_omega1_max),
                center_omega2=0.5 * (payload.viewport_omega2_min + payload.viewport_omega2_max),
                span_omega1=payload.viewport_omega1_max - payload.viewport_omega1_min,
                span_omega2=payload.viewport_omega2_max - payload.viewport_omega2_min,
                pixel_width=payload.image.shape[1],
                pixel_height=payload.image.shape[0],
            )
        else:
            self._pixmap = None
        self._status = "Map ready"
        self._error = ""
        self.update()

    def set_status(self, status: str, error: str = "") -> None:
        labels = {
            "idle": "Map ready",
            "loading": "Rendering landscape",
            "error": error or "Map failed",
        }
        self._status = labels.get(status, status)
        self._error = error
        self.update()

    def set_viewport(self, viewport: MapViewport) -> None:
        self._viewport = viewport
        self.update()

    def current_viewport(self) -> MapViewport:
        return self._viewport

    def set_markers(self, markers: tuple[RegionSearchMarker, ...]) -> None:
        self._markers = markers
        self.update()

    def clear_markers(self) -> None:
        if not self._markers:
            return
        self._markers = tuple()
        self.update()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        map_rect = self._map_rect()
        if not map_rect.contains(event.position()):
            return
        self._press_position = event.position()
        self._selection_rect = None
        if event.button() == Qt.MouseButton.LeftButton:
            self._interaction_mode = "left_pending"
            self._pan_origin = self._viewport
        elif event.button() == Qt.MouseButton.RightButton:
            self._interaction_mode = "box"
            self._selection_rect = QRectF(event.position(), event.position())
            self.update()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._press_position is None or self._interaction_mode is None:
            return
        map_rect = self._map_rect()
        if self._interaction_mode in {"left_pending", "pan"} and self._pan_origin is not None:
            delta = event.position() - self._press_position
            if self._interaction_mode == "left_pending" and (abs(delta.x()) + abs(delta.y())) > 6.0:
                self._interaction_mode = "pan"
            if self._interaction_mode == "pan":
                delta_omega1 = -(delta.x() / max(map_rect.width(), 1.0)) * self._pan_origin.span_omega1
                delta_omega2 = (delta.y() / max(map_rect.height(), 1.0)) * self._pan_origin.span_omega2
                viewport = pan_viewport(
                    self._pan_origin,
                    delta_omega1=delta_omega1,
                    delta_omega2=delta_omega2,
                )
                self._viewport = viewport
                self.viewportChanged.emit(viewport)
                return
        if self._interaction_mode == "box":
            bounded_end = QPointF(
                min(max(event.position().x(), map_rect.left()), map_rect.right()),
                min(max(event.position().y(), map_rect.top()), map_rect.bottom()),
            )
            self._selection_rect = QRectF(self._press_position, bounded_end).normalized()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._press_position is None or self._interaction_mode is None:
            return
        map_rect = self._map_rect()
        if self._interaction_mode == "left_pending":
            marker = self._marker_at(event.position(), map_rect)
            if marker is not None:
                self.seedSelected.emit(marker.seed.omega1, marker.seed.omega2)
            else:
                omega1 = self._x_to_omega(event.position().x(), map_rect)
                omega2 = self._y_to_omega(event.position().y(), map_rect)
                self.seedSelected.emit(omega1, omega2)
        elif self._interaction_mode == "box":
            selection_rect = self._selection_rect.normalized() if self._selection_rect is not None else QRectF()
            if selection_rect.width() >= 10.0 and selection_rect.height() >= 10.0:
                omega1_a = self._x_to_omega(selection_rect.left(), map_rect)
                omega1_b = self._x_to_omega(selection_rect.right(), map_rect)
                omega2_a = self._y_to_omega(selection_rect.top(), map_rect)
                omega2_b = self._y_to_omega(selection_rect.bottom(), map_rect)
                viewport = viewport_from_bounds(
                    self._viewport,
                    omega1_a=omega1_a,
                    omega1_b=omega1_b,
                    omega2_a=omega2_a,
                    omega2_b=omega2_b,
                )
                self._viewport = viewport
                self.viewportChanged.emit(viewport)
                self.boxSearchRequested.emit(omega1_a, omega1_b, omega2_a, omega2_b)
        del event
        self._press_position = None
        self._selection_rect = None
        self._interaction_mode = None
        self._pan_origin = None
        self.update()

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        map_rect = self._map_rect()
        if not map_rect.contains(event.position()):
            return
        delta = event.angleDelta().y()
        factor = 1.18 if delta > 0 else 1.0 / 1.18
        focus_omega1 = self._x_to_omega(event.position().x(), map_rect)
        focus_omega2 = self._y_to_omega(event.position().y(), map_rect)
        viewport = zoom_viewport(
            self._viewport,
            zoom_factor=factor,
            focus_omega1=focus_omega1,
            focus_omega2=focus_omega2,
        )
        self._viewport = viewport
        self.viewportChanged.emit(viewport)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        map_rect = self._map_rect()
        painter.fillRect(self.rect(), QColor("#0a0f1c"))
        painter.fillRect(map_rect, QColor("#070c16"))

        if self._pixmap is not None:
            painter.drawPixmap(map_rect.toRect(), self._pixmap)
        else:
            painter.setPen(QColor("#dfe8f6"))
            painter.drawText(map_rect.toRect(), Qt.AlignmentFlag.AlignCenter, self._error or self._status)
            return

        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.drawRect(map_rect)
        for fraction in (0.25, 0.5, 0.75):
            x_value = map_rect.left() + map_rect.width() * fraction
            y_value = map_rect.top() + map_rect.height() * fraction
            painter.setPen(QPen(QColor(255, 255, 255, 26), 1, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(x_value, map_rect.top()), QPointF(x_value, map_rect.bottom()))
            painter.drawLine(QPointF(map_rect.left(), y_value), QPointF(map_rect.right(), y_value))

        self._paint_markers(painter, map_rect)

        if self._selection_rect is not None and self._selection_rect.width() > 2.0 and self._selection_rect.height() > 2.0:
            painter.setBrush(QColor(115, 210, 222, 38))
            painter.setPen(QPen(QColor("#73d2de"), 2))
            painter.drawRect(self._selection_rect)

        if self._payload is not None:
            marker = QPointF(
                self._omega_to_x(self._payload.selected_omega1, map_rect),
                self._omega_to_y(self._payload.selected_omega2, map_rect),
            )
            cross_pen = QPen(QColor(255, 255, 255, 60), 1)
            painter.setPen(cross_pen)
            painter.drawLine(QPointF(marker.x() - 10.0, marker.y()), QPointF(marker.x() + 10.0, marker.y()))
            painter.drawLine(QPointF(marker.x(), marker.y() - 10.0), QPointF(marker.x(), marker.y() + 10.0))
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(QPen(QColor("#ffffff"), 1.6))
            painter.drawEllipse(marker, 5.5, 5.5)
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(marker, 1.8, 1.8)
            status = (
                f"View {self._payload.resolution_level}"
                f"   Exact {self._payload.exact_resolution_level}"
                f"   Tiles {self._payload.completed_tiles}"
            )
            if self._status == "Rendering landscape":
                status = f"{self._status}   {status}"
            painter.setPen(QColor("#ff9d76"))
            painter.drawText(
                map_rect.adjusted(10, 10, -10, -10).toRect(),
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
                status,
            )
            painter.setPen(QColor("#d7e4f8"))
            legend = "Black = low finite-time divergence   Color = higher finite-time divergence"
            painter.drawText(
                map_rect.adjusted(10, 10, -10, -10).toRect(),
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                legend,
            )

    def _map_rect(self) -> QRectF:
        return QRectF(8.0, 8.0, max(self.width() - 16.0, 80.0), max(self.height() - 16.0, 80.0))

    def _x_to_omega(self, x_value: float, rect: QRectF) -> float:
        ratio = (x_value - rect.left()) / max(rect.width(), 1.0)
        return float(self._viewport.omega1_min + ratio * self._viewport.span_omega1)

    def _y_to_omega(self, y_value: float, rect: QRectF) -> float:
        ratio = (y_value - rect.top()) / max(rect.height(), 1.0)
        return float(self._viewport.omega2_max - ratio * self._viewport.span_omega2)

    def _omega_to_x(self, omega_value: float, rect: QRectF) -> float:
        ratio = (omega_value - self._viewport.omega1_min) / max(self._viewport.span_omega1, 1e-9)
        return rect.left() + ratio * rect.width()

    def _omega_to_y(self, omega_value: float, rect: QRectF) -> float:
        ratio = (self._viewport.omega2_max - omega_value) / max(self._viewport.span_omega2, 1e-9)
        return rect.top() + ratio * rect.height()

    def _marker_at(self, position: QPointF, rect: QRectF) -> RegionSearchMarker | None:
        closest: RegionSearchMarker | None = None
        closest_distance = 1.0e9
        for marker in self._markers:
            point = QPointF(
                self._omega_to_x(marker.seed.omega1, rect),
                self._omega_to_y(marker.seed.omega2, rect),
            )
            distance = np.hypot(position.x() - point.x(), position.y() - point.y())
            if distance <= 10.0 and distance < closest_distance:
                closest = marker
                closest_distance = distance
        return closest

    def _paint_markers(self, painter: QPainter, rect: QRectF) -> None:
        for index, marker in enumerate(self._markers):
            point = QPointF(
                self._omega_to_x(marker.seed.omega1, rect),
                self._omega_to_y(marker.seed.omega2, rect),
            )
            radius = 5.0 if index > 0 else 6.0
            fill = QColor(255, 255, 255, 210 if index == 0 else 150)
            if index > 0:
                fill = QColor(115, 210, 222, 150)
            painter.setBrush(fill)
            painter.setPen(QPen(QColor(215, 228, 248, 220), 1.2))
            painter.drawEllipse(point, radius, radius)
            painter.setBrush(QColor("#0a0f1c"))
            painter.drawEllipse(point, 1.8, 1.8)


class StabilityMapWidget(QWidget):
    seedSelected = Signal(float, float)
    viewportChanged = Signal(object)
    boxSearchRequested = Signal(float, float, float, float)
    matchLoopRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._canvas = StabilityMapCanvas(self)
        self._canvas.seedSelected.connect(self.seedSelected.emit)
        self._canvas.viewportChanged.connect(self.viewportChanged.emit)
        self._canvas.boxSearchRequested.connect(self.boxSearchRequested.emit)
        self._canvas.setToolTip(
            "Left-click to pick a point or marker\nLeft-drag to pan\nRight-drag to zoom into a box and show stable minima\nScroll to zoom"
        )
        self._reset_button = QPushButton("\u27f2 Reset", self)
        self._zoom_out_button = QPushButton("\u2212", self)
        self._zoom_in_button = QPushButton("+", self)
        self._find_loop_button = QPushButton("\u2609 Find Stable Match", self)
        self._find_loop_button.setToolTip("Find low-divergence minima in the selected box or visible screen that best match the current trace")
        self._hint = QLabel("", self)
        self.undo_button = QPushButton("\u21a9 Undo", self)
        self.redo_button = QPushButton("\u21aa Redo", self)
        self._build_ui()
        self._reset_button.clicked.connect(self._reset_view)
        self._zoom_in_button.clicked.connect(lambda: self._zoom(1.22))
        self._zoom_out_button.clicked.connect(lambda: self._zoom(1.0 / 1.22))
        self._find_loop_button.clicked.connect(self.matchLoopRequested.emit)

    @property
    def _payload(self) -> ExplorationMapPayload | None:
        return self._canvas._payload

    def _build_ui(self) -> None:
        for btn in (
            self._reset_button,
            self._zoom_out_button,
            self._zoom_in_button,
            self._find_loop_button,
            self.undo_button,
            self.redo_button,
        ):
            btn.setObjectName("secondaryBtn")
            btn.setMinimumHeight(36)
        self._zoom_out_button.setFixedWidth(44)
        self._zoom_in_button.setFixedWidth(44)
        self._zoom_out_button.setAutoRepeat(True)
        self._zoom_in_button.setAutoRepeat(True)
        self._zoom_out_button.setAutoRepeatDelay(140)
        self._zoom_in_button.setAutoRepeatDelay(140)
        self._zoom_out_button.setAutoRepeatInterval(75)
        self._zoom_in_button.setAutoRepeatInterval(75)
        self.undo_button.setToolTip("Undo map click (Ctrl+Z)")
        self.undo_button.setEnabled(False)
        self.redo_button.setToolTip("Redo map click (Ctrl+Shift+Z)")
        self.redo_button.setEnabled(False)
        self._hint.setStyleSheet("color: #d7e4f8;")
        self._hint.setMinimumHeight(36)
        self._hint.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(8)
        toolbar.addWidget(self._reset_button)
        toolbar.addWidget(self._zoom_out_button)
        toolbar.addWidget(self._zoom_in_button)
        toolbar.addWidget(self._find_loop_button)
        toolbar.addWidget(self.undo_button)
        toolbar.addWidget(self.redo_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self._hint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(toolbar)
        layout.addWidget(self._canvas, 1)
        self.setMinimumHeight(200)

    def set_payload(self, payload: ExplorationMapPayload | None) -> None:
        self._canvas.set_payload(payload)
        if payload is None:
            self._hint.setText("")

    def set_status(self, status: str, error: str = "") -> None:
        self._canvas.set_status(status, error=error)

    def set_viewport(self, viewport: MapViewport) -> None:
        self._canvas.set_viewport(viewport)

    def current_viewport(self) -> MapViewport:
        return self._canvas.current_viewport()

    def set_search_feedback(self, text: str, markers: tuple[RegionSearchMarker, ...] = tuple()) -> None:
        self._hint.setText(text)
        self._canvas.set_markers(markers)

    def clear_search_feedback(self) -> None:
        self._hint.setText("")
        self._canvas.clear_markers()

    def _reset_view(self) -> None:
        seed = self._payload.overlay_seed if self._payload is not None else PendulumSeed()
        self.viewportChanged.emit(default_viewport(seed))

    def _zoom(self, factor: float) -> None:
        viewport = zoom_viewport(self.current_viewport(), zoom_factor=factor)
        self.viewportChanged.emit(viewport)
