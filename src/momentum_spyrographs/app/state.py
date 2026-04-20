from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, Signal

from momentum_spyrographs.core.models import (
    CreativeControls,
    PendulumSeed,
    PreviewDocument,
    PreviewPayload,
    PresetRecord,
    RenderSettings,
    create_preset_record,
    default_preset_name,
)


class AppState(QObject):
    documentChanged = Signal(object)
    dirtyChanged = Signal(bool)
    presetChanged = Signal(object)
    previewRequested = Signal(object)
    previewStatusChanged = Signal(str)
    previewResultChanged = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._seed = PendulumSeed()
        self._creative_controls = CreativeControls()
        self._render_settings = RenderSettings()
        self._current_preset: PresetRecord | None = None
        self._draft_name = default_preset_name()
        self._dirty = False
        self._preview_status = "idle"
        self._preview_payload: PreviewPayload | None = None

    @property
    def seed(self) -> PendulumSeed:
        return self._seed

    @property
    def active_seed(self) -> PendulumSeed:
        return self._seed

    @property
    def creative_controls(self) -> CreativeControls:
        return self._creative_controls

    @property
    def render_settings(self) -> RenderSettings:
        return self._render_settings

    @property
    def current_preset(self) -> PresetRecord | None:
        return self._current_preset

    @property
    def display_name(self) -> str:
        return self._draft_name

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def preview_status(self) -> str:
        return self._preview_status

    @property
    def preview_payload(self) -> PreviewPayload | None:
        return self._preview_payload

    def document(self) -> PreviewDocument:
        return PreviewDocument(
            seed=self._seed,
            render_settings=self._render_settings,
            creative_controls=self._creative_controls,
        )

    def new_draft(self) -> None:
        self._seed = PendulumSeed()
        self._creative_controls = CreativeControls()
        self._render_settings = RenderSettings()
        self._current_preset = None
        self._draft_name = default_preset_name()
        self._preview_payload = None
        self._set_dirty(False)
        self.presetChanged.emit(None)
        self._emit_document_changed()

    def load_preset(self, preset: PresetRecord) -> None:
        self._seed = preset.seed
        self._creative_controls = preset.creative_controls
        self._render_settings = preset.render_settings
        self._current_preset = preset
        self._draft_name = preset.name
        self._preview_payload = None
        self._set_dirty(False)
        self.presetChanged.emit(preset)
        self._emit_document_changed()

    def mark_saved(self, preset: PresetRecord) -> None:
        self._current_preset = preset
        self._seed = preset.seed
        self._creative_controls = preset.creative_controls
        self._render_settings = preset.render_settings
        self._draft_name = preset.name
        self._set_dirty(False)
        self.presetChanged.emit(preset)
        self._emit_document_changed()

    def rename_draft(self, name: str) -> None:
        self._draft_name = name
        self._set_dirty(True)
        self.presetChanged.emit(self._current_preset)

    def update_seed(self, **kwargs: object) -> None:
        self._seed = replace(self._seed, **kwargs)
        self._set_dirty(True)
        self._emit_document_changed()

    def update_creative_controls(self, **kwargs: object) -> None:
        self._creative_controls = replace(self._creative_controls, **kwargs)
        self._set_dirty(True)
        self._emit_document_changed()

    def update_render_settings(self, **kwargs: object) -> None:
        self._render_settings = replace(self._render_settings, **kwargs)
        self._set_dirty(True)
        self._emit_document_changed()

    def apply_suggestion_seed(self, seed: PendulumSeed) -> None:
        self._seed = seed
        self._set_dirty(True)
        self._emit_document_changed()

    def create_snapshot(self, *, name: str | None = None, duplicate: bool = False) -> PresetRecord:
        snapshot_seed = self.active_seed
        if self._current_preset is None or duplicate:
            return create_preset_record(
                seed=snapshot_seed,
                creative_controls=self._creative_controls,
                render_settings=self._render_settings,
                name=name or self._draft_name,
            )
        preset_name = name or self._draft_name
        return self._current_preset.with_updates(
            name=preset_name,
            seed=snapshot_seed,
            creative_controls=self._creative_controls,
            render_settings=self._render_settings,
        )

    def set_preview_status(self, status: str) -> None:
        self._preview_status = status
        self.previewStatusChanged.emit(status)

    def set_preview_payload(self, payload: PreviewPayload | None) -> None:
        self._preview_payload = payload
        self.previewResultChanged.emit(payload)

    def _set_dirty(self, value: bool) -> None:
        if self._dirty == value:
            return
        self._dirty = value
        self.dirtyChanged.emit(value)

    def _emit_document_changed(self) -> None:
        document = self.document()
        self.documentChanged.emit(document)
        self.previewRequested.emit(document)
