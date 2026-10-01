from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .models import TranslationEntry


def read_text_safe(path: Path) -> str:
    """Read file content trying common encodings (UTF-8 with BOM, GBK, etc.)."""
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "cp936", "shift_jis", "latin1"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return path.read_bytes().decode("utf-8", errors="replace")


def parse_lenient_json(raw_text: str) -> Any:
    """Parse JSON tolerating UTF-8 BOM, comments, and trailing commas."""
    text = raw_text.lstrip("\ufeff").strip()
    if not text:
        return {}
    # Try direct parse first for speed
    try:
        return json.loads(text)
    except Exception:
        pass

    # Strip single line comments and trailing commas
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("//") or s.startswith("#"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        return {}


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except Exception:
        text = read_text_safe(path)
        return parse_lenient_json(text)


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

    A user pack is deliberately just ``source: target``.
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


def load_translation_pack_payload(path: Path) -> Any:
    return load_json(path)


def extract_translation_entries_from_payload(payload: Any) -> dict[str, TranslationEntry]:
    """Universal parser for translation payloads (MTool, Translator++, RPGMaker, Ren'Py, etc.)."""
    entries: dict[str, TranslationEntry] = {}
    meta_keys = {
        "version", "updated_at", "update_at", "engine", "signature",
        "metadata", "author", "created_at", "tool", "config", "type",
        "game_title", "target_lang", "source_lang"
    }

    # 1. Internal snapshot format with "entries": list of dicts with "id"
    if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
        for raw in payload["entries"]:
            if isinstance(raw, dict) and "id" in raw:
                entry = TranslationEntry(
                    entry_id=str(raw["id"]),
                    source=str(raw.get("source") or ""),
                    target=str(raw.get("target") or ""),
                    file=str(raw.get("file") or ""),
                    context=str(raw.get("context") or ""),
                    category=str(raw.get("category") or ""),
                )
                entries[entry.entry_id] = entry
        if entries:
            return entries

    def add_item(src: Any, tgt: Any, category: str = "", entry_id: str = "", file_name: str = "") -> None:
        if isinstance(src, (dict, list)) or isinstance(tgt, (dict, list)):
            return
        s = str(src) if src is not None else ""
        t = str(tgt) if tgt is not None else ""
        if not s.strip():
            return
        key = entry_id if entry_id else s
        if key not in entries or (not entries[key].target and t):
            entries[key] = TranslationEntry(
                entry_id=entry_id,
                source=s,
                target=t,
                file=file_name,
                category=category
            )

    def extract_from_list(items: list[Any], default_cat: str = "") -> None:
        for item in items:
            if isinstance(item, dict):
                src = (
                    item.get("src")
                    or item.get("source")
                    or item.get("original")
                    or item.get("key")
                    or item.get("id")
                    or item.get("text")
                    or ""
                )
                tgt = (
                    item.get("dst")
                    or item.get("target")
                    or item.get("translation")
                    or item.get("val")
                    or ""
                )
                cat = str(item.get("category") or item.get("type") or default_cat)
                eid = str(item.get("id") or item.get("entry_id") or "")
                fname = str(item.get("file") or "")
                add_item(src, tgt, category=cat, entry_id=eid, file_name=fname)

    def extract_from_dict(d: dict[str, Any], parent_cat: str = "") -> None:
        # A. Check "translations"
        if "translations" in d:
            trans = d["translations"]
            if isinstance(trans, dict):
                extract_from_dict(trans, parent_cat)
                return
            elif isinstance(trans, list):
                extract_from_list(trans, parent_cat)
                return

        # B. Check "items" or "entries" or "records"
        for list_key in ("items", "entries", "records"):
            if list_key in d and isinstance(d[list_key], list):
                extract_from_list(d[list_key], parent_cat)
                return

        # C. Check "data"
        if "data" in d and isinstance(d["data"], dict) and len(d) <= 5:
            extract_from_dict(d["data"], parent_cat)
            return

        # D. Traverse key-values
        for k, v in d.items():
            k_str = str(k)
            if not k_str.strip() or k_str.strip().lower() in meta_keys:
                continue
            if isinstance(v, (str, int, float, bool)) or v is None:
                add_item(k_str, str(v) if v is not None else "", category=parent_cat)
            elif isinstance(v, dict):
                leaf_tgt = (
                    v.get("target")
                    or v.get("dst")
                    or v.get("translation")
                    or v.get("text")
                )
                if leaf_tgt is not None and isinstance(leaf_tgt, (str, int, float)):
                    add_item(k_str, str(leaf_tgt), category=str(v.get("category") or parent_cat))
                else:
                    extract_from_dict(v, parent_cat=k_str)
            elif isinstance(v, list):
                extract_from_list(v, default_cat=k_str)

    if isinstance(payload, dict):
        extract_from_dict(payload)
    elif isinstance(payload, list):
        extract_from_list(payload)

    return entries


def import_csv_pack(path: Path) -> dict[str, TranslationEntry]:
    entries: dict[str, TranslationEntry] = {}
    text = read_text_safe(path)
    reader = csv.reader(text.splitlines())
    rows = [row for row in reader if row]
    if not rows:
        return {}
    header = [col.strip().lower() for col in rows[0]]
    src_idx = -1
    tgt_idx = -1
    id_idx = -1
    for idx, col in enumerate(header):
        if col in ("source", "src", "original", "原文"):
            src_idx = idx
        elif col in ("target", "dst", "translation", "译文"):
            tgt_idx = idx
        elif col in ("id", "entry_id", "编号"):
            id_idx = idx
    if src_idx != -1 and tgt_idx != -1:
        for row in rows[1:]:
            if len(row) > max(src_idx, tgt_idx):
                s = row[src_idx].strip()
                t = row[tgt_idx].strip()
                eid = row[id_idx].strip() if id_idx != -1 and len(row) > id_idx else ""
                if s:
                    key = eid if eid else s
                    entries[key] = TranslationEntry(entry_id=eid, source=s, target=t)
    else:
        for row in rows:
            if len(row) >= 2:
                s = row[0].strip()
                t = row[1].strip()
                if s:
                    entries[s] = TranslationEntry(entry_id="", source=s, target=t)
    return entries


def import_translation_pack(path: Path) -> dict[str, TranslationEntry]:
    if path.suffix.lower() == ".csv":
        return import_csv_pack(path)
    payload = load_translation_pack_payload(path)
    return extract_translation_entries_from_payload(payload)
