from __future__ import annotations

"""Read-only inspection and isolated runtime support for unknown game engines.

This module deliberately does not patch an imported game in place.  It provides
small, deterministic adapters that an AI planner can reason about: file
signals, candidate text extraction, and an isolated copy where exact string
replacements can be tested and removed without touching the source tree.
"""

import hashlib
import json
import os
import re
import shutil
import struct
from pathlib import Path
from typing import Any

from .detectors import detect_engine, find_launcher
from .models import DataRecord, ProjectInfo, TranslationEntry


TEXT_EXTENSIONS = {
    ".json", ".json5", ".js", ".mjs", ".cjs", ".ts", ".txt", ".csv", ".tsv",
    ".xml", ".html", ".htm", ".po", ".pot", ".ini", ".cfg", ".yaml", ".yml",
    ".rpy", ".asset", ".translation", ".resx", ".strings",
}
BINARY_EXTENSIONS = {".assets", ".bundle", ".resource", ".bytes", ".bin", ".pak", ".pck", ".locres", ".dat", ".mps"}
IGNORED_DIRS = {".git", ".rpgrtl_workspace", ".rpgrtl_backup", "node_modules", "__pycache__"}
PATH_LIKE = re.compile(r"^(?:[a-z]:[\\/]|https?://|file://|[./\\]|[A-Za-z0-9_ -]+\.(?:dll|exe|png|jpg|json|js|css|ttf|otf))", re.I)
PRINTABLE = re.compile(r"[\x20-\x7e\u00a0-\uffff]{3,}")
WOLF_BINARY_SEPARATOR = re.compile(rb"[\x00-\x1f\x7f]+")
EXCLUDED_TEXT_NAMES = {"game.ini", "license.txt", "license_ofl.txt", "readme.txt", "readme.md", "notice.txt", "changelog.txt", "others.txt"}
EXCLUDED_TEXT_DIRS = {"license", "licenses", "readme", "docs", "documentation", "manual"}
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


def _decode_bytes(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp932", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


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
        candidates = ["AssetRipper", "AssetStudio", "UnrealPak", "FModel", "u4pak", "asar", "7z"]
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
            }.get(engine, ["strings/资源扫描", "按需配置进程 Hook 适配器"]),
            "installedTools": installed,
        }

    def extract_translations(self) -> list[TranslationEntry]:
        entries: list[TranslationEntry] = []
        seen: set[tuple[str, str]] = set()
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
        for path in paths:
            suffix = path.suffix.lower()
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
            if suffix in TEXT_EXTENSIONS:
                text = _decode_bytes(raw)
            elif self.project.engine == "Wolf RPG Editor":
                # Wolf's .mps/.dat resources are structured binary records;
                # never treat arbitrary root .txt files as game dialogue.
                text = self._wolf_binary_strings(raw)
            else:
                text = self._binary_strings(raw)
            rel = str(path.relative_to(self.project.root)).replace("\\", "/")
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
                        category="unknown",
                    ))
                    if len(entries) >= 30000:
                        return entries
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
        # Most Wolf text fields use a little-endian byte length followed by a
        # Shift-JIS/UTF-8 string and a NUL terminator. Prefer those records: a
        # complete field preserves the sentence and avoids command-byte noise.
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
                value = re.sub(r"[\x00-\x1f\x7f-\x9f]+", " ", value).strip()
                if _looks_like_wolf_text(value):
                    chunks.append(value)
                    break
        for segment in WOLF_BINARY_SEPARATOR.split(raw):
            if len(segment) < 3:
                continue
            for encoding in ("utf-8", "cp932"):
                try:
                    value = segment.decode(encoding).strip()
                except (LookupError, UnicodeDecodeError):
                    continue
                value = re.sub(r"[\x00-\x1f\x7f-\x9f]+", " ", value).strip()
                if _looks_like_wolf_text(value):
                    chunks.append(value)
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
        by_file: dict[str, list[TranslationEntry]] = {}
        for entry in translations.values():
            if entry.source.strip() and entry.target.strip() and entry.source != entry.target:
                by_file.setdefault(entry.file.replace("/", os.sep), []).append(entry)
        for rel, items in by_file.items():
            target_file = runtime_root / rel
            if not target_file.is_file() or target_file.suffix.lower() not in TEXT_EXTENSIONS:
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
