from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from momentum_spyrographs.app.window import MainWindow


APP_STYLESHEET = """
/* ═══ Base ═══ */
QMainWindow, QWidget {
  background: #0d1321;
  color: #eaf1ff;
  font-size: 13px;
}

/* ═══ Menu Bar ═══ */
QMenuBar {
  background: #0a0f1c;
  color: #b8c9e4;
  border-bottom: 1px solid #182236;
  padding: 2px 4px;
}
QMenuBar::item {
  padding: 6px 14px;
  border-radius: 6px;
  margin: 2px;
}
QMenuBar::item:selected {
  background: #182844;
}
QMenu {
  background: #111a2e;
  border: 1px solid #243754;
  border-radius: 10px;
  padding: 6px 4px;
}
QMenu::item {
  padding: 8px 24px 8px 14px;
  border-radius: 6px;
  margin: 1px 4px;
}
QMenu::item:selected {
  background: #1a2d4a;
  color: #ffb38f;
}
QMenu::separator {
  height: 1px;
  background: #1e2d48;
  margin: 4px 12px;
}

/* ═══ Status Bar ═══ */
QStatusBar {
  background: #0a0f1c;
  color: #6b83a8;
  border-top: 1px solid #182236;
  font-size: 12px;
}

/* ═══ Cards ═══ */
#card {
  background: #111a2e;
  border: 1px solid #182844;
  border-radius: 18px;
}
#cardTitle {
  color: #ffb38f;
  font-weight: 700;
  font-size: 14px;
}
#sectionTitle {
  color: #ffb38f;
  font-weight: 700;
}

/* ═══ Inspector Sections ═══ */
#inspectorSection {
  background: #141e34;
  border: 1px solid #1c2d4a;
  border-radius: 14px;
}

/* ═══ Primary Buttons ═══ */
QPushButton {
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 #ffa882, stop:1 #f08c62);
  color: #111827;
  border: none;
  border-radius: 10px;
  padding: 8px 16px;
  font-weight: 600;
  font-size: 12px;
}
QPushButton:hover {
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 #ffbf9f, stop:1 #f4976c);
}
QPushButton:pressed {
  background: #e07a4e;
}
QPushButton:disabled {
  background: #1c2d4a;
  color: #4d6585;
}

/* ═══ Secondary Buttons ═══ */
#secondaryBtn {
  background: #141e34;
  color: #b8c9e4;
  border: 1px solid #243754;
}
#secondaryBtn:hover {
  background: #1a2844;
  color: #eaf1ff;
  border-color: #2d4261;
}
#secondaryBtn:pressed {
  background: #111a2e;
}

/* ═══ Icon Strip ═══ */
#iconStrip {
  background: #0a0f1c;
  border-left: 1px solid #182844;
}
#iconStripBtn {
  background: #141e34;
  color: #8a9dba;
  border: 1px solid #1c2d4a;
  border-radius: 18px;
  font-size: 16px;
  font-weight: 700;
  padding: 0;
}
#iconStripBtn:hover {
  background: #1a2844;
  color: #eaf1ff;
  border-color: #2d4261;
}
#iconStripBtn:checked {
  background: #1a2844;
  color: #ffb38f;
  border-color: #ff9d76;
}

/* ═══ Ghost Buttons ═══ */
#ghostBtn {
  background: transparent;
  color: #8a9dba;
  border: none;
  padding: 6px 10px;
}
#ghostBtn:hover {
  background: #141e34;
  color: #eaf1ff;
  border-radius: 8px;
}

/* ═══ Inputs ═══ */
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
  background: #0a0f1c;
  border: 1px solid #1c2d4a;
  border-radius: 10px;
  padding: 7px 10px;
  color: #eaf1ff;
  selection-background-color: #243754;
}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus {
  border-color: #ff9d76;
}
QComboBox::drop-down {
  border: none;
  padding-right: 8px;
}
QComboBox QAbstractItemView {
  background: #111a2e;
  border: 1px solid #243754;
  border-radius: 8px;
  selection-background-color: #1a2d4a;
}

/* ═══ List Widget ═══ */
QListWidget {
  background: #0a0f1c;
  border: 1px solid #1c2d4a;
  border-radius: 12px;
  padding: 4px;
}
QListWidget::item {
  padding: 10px 12px;
  border-radius: 8px;
  margin: 1px 0;
  color: #b8c9e4;
}
QListWidget::item:hover {
  background: #111a2e;
  color: #eaf1ff;
}
QListWidget::item:selected {
  background: #182844;
  color: #ffb38f;
}

/* ═══ Group Box ═══ */
QGroupBox {
  background: #111a2e;
  border: 1px solid #1c2d4a;
  border-radius: 14px;
  margin-top: 8px;
  padding: 28px 12px 12px 12px;
  font-weight: 600;
}
QGroupBox::title {
  subcontrol-origin: margin;
  subcontrol-position: top left;
  padding: 4px 12px;
  color: #8a9dba;
  font-size: 11px;
  font-weight: 600;
}

/* ═══ Sliders ═══ */
QSlider::groove:horizontal {
  height: 6px;
  background: #141e34;
  border-radius: 3px;
}
QSlider::sub-page:horizontal {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #f08c62, stop:1 #ff9d76);
  border-radius: 3px;
}
QSlider::handle:horizontal {
  background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
    fx:0.4, fy:0.4, stop:0 #ffc4a8, stop:1 #ff9d76);
  width: 16px;
  height: 16px;
  margin: -5px 0;
  border-radius: 8px;
}
QSlider::handle:horizontal:hover {
  background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
    fx:0.4, fy:0.4, stop:0 #ffd6c2, stop:1 #ffb38f);
  width: 18px;
  height: 18px;
  margin: -6px 0;
  border-radius: 9px;
}

/* ═══ Checkboxes ═══ */
QCheckBox {
  color: #b8c9e4;
  spacing: 8px;
}
QCheckBox::indicator {
  width: 18px;
  height: 18px;
  border-radius: 5px;
  border: 2px solid #243754;
  background: #0a0f1c;
}
QCheckBox::indicator:checked {
  background: #ff9d76;
  border-color: #ff9d76;
}
QCheckBox::indicator:hover {
  border-color: #3a5a82;
}

/* ═══ Scroll Areas ═══ */
QScrollArea {
  background: transparent;
  border: none;
}

/* ═══ Scrollbars ═══ */
QScrollBar:vertical {
  background: transparent;
  width: 8px;
  margin: 4px 2px;
}
QScrollBar::handle:vertical {
  background: #243754;
  border-radius: 4px;
  min-height: 32px;
}
QScrollBar::handle:vertical:hover {
  background: #2d4261;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
  height: 0;
}
QScrollBar:horizontal {
  background: transparent;
  height: 8px;
}
QScrollBar::handle:horizontal {
  background: #243754;
  border-radius: 4px;
  min-width: 32px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
  width: 0;
}

/* ═══ Tool Buttons ═══ */
QToolButton {
  background: transparent;
  color: #8a9dba;
  border: none;
  border-radius: 8px;
  padding: 8px 12px;
  font-weight: 600;
  font-size: 13px;
}
QToolButton:hover {
  background: #141e34;
  color: #eaf1ff;
}
QToolButton:checked {
  color: #ffb38f;
}

/* ═══ Tooltips ═══ */
QToolTip {
  background: #141e34;
  color: #eaf1ff;
  border: 1px solid #243754;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
}

/* ═══ Dialogs ═══ */
QDialog {
  background: #0d1321;
}

/* ═══ Sidebar Frames ═══ */
#sidebarStrip {
  background: #0e1528;
  border-right: 1px solid #182844;
}
#sidebarToggle {
  background: #141e34;
  color: #8a9dba;
  border: 1px solid #1c2d4a;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
}
#sidebarToggle:hover {
  background: #1a2844;
  color: #ffb38f;
  border-color: #2d4261;
}
"""


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Momentum Spyrographs")
    app.setOrganizationName("Momentum Spyrographs")
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()
    return app.exec()
