from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class CollapsiblePanel(QWidget):
    """Original vertical-folding panel.  Kept for backward compatibility."""

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


# ---------------------------------------------------------------------------
# Vertical title label drawn at 90 degrees for the collapsed sidebar strip
# ---------------------------------------------------------------------------

class _VerticalLabel(QWidget):
    """Renders rotated text in a thin strip."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:
        return QSize(32, 120)

    def minimumSizeHint(self) -> QSize:
        return QSize(32, 60)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont()
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#ffb38f")))
        painter.translate(self.width() / 2.0, self.height() / 2.0)
        painter.rotate(-90)
        text_rect = QRect(-self.height() // 2, -self.width() // 2, self.height(), self.width())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self._text)


# ---------------------------------------------------------------------------
# SidebarFrame -- whole-sidebar collapsible container
# ---------------------------------------------------------------------------

SIDEBAR_COLLAPSED_WIDTH = 32
SIDEBAR_EXPANDED_WIDTH = 280


class SidebarFrame(QWidget):
    """A sidebar that shrinks to a thin vertical strip when collapsed.

    Signals:
        toggled(bool)  -- emitted when the sidebar expands or collapses.
    """

    toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        body: QWidget,
        *,
        expanded: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._body = body
        self._expanded = expanded

        # -- Collapsed strip --------------------------------------------------
        self._collapsed_strip = QWidget(self)
        self._collapsed_strip.setObjectName("sidebarStrip")
        self._collapsed_strip.setFixedWidth(SIDEBAR_COLLAPSED_WIDTH)

        self._vertical_label = _VerticalLabel(title, self._collapsed_strip)
        self._expand_button = QToolButton(self._collapsed_strip)
        self._expand_button.setObjectName("sidebarToggle")
        self._expand_button.setText("\u276f")  # right chevron
        self._expand_button.setFixedSize(26, 26)
        self._expand_button.setToolTip(f"Show {title}")
        self._expand_button.clicked.connect(lambda: self.set_expanded(True))

        strip_layout = QVBoxLayout(self._collapsed_strip)
        strip_layout.setContentsMargins(3, 8, 3, 8)
        strip_layout.setSpacing(8)
        strip_layout.addWidget(self._expand_button, 0, Qt.AlignmentFlag.AlignHCenter)
        strip_layout.addWidget(self._vertical_label, 1)

        # -- Expanded body ----------------------------------------------------
        self._expanded_panel = QWidget(self)
        self._expanded_panel.setObjectName("card")

        self._collapse_button = QToolButton(self._expanded_panel)
        self._collapse_button.setObjectName("sidebarToggle")
        self._collapse_button.setText("\u276e")  # left chevron
        self._collapse_button.setFixedSize(26, 26)
        self._collapse_button.setToolTip(f"Hide {title}")
        self._collapse_button.clicked.connect(lambda: self.set_expanded(False))

        title_label = QWidget(self._expanded_panel)
        title_layout = QHBoxLayout(title_label)
        title_layout.setContentsMargins(0, 0, 0, 0)
        from PySide6.QtWidgets import QLabel

        header = QLabel(title, title_label)
        header.setObjectName("cardTitle")
        title_layout.addWidget(header, 1)
        title_layout.addWidget(self._collapse_button)

        separator = QWidget(self._expanded_panel)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background: #1c2d4a;")

        panel_layout = QVBoxLayout(self._expanded_panel)
        panel_layout.setContentsMargins(14, 10, 14, 14)
        panel_layout.setSpacing(10)
        panel_layout.addWidget(title_label)
        panel_layout.addWidget(separator)
        panel_layout.addWidget(body, 1)

        # -- Root layout (horizontal: strip | panel) --------------------------
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._collapsed_strip)
        root.addWidget(self._expanded_panel, 1)

        self._apply_state()

    # -- public API -----------------------------------------------------------

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, value: bool) -> None:
        if value == self._expanded:
            return
        self._expanded = value
        self._apply_state()
        self.toggled.emit(value)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    # -- size hints -----------------------------------------------------------

    def sizeHint(self) -> QSize:
        if self._expanded:
            return QSize(SIDEBAR_EXPANDED_WIDTH, 600)
        return QSize(SIDEBAR_COLLAPSED_WIDTH, 600)

    def minimumSizeHint(self) -> QSize:
        if self._expanded:
            return QSize(200, 200)
        return QSize(SIDEBAR_COLLAPSED_WIDTH, 100)

    # -- internals ------------------------------------------------------------

    def _apply_state(self) -> None:
        self._collapsed_strip.setVisible(not self._expanded)
        self._expanded_panel.setVisible(self._expanded)
        self.updateGeometry()
