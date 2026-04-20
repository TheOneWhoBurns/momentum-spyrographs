from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from momentum_spyrographs.app.window import MainWindow


APP_STYLESHEET = """
QMainWindow, QWidget {
  background: #0d1321;
  color: #eaf1ff;
  font-size: 13px;
}
QMenuBar, QMenu, QStatusBar {
  background: #151c2d;
  color: #eaf1ff;
}
#card {
  background: #151c2d;
  border: 1px solid #2d4261;
  border-radius: 18px;
}
#cardTitle, #sectionTitle {
  color: #ffb38f;
  font-weight: 700;
}
#inspectorSection {
  background: #1c2538;
  border: 1px solid #2d4261;
  border-radius: 14px;
}
QPushButton {
  background: #ff9d76;
  color: #111827;
  border: none;
  border-radius: 10px;
  padding: 8px 12px;
}
QPushButton:hover {
  background: #ffb999;
}
QPushButton:pressed {
  background: #f1885b;
}
QLineEdit, QListWidget, QComboBox, QDoubleSpinBox, QSpinBox {
  background: #101622;
  border: 1px solid #325178;
  border-radius: 10px;
  padding: 6px 8px;
}
QListWidget::item:selected {
  background: #203553;
}
QSlider::groove:horizontal {
  height: 6px;
  background: #233852;
  border-radius: 3px;
}
QSlider::handle:horizontal {
  background: #ff9d76;
  width: 16px;
  margin: -5px 0;
  border-radius: 8px;
}
QScrollBar:vertical {
  background: #111827;
  width: 10px;
  margin: 4px 0 4px 0;
}
QScrollBar::handle:vertical {
  background: #30486a;
  border-radius: 5px;
  min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
  height: 0;
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
