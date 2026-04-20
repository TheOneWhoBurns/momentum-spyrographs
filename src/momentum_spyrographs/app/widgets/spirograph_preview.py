from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from momentum_spyrographs.core.analysis_config import CANONICAL_WINDOW_SECONDS
from momentum_spyrographs.core.discovery import describe_metrics
from momentum_spyrographs.core.models import PreviewPayload, RenderSettings
from momentum_spyrographs.core.render import glow_color, normalize_points, segment_style


def _rgba_to_qcolor(rgba: tuple[int, int, int, int]) -> QColor:
    return QColor(rgba[0], rgba[1], rgba[2], rgba[3])


class PreviewCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points = np.empty((0, 2), dtype=float)
        self._render_settings = RenderSettings()
        self._progress = 0.0
        self._status = "idle"
        self._error = ""
        self._reference_only = True
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)
        self.setMinimumHeight(140)

    def set_payload(self, payload: PreviewPayload | None) -> None:
        self._points = payload.points if payload is not None else np.empty((0, 2), dtype=float)
        if payload is not None:
            self._render_settings = payload.document.render_settings
        self._progress = 0.0
        self._reference_only = True
        self.update()

    def set_render_settings(self, render_settings: RenderSettings) -> None:
        self._render_settings = render_settings
        self.update()

    def set_status(self, status: str, error: str = "") -> None:
        self._status = status
        self._error = error
        self.update()

    def play(self) -> None:
        if len(self._points) >= 2:
            self._reference_only = False
            self._timer.start()

    def pause(self) -> None:
        self._timer.stop()
        self.update()

    def restart(self) -> None:
        self._progress = 0.0
        self._reference_only = False
        self.play()

    def show_complete(self) -> None:
        """Show the full curve instantly without animating."""
        self._timer.stop()
        self._progress = 1.0
        self._reference_only = False
        self.update()

    def show_reference(self) -> None:
        self._timer.stop()
        self._progress = 0.0
        self._reference_only = True
        self.update()

    def _advance(self) -> None:
        increment = 0.004 * max(self._render_settings.animation_speed, 0.02)
        self._progress = min(1.0, self._progress + increment)
        if math.isclose(self._progress, 1.0) or self._progress >= 1.0:
            self._timer.stop()
            self._progress = 0.0
            self._reference_only = True
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_background(painter)

        inset = self.rect().adjusted(18, 18, -18, -18)
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
        painter.drawRoundedRect(QRectF(inset), 20, 20)

        if self._points.shape[0] < 2:
            painter.setPen(QColor("#e7eefb"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._error or "Preview pending")
            return

        scaled = normalize_points(self._points, inset.width(), inset.height())
        scaled[:, 0] += inset.x()
        scaled[:, 1] += inset.y()
        stop = max(2, int((len(scaled) - 1) * self._progress) + 1)

        if self._render_settings.glow_enabled:
            self._paint_glow(painter, scaled, stop)

        base_pen = QPen(QColor(255, 255, 255, 24), max(1.0, self._render_settings.stroke_width * 0.3))
        base_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(base_pen)
        for index in range(1, len(scaled)):
            painter.drawLine(
                QPointF(float(scaled[index - 1, 0]), float(scaled[index - 1, 1])),
                QPointF(float(scaled[index, 0]), float(scaled[index, 1])),
            )

        if not self._reference_only:
            for index in range(1, stop):
                progress_ratio = index / max(len(scaled) - 1, 1)
                age_ratio = 1.0 - (index / max(stop - 1, 1))
                segment_color = _rgba_to_qcolor(segment_style(self._render_settings, progress_ratio, age_ratio, fidelity="full_glow_raster"))
                pen = QPen(segment_color, max(1.0, self._render_settings.stroke_width))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.drawLine(
                    QPointF(float(scaled[index - 1, 0]), float(scaled[index - 1, 1])),
                    QPointF(float(scaled[index, 0]), float(scaled[index, 1])),
                )

        if self._status == "loading":
            painter.setPen(QColor("#ff9d76"))
            painter.drawText(self.rect().adjusted(0, 0, -20, -16), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, "Updating\u2026")

    def _paint_background(self, painter: QPainter) -> None:
        if self._render_settings.background_mode == "gradient":
            gradient = QLinearGradient()
            gradient.setStart(0, self.height())
            gradient.setFinalStop(self.width(), 0)
            gradient.setColorAt(0.0, QColor(self._render_settings.background_gradient_start))
            gradient.setColorAt(1.0, QColor(self._render_settings.background_gradient_end))
            painter.fillRect(self.rect(), gradient)
        else:
            painter.fillRect(self.rect(), QColor(self._render_settings.background_color))

    def _paint_glow(self, painter: QPainter, scaled: np.ndarray, stop: int) -> None:
        glow_width = max(3.0, self._render_settings.stroke_width + self._render_settings.glow_radius * 0.4)
        for layer in range(3, 0, -1):
            alpha_scale = self._render_settings.glow_intensity * (0.18 * layer)
            for index in range(1, stop):
                progress_ratio = index / max(len(scaled) - 1, 1)
                age_ratio = 1.0 - (index / max(stop - 1, 1))
                glow_rgba = glow_color(self._render_settings, progress_ratio)
                color = QColor(glow_rgba[0], glow_rgba[1], glow_rgba[2], int(255 * alpha_scale * (1.0 - 0.45 * age_ratio)))
                pen = QPen(color, glow_width + layer * self._render_settings.glow_radius * 0.18)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.drawLine(
                    QPointF(float(scaled[index - 1, 0]), float(scaled[index - 1, 1])),
                    QPointF(float(scaled[index, 0]), float(scaled[index, 1])),
                )


class SpirographPreview(QWidget):
    exportRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.canvas = PreviewCanvas(self)
        self.status_label = QLabel("Preview ready", self)
        self._descriptor_label = QLabel("Calm Orbit", self)
        self._metrics_label = QLabel("Turns 0.0 · Visual symmetry 0.00", self)
        self._build_ui()

    def _build_ui(self) -> None:
        self.status_label.setObjectName("previewStatusLabel")
        self.status_label.setStyleSheet("color: #6b83a8; font-size: 11px;")
        self._descriptor_label.setObjectName("descriptorLabel")
        self._descriptor_label.setStyleSheet("color: #ffb38f; font-weight: 600; font-size: 14px;")
        self._metrics_label.setStyleSheet("color: #b8c9e4; font-size: 11px;")

        play_button = QPushButton("\u25b6 Play", self)
        pause_button = QPushButton("\u23f8 Pause", self)
        restart_button = QPushButton("\u21bb Restart", self)
        for btn in (play_button, pause_button, restart_button):
            btn.setObjectName("secondaryBtn")
            btn.setFixedHeight(28)
        play_button.clicked.connect(self.canvas.play)
        pause_button.clicked.connect(self.canvas.pause)
        restart_button.clicked.connect(self.canvas.restart)

        export_button = QPushButton("\u2197 Export\u2026", self)
        export_button.setFixedHeight(28)
        export_button.clicked.connect(self.exportRequested.emit)

        # Header: descriptor + status
        header_row = QHBoxLayout()
        header_row.setSpacing(6)
        header_row.addWidget(self._descriptor_label)
        header_row.addStretch(1)
        header_row.addWidget(self.status_label)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(6)
        metrics_row.addWidget(self._metrics_label)
        metrics_row.addStretch(1)

        # Action buttons
        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        action_row.addWidget(play_button)
        action_row.addWidget(pause_button)
        action_row.addWidget(restart_button)
        action_row.addStretch(1)
        action_row.addWidget(export_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(header_row)
        layout.addLayout(metrics_row)
        layout.addLayout(action_row)
        layout.addWidget(self.canvas, 1)

    def set_preview_payload(self, payload: PreviewPayload | None) -> None:
        self.canvas.set_payload(payload)
        if payload is not None:
            self.status_label.setText(f"{payload.selected_seed.space.title()} preview")
            self._descriptor_label.setText(describe_metrics(payload.metrics))
            self._metrics_label.setText(self._format_trace_metrics(payload))
            self.canvas.show_reference()

    def set_render_settings(self, render_settings: RenderSettings) -> None:
        self.canvas.set_render_settings(render_settings)

    def set_status(self, status: str, error: str = "") -> None:
        labels = {
            "idle": "Preview ready",
            "loading": "Computing preview",
            "error": error or "Preview failed",
        }
        self.status_label.setText(labels.get(status, status))
        self.canvas.set_status(status, error=error)

    def _format_trace_metrics(self, payload: PreviewPayload) -> str:
        return (
            f"Turns {payload.metrics.turns_total:.1f}"
            f" \u00b7 Visual symmetry {payload.metrics.visual_symmetry_score:.2f}"
        )
