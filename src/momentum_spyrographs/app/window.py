from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from momentum_spyrographs.app.map_worker import MapWorker
from momentum_spyrographs.app.preview_worker import PreviewWorker
from momentum_spyrographs.app.state import AppState
from momentum_spyrographs.app.widgets.collapsible_panel import CollapsiblePanel
from momentum_spyrographs.app.widgets.export_dialog import ExportDialog
from momentum_spyrographs.app.widgets.inspector_panel import InspectorPanel
from momentum_spyrographs.app.widgets.preset_library import PresetLibrary
from momentum_spyrographs.app.widgets.spirograph_preview import SpirographPreview
from momentum_spyrographs.app.widgets.stability_map import StabilityMapWidget
from momentum_spyrographs.app.widgets.style_studio import StyleStudio
from momentum_spyrographs.core.models import ExportRequest
from momentum_spyrographs.core.presets import PresetStore
from momentum_spyrographs.core.render import write_gif, write_svg


class MainWindow(QMainWindow):
    def __init__(self, preset_root: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Momentum Spyrographs")
        self.resize(1420, 860)
        self.setMinimumSize(980, 640)

        self.store = PresetStore(root=preset_root)
        self.state = AppState()
        self.preview_worker = PreviewWorker(debounce_ms=80)
        self.map_worker = MapWorker(debounce_ms=220)
        self._latest_preview_id = 0
        self._latest_preview_error = ""
        self._latest_map_id = 0
        self._latest_map_error = ""

        self.library = PresetLibrary(self)
        self.setup_panel = InspectorPanel(self)
        self.map_panel = StabilityMapWidget(self)
        self.preview = SpirographPreview(self)
        self.style_studio = StyleStudio(self)

        self._build_layout()
        self._build_menu()
        self._connect_signals()

        self.state.new_draft()
        self.refresh_library()
        self.statusBar().showMessage(f"Preset storage: {self.store.root}")

    def _build_layout(self) -> None:
        center = QWidget(self)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        top_row.addWidget(self._card("Pendulum Setup", self.setup_panel), 7)
        top_row.addWidget(self._card("Start-State Map", self.map_panel), 5)
        center_layout.addLayout(top_row)
        center_layout.addWidget(self._card("Preview", self.preview), 1)

        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        left_layout.addWidget(CollapsiblePanel("Saved Creations", self.library, parent=left))
        left_layout.addStretch(1)

        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        right_layout.addWidget(CollapsiblePanel("Style Studio", self.style_studio, parent=right), 1)
        right_layout.addStretch(1)

        root_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root_splitter.setChildrenCollapsible(False)
        root_splitter.addWidget(self._scroll_widget(left))
        root_splitter.addWidget(center)
        root_splitter.addWidget(self._scroll_widget(right))
        root_splitter.setStretchFactor(0, 0)
        root_splitter.setStretchFactor(1, 1)
        root_splitter.setStretchFactor(2, 0)
        root_splitter.setSizes([260, 840, 320])
        self.setCentralWidget(root_splitter)

    def _card(self, title: str, body: QWidget) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        title_label = QLabel(title, container)
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)
        layout.addWidget(body, 1)
        container.setObjectName("card")
        return container

    def _scroll_widget(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        return scroll

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        export_action = QAction("Export…", self)
        export_action.triggered.connect(self.export_current)
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_current)
        save_as_action = QAction("Save As…", self)
        save_as_action.triggered.connect(lambda: self.save_current(save_as=True))
        new_action = QAction("New", self)
        new_action.triggered.connect(self.new_draft)
        file_menu.addAction(new_action)
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(export_action)

    def _connect_signals(self) -> None:
        self.state.documentChanged.connect(self._sync_ui_from_state)
        self.state.previewRequested.connect(self.preview_worker.request_preview)
        self.state.documentChanged.connect(self.map_worker.request_map)
        self.state.previewStatusChanged.connect(lambda status: self.preview.set_status(status, self._latest_preview_error))
        self.state.previewResultChanged.connect(self._sync_preview_payload)
        self.state.presetChanged.connect(lambda _: self._update_window_title())
        self.state.dirtyChanged.connect(lambda _: self._update_window_title())

        self.preview_worker.previewStarted.connect(self._handle_preview_started)
        self.preview_worker.previewReady.connect(self._handle_preview_ready)
        self.preview_worker.previewFailed.connect(self._handle_preview_failed)
        self.map_worker.mapStarted.connect(self._handle_map_started)
        self.map_worker.mapReady.connect(self._handle_map_ready)
        self.map_worker.mapFailed.connect(self._handle_map_failed)

        self.style_studio.renderChanged.connect(
            lambda key, value: self.state.update_render_settings(**{key: value})
        )
        self.style_studio.exportRequested.connect(self.export_current)
        self.setup_panel.seedChanged.connect(
            lambda key, value: self.state.update_seed(**{key: value})
        )
        self.map_panel.seedSelected.connect(self._apply_map_seed)

        self.library.newRequested.connect(self.new_draft)
        self.library.saveRequested.connect(self.save_current)
        self.library.saveAsRequested.connect(lambda: self.save_current(save_as=True))
        self.library.renameRequested.connect(self.rename_current)
        self.library.duplicateRequested.connect(self.duplicate_current)
        self.library.archiveRequested.connect(self.archive_current)
        self.library.restoreRequested.connect(self.restore_current)
        self.library.deleteRequested.connect(self.delete_current)
        self.library.searchChanged.connect(lambda _: self.refresh_library())
        self.library.archivedFilterChanged.connect(lambda _: self.refresh_library())
        self.library.presetActivated.connect(self.open_preset)

    def _sync_ui_from_state(self, document) -> None:
        self.style_studio.set_render_settings(document.render_settings)
        self.preview.set_render_settings(document.render_settings)
        self.setup_panel.set_document(document.seed)
        self._update_window_title()

    def _sync_preview_payload(self, payload) -> None:
        self.preview.set_preview_payload(payload)

    def _update_window_title(self) -> None:
        dirty_mark = " *" if self.state.is_dirty else ""
        self.setWindowTitle(f"{self.state.display_name}{dirty_mark} | Momentum Spyrographs")

    def _handle_preview_started(self, request_id: int) -> None:
        self._latest_preview_id = request_id
        self._latest_preview_error = ""
        self.state.set_preview_status("loading")

    def _handle_preview_ready(self, request_id: int, payload) -> None:
        if request_id != self._latest_preview_id:
            return
        self._latest_preview_error = ""
        self.state.set_preview_payload(payload)
        self.state.set_preview_status("idle")

    def _handle_preview_failed(self, request_id: int, message: str) -> None:
        if request_id != self._latest_preview_id:
            return
        self._latest_preview_error = message
        self.state.set_preview_status("error")
        self.statusBar().showMessage(f"Preview failed: {message}", 6000)

    def _handle_map_started(self, request_id: int) -> None:
        self._latest_map_id = request_id
        self._latest_map_error = ""
        self.map_panel.set_status("loading")

    def _handle_map_ready(self, request_id: int, payload) -> None:
        if request_id != self._latest_map_id:
            return
        self._latest_map_error = ""
        self.map_panel.set_payload(payload)

    def _handle_map_failed(self, request_id: int, message: str) -> None:
        if request_id != self._latest_map_id:
            return
        self._latest_map_error = message
        self.map_panel.set_status("error", error=message)
        self.statusBar().showMessage(f"Map failed: {message}", 6000)

    def _apply_map_seed(self, omega1: float, omega2: float) -> None:
        self.state.update_seed(omega1=omega1, omega2=omega2)

    def refresh_library(self) -> None:
        presets = self.store.list_presets(
            include_archived=self.library.show_archived.isChecked(),
            query=self.library.search_input.text(),
        )
        current_id = self.state.current_preset.id if self.state.current_preset else None
        self.library.set_presets(presets, current_id)

    def maybe_save_changes(self) -> bool:
        if not self.state.is_dirty:
            return True
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Unsaved changes")
        dialog.setText("Save changes to the current creation?")
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        choice = dialog.exec()
        if choice == QMessageBox.StandardButton.Save:
            return self.save_current()
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        return True

    def new_draft(self) -> None:
        if not self.maybe_save_changes():
            return
        self.state.new_draft()
        self.refresh_library()

    def open_preset(self, preset_id: str) -> None:
        current_id = self.state.current_preset.id if self.state.current_preset else None
        if preset_id == current_id:
            return
        if not self.maybe_save_changes():
            self.library.reselect(current_id)
            return
        preset = self.store.load_preset(preset_id)
        self.state.load_preset(preset)
        self.refresh_library()

    def save_current(self, save_as: bool = False) -> bool:
        existing_name = self.state.display_name
        if save_as or self.state.current_preset is None:
            name, ok = QInputDialog.getText(self, "Save Creation", "Creation name:", text=existing_name)
            if not ok or not name.strip():
                return False
            preset = self.state.create_snapshot(name=name.strip(), duplicate=save_as or self.state.current_preset is None)
        else:
            preset = self.state.create_snapshot(name=existing_name)

        stored = self.store.save_preset(preset)
        self.state.mark_saved(stored)
        self.refresh_library()
        self.statusBar().showMessage(f"Saved {stored.name}", 4000)
        return True

    def rename_current(self) -> None:
        if self.state.current_preset is None:
            self.statusBar().showMessage("Save the current draft before renaming.", 4000)
            return
        name, ok = QInputDialog.getText(self, "Rename Creation", "New name:", text=self.state.display_name)
        if ok and name.strip():
            self.state.rename_draft(name.strip())
            self.save_current()

    def duplicate_current(self) -> None:
        default_name = f"{self.state.display_name} Copy"
        name, ok = QInputDialog.getText(self, "Duplicate Creation", "Name:", text=default_name)
        if not ok or not name.strip():
            return
        preset = self.state.create_snapshot(name=name.strip(), duplicate=True)
        stored = self.store.save_preset(preset)
        self.state.mark_saved(stored)
        self.refresh_library()

    def archive_current(self) -> None:
        if self.state.current_preset is None:
            self.statusBar().showMessage("Save the creation before archiving it.", 4000)
            return
        stored = self.store.archive_preset(self.state.current_preset.id)
        self.state.mark_saved(stored)
        self.refresh_library()

    def restore_current(self) -> None:
        if self.state.current_preset is None:
            return
        stored = self.store.restore_preset(self.state.current_preset.id)
        self.state.mark_saved(stored)
        self.refresh_library()

    def delete_current(self) -> None:
        preset_id = self.library.current_preset_id() or (self.state.current_preset.id if self.state.current_preset else None)
        if preset_id is None:
            return
        preset = self.store.load_preset(preset_id)
        if not preset.is_archived:
            self.statusBar().showMessage("Archive a creation before deleting it permanently.", 5000)
            return
        confirm = QMessageBox.question(
            self,
            "Delete Creation",
            f"Delete '{preset.name}' permanently?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_preset(preset_id)
        if self.state.current_preset and self.state.current_preset.id == preset_id:
            self.state.new_draft()
        self.refresh_library()

    def export_current(self) -> None:
        dialog = ExportDialog(self.state.display_name.replace(" ", "-").lower(), self.state.render_settings, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        request = dialog.export_request()
        self._perform_export(request)

    def _perform_export(self, request: ExportRequest) -> None:
        request.path.parent.mkdir(parents=True, exist_ok=True)
        points = self.state.preview_payload.points if self.state.preview_payload is not None else None
        export_seed = self.state.active_seed
        if points is None:
            from momentum_spyrographs.core.project import simulate_projected_points

            points = simulate_projected_points(export_seed)
        render_settings = self.state.render_settings
        if request.kind == "svg":
            write_svg(
                points,
                request.path,
                width=request.size,
                height=request.size,
                render_settings=render_settings,
                fidelity=request.fidelity,
            )
            if render_settings.glow_enabled and request.fidelity == "styled":
                self.statusBar().showMessage("Styled SVG exported with vector-safe glow simplification.", 5000)
        else:
            write_gif(
                points,
                request.path,
                width=request.size,
                height=request.size,
                frames=request.frames,
                fps=request.fps,
                render_settings=render_settings,
                fidelity=request.fidelity,
            )
        self.statusBar().showMessage(f"Exported {request.path}", 5000)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.maybe_save_changes():
            self.preview_worker.shutdown()
            self.map_worker.shutdown()
            event.accept()
        else:
            event.ignore()
