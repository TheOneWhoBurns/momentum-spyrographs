from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QToolButton, QVBoxLayout, QWidget


class CollapsiblePanel(QWidget):
    def __init__(self, title: str, body: QWidget, *, expanded: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._body = body
        self._toggle = QToolButton(self)
        self._toggle.setText(f"  {title}")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(expanded)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self._toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._toggle.toggled.connect(self._set_expanded)

        self._separator = QWidget(self)
        self._separator.setFixedHeight(1)
        self._separator.setStyleSheet("background: #1c2d4a;")
        self._separator.setVisible(expanded)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.setSpacing(12)
        layout.addWidget(self._toggle)
        layout.addWidget(self._separator)
        layout.addWidget(body, 1)
        self.setObjectName("card")
        self._body.setVisible(expanded)

    def _set_expanded(self, expanded: bool) -> None:
        self._toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self._body.setVisible(expanded)
        self._separator.setVisible(expanded)
        self.updateGeometry()
