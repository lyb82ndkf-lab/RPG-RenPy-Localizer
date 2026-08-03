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
    """Export the portable, human-editable translation format.

    IDs/files/categories are implementation details and make a translation
    pack needlessly huge.  A user pack is deliberately just ``source: target``.
    Internal revision snapshots use :func:`export_translation_snapshot`.
    """
    del engine, signature
    payload: dict[str, str] = {}
    for entry in entries:
        source = str(entry.source or "")
        target = str(entry.target or "")
        if source.strip() and target.strip():
            payload[source] = target
    save_json(path, payload)


def export_translation_snapshot(path: Path, engine: str, entries: list[TranslationEntry], signature: str | None = None) -> None:
    """Write the rich private format used for exact per-entry version restore."""
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
    # Legacy/internal snapshots retain IDs and are still accepted.
    for raw in payload.get("entries", []) if isinstance(payload.get("entries"), list) else []:
        if not isinstance(raw, dict) or "id" not in raw:
            continue
        entry = TranslationEntry(
            entry_id=raw["id"],
            source=raw.get("source", ""),
            target=raw.get("target", ""),
            file=raw.get("file", ""),
            context=raw.get("context", ""),
            category=raw.get("category", ""),
        )
        entries[entry.entry_id] = entry
    if entries:
        return entries
    # Public packs are intentionally a plain {"original": "translation"}
    # mapping.  Entry IDs are resolved against the currently loaded project.
    for source, target in payload.items():
        if isinstance(target, str) and str(source).strip():
            entries[str(source)] = TranslationEntry(entry_id="", source=str(source), target=target)
    return entries
