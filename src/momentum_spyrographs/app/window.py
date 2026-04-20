from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from momentum_spyrographs.app.loop_search_worker import LoopSearchWorker
from momentum_spyrographs.app.map_worker import MapWorker
from momentum_spyrographs.app.preview_worker import PreviewWorker
from momentum_spyrographs.app.state import AppState
from momentum_spyrographs.app.widgets.export_dialog import ExportDialog
from momentum_spyrographs.app.widgets.inspector_panel import InspectorPanel
from momentum_spyrographs.app.widgets.preset_library import PresetLibrary
from momentum_spyrographs.app.widgets.spirograph_preview import SpirographPreview
from momentum_spyrographs.app.widgets.stability_map import StabilityMapWidget
from momentum_spyrographs.app.widgets.style_studio import StyleStudio
from momentum_spyrographs.core.map_tiles import RESOLUTION_LEVELS
from momentum_spyrographs.core.models import ExportRequest, RegionSearchRequest
from momentum_spyrographs.core.presets import PresetStore
from momentum_spyrographs.core.render import write_gif, write_svg


class _PanelProxy:
    """Lightweight stand-in so shortcuts and tests can toggle overlay panels."""

    def __init__(self, stack: QStackedWidget, page_index: int, icon_button: QToolButton) -> None:
        self._stack = stack
        self._page_index = page_index
        self._icon_button = icon_button
        self._expanded_panel: QWidget = stack.widget(page_index)
        self._collapsed_strip: QWidget = icon_button

    @property
    def expanded(self) -> bool:
        return self._stack.currentIndex() == self._page_index

    def set_expanded(self, value: bool) -> None:
        self._icon_button.setChecked(value)

    def toggle(self) -> None:
        self._icon_button.setChecked(not self._icon_button.isChecked())


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
        self.loop_search_worker = LoopSearchWorker()
        self._latest_preview_id = 0
        self._latest_preview_error = ""
        self._latest_map_id = 0
        self._latest_map_error = ""
        self._latest_loop_search_id = 0
        self._panel_switching = False
        self._last_search_bounds: tuple[float, float, float, float] | None = None

        self.library = PresetLibrary(self)
        self.setup_panel = InspectorPanel(self)
        self.map_panel = StabilityMapWidget(self)
        self.preview = SpirographPreview(self)
        self.style_studio = StyleStudio(self)

        self._build_layout()
        self._build_menu()
        self._connect_signals()
        self._build_shortcuts()

        self.state.new_draft()
        self.refresh_library()
        self.statusBar().showMessage(f"Preset storage: {self.store.root}")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        # -- Left: Exploration Map (hero, full height)
        map_card = self._card("Exploration Map", self.map_panel)
        map_card.setMinimumHeight(280)
        map_card.setMinimumWidth(400)

        # -- Right column default page: Pendulum (top) + Preview (bottom)
        default_page = QWidget(self)
        pendulum_card = self._card("Pendulum Setup", self.setup_panel)
        preview_card = self._card("Preview", self.preview)

        right_splitter = QSplitter(Qt.Orientation.Vertical, default_page)
        right_splitter.setChildrenCollapsible(False)
        right_splitter.addWidget(pendulum_card)
        right_splitter.addWidget(preview_card)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)

        default_layout = QVBoxLayout(default_page)
        default_layout.setContentsMargins(0, 0, 0, 0)
        default_layout.addWidget(right_splitter)

        # -- Overlay pages inside a QStackedWidget
        self._right_stack = QStackedWidget(self)
        self._right_stack.addWidget(default_page)                            # index 0
        self._right_stack.addWidget(self._scroll_widget(self.library))       # index 1
        self._right_stack.addWidget(self._scroll_widget(self.style_studio))  # index 2
        self._right_stack.setCurrentIndex(0)
        self._right_stack.setMinimumWidth(280)

        # -- Thin icon strip (far right)
        self._icon_strip = QWidget(self)
        self._icon_strip.setObjectName("iconStrip")
        self._icon_strip.setFixedWidth(48)

        self._library_icon = QToolButton(self._icon_strip)
        self._library_icon.setText("\u2630")
        self._library_icon.setToolTip("Saved Creations (Ctrl+1)")
        self._library_icon.setFixedSize(36, 36)
        self._library_icon.setCheckable(True)
        self._library_icon.setObjectName("iconStripBtn")

        self._style_icon = QToolButton(self._icon_strip)
        self._style_icon.setText("\u25c9")
        self._style_icon.setToolTip("Style Studio (Ctrl+2)")
        self._style_icon.setFixedSize(36, 36)
        self._style_icon.setCheckable(True)
        self._style_icon.setObjectName("iconStripBtn")

        self._export_icon = QToolButton(self._icon_strip)
        self._export_icon.setText("\u2197")
        self._export_icon.setToolTip("Export")
        self._export_icon.setFixedSize(36, 36)
        self._export_icon.setObjectName("iconStripBtn")

        strip_layout = QVBoxLayout(self._icon_strip)
        strip_layout.setContentsMargins(6, 12, 6, 12)
        strip_layout.setSpacing(8)
        strip_layout.addWidget(self._library_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        strip_layout.addWidget(self._style_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        strip_layout.addStretch(1)
        strip_layout.addWidget(self._export_icon, 0, Qt.AlignmentFlag.AlignHCenter)

        self._library_icon.toggled.connect(self._on_library_toggled)
        self._style_icon.toggled.connect(self._on_style_toggled)
        self._export_icon.clicked.connect(self.export_current)

        # -- Main horizontal splitter: map | right panels
        self._root_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._root_splitter.setChildrenCollapsible(False)
        self._root_splitter.addWidget(map_card)
        self._root_splitter.addWidget(self._right_stack)
        self._root_splitter.setStretchFactor(0, 3)
        self._root_splitter.setStretchFactor(1, 1)
        self._root_splitter.setSizes([860, 360])

        # -- Assemble: splitter + icon strip
        central = QWidget(self)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._root_splitter, 1)
        root_layout.addWidget(self._icon_strip)
        self.setCentralWidget(central)

        # -- Test-compatibility proxies
        self._left_sidebar = _PanelProxy(self._right_stack, 1, self._library_icon)
        self._right_sidebar = _PanelProxy(self._right_stack, 2, self._style_icon)

    def _on_library_toggled(self, checked: bool) -> None:
        if self._panel_switching:
            return
        self._panel_switching = True
        if checked:
            self._style_icon.setChecked(False)
            self._right_stack.setCurrentIndex(1)
        else:
            self._right_stack.setCurrentIndex(0)
        self._panel_switching = False

    def _on_style_toggled(self, checked: bool) -> None:
        if self._panel_switching:
            return
        self._panel_switching = True
        if checked:
            self._library_icon.setChecked(False)
            self._right_stack.setCurrentIndex(2)
        else:
            self._right_stack.setCurrentIndex(0)
        self._panel_switching = False

    def _card(self, title: str, body: QWidget) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        title_label = QLabel(title, container)
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)
        separator = QWidget(container)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background: #1c2d4a;")
        layout.addWidget(separator)
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

    # ------------------------------------------------------------------
    # Menu & shortcuts
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        export_action = QAction("Export\u2026", self)
        export_action.triggered.connect(self.export_current)
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_current)
        save_as_action = QAction("Save As\u2026", self)
        save_as_action.triggered.connect(lambda: self.save_current(save_as=True))
        new_action = QAction("New", self)
        new_action.triggered.connect(self.new_draft)
        file_menu.addAction(new_action)
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(export_action)

        edit_menu = self.menuBar().addMenu("&Edit")
        undo_action = QAction("\u21a9 Undo Map Click", self)
        undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        undo_action.triggered.connect(self.state.undo)
        redo_action = QAction("\u21aa Redo Map Click", self)
        redo_action.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        redo_action.triggered.connect(self.state.redo)
        edit_menu.addAction(undo_action)
        edit_menu.addAction(redo_action)

    def _build_shortcuts(self) -> None:
        toggle_left = QShortcut(QKeySequence("Ctrl+1"), self)
        toggle_left.activated.connect(self._left_sidebar.toggle)
        toggle_right = QShortcut(QKeySequence("Ctrl+2"), self)
        toggle_right.activated.connect(self._right_sidebar.toggle)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.state.documentChanged.connect(self._sync_ui_from_state)
        self.state.previewRequested.connect(self.preview_worker.request_preview)
        self.state.mapRequested.connect(self.map_worker.request_map)
        self.state.previewStatusChanged.connect(lambda status: self.preview.set_status(status, self._latest_preview_error))
        self.state.previewResultChanged.connect(self._sync_preview_payload)
        self.state.mapStatusChanged.connect(lambda status: self.map_panel.set_status(status, self._latest_map_error))
        self.state.mapResultChanged.connect(self.map_panel.set_payload)
        self.state.presetChanged.connect(lambda _: self._update_window_title())
        self.state.dirtyChanged.connect(lambda _: self._update_window_title())
        self.state.undoAvailableChanged.connect(self.map_panel.undo_button.setEnabled)
        self.state.redoAvailableChanged.connect(self.map_panel.redo_button.setEnabled)

        self.preview_worker.previewStarted.connect(self._handle_preview_started)
        self.preview_worker.previewReady.connect(self._handle_preview_ready)
        self.preview_worker.previewFailed.connect(self._handle_preview_failed)
        self.map_worker.mapStarted.connect(self._handle_map_started)
        self.map_worker.mapReady.connect(self._handle_map_ready)
        self.map_worker.mapFailed.connect(self._handle_map_failed)
        self.loop_search_worker.searchStarted.connect(self._handle_loop_search_started)
        self.loop_search_worker.searchReady.connect(self._handle_loop_search_ready)
        self.loop_search_worker.searchFailed.connect(self._handle_loop_search_failed)

        self.style_studio.renderChanged.connect(
            lambda key, value: self.state.update_render_settings(**{key: value})
        )
        self.style_studio.exportRequested.connect(self.export_current)
        self.preview.exportRequested.connect(self.export_current)
        self.map_panel.undo_button.clicked.connect(self.state.undo)
        self.map_panel.redo_button.clicked.connect(self.state.redo)
        self.setup_panel.seedChanged.connect(
            lambda key, value: self.state.update_seed(**{key: value})
        )
        self.map_panel.seedSelected.connect(self._apply_map_seed)
        self.map_panel.viewportChanged.connect(self._handle_viewport_changed)
        self.map_panel.boxSearchRequested.connect(self._search_box_for_matching_loop)
        self.map_panel.matchLoopRequested.connect(self._search_last_region_or_viewport)

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

    # ------------------------------------------------------------------
    # State sync helpers
    # ------------------------------------------------------------------

    def _sync_ui_from_state(self, document) -> None:
        self.style_studio.set_render_settings(document.render_settings)
        self.preview.set_render_settings(document.render_settings)
        self.setup_panel.set_document(document.seed)
        if self.map_panel.current_viewport() != self.state.map_viewport:
            self.map_panel.clear_search_feedback()
        self.map_panel.set_viewport(self.state.map_viewport)
        self._update_window_title()

    def _sync_preview_payload(self, payload) -> None:
        self.preview.set_preview_payload(payload)

    def _update_window_title(self) -> None:
        dirty_mark = " *" if self.state.is_dirty else ""
        self.setWindowTitle(f"{self.state.display_name}{dirty_mark} | Momentum Spyrographs")

    # ------------------------------------------------------------------
    # Preview worker handlers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Map worker handlers
    # ------------------------------------------------------------------

    def _handle_map_started(self, request_id: int) -> None:
        self._latest_map_id = request_id
        self._latest_map_error = ""
        self.state.set_map_status("loading")

    def _handle_map_ready(self, request_id: int, payload) -> None:
        if request_id != self._latest_map_id:
            return
        self._latest_map_error = ""
        self.state.set_map_payload(payload)
        if getattr(payload, "resolution_level", 0) >= RESOLUTION_LEVELS[-1]:
            self.state.set_map_status("idle")

    def _handle_map_failed(self, request_id: int, message: str) -> None:
        if request_id != self._latest_map_id:
            return
        self._latest_map_error = message
        self.state.set_map_status("error")
        self.map_panel.set_status("error", error=message)
        self.statusBar().showMessage(f"Map failed: {message}", 6000)

    def _apply_map_seed(self, omega1: float, omega2: float) -> None:
        self.state.update_map_selection(omega1=omega1, omega2=omega2)

    def _handle_viewport_changed(self, viewport) -> None:
        self.loop_search_worker.cancel_pending()
        self.map_panel.clear_search_feedback()
        self.state.update_map_viewport(viewport)

    def _handle_loop_search_started(self, request_id: int) -> None:
        self._latest_loop_search_id = request_id
        self.map_panel.set_search_feedback("Finding stable minima…")

    def _handle_loop_search_ready(self, request_id: int, result) -> None:
        if request_id != self._latest_loop_search_id:
            return
        self.map_panel.set_search_feedback(result.status_text, result.markers)
        self.statusBar().showMessage(result.status_text, 5000)

    def _handle_loop_search_failed(self, request_id: int, message: str) -> None:
        if request_id != self._latest_loop_search_id:
            return
        self.map_panel.set_search_feedback("Stable-minima search failed")
        self.statusBar().showMessage(f"Stable-minima search failed: {message}", 6000)

    def _search_box_for_matching_loop(self, omega1_a: float, omega1_b: float, omega2_a: float, omega2_b: float) -> None:
        self._last_search_bounds = (omega1_a, omega1_b, omega2_a, omega2_b)
        self._start_loop_search(
            mode="box",
            omega1_a=omega1_a,
            omega1_b=omega1_b,
            omega2_a=omega2_a,
            omega2_b=omega2_b,
        )

    def _search_last_region_or_viewport(self) -> None:
        if self._last_search_bounds is not None:
            omega1_a, omega1_b, omega2_a, omega2_b = self._last_search_bounds
            self._start_loop_search(
                mode="box",
                omega1_a=omega1_a,
                omega1_b=omega1_b,
                omega2_a=omega2_a,
                omega2_b=omega2_b,
            )
            return
        viewport = self.state.map_viewport
        self._start_loop_search(
            mode="viewport",
            omega1_a=viewport.omega1_min,
            omega1_b=viewport.omega1_max,
            omega2_a=viewport.omega2_min,
            omega2_b=viewport.omega2_max,
        )

    def _start_loop_search(
        self,
        *,
        mode: str,
        omega1_a: float,
        omega1_b: float,
        omega2_a: float,
        omega2_b: float,
    ) -> None:
        preview_payload = self.state.preview_payload
        map_payload = self.state.map_payload
        if preview_payload is None or map_payload is None or len(preview_payload.points) < 8:
            self.map_panel.set_search_feedback("Preview reference unavailable")
            return
        request = RegionSearchRequest(
            mode=mode,
            payload=map_payload,
            reference_seed=self.state.seed,
            reference_points=preview_payload.points,
            reference_metrics=preview_payload.metrics,
            omega1_min=min(omega1_a, omega1_b),
            omega1_max=max(omega1_a, omega1_b),
            omega2_min=min(omega2_a, omega2_b),
            omega2_max=max(omega2_a, omega2_b),
        )
        self.loop_search_worker.request_search(request)

    # ------------------------------------------------------------------
    # Preset operations
    # ------------------------------------------------------------------

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
        if self.state.current_preset is not None and not save_as and not self.state.is_dirty:
            self.statusBar().showMessage("No changes to save.", 3000)
            return True

        existing_name = self.state.display_name
        if save_as or self.state.current_preset is None:
            name, ok = QInputDialog.getText(self, "Save Creation", "Creation name:", text=existing_name)
            if not ok or not name.strip():
                return False
            preset = self.state.create_snapshot(
                name=name.strip(),
                duplicate=save_as or self.state.current_preset is None,
            )
        else:
            version_name = self.store.next_version_name(existing_name)
            preset = self.state.create_snapshot(name=version_name, duplicate=True)

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
            preset = self.state.create_snapshot(name=name.strip())
            stored = self.store.save_preset(preset)
            self.state.mark_saved(stored)
            self.refresh_library()
            self.statusBar().showMessage(f"Renamed to {stored.name}", 4000)

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

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.maybe_save_changes():
            self.preview_worker.shutdown()
            self.map_worker.shutdown()
            self.loop_search_worker.shutdown()
            event.accept()
        else:
            event.ignore()
