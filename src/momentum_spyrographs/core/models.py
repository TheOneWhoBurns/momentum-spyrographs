from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from momentum_spyrographs.core.sim import PendulumConfig


LEGACY_BACKGROUND_THEME_MAP = {
    "midnight": "#0d1117",
    "paper": "#f4efe4",
    "forest": "#102a25",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PendulumSeed:
    theta1: float = 0.0
    theta2: float = 0.0
    omega1: float = 1.8
    omega2: float = -0.4
    length1: float = 1.0
    length2: float = 1.0
    mass1: float = 1.0
    mass2: float = 1.0
    gravity: float = 9.81
    duration: float = 80.0
    dt: float = 0.01
    space: str = "trace"

    def to_config(self) -> PendulumConfig:
        return PendulumConfig(
            theta1=self.theta1,
            theta2=self.theta2,
            omega1=self.omega1,
            omega2=self.omega2,
            length1=self.length1,
            length2=self.length2,
            mass1=self.mass1,
            mass2=self.mass2,
            gravity=self.gravity,
            duration=self.duration,
            dt=self.dt,
        )

    def with_updates(self, **kwargs: Any) -> "PendulumSeed":
        return replace(self, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PendulumSeed":
        return cls(**payload)


@dataclass(frozen=True)
class CreativeControls:
    shape_x: float = 0.0
    shape_y: float = 0.0
    motion_x: float = 0.0
    motion_y: float = 0.0

    def with_updates(self, **kwargs: Any) -> "CreativeControls":
        return replace(self, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "CreativeControls":
        if payload is None:
            return cls()
        return cls(**payload)


@dataclass(frozen=True)
class SeedMetrics:
    energy: float = 0.0
    energy_score: float = 0.0
    stability_score: float = 0.0
    circularity_score: float = 0.0
    density_score: float = 0.0
    chaos_score: float = 0.0
    symmetry_score: float = 0.0
    closure_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RenderSettings:
    stroke_mode: str = "solid"
    stroke_color: str = "#ff9d76"
    stroke_gradient_start: str = "#ffd36e"
    stroke_gradient_end: str = "#73d2de"
    stroke_gradient_mode: str = "path"
    stroke_width: float = 2.4
    background_mode: str = "solid"
    background_color: str = "#0d1321"
    background_gradient_start: str = "#0d1321"
    background_gradient_end: str = "#19324a"
    background_gradient_angle: int = 24
    fade_mode: str = "transparent"
    fadeout: float = 0.35
    fade_color: str = "#0d1321"
    fade_gradient_start: str = "#0d1321"
    fade_gradient_end: str = "#73d2de"
    glow_enabled: bool = False
    glow_mode: str = "match_line"
    glow_color: str = "#ffb38f"
    glow_intensity: float = 0.4
    glow_radius: float = 12.0
    animation_speed: float = 0.18
    svg_size: int = 1600
    gif_size: int = 1200
    frames: int = 120
    fps: int = 24

    def with_updates(self, **kwargs: Any) -> "RenderSettings":
        return replace(self, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RenderSettings":
        migrated = dict(payload)
        background_theme = migrated.pop("background_theme", None)
        if background_theme is not None and "background_color" not in migrated:
            migrated["background_mode"] = "solid"
            migrated["background_color"] = LEGACY_BACKGROUND_THEME_MAP.get(
                background_theme,
                cls().background_color,
            )
        defaults = cls()
        merged = defaults.to_dict()
        merged.update(migrated)
        return cls(**merged)


@dataclass(frozen=True)
class PreviewDocument:
    seed: PendulumSeed
    render_settings: RenderSettings
    creative_controls: CreativeControls


@dataclass(frozen=True)
class SuggestionCandidate:
    label: str
    seed: PendulumSeed
    metrics: SeedMetrics
    points: np.ndarray


@dataclass(frozen=True)
class PreviewPayload:
    document: PreviewDocument
    selected_seed: PendulumSeed
    points: np.ndarray
    metrics: SeedMetrics
    suggestions: tuple[SuggestionCandidate, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StabilityMapPayload:
    omega1_values: np.ndarray
    omega2_values: np.ndarray
    image: np.ndarray
    periodicity: np.ndarray
    chaos: np.ndarray
    overlay_seed: PendulumSeed
    selected_omega1: float
    selected_omega2: float


@dataclass(frozen=True)
class PresetRecord:
    id: str
    name: str
    seed: PendulumSeed
    creative_controls: CreativeControls
    render_settings: RenderSettings
    created_at: str
    updated_at: str
    archived_at: str | None = None
    thumbnail_path: str | None = None

    def with_updates(self, **kwargs: Any) -> "PresetRecord":
        return replace(self, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["seed"] = self.seed.to_dict()
        payload["creative_controls"] = self.creative_controls.to_dict()
        payload["render_settings"] = self.render_settings.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PresetRecord":
        return cls(
            id=payload["id"],
            name=payload["name"],
            seed=PendulumSeed.from_dict(payload["seed"]),
            creative_controls=CreativeControls.from_dict(payload.get("creative_controls")),
            render_settings=RenderSettings.from_dict(payload["render_settings"]),
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            archived_at=payload.get("archived_at"),
            thumbnail_path=payload.get("thumbnail_path"),
        )

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


@dataclass(frozen=True)
class ExportRequest:
    kind: str
    fidelity: str
    path: Path
    size: int
    frames: int
    fps: int


def default_preset_name() -> str:
    return "New Configuration"


def create_preset_record(
    seed: PendulumSeed | None = None,
    creative_controls: CreativeControls | None = None,
    render_settings: RenderSettings | None = None,
    name: str | None = None,
) -> PresetRecord:
    now = utc_now_iso()
    return PresetRecord(
        id=uuid4().hex,
        name=name or default_preset_name(),
        seed=seed or PendulumSeed(),
        creative_controls=creative_controls or CreativeControls(),
        render_settings=render_settings or RenderSettings(),
        created_at=now,
        updated_at=now,
    )
