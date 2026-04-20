from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from momentum_spyrographs.core.discovery import describe_metrics
from momentum_spyrographs.core.models import PreviewPayload, RenderSettings, SeedMetrics
from momentum_spyrographs.core.render import glow_color, normalize_points, segment_style


def _rgba_to_qcolor(rgba: tuple[int, int, int, int]) -> QColor:
    return QColor(rgba[0], rgba[1], rgba[2], rgba[3])


def _metric_badges(metrics: SeedMetrics) -> list[str]:
    badges: list[str] = []
    badges.append("Stable" if metrics.stability_score >= 0.62 else "Wild")
    badges.append("Circular" if metrics.circularity_score >= 0.6 else "Eccentric")
    badges.append("Dense" if metrics.density_score >= 0.54 else "Open")
    badges.append("Soft" if metrics.energy_score <= 0.45 else "Energetic")
    return badges


class PreviewCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points = np.empty((0, 2), dtype=float)
        self._render_settings = RenderSettings()
        self._progress = 0.0
        self._status = "idle"
        self._error = ""
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)
        self.setMinimumHeight(280)

    def set_payload(self, payload: PreviewPayload | None) -> None:
        self._points = payload.points if payload is not None else np.empty((0, 2), dtype=float)
        if payload is not None:
            self._render_settings = payload.document.render_settings
        self._progress = 0.0
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
            self._timer.start()

    def pause(self) -> None:
        self._timer.stop()
        self.update()

    def restart(self) -> None:
        self._progress = 0.0
        self.play()

    def _advance(self) -> None:
        increment = 0.004 * max(self._render_settings.animation_speed, 0.02)
        self._progress = min(1.0, self._progress + increment)
        if math.isclose(self._progress, 1.0) or self._progress >= 1.0:
            self._timer.stop()
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
            painter.drawText(self.rect().adjusted(0, 0, -20, -16), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, "Updating…")

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
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.canvas = PreviewCanvas(self)
        self.status_label = QLabel("Preview ready", self)
        self._descriptor_label = QLabel("Calm Orbit", self)
        self._badges = [QLabel("", self) for _ in range(4)]
        self._build_ui()

    def _build_ui(self) -> None:
        self.status_label.setObjectName("previewStatusLabel")
        self.status_label.setStyleSheet("color: #6b83a8; font-size: 12px;")
        self._descriptor_label.setObjectName("descriptorLabel")
        self._descriptor_label.setStyleSheet("color: #ffb38f; font-weight: 600; font-size: 15px;")

        play_button = QPushButton("Play", self)
        pause_button = QPushButton("Pause", self)
        restart_button = QPushButton("Restart", self)
        for btn in (play_button, pause_button, restart_button):
            btn.setObjectName("secondaryBtn")
            btn.setFixedHeight(30)
        play_button.clicked.connect(self.canvas.play)
        pause_button.clicked.connect(self.canvas.pause)
        restart_button.clicked.connect(self.canvas.restart)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        top_row.addWidget(self._descriptor_label)
        top_row.addStretch(1)
        top_row.addWidget(self.status_label)
        top_row.addWidget(play_button)
        top_row.addWidget(pause_button)
        top_row.addWidget(restart_button)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        for badge in self._badges:
            badge.setStyleSheet(
                "background: #141e34; color: #b8c9e4; border: 1px solid #1c2d4a;"
                " border-radius: 10px; padding: 4px 10px; font-size: 11px;"
            )
            badge_row.addWidget(badge)
        badge_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(top_row)
        layout.addLayout(badge_row)
        layout.addWidget(self.canvas, 1)

    def set_preview_payload(self, payload: PreviewPayload | None) -> None:
        self.canvas.set_payload(payload)
        if payload is not None:
            self.status_label.setText(f"{payload.selected_seed.space.title()} preview")
            self._descriptor_label.setText(describe_metrics(payload.metrics))
            for badge, text in zip(self._badges, _metric_badges(payload.metrics)):
                badge.setText(text)
            self.canvas.restart()

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
