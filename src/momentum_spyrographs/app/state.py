from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, Signal

from momentum_spyrographs.core.map_tiles import default_viewport, structural_seed_key
from momentum_spyrographs.core.models import (
    CreativeControls,
    MapRequest,
    MapViewport,
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
    mapRequested = Signal(object)
    previewStatusChanged = Signal(str)
    previewResultChanged = Signal(object)
    mapStatusChanged = Signal(str)
    mapResultChanged = Signal(object)
    undoAvailableChanged = Signal(bool)
    redoAvailableChanged = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._seed = PendulumSeed()
        self._creative_controls = CreativeControls()
        self._render_settings = RenderSettings()
        self._map_viewport = default_viewport(self._seed)
        self._current_preset: PresetRecord | None = None
        self._draft_name = default_preset_name()
        self._dirty = False
        self._preview_status = "idle"
        self._preview_payload: PreviewPayload | None = None
        self._map_status = "idle"
        self._map_payload = None
        self._history: list[tuple] = []
        self._history_index: int = -1
        self._max_history: int = 50

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

    @property
    def map_viewport(self) -> MapViewport:
        return self._map_viewport

    @property
    def map_status(self) -> str:
        return self._map_status

    @property
    def map_payload(self):
        return self._map_payload

    def document(self) -> PreviewDocument:
        return PreviewDocument(
            seed=self._seed,
            render_settings=self._render_settings,
            creative_controls=self._creative_controls,
        )

    def map_request(self) -> MapRequest:
        return MapRequest(
            seed=self._seed,
            viewport=self._map_viewport,
            structural_key=structural_seed_key(self._seed),
            selected_omega1=self._seed.omega1,
            selected_omega2=self._seed.omega2,
        )

    def new_draft(self) -> None:
        self._seed = PendulumSeed()
        self._creative_controls = CreativeControls()
        self._render_settings = RenderSettings()
        self._map_viewport = default_viewport(self._seed)
        self._current_preset = None
        self._draft_name = default_preset_name()
        self._preview_payload = None
        self._map_payload = None
        self._history = []
        self._history_index = -1
        self._set_dirty(False)
        self.presetChanged.emit(None)
        self._emit_document_changed()

    def load_preset(self, preset: PresetRecord) -> None:
        self._seed = preset.seed
        self._creative_controls = preset.creative_controls
        self._render_settings = preset.render_settings
        self._map_viewport = default_viewport(self._seed)
        self._current_preset = preset
        self._draft_name = preset.name
        self._preview_payload = None
        self._map_payload = None
        self._history = []
        self._history_index = -1
        self._set_dirty(False)
        self.presetChanged.emit(preset)
        self._emit_document_changed()

    def mark_saved(self, preset: PresetRecord) -> None:
        self._current_preset = preset
        self._draft_name = preset.name
        self._set_dirty(False)
        self.presetChanged.emit(preset)

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

    def update_map_viewport(self, viewport: MapViewport) -> None:
        self._map_viewport = viewport
        self.mapRequested.emit(self.map_request())

    def update_map_selection(self, omega1: float, omega2: float) -> None:
        if not self._history:
            self._history.append((self._seed.omega1, self._seed.omega2))
            self._history_index = 0
        self._history = self._history[: self._history_index + 1]
        self._history.append((omega1, omega2))
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]
        self._history_index = len(self._history) - 1
        self._emit_history_state()
        self._seed = replace(self._seed, omega1=omega1, omega2=omega2)
        self._set_dirty(True)
        self._broadcast_document()

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

    def set_map_status(self, status: str) -> None:
        self._map_status = status
        self.mapStatusChanged.emit(status)

    def set_map_payload(self, payload) -> None:
        self._map_payload = payload
        self.mapResultChanged.emit(payload)

    def _set_dirty(self, value: bool) -> None:
        if self._dirty == value:
            return
        self._dirty = value
        self.dirtyChanged.emit(value)

    def undo(self) -> None:
        """Undo the last map click position."""
        if self._history_index <= 0:
            return
        self._history_index -= 1
        self._restore_from_history()

    def redo(self) -> None:
        """Redo the next map click position."""
        if self._history_index >= len(self._history) - 1:
            return
        self._history_index += 1
        self._restore_from_history()

    @property
    def can_undo(self) -> bool:
        return self._history_index > 0

    @property
    def can_redo(self) -> bool:
        return self._history_index < len(self._history) - 1

    def _restore_from_history(self) -> None:
        omega1, omega2 = self._history[self._history_index]
        self._seed = replace(self._seed, omega1=omega1, omega2=omega2)
        self._set_dirty(True)
        self._emit_history_state()
        self._broadcast_document()

    def _emit_history_state(self) -> None:
        self.undoAvailableChanged.emit(self.can_undo)
        self.redoAvailableChanged.emit(self.can_redo)

    def _broadcast_document(self) -> None:
        document = self.document()
        self.documentChanged.emit(document)
        self.previewRequested.emit(document)
        self.mapRequested.emit(self.map_request())

    def _emit_document_changed(self) -> None:
        self._broadcast_document()
