from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from momentum_spyrographs.core.models import ExportRequest, RenderSettings


class ExportDialog(QDialog):
    def __init__(
        self,
        suggested_name: str,
        render_settings: RenderSettings,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export")
        self.kind_combo = QComboBox(self)
        self.fidelity_combo = QComboBox(self)
        self.path_edit = QLineEdit(self)
        self.size_spin = QSpinBox(self)
        self.frames_spin = QSpinBox(self)
        self.fps_spin = QSpinBox(self)
        self._suggested_name = suggested_name
        self._build_ui(render_settings)

    def _build_ui(self, render_settings: RenderSettings) -> None:
        self.kind_combo.addItems(["svg", "gif"])
        self.kind_combo.currentTextChanged.connect(self._sync_path_extension)
        self.kind_combo.currentTextChanged.connect(self._sync_fidelity_options)

        browse_button = QPushButton("Browse…", self)
        browse_button.clicked.connect(self._browse)

        self.path_edit.setText(str(Path.cwd() / "exports" / f"{self._suggested_name}.svg"))
        self.size_spin.setRange(256, 4096)
        self.size_spin.setValue(render_settings.svg_size)
        self.frames_spin.setRange(12, 600)
        self.frames_spin.setValue(render_settings.frames)
        self.fps_spin.setRange(1, 120)
        self.fps_spin.setValue(render_settings.fps)
        self._sync_fidelity_options("svg")

        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse_button)
        path_widget = QWidget(self)
        path_widget.setLayout(path_row)

        form = QFormLayout()
        form.addRow("Format", self.kind_combo)
        form.addRow("Style Fidelity", self.fidelity_combo)
        form.addRow("Destination", path_widget)
        form.addRow("Size", self.size_spin)
        form.addRow("Frames", self.frames_spin)
        form.addRow("FPS", self.fps_spin)

        buttons = QHBoxLayout()
        save_button = QPushButton("Export", self)
        cancel_button = QPushButton("Cancel", self)
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
        self._sync_visibility("svg")

    def _browse(self) -> None:
        current_kind = self.kind_combo.currentText()
        filter_value = "SVG Files (*.svg)" if current_kind == "svg" else "GIF Files (*.gif)"
        path, _ = QFileDialog.getSaveFileName(self, "Export File", self.path_edit.text(), filter_value)
        if path:
            self.path_edit.setText(path)

    def _sync_path_extension(self, current_kind: str) -> None:
        path = Path(self.path_edit.text())
        if path.suffix.lower() != f".{current_kind}":
            path = path.with_suffix(f".{current_kind}")
            self.path_edit.setText(str(path))
        self._sync_visibility(current_kind)

    def _sync_fidelity_options(self, current_kind: str) -> None:
        current_value = self.fidelity_combo.currentText()
        self.fidelity_combo.clear()
        if current_kind == "svg":
            self.fidelity_combo.addItems(["flat", "styled"])
        else:
            self.fidelity_combo.addItems(["flat", "styled", "full_glow_raster"])
        if current_value:
            index = self.fidelity_combo.findText(current_value)
            if index >= 0:
                self.fidelity_combo.setCurrentIndex(index)

    def _sync_visibility(self, current_kind: str) -> None:
        is_gif = current_kind == "gif"
        self.frames_spin.setVisible(is_gif)
        self.fps_spin.setVisible(is_gif)

    def export_request(self) -> ExportRequest:
        return ExportRequest(
            kind=self.kind_combo.currentText(),
            fidelity=self.fidelity_combo.currentText(),
            path=Path(self.path_edit.text()),
            size=self.size_spin.value(),
            frames=self.frames_spin.value(),
            fps=self.fps_spin.value(),
        )
