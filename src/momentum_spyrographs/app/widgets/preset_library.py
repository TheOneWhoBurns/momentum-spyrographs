from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSignalBlocker, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QToolButton,
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
        self.search_input.setPlaceholderText("Search creations\u2026")
        self.search_input.textChanged.connect(self.searchChanged.emit)
        self.show_archived.toggled.connect(self.archivedFilterChanged.emit)
        self.list_widget.currentItemChanged.connect(self._emit_current_item)
        self.list_widget.setIconSize(QPixmap(72, 72).size())
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        new_btn = QPushButton("+ New", self)
        new_btn.setFixedHeight(32)
        new_btn.clicked.connect(self.newRequested.emit)

        save_btn = QPushButton("Save", self)
        save_btn.setObjectName("secondaryBtn")
        save_btn.setFixedHeight(32)
        save_btn.clicked.connect(self.saveRequested.emit)

        more_menu = QMenu(self)
        save_as_action = more_menu.addAction("Save As\u2026")
        save_as_action.triggered.connect(self.saveAsRequested.emit)
        rename_action = more_menu.addAction("Rename")
        rename_action.triggered.connect(self.renameRequested.emit)
        duplicate_action = more_menu.addAction("Duplicate")
        duplicate_action.triggered.connect(self.duplicateRequested.emit)
        more_menu.addSeparator()
        archive_action = more_menu.addAction("Archive")
        archive_action.triggered.connect(self.archiveRequested.emit)
        restore_action = more_menu.addAction("Restore")
        restore_action.triggered.connect(self.restoreRequested.emit)
        more_menu.addSeparator()
        delete_action = more_menu.addAction("Delete")
        delete_action.triggered.connect(self.deleteRequested.emit)

        more_btn = QToolButton(self)
        more_btn.setText("\u22EF")
        more_btn.setFixedSize(32, 32)
        more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_btn.setMenu(more_menu)
        more_btn.setStyleSheet(
            "QToolButton { font-size: 18px; font-weight: 700; }"
            "QToolButton::menu-indicator { width: 0; height: 0; }"
        )

        toolbar.addWidget(new_btn)
        toolbar.addWidget(save_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(more_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addLayout(toolbar)
        layout.addWidget(self.search_input)
        layout.addWidget(self.show_archived)
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
