from __future__ import annotations

import hashlib
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


def translation_pack_signature(engine: str, entries: list[TranslationEntry]) -> str:
    digest = hashlib.sha256()
    digest.update(engine.encode("utf-8"))
    for entry in entries:
        digest.update(b"\0")
        digest.update(entry.entry_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry.source.encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry.category.encode("utf-8"))
    return digest.hexdigest()


def export_translation_pack(path: Path, engine: str, entries: list[TranslationEntry], signature: str | None = None) -> None:
    payload = {
        "engine": engine,
        "signature": signature or translation_pack_signature(engine, entries),
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


def load_translation_pack_payload(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def import_translation_pack(path: Path) -> dict[str, TranslationEntry]:
    payload = load_translation_pack_payload(path)
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
