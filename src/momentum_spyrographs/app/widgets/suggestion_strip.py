from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from momentum_spyrographs.core.discovery import describe_metrics
from momentum_spyrographs.core.models import RenderSettings, SuggestionCandidate
from momentum_spyrographs.core.render import normalize_points


class SuggestionTile(QWidget):
    clicked = Signal(object)

    def __init__(self, candidate: SuggestionCandidate, render_settings: RenderSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.candidate = candidate
        self.render_settings = render_settings
        self.setFixedSize(144, 120)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        del event
        self.clicked.emit(self.candidate.seed)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#101622"))
        card = QRectF(6, 6, self.width() - 12, self.height() - 12)
        painter.setBrush(QColor("#162133"))
        painter.setPen(QPen(QColor(255, 255, 255, 24), 1))
        painter.drawRoundedRect(card, 14, 14)

        preview_rect = QRectF(14, 14, self.width() - 28, 58)
        scaled = normalize_points(self.candidate.points, int(preview_rect.width()), int(preview_rect.height()))
        scaled[:, 0] += preview_rect.x()
        scaled[:, 1] += preview_rect.y()
        pen = QPen(QColor(self.render_settings.stroke_color), max(1.0, self.render_settings.stroke_width * 0.45))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        for index in range(1, len(scaled)):
            painter.drawLine(
                QPointF(float(scaled[index - 1, 0]), float(scaled[index - 1, 1])),
                QPointF(float(scaled[index, 0]), float(scaled[index, 1])),
            )

        painter.setPen(QColor("#ffb38f"))
        painter.drawText(QRectF(12, 78, self.width() - 24, 16), Qt.AlignmentFlag.AlignLeft, self.candidate.label)
        painter.setPen(QColor("#dfe8f6"))
        painter.drawText(QRectF(12, 94, self.width() - 24, 16), Qt.AlignmentFlag.AlignLeft, describe_metrics(self.candidate.metrics))


class SuggestionStrip(QWidget):
    suggestionActivated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self._empty = QLabel("Suggestions appear here as you explore.", self)
        self._empty.setStyleSheet("color: #d7e4f8;")
        self._layout.addWidget(self._empty)

    def set_suggestions(self, suggestions: tuple[SuggestionCandidate, ...], render_settings: RenderSettings) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not suggestions:
            self._empty = QLabel("Suggestions appear here as you explore.", self)
            self._empty.setStyleSheet("color: #d7e4f8;")
            self._layout.addWidget(self._empty)
            return
        for suggestion in suggestions:
            tile = SuggestionTile(suggestion, render_settings, self)
            tile.clicked.connect(self.suggestionActivated.emit)
            self._layout.addWidget(tile)
        self._layout.addStretch(1)
