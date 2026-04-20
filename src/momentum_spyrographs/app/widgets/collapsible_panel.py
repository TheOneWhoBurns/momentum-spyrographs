from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton, QVBoxLayout, QWidget


class CollapsiblePanel(QWidget):
    def __init__(self, title: str, body: QWidget, *, expanded: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._body = body
        self._toggle = QToolButton(self)
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(expanded)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self._toggle.toggled.connect(self._set_expanded)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(self._toggle)
        layout.addWidget(body, 1)
        self.setObjectName("card")
        self._body.setVisible(expanded)

    def _set_expanded(self, expanded: bool) -> None:
        self._toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self._body.setVisible(expanded)
        self.updateGeometry()
