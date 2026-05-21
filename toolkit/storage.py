from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import TranslationEntry


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def save_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def export_translation_pack(path: Path, engine: str, entries: list[TranslationEntry]) -> None:
    payload = {
        "engine": engine,
        "entries": [
            {
                "id": entry.entry_id,
                "source": entry.source,
                "target": entry.target,
                "file": entry.file,
                "context": entry.context,
                "category": entry.category,
            }
            for entry in entries
        ],
    }
    save_json(path, payload)


def import_translation_pack(path: Path) -> dict[str, TranslationEntry]:
    payload = load_json(path)
    entries: dict[str, TranslationEntry] = {}
    for raw in payload.get("entries", []):
        entry = TranslationEntry(
            entry_id=raw["id"],
            source=raw.get("source", ""),
            target=raw.get("target", ""),
            file=raw.get("file", ""),
            context=raw.get("context", ""),
            category=raw.get("category", ""),
        )
        entries[entry.entry_id] = entry
    return entries
