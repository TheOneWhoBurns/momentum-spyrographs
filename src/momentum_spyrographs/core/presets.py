from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_data_dir

from momentum_spyrographs.core.models import PresetRecord, utc_now_iso
from momentum_spyrographs.core.project import simulate_projected_points
from momentum_spyrographs.core.render import background_color, render_thumbnail


class PresetStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(user_data_dir("momentum-spyrographs", "Momentum Spyrographs"))
        self.presets_dir = self.root / "presets"
        self.thumbnails_dir = self.root / "thumbnails"
        self.presets_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)

    def preset_path(self, preset_id: str) -> Path:
        return self.presets_dir / f"{preset_id}.json"

    def thumbnail_path(self, preset_id: str) -> Path:
        return self.thumbnails_dir / f"{preset_id}.png"

    def list_presets(self, include_archived: bool = False, query: str = "") -> list[PresetRecord]:
        records: list[PresetRecord] = []
        query_lower = query.strip().lower()
        for path in sorted(self.presets_dir.glob("*.json")):
            record = PresetRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
            if not include_archived and record.is_archived:
                continue
            if query_lower and query_lower not in record.name.lower():
                continue
            records.append(record)
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def load_preset(self, preset_id: str) -> PresetRecord:
        return PresetRecord.from_dict(
            json.loads(self.preset_path(preset_id).read_text(encoding="utf-8"))
        )

    def save_preset(self, preset: PresetRecord) -> PresetRecord:
        thumb_path = self.thumbnail_path(preset.id)
        points = simulate_projected_points(preset.seed, max_points=2400)
        render_thumbnail(
            points,
            thumb_path,
            render_settings=preset.render_settings,
        )
        stored = preset.with_updates(
            updated_at=utc_now_iso(),
            thumbnail_path=str(thumb_path),
        )
        self.preset_path(stored.id).write_text(
            json.dumps(stored.to_dict(), indent=2),
            encoding="utf-8",
        )
        return stored

    def archive_preset(self, preset_id: str) -> PresetRecord:
        record = self.load_preset(preset_id).with_updates(
            archived_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        return self.save_preset(record)

    def restore_preset(self, preset_id: str) -> PresetRecord:
        record = self.load_preset(preset_id).with_updates(
            archived_at=None,
            updated_at=utc_now_iso(),
        )
        return self.save_preset(record)

    def delete_preset(self, preset_id: str) -> None:
        self.preset_path(preset_id).unlink(missing_ok=True)
        self.thumbnail_path(preset_id).unlink(missing_ok=True)
