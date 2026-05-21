from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ProjectInfo:
    engine: str
    root: Path
    game_dir: Path
    launcher_path: Path | None = None
    data_dir: Path | None = None
    scripts_dir: Path | None = None


@dataclass(slots=True)
class TranslationEntry:
    entry_id: str
    source: str
    target: str = ""
    file: str = ""
    context: str = ""
    category: str = ""


@dataclass(slots=True)
class DataRecord:
    record_id: str
    label: str
    value: str
    file: str
    category: str = ""
    object_id: str = ""
    object_label: str = ""
    location: str = ""
    json_path: list[str | int] = field(default_factory=list)
    line_number: int | None = None


@dataclass(slots=True)
class SaveSlot:
    slot_id: int
    label: str
    path: Path
    supported: bool = True
    modified_at: str = ""


@dataclass(slots=True)
class MapRecord:
    map_id: int
    name: str
    display_name: str
    file: str
    width: int = 0
    height: int = 0
    tileset_id: int = 0
    event_count: int = 0
