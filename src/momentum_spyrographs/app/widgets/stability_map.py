from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from momentum_spyrographs.core.map_tiles import default_viewport, pan_viewport, zoom_viewport
from momentum_spyrographs.core.models import MapViewport, PendulumSeed, StabilityMapPayload
from momentum_spyrographs.core.stability_map import find_region_loop_candidates


def _as_qpixmap(image: np.ndarray) -> QPixmap:
    height, width, _ = image.shape
    qimage = QImage(image.data, width, height, image.strides[0], QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimage.copy())


class StabilityMapCanvas(QWidget):
    seedSelected = Signal(float, float)
    viewportChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._payload: StabilityMapPayload | None = None
        self._pixmap: QPixmap | None = None
        self._status = "Map pending"
        self._error = ""
        self._viewport = default_viewport(PendulumSeed())
        self._pan_start: QPointF | None = None
        self._pan_origin: MapViewport | None = None
        self._dragging = False
        self.setMinimumHeight(160)
        self.setMouseTracking(True)

    def set_payload(self, payload: StabilityMapPayload | None) -> None:
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

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        map_rect = self._map_rect()
        if event.button() != Qt.MouseButton.LeftButton or not map_rect.contains(event.position()):
            return
        self._pan_start = event.position()
        self._pan_origin = self._viewport
        self._dragging = False

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._pan_start is None or self._pan_origin is None:
            return
        map_rect = self._map_rect()
        delta = event.position() - self._pan_start
        if not self._dragging and abs(delta.x()) + abs(delta.y()) < 5.0:
            return
        self._dragging = True
        delta_omega1 = -(delta.x() / max(map_rect.width(), 1.0)) * self._pan_origin.span_omega1
        delta_omega2 = (delta.y() / max(map_rect.height(), 1.0)) * self._pan_origin.span_omega2
        viewport = pan_viewport(
            self._pan_origin,
            delta_omega1=delta_omega1,
            delta_omega2=delta_omega2,
        )
        self._viewport = viewport
        self.viewportChanged.emit(viewport)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._pan_start is None:
            return
        map_rect = self._map_rect()
        if not self._dragging and self._payload is not None and map_rect.contains(event.position()):
            omega1 = self._x_to_omega(event.position().x(), map_rect)
            omega2 = self._y_to_omega(event.position().y(), map_rect)
            self.seedSelected.emit(omega1, omega2)
        self._pan_start = None
        self._pan_origin = None
        self._dragging = False

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

        if self._payload is not None:
            marker = QPointF(
                self._omega_to_x(self._payload.selected_omega1, map_rect),
                self._omega_to_y(self._payload.selected_omega2, map_rect),
            )
            self._paint_pendulum_overlay(painter, map_rect, marker, self._payload.overlay_seed)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawEllipse(marker, 6.0, 6.0)
            status = f"Detail {self._payload.resolution_level}   Tiles {self._payload.completed_tiles}"
            if self._status == "Rendering landscape":
                status = f"{self._status}   {status}"
            painter.setPen(QColor("#ff9d76"))
            painter.drawText(
                map_rect.adjusted(10, 10, -10, -10).toRect(),
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
                status,
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

    def _paint_pendulum_overlay(
        self,
        painter: QPainter,
        map_rect: QRectF,
        marker: QPointF,
        seed: PendulumSeed,
    ) -> None:
        max_span = max(seed.length1 + seed.length2, 1e-6)
        overlay_radius = min(map_rect.width(), map_rect.height()) * 0.08
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
        margin = 10.0
        shift_x = 0.0
        shift_y = 0.0
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
    viewportChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._canvas = StabilityMapCanvas(self)
        self._canvas.seedSelected.connect(self.seedSelected.emit)
        self._canvas.viewportChanged.connect(self.viewportChanged.emit)
        self._loop_candidates: list[tuple[float, float, float]] = []
        self._loop_candidate_index = 0
        self._candidate_signature: tuple[float, float, int] | None = None
        self._canvas.setToolTip(
            "Click to select start speeds\nDrag to pan \u00b7 Scroll to zoom"
        )
        self._reset_button = QPushButton("Reset", self)
        self._zoom_out_button = QPushButton("\u2212", self)
        self._zoom_in_button = QPushButton("+", self)
        self._find_loop_button = QPushButton("Find Nearby Loop", self)
        self._hint = QLabel("", self)
        self._build_ui()
        self._reset_button.clicked.connect(self._reset_view)
        self._zoom_in_button.clicked.connect(lambda: self._zoom(1.22))
        self._zoom_out_button.clicked.connect(lambda: self._zoom(1.0 / 1.22))
        self._find_loop_button.clicked.connect(self._select_nearby_loop)

    @property
    def _payload(self) -> StabilityMapPayload | None:
        return self._canvas._payload

    def _build_ui(self) -> None:
        for btn in (self._reset_button, self._zoom_out_button, self._zoom_in_button, self._find_loop_button):
            btn.setObjectName("secondaryBtn")
            btn.setFixedHeight(24)
        self._zoom_out_button.setFixedWidth(32)
        self._zoom_in_button.setFixedWidth(32)
        self._zoom_out_button.setAutoRepeat(True)
        self._zoom_in_button.setAutoRepeat(True)
        self._zoom_out_button.setAutoRepeatDelay(140)
        self._zoom_in_button.setAutoRepeatDelay(140)
        self._zoom_out_button.setAutoRepeatInterval(75)
        self._zoom_in_button.setAutoRepeatInterval(75)
        self._hint.setStyleSheet("color: #d7e4f8;")

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(4)
        toolbar.addWidget(self._reset_button)
        toolbar.addWidget(self._zoom_out_button)
        toolbar.addWidget(self._zoom_in_button)
        toolbar.addWidget(self._find_loop_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self._hint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(toolbar)
        layout.addWidget(self._canvas, 1)
        self.setMinimumHeight(200)

    def set_payload(self, payload: StabilityMapPayload | None) -> None:
        self._canvas.set_payload(payload)
        self._loop_candidates = []
        self._loop_candidate_index = 0
        self._candidate_signature = None
        if payload is None:
            self._hint.setText("")

    def set_status(self, status: str, error: str = "") -> None:
        self._canvas.set_status(status, error=error)

    def set_viewport(self, viewport: MapViewport) -> None:
        self._canvas.set_viewport(viewport)

    def current_viewport(self) -> MapViewport:
        return self._canvas.current_viewport()

    def _reset_view(self) -> None:
        seed = self._payload.overlay_seed if self._payload is not None else PendulumSeed()
        self.viewportChanged.emit(default_viewport(seed))

    def _zoom(self, factor: float) -> None:
        viewport = zoom_viewport(self.current_viewport(), zoom_factor=factor)
        self.viewportChanged.emit(viewport)

    def _select_nearby_loop(self) -> None:
        payload = self._payload
        if payload is None:
            return
        signature = (
            round(payload.selected_omega1, 5),
            round(payload.selected_omega2, 5),
            payload.resolution_level,
        )
        if signature != self._candidate_signature or not self._loop_candidates:
            self._loop_candidates = find_region_loop_candidates(
                payload,
                center_omega1=payload.selected_omega1,
                center_omega2=payload.selected_omega2,
                radius_fraction=0.16,
                limit=8,
            )
            self._loop_candidate_index = 0
            self._candidate_signature = signature
        if not self._loop_candidates:
            self._hint.setText("No nearby loops")
            return
        omega1, omega2, score = self._loop_candidates[self._loop_candidate_index % len(self._loop_candidates)]
        self._loop_candidate_index += 1
        self._hint.setText(
            f"Nearby loop {self._loop_candidate_index}/{len(self._loop_candidates)}  score {score:.2f}"
        )
        self.seedSelected.emit(omega1, omega2)
