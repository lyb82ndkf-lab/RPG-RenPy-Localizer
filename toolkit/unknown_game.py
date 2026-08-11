from __future__ import annotations

"""Read-only inspection and isolated runtime support for unknown game engines.

This module deliberately does not patch an imported game in place.  It provides
small, deterministic adapters that an AI planner can reason about: file
signals, candidate text extraction, and an isolated copy where exact string
replacements can be tested and removed without touching the source tree.
"""

import hashlib
import csv
import io
import json
import os
import re
import shutil
import struct
import time
from urllib.parse import quote, unquote
from pathlib import Path
from typing import Any

from .detectors import detect_engine, find_launcher
from .models import DataRecord, ProjectInfo, TranslationEntry


TEXT_EXTENSIONS = {
    ".json", ".json5", ".js", ".mjs", ".cjs", ".ts", ".txt", ".csv", ".tsv",
    ".xml", ".html", ".htm", ".po", ".pot", ".ini", ".cfg", ".yaml", ".yml",
    ".rpy", ".asset", ".translation", ".resx", ".strings", ".ks", ".tjs", ".scn", ".spt", ".mes", ".scr", ".jsonl",
}
BINARY_EXTENSIONS = {
    ".assets", ".bundle", ".resource", ".bytes", ".bin", ".pak", ".pck",
    ".locres", ".dat", ".mps", ".ldb", ".lmt", ".lmu", ".rxdata",
    ".rvdata", ".rvdata2",
}
IGNORED_DIRS = {".git", ".rpgrtl_workspace", ".rpgrtl_backup", "node_modules", "__pycache__"}
PATH_LIKE = re.compile(r"^(?:[a-z]:[\\/]|https?://|file://|[./\\]|[A-Za-z0-9_ -]+\.(?:dll|exe|png|jpg|json|js|css|ttf|otf))", re.I)
PRINTABLE = re.compile(r"[\x20-\x7e\u00a0-\uffff]{3,}")
WOLF_BINARY_SEPARATOR = re.compile(rb"[\x00-\x1f\x7f]+")
EXCLUDED_TEXT_NAMES = {"game.ini", "license.txt", "license_ofl.txt", "readme.txt", "readme.md", "notice.txt", "changelog.txt", "others.txt"}
EXCLUDED_TEXT_DIRS = {"license", "licenses", "readme", "docs", "documentation", "manual"}
LEGACY_RPG_EXTENSIONS = {".ldb", ".lmt", ".lmu"}
ENGLISH_HINT_WORDS = {
    "a", "about", "after", "again", "all", "am", "an", "and", "any", "are", "as", "at", "away",
    "back", "be", "because", "been", "before", "being", "but", "by", "can", "come", "could", "did",
    "do", "does", "don't", "down", "for", "from", "get", "give", "go", "good", "got", "had", "has",
    "have", "he", "her", "here", "him", "his", "how", "i", "if", "in", "into", "is", "it", "its", "just",
    "know", "like", "look", "make", "me", "more", "my", "new", "no", "not", "now", "of", "off", "oh",
    "on", "one", "only", "or", "our", "out", "over", "please", "really", "right", "said", "say", "see",
    "she", "should", "so", "some", "something", "tell", "than", "that", "the", "their", "them", "there",
    "they", "think", "this", "to", "too", "up", "us", "very", "want", "was", "we", "were", "what", "when",
    "where", "which", "who", "why", "will", "with", "would", "yes", "you", "your",
}

UNITY_ENGLISH_LOCALES = {"en", "en-us", "en_us", "english", "english (en)", "english (united states)"}
UNITY_SIMPLIFIED_CHINESE_LOCALES = {
    "zh", "zh-cn", "zh_cn", "zh-hans", "zh_hans", "chinese", "simplified chinese",
    "chinese (simplified)", "simplified_chinese", "simplified-chinese",
}
POLYGLOT_TARGET_COLUMN = 2 + 17  # Key + description + Language.Simplified_Chinese


def _normalise_locale(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower().replace("_", "-"))


def _is_unity_localization_name(path: Path) -> bool:
    lower = str(path).replace("\\", "/").lower()
    name = path.name.lower()
    return any(token in lower for token in ("localization", "localisation", "stringtable", "string_table", "polyglot", "/resources/")) and (
        path.suffix.lower() in {".csv", ".tsv", ".json"} or "table" in name or "locale" in name
    )


def _unity_table_context(kind: str, row: int, source_column: int, target_column: int, delimiter: str) -> str:
    delimiter_name = "tab" if delimiter == "\t" else "comma"
    return f"unity-table;kind={kind};row={row};sourceColumn={source_column};targetColumn={target_column};delimiter={delimiter_name}"


def _unity_context_field(context: str, name: str) -> str:
    match = re.search(rf"(?:^|;){re.escape(name)}=([^;]*)", str(context or ""))
    return match.group(1) if match else ""


def _unity_localization_entries(path: Path, raw: bytes, rel: str, limit: int) -> tuple[list[TranslationEntry], bool]:
    """Read CSV/TSV/JSON tables used by Unity Localization and Polyglot.

    Both referenced Unity projects revolve around keyed string tables rather
    than indiscriminate binary string replacement.  We therefore emit entries
    only when a Simplified-Chinese destination slot already exists (or is part
    of Polyglot's fixed language layout), so every result has a deterministic
    write-back target in the isolated runtime copy.
    """
    if not _is_unity_localization_name(path):
        return [], False
    suffix = path.suffix.lower()
    entries: list[TranslationEntry] = []
    handled = False
    if suffix in {".csv", ".tsv"}:
        text = _decode_bytes(raw)
        delimiter = "\t" if suffix == ".tsv" else ","
        try:
            rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
        except csv.Error:
            return [], False
        marker_row = next((index for index, row in enumerate(rows) if row and row[0].strip() in {"Polyglot", "PolyMaster", "BEGIN"}), None)
        if marker_row is not None:
            handled = True
            for row_index in range(marker_row + 1, len(rows)):
                row = rows[row_index]
                if not row or row[0].strip() == "END":
                    break
                if len(row) <= 2:
                    continue
                source = str(row[2]).strip()
                if not _looks_like_dialogue(source):
                    continue
                digest = hashlib.sha1(f"{rel}:polyglot:{row_index}:{row[0]}:{source}".encode("utf-8")).hexdigest()[:12]
                entries.append(TranslationEntry(
                    entry_id=f"unity::{rel}::polyglot::{row_index}::{digest}",
                    source=source,
                    file=rel,
                    context=_unity_table_context("polyglot", row_index, 2, POLYGLOT_TARGET_COLUMN, delimiter),
                    category="unity_localization",
                ))
                if len(entries) >= limit:
                    return entries, handled
            return entries, handled
        if not rows:
            return [], False
        header = rows[0]
        normalised = [_normalise_locale(value) for value in header]
        source_column = next((index for index, value in enumerate(normalised) if value in UNITY_ENGLISH_LOCALES), None)
        target_column = next((index for index, value in enumerate(normalised) if value in UNITY_SIMPLIFIED_CHINESE_LOCALES), None)
        key_column = next((index for index, value in enumerate(normalised) if value in {"key", "id", "key id", "entry key"}), None)
        if source_column is None or target_column is None or key_column is None:
            return [], False
        handled = True
        for row_index, row in enumerate(rows[1:], 1):
            if max(source_column, target_column, key_column) >= len(row):
                continue
            source = str(row[source_column]).strip()
            if not _looks_like_dialogue(source):
                continue
            key = str(row[key_column])
            digest = hashlib.sha1(f"{rel}:header:{row_index}:{key}:{source}".encode("utf-8")).hexdigest()[:12]
            entries.append(TranslationEntry(
                entry_id=f"unity::{rel}::table::{row_index}::{digest}",
                source=source,
                file=rel,
                context=_unity_table_context("header", row_index, source_column, target_column, delimiter),
                category="unity_localization",
            ))
            if len(entries) >= limit:
                break
        return entries, handled
    if suffix == ".json":
        try:
            payload = json.loads(_decode_bytes(raw))
        except (ValueError, TypeError):
            return [], False
        if not isinstance(payload, dict):
            return [], False
        locale_keys = {_normalise_locale(str(key)): str(key) for key in payload}
        source_locale = next((locale_keys[key] for key in UNITY_ENGLISH_LOCALES if key in locale_keys), None)
        target_locale = next((locale_keys[key] for key in UNITY_SIMPLIFIED_CHINESE_LOCALES if key in locale_keys), None)
        source_map = payload.get(source_locale) if source_locale else None
        target_map = payload.get(target_locale) if target_locale else None
        if not isinstance(source_map, dict) or not isinstance(target_map, dict):
            return [], False
        handled = True
        for key, value in source_map.items():
            source = str(value or "").strip()
            if str(key) not in target_map or not _looks_like_dialogue(source):
                continue
            digest = hashlib.sha1(f"{rel}:json:{key}:{source}".encode("utf-8")).hexdigest()[:12]
            entries.append(TranslationEntry(
                entry_id=f"unity::{rel}::json::{digest}",
                source=source,
                file=rel,
                context=f"unity-json;sourceLocale={quote(source_locale, safe='')};targetLocale={quote(target_locale, safe='')};key={quote(str(key), safe='')}",
                category="unity_localization",
            ))
            if len(entries) >= limit:
                break
        return entries, handled
    return [], False


def _apply_unity_localization_entries(path: Path, entries: list[TranslationEntry]) -> int:
    """Apply verified Unity-table targets to one isolated runtime resource."""
    if not entries:
        return 0
    is_json = all(str(entry.context).startswith("unity-json;") for entry in entries)
    try:
        raw = path.read_bytes()
    except OSError:
        return 0
    if is_json:
        try:
            payload = json.loads(_decode_bytes(raw))
        except (ValueError, TypeError):
            return 0
        if not isinstance(payload, dict):
            return 0
        changed = False
        for entry in entries:
            source_locale = unquote(_unity_context_field(entry.context, "sourceLocale"))
            target_locale = unquote(_unity_context_field(entry.context, "targetLocale"))
            key = unquote(_unity_context_field(entry.context, "key"))
            source_map = payload.get(source_locale)
            target_map = payload.get(target_locale)
            if not isinstance(source_map, dict) or not isinstance(target_map, dict):
                continue
            if str(source_map.get(key) or "") != entry.source or key not in target_map:
                continue
            if target_map.get(key) != entry.target:
                target_map[key] = entry.target
                changed = True
        if not changed:
            return 0
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        except OSError:
            return 0
        return 1
    delimiter = "\t" if _unity_context_field(entries[0].context, "delimiter") == "tab" else ","
    try:
        rows = list(csv.reader(io.StringIO(_decode_bytes(raw)), delimiter=delimiter))
    except csv.Error:
        return 0
    changed = False
    for entry in entries:
        try:
            row_index = int(_unity_context_field(entry.context, "row"))
            source_column = int(_unity_context_field(entry.context, "sourceColumn"))
            target_column = int(_unity_context_field(entry.context, "targetColumn"))
        except ValueError:
            continue
        if row_index < 0 or row_index >= len(rows):
            continue
        row = rows[row_index]
        if source_column >= len(row) or str(row[source_column]).strip() != entry.source:
            continue
        if len(row) <= target_column:
            row.extend([""] * (target_column + 1 - len(row)))
        if row[target_column] != entry.target:
            row[target_column] = entry.target
            changed = True
    if not changed:
        return 0
    output = io.StringIO(newline="")
    csv.writer(output, delimiter=delimiter, lineterminator="\n").writerows(rows)
    try:
        path.write_text(output.getvalue(), encoding="utf-8", newline="")
    except OSError:
        return 0
    return 1


def _is_unreal_localization_name(path: Path) -> bool:
    lower = str(path).replace("\\", "/").lower()
    return path.suffix.lower() == ".archive" and ("/localization/" in lower or "localization" in path.name.lower())


def _unreal_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("Text") or "")
    return str(value or "")


def _unreal_archive_entries(path: Path, raw: bytes, rel: str, limit: int) -> tuple[list[TranslationEntry], bool]:
    """Extract UE4/UE5 JSON localization archive records.

    UE4 and UE5 use the same source-control-friendly ``.archive`` hierarchy
    (Namespaces/Subnamespaces/Children).  Its Source/Translation pair is the
    precise counterpart of the editor workflow used by LocalizationUE4.
    """
    if not _is_unreal_localization_name(path):
        return [], False
    try:
        payload = json.loads(_decode_bytes(raw))
    except (ValueError, TypeError):
        return [], False
    if not isinstance(payload, dict):
        return [], False
    entries: list[TranslationEntry] = []

    def visit(node: Any, pointer: list[str]) -> None:
        if not isinstance(node, dict) or len(entries) >= limit:
            return
        children = node.get("Children")
        if isinstance(children, list):
            for index, child in enumerate(children):
                if not isinstance(child, dict):
                    continue
                source = _unreal_text(child.get("Source")).strip()
                has_translation = "Translation" in child and isinstance(child.get("Translation"), (dict, str))
                if has_translation and _looks_like_dialogue(source):
                    child_pointer = pointer + ["Children", str(index)]
                    digest = hashlib.sha1(f"{rel}:{'/'.join(child_pointer)}:{source}".encode("utf-8")).hexdigest()[:12]
                    entries.append(TranslationEntry(
                        entry_id=f"unreal::{rel}::{digest}",
                        source=source,
                        file=rel,
                        context=f"unreal-archive;pointer={quote('/'.join(child_pointer), safe='/')}",
                        category="unreal_localization",
                    ))
                    if len(entries) >= limit:
                        return
        subnamespaces = node.get("Subnamespaces")
        if isinstance(subnamespaces, list):
            for index, child in enumerate(subnamespaces):
                visit(child, pointer + ["Subnamespaces", str(index)])
                if len(entries) >= limit:
                    return

    visit(payload, [])
    return entries, True


def _unreal_pointer_node(payload: Any, pointer: str) -> dict[str, Any] | None:
    current = payload
    for part in [segment for segment in pointer.split("/") if segment]:
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current if isinstance(current, dict) else None


def _apply_unreal_archive_entries(path: Path, entries: list[TranslationEntry]) -> int:
    try:
        payload = json.loads(_decode_bytes(path.read_bytes()))
    except (OSError, ValueError, TypeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    changed = False
    for entry in entries:
        pointer = unquote(_unity_context_field(entry.context, "pointer"))
        node = _unreal_pointer_node(payload, pointer)
        if not node or _unreal_text(node.get("Source")).strip() != entry.source:
            continue
        translation = node.get("Translation")
        if isinstance(translation, dict):
            if translation.get("Text") != entry.target:
                translation["Text"] = entry.target
                changed = True
        elif isinstance(translation, str) and translation != entry.target:
            node["Translation"] = entry.target
            changed = True
    if not changed:
        return 0
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    except OSError:
        return 0
    return 1


def _is_galtransl_json(path: Path, raw: bytes) -> bool:
    if path.suffix.lower() != ".json":
        return False
    # GalTransl's name-message JSON is common in extracted visual-novel
    # projects; accepting the field structure rather than a filename keeps
    # custom dump names compatible.
    try:
        payload = json.loads(_decode_bytes(raw))
    except (ValueError, TypeError):
        return False
    return isinstance(payload, list) and any(isinstance(item, dict) and any(field in item for field in ("message", "pre_jp", "post_jp")) for item in payload)


def _galtransl_entries(path: Path, raw: bytes, rel: str, limit: int) -> tuple[list[TranslationEntry], bool]:
    if not _is_galtransl_json(path, raw):
        return [], False
    try:
        payload = json.loads(_decode_bytes(raw))
    except (ValueError, TypeError):
        return [], False
    if not isinstance(payload, list):
        return [], False
    entries: list[TranslationEntry] = []
    for row_index, row in enumerate(payload):
        if not isinstance(row, dict):
            continue
        source_field = next((field for field in ("message", "post_jp", "pre_jp") if str(row.get(field) or "").strip()), "")
        source = str(row.get(source_field) or "").strip()
        if not source_field or not _looks_like_dialogue(source):
            continue
        # GalTransl consumes ``pre_zh``/``proofread_zh`` in its cache/output
        # pipeline.  New name-message dumps receive ``pre_zh`` so the copied
        # JSON is directly useful as a GalTransl-compatible translation file.
        target_field = "proofread_zh" if "proofread_zh" in row else "pre_zh"
        speaker = str(row.get("name") or "").strip()
        digest = hashlib.sha1(f"{rel}:{row_index}:{source_field}:{source}".encode("utf-8")).hexdigest()[:12]
        entries.append(TranslationEntry(
            entry_id=f"galtransl::{rel}::{row_index}::{digest}",
            source=source,
            file=rel,
            context=f"galtransl-json;row={row_index};sourceField={source_field};targetField={target_field};speaker={quote(speaker, safe='')}",
            category="galgame_dialogue",
        ))
        if len(entries) >= limit:
            break
    return entries, True


def _apply_galtransl_entries(path: Path, entries: list[TranslationEntry]) -> int:
    try:
        payload = json.loads(_decode_bytes(path.read_bytes()))
    except (OSError, ValueError, TypeError):
        return 0
    if not isinstance(payload, list):
        return 0
    changed = False
    for entry in entries:
        try:
            row_index = int(_unity_context_field(entry.context, "row"))
        except ValueError:
            continue
        source_field = _unity_context_field(entry.context, "sourceField")
        target_field = _unity_context_field(entry.context, "targetField")
        if row_index < 0 or row_index >= len(payload) or not isinstance(payload[row_index], dict):
            continue
        row = payload[row_index]
        if str(row.get(source_field) or "").strip() != entry.source:
            continue
        if row.get(target_field) != entry.target:
            row[target_field] = entry.target
            changed = True
    if not changed:
        return 0
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    except OSError:
        return 0
    return 1


def _looks_like_dialogue(value: str) -> bool:
    text = str(value or "").replace("\x00", " ").strip()
    if len(text) < 2 or len(text) > 1000 or PATH_LIKE.match(text):
        return False
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        return False
    if any(0xE000 <= ord(char) <= 0xF8FF for char in text) or "�" in text:
        return False
    if text.upper().startswith(("WOLFM", "OLUFM", "OLUFC", "VER", "SYS")):
        return False
    if re.search(r"^[A-Za-z_][A-Za-z0-9_.-]{1,40}\s*=", text):
        return False
    if re.search(r"(?:license|copyright|font software|sil open font|all rights reserved)", text, re.I):
        return False
    letters = sum(1 for char in text if char.isalpha())
    if letters < 3 or letters / max(1, len(text)) < 0.45:
        return False
    if text.startswith(("{", "[", "<", "//", "/*")) and text.endswith(("}", "]", ">", "*/")):
        return False
    if re.fullmatch(r"[A-Za-z0-9_ .:+\-/\\]+", text) and (" " not in text or re.fullmatch(r"[A-Za-z0-9_.-]+", text)):
        return False
    return bool(re.search(r"[A-Za-z\u00c0-\u024f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", text))


def _looks_like_wolf_text(value: str) -> bool:
    """Reject binary-field noise before it reaches the Agent workbench.

    Wolf resources are records rather than line-oriented text files. Decoding
    the whole file as CP932 makes arbitrary record bytes look like half-width
    kana, so this predicate is intentionally stricter than the generic text
    predicate. It accepts real Latin/Japanese text and rejects resource paths,
    editor metadata, private-use glyphs and mojibake fragments.
    """
    text = str(value or "").replace("\x00", " ").strip()
    if not _looks_like_dialogue(text):
        return False
    if len(text) < 4 or len(text) > 1000:
        return False
    # Strip Wolf inline controls before checking path separators. Controls such
    # as ``\c[21]`` are part of a message; ordinary slash/backslash strings are
    # asset paths and never belong in the translation queue.
    without_controls = re.sub(r"\\[A-Za-z]+\[[^\]]*\]", "", text)
    if "/" in without_controls or "\\" in without_controls:
        return False
    if re.search(r"\.(?:png|jpg|jpeg|webp|ogg|wav|mps|dat|wolfx|ttf|otf)$", text, re.I):
        return False
    japanese = sum(1 for char in text if "\u3040" <= char <= "\u30ff" or "\u3400" <= char <= "\u9fff")
    halfwidth = sum(1 for char in text if "\uff61" <= char <= "\uff9f")
    # A CP932 decode of arbitrary bytes is dominated by half-width kana. Real
    # Japanese dialogue has kana/kanji around it, while English resources are
    # ASCII and should not contain any half-width kana at all.
    if halfwidth:
        # Half-width kana in these resources is almost always a CP932 decode
        # of command bytes; genuine dialogue uses full-width Japanese text.
        return False
    if not text.isascii() and (japanese < 3 or japanese / max(1, len(text)) < 0.25):
        return False
    if any(0x0370 <= ord(char) <= 0x052F for char in text):
        return False
    if text.isascii():
        letters = sum(1 for char in text if char.isalpha())
        if letters < 4:
            return False
        if re.search(r"[^A-Za-z0-9\s.,!?;:'\"()\[\]{}%+\-]", text):
            return False
        words = [word.lower() for word in re.findall(r"[A-Za-z]{2,}", text)]
        if " " in text and words and not any(word in ENGLISH_HINT_WORDS for word in words):
            return False
        if " " in text and not any(len(word) >= 3 for word in words):
            return False
        # Keep names/items such as Fireball, but never paths or short binary
        # fragments ("htavern", "fnds isb") produced by record boundaries.
        if " " not in text and len(text) < 6:
            return False
        if re.fullmatch(r"[A-Za-z0-9_.-]+", text) and len(text) < 6:
            return False
    return True


def _looks_like_wolf_dialogue_or_choice(value: str, command_name: str | None) -> bool:
    """Keep normal dialogue rules while accepting short player choices."""
    if _looks_like_wolf_text(value):
        return True
    text = str(value or "").strip()
    if command_name != "Choices" or not text or len(text) > 120 or PATH_LIKE.match(text):
        return False
    if any(ord(char) < 32 for char in text) or "\ufffd" in text:
        return False
    return bool(re.search(r"[A-Za-z\u00c0-\u024f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", text))


def _clean_wolf_text(value: str) -> str:
    """Remove command-byte residue without changing player-facing markup."""
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]+", " ", str(value or "")).strip()
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"([!?！？。])\.+$", r"\1", text)
    # In protected/newer MPS files a one-byte command argument can be adjacent
    # to a UTF-8 message.  A trailing digit/letter after CJK punctuation is
    # metadata, not dialogue.  Keep short names such as ``女仆1`` untouched.
    if len(text) >= 4 and re.search(r"[\u3040-\u30ff\u3400-\u9fff][0-9A-Za-z]$", text):
        if not re.search(r"(?:第|No\.?|v|V)\s*[0-9A-Za-z]+$", text):
            text = text[:-1].rstrip()
    elif len(text) >= 8 and re.search(r"[^\s]\d$", text) and not re.search(r"\s\d$", text):
        # Numeric command arguments are often appended to ASCII messages; a
        # spaced number ("Level 5") remains valid game text.
        text = text[:-1].rstrip()
    return text


def _decode_bytes(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp932", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


class _WolfParseError(ValueError):
    """Raised when a resource does not follow the unencrypted Wolf map format."""


class _WolfReader:
    """Small bounded reader for the public Wolf RPG Editor map format.

    This deliberately understands only enough of the format to locate message
    and choice command string fields.  Keeping the raw field offset and its
    four-byte length prefix means translated strings can be written back with
    an updated length, rather than a fragile byte-for-byte search.
    """

    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.offset = 0

    def _need(self, count: int) -> None:
        if count < 0 or self.offset + count > len(self.raw):
            raise _WolfParseError("unexpected end of Wolf resource")

    def expect(self, value: bytes) -> None:
        self._need(len(value))
        if self.raw[self.offset:self.offset + len(value)] != value:
            raise _WolfParseError("unexpected Wolf record marker")
        self.offset += len(value)

    def byte(self) -> int:
        self._need(1)
        value = self.raw[self.offset]
        self.offset += 1
        return value

    def uint32(self) -> int:
        self._need(4)
        value = struct.unpack_from("<I", self.raw, self.offset)[0]
        self.offset += 4
        return value

    def skip(self, count: int) -> None:
        self._need(count)
        self.offset += count

    def string(self) -> tuple[str, int, int, str]:
        length_offset = self.offset
        length = self.uint32()
        if length < 1 or length > 1_048_576:
            raise _WolfParseError(f"invalid Wolf string length: {length}")
        self._need(length)
        payload = self.raw[self.offset:self.offset + length - 1]
        if self.raw[self.offset + length - 1] != 0:
            raise _WolfParseError("Wolf string is missing a NUL terminator")
        self.offset += length
        # Actual Wolf game data is normally Shift-JIS; UTF-8 is used by some
        # community conversions.  Record the successful encoding so apply can
        # keep UTF-8 projects UTF-8 and emit GBK for Chinese Wolf projects.
        decoded: list[tuple[str, str]] = []
        for encoding in ("cp932", "utf-8", "gbk"):
            try:
                value = payload.decode(encoding)
            except UnicodeDecodeError:
                continue
            # CP932 can decode many GBK byte sequences as unrelated glyphs.
            # Prefer the first decode that passes the dialogue-quality gate,
            # which makes generated Chinese GBK maps re-open correctly.
            if _looks_like_wolf_text(value):
                return value, length_offset, length, encoding
            decoded.append((value, encoding))
        if decoded:
            value, encoding = decoded[0]
            return value, length_offset, length, encoding
        raise _WolfParseError("unsupported Wolf string encoding")


WOLF_MAP_JP_HEADER = bytes((
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x57, 0x4F, 0x4C, 0x46, 0x4D, 0,
    0, 0, 0, 0, 0x64, 0, 0, 0, 0x65, 0x05, 0, 0, 0, 0x82, 0xC8, 0x82,
    0xB5, 0,
))
WOLF_MAP_EN_HEADER = bytes((
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x57, 0x4F, 0x4C, 0x46, 0x4D, 0,
    0, 0, 0, 0, 0x64, 0, 0, 0, 0x65, 0x03, 0, 0, 0, 0x4E, 0x6F, 0,
))
WOLF_MESSAGE_COMMANDS = {101: "Message", 102: "Choices"}


def _skip_wolf_route(reader: _WolfReader) -> None:
    reader.byte()
    reader.skip(reader.byte() * 4)
    reader.expect(b"\x01\x00")


def _skip_wolf_move_tail(reader: _WolfReader) -> None:
    reader.skip(5)
    reader.byte()
    for _ in range(reader.uint32()):
        _skip_wolf_route(reader)


def _wolf_mps_message_fields(raw: bytes) -> list[dict[str, Any]]:
    """Return patchable Message/Choices string fields from one normal MPS.

    The layout follows the MPS command stream used by WolfTrans and
    rewolf-trans.  Protected/encrypted archives intentionally return no
    fields here: they must be unpacked first (for example with UberWolf).
    """
    reader = _WolfReader(raw)
    if raw.startswith(WOLF_MAP_JP_HEADER):
        reader.skip(len(WOLF_MAP_JP_HEADER))
    elif raw.startswith(WOLF_MAP_EN_HEADER):
        reader.skip(len(WOLF_MAP_EN_HEADER))
    else:
        # Wolf RPG Editor 3.x / MTool distributions use a different map
        # header (for example ``...WOLFM\0U``) but retain the normal event
        # record stream.  Locate and validate every full event record rather
        # than rejecting the whole map based on its version header.
        return _wolf_mps_message_fields_from_event_stream(raw)
    try:
        reader.uint32()  # tileset
        width = reader.uint32()
        height = reader.uint32()
        event_count = reader.uint32()
        if width > 10_000 or height > 10_000:
            raise _WolfParseError("unreasonable map dimensions")
        reader.skip(width * height * 12)
        fields: list[dict[str, Any]] = []
        events_seen = 0
        while True:
            marker = reader.byte()
            if marker == 0x66:  # event list terminator
                break
            if marker != 0x6F:
                raise _WolfParseError("invalid event marker")
            reader.expect(b"\x39\x30\x00\x00")
            event_id = reader.uint32()
            reader.string()  # event name: context only
            reader.skip(12)  # x, y, declared page count
            reader.expect(b"\x00\x00\x00\x00")
            page_index = 0
            while True:
                page_marker = reader.byte()
                if page_marker == 0x70:
                    break
                if page_marker != 0x79:
                    raise _WolfParseError("invalid page marker")
                reader.skip(4)
                reader.string()  # graphic filename
                reader.skip(4 + 37 + 4 + 2)
                for _ in range(reader.uint32()):
                    _skip_wolf_route(reader)
                command_count = reader.uint32()
                for command_index in range(command_count):
                    argument_count = reader.byte()
                    if argument_count < 1:
                        raise _WolfParseError("invalid command argument count")
                    command_id = reader.uint32()
                    reader.skip((argument_count - 1) * 4)
                    reader.byte()  # indentation
                    string_count = reader.byte()
                    command_name = WOLF_MESSAGE_COMMANDS.get(command_id)
                    for string_index in range(string_count):
                        source, offset, length, encoding = reader.string()
                        if command_name and _looks_like_wolf_dialogue_or_choice(source, command_name):
                            fields.append({
                                "source": source,
                                "offset": offset,
                                "length": length,
                                "encoding": encoding,
                                "context": f"event={event_id};page={page_index};command={command_index};kind={command_name};arg={string_index}",
                            })
                    terminator = reader.byte()
                    if terminator == 1:
                        _skip_wolf_move_tail(reader)
                    elif terminator != 0:
                        raise _WolfParseError("invalid command terminator")
                reader.expect(b"\x03\x00\x00\x00")
                reader.skip(3)
                if reader.byte() != 0x7A:
                    raise _WolfParseError("invalid page terminator")
                page_index += 1
            events_seen += 1
        if events_seen != event_count:
            raise _WolfParseError("event count mismatch")
        return fields
    except _WolfParseError:
        return []


def _wolf_mps_message_fields_from_event_stream(raw: bytes) -> list[dict[str, Any]]:
    """Parse MTool/Wolf 3.x maps whose tile/header layout is version-specific."""
    fields: list[dict[str, Any]] = []
    marker = b"\x6f\x39\x30\x00\x00"
    start = 0
    while True:
        event_offset = raw.find(marker, start)
        if event_offset < 0:
            break
        start = event_offset + 1
        reader = _WolfReader(raw)
        reader.offset = event_offset
        try:
            reader.byte()  # outer event marker: 0x6f
            reader.expect(b"\x39\x30\x00\x00")
            event_id = reader.uint32()
            reader.string()  # event name
            reader.skip(12)  # x, y, declared page count
            reader.expect(b"\x00\x00\x00\x00")
            page_index = 0
            while True:
                page_marker = reader.byte()
                if page_marker == 0x70:
                    break
                if page_marker != 0x79:
                    raise _WolfParseError("invalid page marker")
                reader.skip(4)
                reader.string()
                reader.skip(4 + 37 + 4 + 2)
                for _ in range(reader.uint32()):
                    _skip_wolf_route(reader)
                command_count = reader.uint32()
                if command_count > 100_000:
                    raise _WolfParseError("unreasonable command count")
                for command_index in range(command_count):
                    argument_count = reader.byte()
                    if argument_count < 1:
                        raise _WolfParseError("invalid command argument count")
                    command_id = reader.uint32()
                    reader.skip((argument_count - 1) * 4)
                    reader.byte()
                    string_count = reader.byte()
                    command_name = WOLF_MESSAGE_COMMANDS.get(command_id)
                    for string_index in range(string_count):
                        source, offset, length, encoding = reader.string()
                        if command_name and _looks_like_wolf_dialogue_or_choice(source, command_name):
                            fields.append({
                                "source": source,
                                "offset": offset,
                                "length": length,
                                "encoding": encoding,
                                "context": f"event={event_id};page={page_index};command={command_index};kind={command_name};arg={string_index}",
                            })
                    terminator = reader.byte()
                    if terminator == 1:
                        _skip_wolf_move_tail(reader)
                    elif terminator != 0:
                        raise _WolfParseError("invalid command terminator")
                reader.expect(b"\x03\x00\x00\x00")
                reader.skip(3)
                if reader.byte() != 0x7A:
                    raise _WolfParseError("invalid page terminator")
                page_index += 1
        except _WolfParseError:
            continue
    # A malformed resource can contain the same marker twice due to a binary
    # string argument.  Keep every exact field location only once.
    unique: dict[int, dict[str, Any]] = {}
    for field in fields:
        unique[int(field["offset"])] = field
    return [unique[offset] for offset in sorted(unique)]


def _wolf_common_event_message_fields(raw: bytes) -> list[dict[str, Any]]:
    """Extract patchable Message/Choices fields from CommonEvent.dat.

    Wolf 3.x and MTool builds vary the file header but preserve the common
    event record layout.  Event records begin with ``0x8e`` followed by their
    id, metadata and a normal Wolf command array, so each candidate is fully
    validated before it reaches the translation table.
    """
    fields: list[dict[str, Any]] = []
    start = 0
    while True:
        event_offset = raw.find(b"\x8e", start)
        if event_offset < 0:
            break
        start = event_offset + 1
        reader = _WolfReader(raw)
        reader.offset = event_offset
        try:
            reader.byte()
            event_id = reader.uint32()
            reader.skip(4 + 7)
            reader.string()  # common-event name
            command_count = reader.uint32()
            if command_count > 100_000:
                raise _WolfParseError("unreasonable common-event command count")
            for command_index in range(command_count):
                argument_count = reader.byte()
                if argument_count < 1:
                    raise _WolfParseError("invalid command argument count")
                command_id = reader.uint32()
                reader.skip((argument_count - 1) * 4)
                reader.byte()
                string_count = reader.byte()
                command_name = WOLF_MESSAGE_COMMANDS.get(command_id)
                for string_index in range(string_count):
                    source, offset, length, encoding = reader.string()
                    if command_name and _looks_like_wolf_dialogue_or_choice(source, command_name):
                        fields.append({
                            "source": source,
                            "offset": offset,
                            "length": length,
                            "encoding": encoding,
                            "context": f"common-event={event_id};command={command_index};kind={command_name};arg={string_index}",
                        })
                terminator = reader.byte()
                if terminator == 1:
                    _skip_wolf_move_tail(reader)
                elif terminator != 0:
                    raise _WolfParseError("invalid command terminator")
        except _WolfParseError:
            continue
    unique: dict[int, dict[str, Any]] = {}
    for field in fields:
        unique[int(field["offset"])] = field
    return [unique[offset] for offset in sorted(unique)]


WOLF_FIELD_CONTEXT = re.compile(
    r"(?:^|;)wolf-(?:mps|field);offset=(?P<offset>\d+);length=(?P<length>\d+);encoding=(?P<encoding>utf-8|cp932)(?:;|$)"
)


def _apply_wolf_mps_translations(path: Path, entries: list[TranslationEntry]) -> int:
    """Patch verified Wolf MPS string records in an isolated runtime copy.

    Replacements are processed from the end of the file, so a translated
    string may grow or shrink without invalidating offsets of earlier fields.
    Each field is checked against its original source text immediately before
    writing; stale translation packs therefore skip safely instead of touching
    a matching byte sequence in another command.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return 0
    replacements: list[tuple[int, int, bytes]] = []
    for entry in entries:
        match = WOLF_FIELD_CONTEXT.search(entry.context or "")
        if not match or not entry.source.strip() or not entry.target.strip() or entry.source == entry.target:
            continue
        offset = int(match.group("offset"))
        expected_length = int(match.group("length"))
        source_encoding = match.group("encoding")
        if offset < 0 or expected_length < 1 or offset + 4 + expected_length > len(raw):
            continue
        stored_length = struct.unpack_from("<I", raw, offset)[0]
        if stored_length != expected_length or raw[offset + 4 + stored_length - 1] != 0:
            continue
        try:
            source = raw[offset + 4:offset + 4 + stored_length - 1].decode(source_encoding)
        except UnicodeDecodeError:
            continue
        if source != entry.source:
            continue
        # WolfTrans/rewolf-trans write translated Shift-JIS projects using
        # GBK by default, while UTF-8 fan conversions stay UTF-8.  A desktop
        # user can override this for a locale-specific Wolf runtime.
        target_encoding = os.environ.get(
            "WOLF_RPG_WRITE_ENCODING",
            "utf-8" if source_encoding == "utf-8" else "gbk",
        )
        try:
            payload = entry.target.encode(target_encoding)
        except (LookupError, UnicodeEncodeError):
            continue
        replacement = struct.pack("<I", len(payload) + 1) + payload + b"\x00"
        replacements.append((offset, 4 + stored_length, replacement))
    if not replacements:
        return 0
    # One location can only have one entry, but guard against a malformed
    # imported translation pack before slicing the byte stream.
    applied_offsets: set[int] = set()
    for offset, old_size, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
        if offset in applied_offsets:
            continue
        raw = raw[:offset] + replacement + raw[offset + old_size:]
        applied_offsets.add(offset)
    try:
        path.write_bytes(raw)
    except OSError:
        return 0
    return len(applied_offsets)


def _apply_mtool_translation_map(runtime_root: Path, entries: list[TranslationEntry]) -> int:
    """Update MTool's source-to-target map in an isolated Wolf runtime copy."""
    updates = {
        entry.source: entry.target
        for entry in entries
        if entry.entry_id.startswith("mtool::") and entry.source.strip() and entry.target.strip()
        and entry.source != entry.target
    }
    if not updates:
        return 0
    path = runtime_root / "翻译文件.json"
    payload: dict[str, str] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                payload = {str(key): str(value) for key, value in loaded.items()}
        except (OSError, UnicodeDecodeError, ValueError, TypeError):
            return 0
    payload.update(updates)
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    except OSError:
        return 0
    return 1


class UnknownGameService:
    def __init__(self, project: ProjectInfo) -> None:
        # A caller may have imported a folder as the generic fallback before
        # the engine detector was updated. Re-detect from local file signals so
        # a Wolf package is never handled as a plain ``.txt`` project.
        detected = detect_engine(project.root)
        if project.engine in {"Generic Windows Game", "Unknown"} and detected not in {"Generic Windows Game", "Unknown"}:
            self.project = ProjectInfo(
                engine=detected,
                root=project.root,
                game_dir=project.game_dir,
                launcher_path=project.launcher_path,
                data_dir=project.data_dir,
                scripts_dir=project.scripts_dir,
            )
        else:
            self.project = project

    def inspect(self) -> dict[str, Any]:
        root = self.project.root
        files: list[dict[str, Any]] = []
        signals: list[str] = []
        total_bytes = 0
        file_count = 0
        for path in self._iter_files(limit=16000):
            file_count += 1
            try:
                size = path.stat().st_size
            except OSError:
                continue
            total_bytes += size
            rel = str(path.relative_to(root)).replace("\\", "/")
            lower = rel.lower()
            if path.name.lower() in {"unityplayer.dll", "gameassembly.dll"}:
                signals.append(f"Unity 运行时文件：{rel}")
            elif path.suffix.lower() in {".pak", ".utoc", ".ucas", ".locres"}:
                signals.append(f"Unreal/本地化资源：{rel}")
            elif path.name.lower() in {"project.godot", "resources.pck"}:
                signals.append(f"Godot 项目文件：{rel}")
            elif lower.endswith("resources/app.asar"):
                signals.append(f"Electron 包：{rel}")
            if self.project.engine == "Wolf RPG Editor" and path.suffix.lower() == ".mps":
                signals.append(f"Wolf event resource: {rel}")
            elif self.project.engine == "Wolf RPG Editor" and lower.endswith("wolfdatalock.json"):
                signals.append(f"Wolf data lock: {rel}")
            elif self.project.engine == "RPG Maker 2000/2003" and path.suffix.lower() in LEGACY_RPG_EXTENSIONS:
                signals.append(f"RPG Maker 2000/2003 binary resource: {rel}")
            if len(files) < 300:
                files.append({"path": rel, "size": size, "extension": path.suffix.lower()})
        return {
            "engine": self.project.engine,
            "root": str(root),
            "launcher": str(self.project.launcher_path) if self.project.launcher_path else "",
            "signals": list(dict.fromkeys(signals))[:80],
            "fileCount": file_count,
            "sampleFiles": files,
            "totalBytes": total_bytes,
            "readOnly": True,
            "capabilities": self.capabilities(),
            "tools": self.tool_manifest(),
        }

    def plan(self) -> dict[str, Any]:
        """Return a deterministic, confirmation-gated localization plan."""
        engine = self.project.engine
        if engine == "Wolf RPG Editor":
            return {
                "engine": engine,
                "confidence": 0.99,
                "extraction_plan": [
                    "仅扫描 Data/MapData/*.mps 的事件消息、角色名和选项",
                    "按 Wolf 二进制字段边界解码 UTF-8/CP932；丢弃 dump、存档、许可证和 Game.ini",
                    "保留文件相对路径与事件上下文，去重后输出候选文本",
                    "解析失败的加密/变体资源只记录为待人工确认，不把任意 .txt 当作游戏文本",
                ],
                "translation_scope": [
                    "地图事件 Message、Choices、角色名和确认为玩家可见的公共事件文本",
                    "不翻译路径、配置键值、字体许可证、说明文档和调试日志",
                ],
                "runtime_plan": [
                    "先生成 .rpgrtl_workspace 下的隔离副本",
                    "当前只对可安全重写的文本资源应用译文；原目录保持不变",
                    "Wolf 二进制回写需确认文件版本并通过副本启动验证后再启用",
                ],
                "risks": [
                    "该目录存在 wolfDataLock.json、.wolfx 和 .mps，文件信号属于 Wolf RPG Editor，不是 RPG Maker 2000/2003/XP/VX/Ace",
                    "MTool/加密或新版本 MPS 可能让通用解析器无法得到完整事件树，片段会标记为低置信度",
                    "未经确认不执行 Hook，也不修改原游戏目录",
                ],
                "required_tools": [
                    "内置只读扫描器",
                    "可选 wolfrpg-map-parser/WolfTrans 兼容解析器（仅用于隔离副本）",
                ],
            }
        if engine == "RPG Maker 2000/2003":
            return {
                "engine": engine,
                "confidence": 0.98,
                "extraction_plan": [
                    "扫描 RPG_RT.exe/RPG_RT.ini、*.ldb、*.lmt、*.lmu",
                    "优先从地图/公共事件二进制记录解码日文文本，按文件与偏移建立稳定 ID",
                    "过滤启动配置、资源路径和非文本字节，并保留原始编码信息",
                ],
                "translation_scope": ["地图事件消息、选项、角色/物品名称和公共事件文本"],
                "runtime_plan": ["写入 .rpgrtl_workspace 隔离副本；原目录只读；通过副本 RPG_RT.exe 启动"],
                "risks": ["LDB/LMU 可能使用压缩或自定义编码，解析失败项需人工确认"],
                "required_tools": ["内置二进制字符串扫描器", "可选 RPG Maker 2000/2003 数据解析器"],
            }
        if engine == "Visual Novel / Galgame":
            return {
                "engine": engine,
                "confidence": 0.86,
                "extraction_plan": [
                    "?? Kirikiri/KAG?XP3?.ks?.tjs??NScripter/ONScripter?nscript.dat?SAR??????????",
                    "???? GalTransl ??? name/message?pre_jp/post_jp JSON ????",
                    "???????????????????????????",
                ],
                "translation_scope": [
                    "GalTransl JSON ? message/pre_jp ??????? pre_zh?proofread_zh ? message_cn ????",
                    "???????????????????????????????",
                ],
                "runtime_plan": [
                    "?? .rpgrtl_workspace ????? GalTransl ?? JSON ??",
                    "???????? XP3/SAR/??????????????????????",
                ],
                "risks": [
                    "?? XP3/SAR ?????????????????????????",
                    "Shift-JIS ???????????????????????",
                ],
                "required_tools": ["?? GalTransl JSON ???", "?? KirikiriTools / VNTextPatch / Textractor ????"],
            }
        if engine == "Unreal Engine 4/5":
            return {
                "engine": engine,
                "confidence": 0.91,
                "extraction_plan": [
                    "?? Content/Localization ?? UE4/UE5 .archive ????",
                    "? Namespace/Subnamespaces/Children ?? Source/Translation ???",
                    "?? .locres?.pak?.utoc/.ucas ????????????????????????",
                ],
                "translation_scope": [
                    "?????? Translation ??????????",
                    "?? Namespace?Key?Path?Source ??????????????????",
                ],
                "runtime_plan": [
                    "? .rpgrtl_workspace ???????? .archive ????",
                    "UE4/UE5 ??????? Gather/Compile ???? .locres????????",
                ],
                "risks": [
                    "?????????? .locres ? PAK?????? UnrealPak/FModel/??????????",
                    "????????? PAK ??? cooked Asset/Blueprint ??",
                ],
                "required_tools": ["?? UE4/UE5 Archive ???", "?? UnrealPak/FModel ????"],
            }
        if engine == "Unity":
            return {
                "engine": engine,
                "confidence": 0.91,
                "extraction_plan": [
                    "?? *_Data/StreamingAssets?Resources ? Localization/StringTable/Polyglot ?",
                    "???? Unity Localization ? English/zh-Hans ??Polyglot BEGIN?END ???? JSON ??",
                    "??????????????????????????????",
                ],
                "translation_scope": [
                    "????????????????????",
                    "?? Key?????????????????? AssetBundle?????????",
                ],
                "runtime_plan": [
                    "? .rpgrtl_workspace ???????? zh-Hans / Simplified_Chinese ?????",
                    "???????????????????",
                ],
                "risks": [
                    "???? CSV/TSV/JSON ? Addressables ? AssetBundle ??????????????",
                    "?????????????????????? Unity ??????????",
                ],
                "required_tools": ["?? Unity Localization / Polyglot ????", "?? AssetRipper/AssetStudio ????"],
            }
        return {
            "engine": engine,
            "confidence": 0.65 if engine != "Unknown" else 0.35,
            "extraction_plan": ["按已识别资源格式扫描文本字段和二进制字符串", "过滤路径、许可证、配置和日志，再按文件去重"],
            "translation_scope": ["只处理确认属于玩家可见文本的资源字段"],
            "runtime_plan": ["仅在 .rpgrtl_workspace 生成隔离副本，原目录不写入；确认后才启动副本"],
            "risks": ["未知格式可能出现误检或漏检，需提供资源格式/引擎版本后再扩展解析器"],
            "required_tools": ["内置只读扫描器", "按引擎选择的专用资源解析器"],
        }

    @staticmethod
    def tool_manifest() -> list[dict[str, Any]]:
        """MCP-style, read-only tools exposed to an AI planner."""
        return [
            {"name": "inspect_engine", "description": "读取引擎文件信号和启动文件", "readOnly": True, "inputSchema": {"type": "object"}},
            {"name": "extract_text", "description": "从文本资源和可读字符串提取候选对话", "readOnly": True, "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
            {"name": "list_resources", "description": "列出 Unity/Unreal/Godot/Electron 资源文件", "readOnly": True, "inputSchema": {"type": "object"}},
            {"name": "build_isolated_runtime", "description": "在 .rpgrtl_workspace 生成可删除的运行副本", "readOnly": False, "requiresConfirmation": True, "inputSchema": {"type": "object", "properties": {"versionId": {"type": "string"}}}},
        ]

    def capabilities(self) -> dict[str, Any]:
        engine = self.project.engine
        candidates = [
            "AssetRipper", "AssetStudio", "UnrealPak", "FModel", "u4pak", "asar", "7z",
            "wolftrans", "wolfrpg-map-parser",
        ]
        installed = [name for name in candidates if shutil.which(name) or shutil.which(name.lower())]
        return {
            "staticExtraction": True,
            "isolatedRuntimeCopy": True,
            "liveHook": False,
            "recommendedTools": {
                "Unity": ["AssetRipper/AssetStudio", "BepInEx 或 Harmony（仅隔离副本）"],
                "Unreal Engine 4/5": ["UnrealPak", "locres 导出器", "FModel（只读分析）"],
                "Godot": ["PCK 解包器", "文本资源扫描"],
                "Electron/Web": ["asar 解包器", "开发者工具文本扫描"],
                "Wolf RPG Editor": ["wolfrpg-map-parser/WolfTrans（只读解析）", "CP932/UTF-8 字段扫描"],
                "RPG Maker 2000/2003": ["LDB/LMU 二进制解析器", "CP932 字符串扫描"],
            }.get(engine, ["strings/资源扫描", "按需配置进程 Hook 适配器"]),
            "installedTools": installed,
        }

    def extract_translations(self, limit: int = 30000, progress_callback: Any = None) -> list[TranslationEntry]:
        """Extract candidate dialogue without blocking the UI caller.

        ``progress_callback`` receives small operational snapshots.  It is
        deliberately a callback rather than a generator so existing API
        callers remain compatible while the Agent endpoint can run this work
        on a background thread.
        """
        entries: list[TranslationEntry] = []
        seen: set[tuple[str, str]] = set()
        # MTool exports decrypted Wolf resources as structured JSON beside the
        # game.  Protected ``WOLUFM/WOLUFC`` binaries cannot be safely parsed
        # or rewritten in place, while these dumps preserve every command and
        # MTool loads 翻译文件.json at runtime. Prefer this complete, native
        # translation path when the export is available.
        if self.project.engine == "Wolf RPG Editor":
            mtool_entries = self._extract_mtool_dump_translations(limit=limit)
            if mtool_entries:
                return mtool_entries
        paths = list(self._iter_files(limit=16000))
        if self.project.engine == "Wolf RPG Editor":
            # Put player-facing map/event resources ahead of CommonEvent.dat,
            # which also contains thousands of editor/system labels. This makes
            # the first page of candidates immediately useful to the Agent.
            def wolf_priority(path: Path) -> tuple[int, str]:
                rel = str(path.relative_to(self.project.root)).replace("\\", "/").lower()
                if path.suffix.lower() == ".mps":
                    return (0, rel)
                if rel.endswith("/cdatabase.dat") or rel.endswith("/database.dat"):
                    return (1, rel)
                if rel.endswith("/commonevent.dat"):
                    return (3, rel)
                return (2, rel)
            paths.sort(key=wolf_priority)
        unity_handled_files: set[str] = set()
        if self.project.engine == "Unity":
            # Unity Localization and Polyglot use keyed language tables. Parse
            # them before the generic scanner so only English source cells enter
            # the workbench and every candidate keeps a Chinese target location.
            max_entries = max(1, min(int(limit or 30000), 30000))
            for path in paths:
                rel = str(path.relative_to(self.project.root)).replace("\\", "/")
                if not _is_unity_localization_name(path):
                    continue
                try:
                    raw = path.read_bytes()
                except OSError:
                    continue
                table_entries, handled = _unity_localization_entries(path, raw, rel, max_entries - len(entries))
                if handled:
                    unity_handled_files.add(rel)
                for entry in table_entries:
                    if (entry.file, entry.source) in seen:
                        continue
                    seen.add((entry.file, entry.source))
                    entries.append(entry)
                    if len(entries) >= max_entries:
                        return entries
        unreal_handled_files: set[str] = set()
        if self.project.engine == "Unreal Engine 4/5":
            # UE4 and UE5 editor localization archives share the same JSON
            # hierarchy. Treat them as structured target fields, not raw text.
            max_entries = max(1, min(int(limit or 30000), 30000))
            for path in paths:
                rel = str(path.relative_to(self.project.root)).replace("\\", "/")
                if not _is_unreal_localization_name(path):
                    continue
                try:
                    raw = path.read_bytes()
                except OSError:
                    continue
                archive_entries, handled = _unreal_archive_entries(path, raw, rel, max_entries - len(entries))
                if handled:
                    unreal_handled_files.add(rel)
                for entry in archive_entries:
                    if (entry.file, entry.source) in seen:
                        continue
                    seen.add((entry.file, entry.source))
                    entries.append(entry)
                    if len(entries) >= max_entries:
                        return entries
        galtransl_handled_files: set[str] = set()
        if self.project.engine == "Visual Novel / Galgame":
            # Preserve the GalTransl name-message structure so the AI can use
            # dialogue records and write a compatible json_cn style result.
            max_entries = max(1, min(int(limit or 30000), 30000))
            for path in paths:
                if path.suffix.lower() != ".json":
                    continue
                rel = str(path.relative_to(self.project.root)).replace("\\", "/")
                try:
                    raw = path.read_bytes()
                except OSError:
                    continue
                json_entries, handled = _galtransl_entries(path, raw, rel, max_entries - len(entries))
                if handled:
                    galtransl_handled_files.add(rel)
                for entry in json_entries:
                    if (entry.file, entry.source) in seen:
                        continue
                    seen.add((entry.file, entry.source))
                    entries.append(entry)
                    if len(entries) >= max_entries:
                        return entries
        total_paths = len(paths)
        last_report = 0.0
        def report(processed: int, phase: str, current: str = "") -> None:
            nonlocal last_report
            now = time.monotonic()
            if phase != "完成" and processed < total_paths and processed not in {0, total_paths} and now - last_report < 0.08:
                return
            last_report = now
            if callable(progress_callback):
                try:
                    progress_callback({
                        "phase": phase,
                        "processedFiles": processed,
                        "totalFiles": total_paths,
                        "entryCount": len(entries),
                        "currentFile": current,
                    })
                except Exception:
                    pass
        report(0, "扫描文件")
        for processed, path in enumerate(paths, 1):
            suffix = path.suffix.lower()
            rel = str(path.relative_to(self.project.root)).replace("\\", "/")
            if rel in unity_handled_files or rel in unreal_handled_files or rel in galtransl_handled_files:
                continue
            report(processed, "解码资源", rel)
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if not self._is_candidate_resource(path, suffix):
                continue
            if size > (16 * 1024 * 1024 if suffix in TEXT_EXTENSIONS else 8 * 1024 * 1024):
                continue
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            # Standard, unencrypted Wolf maps have an explicit event-command
            # structure.  Prefer it over a byte-string scan: every result gets
            # a stable location and can be translated in the PC runtime copy.
            if self.project.engine == "Wolf RPG Editor" and (suffix == ".mps" or path.name.lower() == "commonevent.dat"):
                fields = (
                    _wolf_mps_message_fields(raw)
                    if suffix == ".mps"
                    else _wolf_common_event_message_fields(raw)
                )
                for field in fields:
                    source = str(field["source"])
                    offset = int(field["offset"])
                    if (rel, str(offset)) in seen:
                        continue
                    seen.add((rel, str(offset)))
                    digest = hashlib.sha1(f"{rel}:{offset}:{source}".encode("utf-8")).hexdigest()[:12]
                    context = (
                        f"wolf-field;offset={offset};length={int(field['length'])};"
                        f"encoding={field['encoding']};{field['context']}"
                    )
                    entries.append(TranslationEntry(
                        entry_id=f"wolf::{rel}::{offset}::{digest}",
                        source=source,
                        file=rel,
                        context=context,
                        category="wolf_dialogue",
                    ))
                    if len(entries) >= max(1, min(int(limit or 30000), 30000)):
                        report(processed, "完成", rel)
                        return entries
                # Do not add raw string-scan fragments for a valid MPS.  When
                # parsing fails, the fallback below remains read-only and is
                # deliberately not eligible for binary write-back.
                if fields:
                    continue
            if suffix in TEXT_EXTENSIONS:
                text = _decode_bytes(raw)
            elif self.project.engine == "Wolf RPG Editor":
                # Wolf's .mps/.dat resources are structured binary records;
                # never treat arbitrary root .txt files as game dialogue.
                text = self._wolf_binary_strings(raw)
            else:
                text = self._binary_strings(raw)
            for line_no, line in enumerate(text.splitlines(), 1):
                candidates = [line.strip()]
                # JSON/JS/resource files often keep one or more values on a line.
                candidates.extend(match.group(1).strip() for match in re.finditer(r"[\"']((?:\\.|[^\"']){2,1000})[\"']", line))
                for source in candidates:
                    if "\\" in source:
                        source = source.replace('\\"', '"').replace('\\n', "\n").replace('\\r', "\r").replace('\\t', "\t").replace('\\\\', "\\")
                    is_dialogue = _looks_like_wolf_text(source) if self.project.engine == "Wolf RPG Editor" and suffix in BINARY_EXTENSIONS else _looks_like_dialogue(source)
                    if not is_dialogue or (rel, source) in seen:
                        continue
                    seen.add((rel, source))
                    digest = hashlib.sha1(f"{rel}:{line_no}:{source}".encode("utf-8")).hexdigest()[:12]
                    entries.append(TranslationEntry(
                        entry_id=f"unknown::{rel}::{line_no}::{digest}",
                        source=source,
                        file=rel,
                        context=f"第 {line_no} 行",
                        category="galgame_dialogue" if self.project.engine == "Visual Novel / Galgame" else "unknown",
                    ))
                    if len(entries) >= max(1, min(int(limit or 30000), 30000)):
                        report(processed, "完成", rel)
                        return entries
        report(total_paths, "完成")
        return entries

    def _is_candidate_resource(self, path: Path, suffix: str) -> bool:
        rel_parts = [part.lower() for part in path.relative_to(self.project.root).parts]
        name = path.name.lower()
        if name in EXCLUDED_TEXT_NAMES or any(part in EXCLUDED_TEXT_DIRS for part in rel_parts[:-1]):
            return False
        if self.project.engine == "Wolf RPG Editor":
            # Wolf stores player-facing messages in map/event binaries and in
            # selected runtime databases. Editor metadata, Game.ini, licenses
            # and promotion/readme text are not game dialogue.
            rel = "/".join(rel_parts)
            if suffix == ".mps":
                return True
            if rel.startswith("data/basicdata/") and name in {"commonevent.dat", "database.dat", "cdatabase.dat", "sysdatabase.dat"}:
                return True
            return False
        return suffix in TEXT_EXTENSIONS or suffix in BINARY_EXTENSIONS

    @staticmethod
    def _wolf_binary_strings(raw: bytes) -> str:
        """Extract candidate strings from Wolf record boundaries.

        Wolf 2.x/3.x files place text between command bytes and length fields;
        the older ``strings``-style scan decodes those bytes as CP932 and
        produces thousands of false half-width-kana fragments. Splitting on
        command/control bytes, then validating each UTF-8/CP932 segment, keeps
        the actual game messages while dropping editor metadata and asset paths.
        """
        chunks: list[str] = []
        seen: set[str] = set()

        def add(value: str) -> None:
            cleaned = _clean_wolf_text(value)
            if cleaned not in seen and _looks_like_wolf_text(cleaned):
                seen.add(cleaned)
                chunks.append(cleaned)

        # Most Wolf text fields use a little-endian byte length followed by a
        # Shift-JIS/UTF-8 string and a NUL terminator. Prefer those records: a
        # complete field preserves the sentence and avoids command-byte noise.
        # The bounded scan is useful for small map resources.  Running it on
        # multi-megabyte CommonEvent/DataBase blobs makes extraction quadratic
        # in Python and was the main cause of the long "unknown game" wait.
        if len(raw) <= 1024 * 1024:
            for offset in range(0, max(0, len(raw) - 8)):
                length = struct.unpack_from("<I", raw, offset)[0]
                if length < 2 or length > 8192:
                    continue
                end = offset + 4 + length
                if end > len(raw) or raw[end - 1] != 0:
                    continue
                payload = raw[offset + 4:end - 1]
                for encoding in ("utf-8", "cp932"):
                    try:
                        value = payload.decode(encoding).strip()
                    except (LookupError, UnicodeDecodeError):
                        continue
                    before = len(chunks)
                    add(value)
                    if len(chunks) > before:
                        break

        # UTF-8 messages may be separated from command bytes by values above
        # 0x1f, so also scan NUL-delimited fields and valid CJK runs.  The
        # quality gate below prevents arbitrary licence/path fragments from
        # entering the queue.
        segments = WOLF_BINARY_SEPARATOR.split(raw)
        for segment in segments:
            if len(segment) < 3:
                continue
            for encoding in ("utf-8", "cp932"):
                try:
                    value = segment.decode(encoding).strip()
                except (LookupError, UnicodeDecodeError):
                    continue
                before = len(chunks)
                add(value)
                if len(chunks) > before:
                    break

        return "\n".join(dict.fromkeys(chunks))

    @staticmethod
    def _binary_strings(raw: bytes) -> str:
        chunks: list[str] = []
        for encoding in ("cp932", "utf-8", "utf-16le"):
            try:
                decoded = raw.decode(encoding, errors="ignore")
            except (LookupError, UnicodeError):
                continue
            for match in PRINTABLE.finditer(decoded):
                value = re.sub(r"[\x00-\x1f\x7f-\x9f]+", " ", match.group(0)).strip()
                if value:
                    chunks.append(value)
        # Keep the order from the first encoding and remove duplicates. The
        # CP932 pass is important for Japanese Wolf RPG resources.
        return "\n".join(dict.fromkeys(chunks))

    def list_data_records(self) -> list[DataRecord]:
        return []

    def _extract_mtool_dump_translations(self, limit: int = 30000) -> list[TranslationEntry]:
        dump_root = self.project.root / "dump"
        if not dump_root.is_dir():
            return []
        entries: list[TranslationEntry] = []
        seen: set[tuple[str, str, int]] = set()
        # MTool writes map events to dump/mps and common events to dump/common.
        # Only message / choice arguments are included: comments, command
        # names and database metadata remain outside the normal AI queue.
        for folder in ("mps", "common"):
            directory = dump_root / folder
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json"), key=lambda item: item.name.lower()):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8-sig"))
                except (OSError, UnicodeDecodeError, ValueError):
                    continue
                rel = str(path.relative_to(self.project.root)).replace("\\", "/")
                command_sets: list[tuple[str, list[Any]]] = []
                if folder == "mps" and isinstance(payload, dict):
                    for event in payload.get("events") or []:
                        if not isinstance(event, dict):
                            continue
                        event_id = event.get("id", "?")
                        for page in event.get("pages") or []:
                            if isinstance(page, dict) and isinstance(page.get("list"), list):
                                command_sets.append((f"event={event_id};page={page.get('id', '?')}", page["list"]))
                elif folder == "common" and isinstance(payload, dict) and isinstance(payload.get("commands"), list):
                    command_sets.append((f"common-event={payload.get('id', '?')}", payload["commands"]))
                for prefix, commands in command_sets:
                    for command_pos, command in enumerate(commands):
                        if not isinstance(command, dict) or int(command.get("code") or -1) not in WOLF_MESSAGE_COMMANDS:
                            continue
                        arguments = command.get("stringArgs")
                        if not isinstance(arguments, list):
                            continue
                        command_index = command.get("index", command_pos)
                        kind = WOLF_MESSAGE_COMMANDS[int(command["code"])]
                        for argument_index, value in enumerate(arguments):
                            source = str(value or "")
                            if not _looks_like_wolf_dialogue_or_choice(source, kind):
                                continue
                            marker = (rel, f"{prefix};command={command_index};arg={argument_index}", hash(source))
                            if marker in seen:
                                continue
                            seen.add(marker)
                            digest = hashlib.sha1(f"{rel}:{marker[1]}:{source}".encode("utf-8")).hexdigest()[:12]
                            entries.append(TranslationEntry(
                                entry_id=f"mtool::{rel}::{command_index}:{argument_index}::{digest}",
                                source=source,
                                file=rel,
                                context=f"mtool-dump;{prefix};command={command_index};kind={kind};arg={argument_index}",
                                category="wolf_dialogue",
                            ))
                            if len(entries) >= max(1, min(int(limit or 30000), 30000)):
                                return entries
        return entries

    def build_runtime_copy(self, translations: dict[str, TranslationEntry], version_id: str = "current") -> tuple[Path, Path | None, int]:
        workspace = self.project.root / ".rpgrtl_workspace"
        safe_version = re.sub(r"[^A-Za-z0-9._-]+", "_", str(version_id or "current"))[:80] or "current"
        runtime_root = workspace / "unknown_runtime_game" / safe_version
        staging = runtime_root.with_name(runtime_root.name + ".building")
        if staging.exists():
            shutil.rmtree(staging)
        workspace.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.project.root, staging, ignore=shutil.ignore_patterns(*IGNORED_DIRS))
        if runtime_root.exists():
            shutil.rmtree(runtime_root)
        staging.rename(runtime_root)
        changed = 0
        changed += _apply_mtool_translation_map(runtime_root, list(translations.values()))
        by_file: dict[str, list[TranslationEntry]] = {}
        for entry in translations.values():
            if entry.entry_id.startswith("mtool::"):
                continue
            if entry.source.strip() and entry.target.strip() and entry.source != entry.target:
                by_file.setdefault(entry.file.replace("/", os.sep), []).append(entry)
        for rel, items in by_file.items():
            target_file = runtime_root / rel
            if not target_file.is_file():
                continue
            if self.project.engine == "Unity" and all(str(item.context).startswith(("unity-table;", "unity-json;")) for item in items):
                changed += _apply_unity_localization_entries(target_file, items)
                continue
            if self.project.engine == "Unreal Engine 4/5" and all(str(item.context).startswith("unreal-archive;") for item in items):
                changed += _apply_unreal_archive_entries(target_file, items)
                continue
            if self.project.engine == "Visual Novel / Galgame" and all(str(item.context).startswith("galtransl-json;") for item in items):
                changed += _apply_galtransl_entries(target_file, items)
                continue
            if self.project.engine == "Wolf RPG Editor" and (target_file.suffix.lower() == ".mps" or target_file.name.lower() == "commonevent.dat"):
                changed += int(bool(_apply_wolf_mps_translations(target_file, items)))
                continue
            if target_file.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            try:
                content = _decode_bytes(target_file.read_bytes())
                original = content
                for entry in items:
                    content = content.replace(entry.source, entry.target)
                if content != original:
                    target_file.write_text(content, encoding="utf-8", newline="")
                    changed += 1
            except (OSError, UnicodeError):
                continue
        launcher = None
        if self.project.launcher_path:
            try:
                candidate = runtime_root / self.project.launcher_path.relative_to(self.project.root)
                launcher = candidate if candidate.is_file() else None
            except ValueError:
                launcher = None
        launcher = launcher or find_launcher(runtime_root)
        manifest = runtime_root / ".rpgrtl_agent_runtime.json"
        manifest.write_text(json.dumps({"engine": self.project.engine, "sourceRoot": str(self.project.root), "changedFiles": changed, "reversible": True}, ensure_ascii=False, indent=2), encoding="utf-8")
        return runtime_root, launcher, changed

    def agent_prompt(self, sample_entries: list[TranslationEntry] | None = None) -> str:
        samples = sample_entries or self.extract_translations()[:20]
        sample_text = "\n".join(f"- {item.file}: {item.source}" for item in samples[:20]) or "（暂未提取到文本）"
        return (
            "你是游戏本地化工程 Agent。只允许分析隔离副本，不得修改原游戏目录。\n"
            f"引擎：{self.project.engine}\n根目录：{self.project.root}\n"
            "请根据文件信号、资源格式和样本文本，输出 JSON："
            "{engine,confidence,extraction_plan,translation_scope,runtime_plan,risks,required_tools}。\n"
            "优先给出可回滚的静态资源方案；只有用户明确确认后才建议隔离副本 Hook。\n"
            f"样本文本：\n{sample_text}"
        )

    def _iter_files(self, limit: int = 16000):
        count = 0
        ignored = set(IGNORED_DIRS)
        if self.project.engine == "Wolf RPG Editor":
            # Translation tools often leave a huge ``dump`` tree beside a Wolf
            # game. It is not runtime data and used to consume the scan budget
            # before Data/MapData/*.mps was reached.
            ignored.update({"dump", "save", "savedata", "saves", "backup"})
        for current, dirnames, filenames in os.walk(self.project.root):
            dirnames[:] = [name for name in dirnames if name.lower() not in ignored]
            if self.project.engine == "Wolf RPG Editor":
                rel_dir = Path(current).relative_to(self.project.root).parts
                if len(rel_dir) == 1 and rel_dir[0].lower() == "data":
                    # Runtime messages live in Data/BasicData and map events;
                    # images/audio/cache folders can contain tens of thousands
                    # of files and must not starve the candidate scan budget.
                    dirnames[:] = [name for name in dirnames if name.lower() in {"basicdata", "mapdata"}]
            for filename in filenames:
                yield Path(current) / filename
                count += 1
                if count >= limit:
                    return
