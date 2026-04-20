from __future__ import annotations

import re

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QSlider, QToolButton, QVBoxLayout, QWidget

from momentum_spyrographs.core.models import RenderSettings


HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class ColorIndicator(QWidget):
    """Small swatch that previews the current hex color value."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self._color = "#000000"

    def set_color(self, hex_color: str) -> None:
        if HEX_RE.match(hex_color.strip()):
            self._color = hex_color.strip()
            self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(QColor(self._color))
        painter.drawRoundedRect(QRectF(2, 2, 24, 24), 6, 6)


class StyleStudio(QWidget):
    renderChanged = Signal(str, object)
    exportRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._syncing = False
        self._hex_fields: dict[str, QLineEdit] = {}
        self._color_indicators: dict[str, ColorIndicator] = {}
        self._combos: dict[str, QComboBox] = {}
        self._value_labels: dict[str, QLabel] = {}
        self._sliders: dict[str, QSlider] = {}
        self._glow_toggle = QCheckBox("Enable Glow", self)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(self._style_group("Line", self._build_line_group(), expanded=True))
        layout.addWidget(self._style_group("Background", self._build_background_group(), expanded=False))
        layout.addWidget(self._style_group("Fade", self._build_fade_group(), expanded=False))
        layout.addWidget(self._style_group("Glow", self._build_glow_group(), expanded=False))
        layout.addWidget(self._style_group("Motion", self._build_motion_group(), expanded=False))
        layout.addStretch(1)

    def _style_group(self, title: str, body: QWidget, *, expanded: bool = True) -> QWidget:
        container = QWidget(self)
        toggle = QToolButton(container)
        toggle.setText(f"  {title}")
        toggle.setCheckable(True)
        toggle.setChecked(expanded)
        toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        def on_toggle(checked: bool) -> None:
            toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
            body.setVisible(checked)

        toggle.toggled.connect(on_toggle)
        body.setVisible(expanded)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)
        container_layout.addWidget(toggle)
        container_layout.addWidget(body)
        return container

    def _build_background_group(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)
        form.setSpacing(6)
        mode = self._combo("background_mode", ["solid", "gradient"])
        angle_row = self._slider_row("background_gradient_angle", 0, 360, "35°")
        form.addRow("Mode", mode)
        form.addRow("Color", self._hex_edit("background_color"))
        form.addRow("Start", self._hex_edit("background_gradient_start"))
        form.addRow("End", self._hex_edit("background_gradient_end"))
        form.addRow("Angle", angle_row)
        return widget

    def _build_line_group(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)
        form.setSpacing(6)
        mode = self._combo("stroke_mode", ["solid", "gradient"])
        width_row = self._slider_row("stroke_width", 10, 120, "2.4 px")
        form.addRow("Mode", mode)
        form.addRow("Color", self._hex_edit("stroke_color"))
        form.addRow("Start", self._hex_edit("stroke_gradient_start"))
        form.addRow("End", self._hex_edit("stroke_gradient_end"))
        form.addRow("Width", width_row)
        return widget

    def _build_fade_group(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)
        form.setSpacing(6)
        mode = self._combo("fade_mode", ["transparent", "color", "gradient"])
        strength_row = self._slider_row("fadeout", 0, 100, "0.35")
        form.addRow("Mode", mode)
        form.addRow("Strength", strength_row)
        form.addRow("Color", self._hex_edit("fade_color"))
        form.addRow("Start", self._hex_edit("fade_gradient_start"))
        form.addRow("End", self._hex_edit("fade_gradient_end"))
        return widget

    def _build_glow_group(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)
        form.setSpacing(6)
        self._glow_toggle.toggled.connect(lambda value: self._emit_toggle("glow_enabled", bool(value)))
        mode = self._combo("glow_mode", ["match_line", "custom"])
        intensity_row = self._slider_row("glow_intensity", 0, 100, "0.40")
        radius_row = self._slider_row("glow_radius", 0, 400, "12 px")
        form.addRow(self._glow_toggle)
        form.addRow("Mode", mode)
        form.addRow("Color", self._hex_edit("glow_color"))
        form.addRow("Intensity", intensity_row)
        form.addRow("Radius", radius_row)
        return widget

    def _build_motion_group(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)
        speed_row = self._slider_row("animation_speed", 2, 100, "0.18x")
        form.addRow("Playback", speed_row)
        return widget

    def _combo(self, field_name: str, items: list[str]) -> QComboBox:
        combo = QComboBox(self)
        combo.addItems(items)
        combo.currentTextChanged.connect(lambda value, field=field_name: self._emit_combo(field, value))
        self._combos[field_name] = combo
        return combo

    def _hex_edit(self, field_name: str) -> QWidget:
        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        indicator = ColorIndicator(row)
        self._color_indicators[field_name] = indicator

        edit = QLineEdit(row)
        edit.setPlaceholderText("#000000")
        edit.textChanged.connect(lambda text: indicator.set_color(text))
        edit.editingFinished.connect(lambda field=field_name, target=edit: self._emit_hex(field, target))
        self._hex_fields[field_name] = edit

        row_layout.addWidget(indicator)
        row_layout.addWidget(edit, 1)
        return row

    def _slider_row(self, field_name: str, minimum: int, maximum: int, label: str) -> QWidget:
        widget = QWidget(self)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        slider = QSlider(Qt.Orientation.Horizontal, widget)
        slider.setRange(minimum, maximum)
        value_label = QLabel(label, widget)
        slider.valueChanged.connect(lambda value, key=field_name: self._update_value_label(key, value))
        slider.valueChanged.connect(lambda value, key=field_name: self._emit_slider(key, value))
        self._sliders[field_name] = slider
        self._value_labels[field_name] = value_label
        layout.addWidget(slider, 1)
        layout.addWidget(value_label)
        return widget

    def set_render_settings(self, render_settings: RenderSettings) -> None:
        self._syncing = True
        try:
            for field_name, combo in self._combos.items():
                combo.setCurrentText(str(getattr(render_settings, field_name)))
            for field_name, edit in self._hex_fields.items():
                edit.setText(str(getattr(render_settings, field_name)))
            self._glow_toggle.setChecked(render_settings.glow_enabled)
            self._sliders["background_gradient_angle"].setValue(render_settings.background_gradient_angle)
            self._value_labels["background_gradient_angle"].setText(f"{render_settings.background_gradient_angle}°")
            self._sliders["stroke_width"].setValue(int(round(render_settings.stroke_width * 10)))
            self._value_labels["stroke_width"].setText(f"{render_settings.stroke_width:.1f} px")
            self._sliders["fadeout"].setValue(int(round(render_settings.fadeout * 100)))
            self._value_labels["fadeout"].setText(f"{render_settings.fadeout:.2f}")
            self._sliders["glow_intensity"].setValue(int(round(render_settings.glow_intensity * 100)))
            self._value_labels["glow_intensity"].setText(f"{render_settings.glow_intensity:.2f}")
            self._sliders["glow_radius"].setValue(int(round(render_settings.glow_radius * 10)))
            self._value_labels["glow_radius"].setText(f"{render_settings.glow_radius:.0f} px")
            self._sliders["animation_speed"].setValue(int(round(render_settings.animation_speed * 100)))
            self._value_labels["animation_speed"].setText(f"{render_settings.animation_speed:.2f}x")
        finally:
            self._syncing = False

    def _emit_combo(self, field_name: str, value: str) -> None:
        if not self._syncing:
            self.renderChanged.emit(field_name, value)

    def _emit_toggle(self, field_name: str, value: bool) -> None:
        if not self._syncing:
            self.renderChanged.emit(field_name, value)

    def _emit_slider(self, field_name: str, value: int) -> None:
        if self._syncing:
            return
        if field_name == "background_gradient_angle":
            self.renderChanged.emit(field_name, value)
        elif field_name == "stroke_width":
            self.renderChanged.emit(field_name, value / 10.0)
        elif field_name == "fadeout":
            self.renderChanged.emit(field_name, value / 100.0)
        elif field_name == "glow_intensity":
            self.renderChanged.emit(field_name, value / 100.0)
        elif field_name == "glow_radius":
            self.renderChanged.emit(field_name, value / 10.0)
        elif field_name == "animation_speed":
            self.renderChanged.emit(field_name, value / 100.0)

    def _emit_hex(self, field_name: str, target: QLineEdit) -> None:
        value = target.text().strip()
        if HEX_RE.match(value):
            target.setStyleSheet("")
            if not self._syncing:
                self.renderChanged.emit(field_name, value.lower())
        else:
            target.setStyleSheet("border: 1px solid #cc6655;")

    def _update_value_label(self, field_name: str, value: int) -> None:
        label = self._value_labels[field_name]
        if field_name == "background_gradient_angle":
            label.setText(f"{value}°")
        elif field_name == "stroke_width":
            label.setText(f"{value / 10.0:.1f} px")
        elif field_name == "fadeout":
            label.setText(f"{value / 100.0:.2f}")
        elif field_name == "glow_intensity":
            label.setText(f"{value / 100.0:.2f}")
        elif field_name == "glow_radius":
            label.setText(f"{value / 10.0:.0f} px")
        elif field_name == "animation_speed":
            label.setText(f"{value / 100.0:.2f}x")
