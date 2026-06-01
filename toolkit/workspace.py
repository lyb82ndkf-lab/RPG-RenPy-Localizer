from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class LibraryEntry:
    name: str
    path: str
    engine: str
    added_at: str
    last_opened_at: str = ""
    launcher_path: str = ""
    note: str = ""
    tags: list[str] | None = None


@dataclass(slots=True)
class RecentTask:
    title: str
    project_path: str
    action: str
    created_at: str


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.config_dir = self._user_config_dir()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.library_path = self.config_dir / "library.json"
        self.settings_path = self.config_dir / "settings.json"
        self.recent_tasks_path = self.config_dir / "recent_tasks.json"
        self.translation_memory_path = self.config_dir / "translation_memory.json"

    @staticmethod
    def _user_config_dir() -> Path:
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "RPGRenPyLocalizer"
        return Path.home() / "AppData" / "Roaming" / "RPGRenPyLocalizer"

    def load_library(self) -> list[LibraryEntry]:
        payload = self._read_json(self.library_path, default={"games": []})
        return [LibraryEntry(**item) for item in payload.get("games", [])]

    def save_library(self, entries: list[LibraryEntry]) -> None:
        payload = {"games": [asdict(entry) for entry in entries]}
        self._write_json(self.library_path, payload)

    def load_recent_tasks(self) -> list[RecentTask]:
        payload = self._read_json(self.recent_tasks_path, default={"tasks": []})
        return [RecentTask(**item) for item in payload.get("tasks", [])]

    def save_recent_tasks(self, tasks: list[RecentTask]) -> None:
        payload = {"tasks": [asdict(task) for task in tasks[:30]]}
        self._write_json(self.recent_tasks_path, payload)

    def load_settings(self) -> dict[str, Any]:
        return self._read_json(self.settings_path, default={})

    def save_settings(self, settings: dict[str, Any]) -> None:
        self._write_json(self.settings_path, settings)

    def load_translation_memory(self) -> dict[str, str]:
        payload = self._read_json(self.translation_memory_path, default={"translations": {}})
        translations = payload.get("translations", {}) if isinstance(payload, dict) else {}
        if not isinstance(translations, dict):
            return {}
        return {str(source): str(target) for source, target in translations.items() if str(source).strip() and str(target).strip()}

    def save_translation_memory(self, translations: dict[str, str]) -> None:
        clean = {str(source).strip(): str(target).strip() for source, target in translations.items() if str(source).strip() and str(target).strip()}
        self._write_json(self.translation_memory_path, {"translations": clean})

    # ── 项目级缓存隔离 ──────────────────────────────────────────

    @staticmethod
    def _project_tm_path(config_dir: Path, project_root: Path) -> Path:
        """按项目根路径哈希生成独立缓存文件名。"""
        hash_id = hashlib.md5(str(project_root.resolve()).encode()).hexdigest()[:12]
        return config_dir / f"tm_project_{hash_id}.json"

    def load_project_translation_memory(self, project_root: Path | None) -> dict[str, str]:
        if not project_root:
            return {}
        path = self._project_tm_path(self.config_dir, project_root)
        if not path.exists():
            return {}
        payload = self._read_json(path, default={"translations": {}})
        translations = payload.get("translations", {}) if isinstance(payload, dict) else {}
        if not isinstance(translations, dict):
            return {}
        return {str(source): str(target) for source, target in translations.items() if str(source).strip() and str(target).strip()}

    def save_project_translation_memory(self, project_root: Path | None, translations: dict[str, str]) -> None:
        if not project_root:
            return
        path = self._project_tm_path(self.config_dir, project_root)
        clean = {str(source).strip(): str(target).strip() for source, target in translations.items() if str(source).strip() and str(target).strip()}
        self._write_json(path, {"translations": clean})

    def delete_project_translation_memory(self, project_root: Path | None) -> None:
        if not project_root:
            return
        path = self._project_tm_path(self.config_dir, project_root)
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
