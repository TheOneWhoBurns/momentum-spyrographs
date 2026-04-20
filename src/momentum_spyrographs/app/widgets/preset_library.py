from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSignalBlocker, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from momentum_spyrographs.core.models import PresetRecord


class PresetLibrary(QWidget):
    newRequested = Signal()
    saveRequested = Signal()
    saveAsRequested = Signal()
    renameRequested = Signal()
    duplicateRequested = Signal()
    archiveRequested = Signal()
    restoreRequested = Signal()
    deleteRequested = Signal()
    presetActivated = Signal(str)
    searchChanged = Signal(str)
    archivedFilterChanged = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.search_input = QLineEdit(self)
        self.show_archived = QCheckBox("Show Archived", self)
        self.list_widget = QListWidget(self)
        self._build_ui()

    def _build_ui(self) -> None:
        self.search_input.setPlaceholderText("Search presets")
        self.search_input.textChanged.connect(self.searchChanged.emit)
        self.show_archived.toggled.connect(self.archivedFilterChanged.emit)
        self.list_widget.currentItemChanged.connect(self._emit_current_item)
        self.list_widget.setIconSize(QPixmap(72, 72).size())
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        button_grid = QGridLayout()
        buttons = [
            ("New", self.newRequested),
            ("Save", self.saveRequested),
            ("Save As", self.saveAsRequested),
            ("Rename", self.renameRequested),
            ("Duplicate", self.duplicateRequested),
            ("Archive", self.archiveRequested),
            ("Restore", self.restoreRequested),
            ("Delete", self.deleteRequested),
        ]
        for index, (label, signal) in enumerate(buttons):
            button = QPushButton(label, self)
            button.clicked.connect(signal.emit)
            button_grid.addWidget(button, index // 2, index % 2)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_input)
        layout.addWidget(self.show_archived)
        layout.addLayout(button_grid)
        layout.addWidget(self.list_widget, 1)

    def current_preset_id(self) -> str | None:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def set_presets(self, presets: list[PresetRecord], current_preset_id: str | None) -> None:
        blocker = QSignalBlocker(self.list_widget)
        self.list_widget.clear()
        for preset in presets:
            item = QListWidgetItem(preset.name)
            item.setData(Qt.ItemDataRole.UserRole, preset.id)
            item.setToolTip(preset.name)
            if preset.thumbnail_path and Path(preset.thumbnail_path).exists():
                item.setIcon(QIcon(preset.thumbnail_path))
            self.list_widget.addItem(item)
            if preset.id == current_preset_id:
                self.list_widget.setCurrentItem(item)
        del blocker

    def reselect(self, preset_id: str | None) -> None:
        blocker = QSignalBlocker(self.list_widget)
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == preset_id:
                self.list_widget.setCurrentItem(item)
                break
        del blocker

    def _emit_current_item(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        del previous
        if current is None:
            return
        preset_id = current.data(Qt.ItemDataRole.UserRole)
        if preset_id:
            self.presetActivated.emit(preset_id)
