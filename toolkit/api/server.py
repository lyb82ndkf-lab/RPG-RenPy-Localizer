from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import ctypes
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
from dataclasses import asdict, is_dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from toolkit.detectors import detect_project, find_launcher
from toolkit.models import DataRecord, ProjectInfo, TranslationEntry
from toolkit.renpy import RenPyService
from toolkit.rpgmaker import RPGMakerService, load_json
from toolkit.storage import export_translation_pack, import_translation_pack, save_json, translation_pack_signature
from toolkit.workspace import LibraryEntry, Workspace

JsonDict = dict[str, Any]


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    return value


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _entry_from_raw(raw: JsonDict, fallback: TranslationEntry | None = None) -> TranslationEntry:
    return TranslationEntry(
        entry_id=str(raw.get("entry_id") or raw.get("id") or (fallback.entry_id if fallback else "")),
        source=str(raw.get("source") if raw.get("source") is not None else (fallback.source if fallback else "")),
        target=str(raw.get("target") if raw.get("target") is not None else (fallback.target if fallback else "")),
        file=str(raw.get("file") if raw.get("file") is not None else (fallback.file if fallback else "")),
        context=str(raw.get("context") if raw.get("context") is not None else (fallback.context if fallback else "")),
        category=str(raw.get("category") if raw.get("category") is not None else (fallback.category if fallback else "")),
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class ToolkitApi:
    def __init__(self, project_root: Path, config_dir: Path | None = None) -> None:
        self.project_root = project_root
        self.workspace = Workspace(project_root, config_dir=config_dir)
        self.project: ProjectInfo | None = None
        self.translation_entries: list[TranslationEntry] = []
        self.data_records: list[DataRecord] = []
        self.save_payload: JsonDict | None = None
        self.save_path: Path | None = None
        self.processes: list[subprocess.Popen[Any]] = []
        self.game_processes: dict[str, subprocess.Popen[Any]] = {}
        self.live_worker_stop = threading.Event()
        self.live_worker_thread: threading.Thread | None = None
        self.live_worker_project = ""
        self.live_worker_stats: JsonDict = {"running": False, "state": "stopped", "translated": 0, "failures": 0, "lastError": "", "lastSource": "", "startedAt": 0.0}
        self.live_debug_events: list[JsonDict] = []
        self.live_debug_seq = 0
        self.lock = threading.RLock()

    def health(self) -> JsonDict:
        return {
            "ok": True,
            "name": "RPGRenPyLocalizer API",
            "projectRoot": str(self.project_root),
            "python": sys.version.split()[0],
            "time": time.time(),
        }

    def settings_get(self) -> JsonDict:
        settings = self.workspace.load_settings()
        keys = settings.get("ai_api_keys") if isinstance(settings.get("ai_api_keys"), dict) else {}
        urls = settings.get("ai_base_urls") if isinstance(settings.get("ai_base_urls"), dict) else {}
        models = settings.get("ai_models") if isinstance(settings.get("ai_models"), dict) else {}
        raw_ai = settings.get("ai") if isinstance(settings.get("ai"), dict) else {}
        legacy_provider = str(raw_ai.get("provider") or settings.get("ai_provider") or "openai")
        raw_base_url = str(raw_ai.get("baseUrl") or urls.get(legacy_provider) or "")
        provider = "ollama" if "11434" in raw_base_url else self._normalize_ai_provider(legacy_provider)
        old_profiles = settings.get("ai_profiles") if isinstance(settings.get("ai_profiles"), dict) else {}

        def profile(name: str) -> JsonDict:
            aliases = {"openai": ("openai", "openai-compatible"), "anthropic": ("anthropic", "anthropic-compatible"), "ollama": ("ollama", "Ollama 本地模型")}[name]
            saved = next((old_profiles.get(alias) for alias in aliases if isinstance(old_profiles.get(alias), dict)), {})
            use_legacy = name == provider and legacy_provider not in {"openai", "anthropic", "ollama"}
            source_name = legacy_provider if use_legacy else name
            available = saved.get("models") if isinstance(saved.get("models"), list) else []
            return {
                "apiKey": str(saved.get("apiKey") or keys.get(source_name) or ""),
                "baseUrl": str(saved.get("baseUrl") or urls.get(source_name) or self._default_base_url(source_name) or self._default_base_url(name)),
                "model": str(saved.get("model") or models.get(source_name) or ""),
                "models": [str(item) for item in available if item],
            }

        profiles = {name: profile(name) for name in ("openai", "anthropic", "ollama")}
        current = profiles[provider]
        named_configs = settings.get("ai_named_configs") if isinstance(settings.get("ai_named_configs"), dict) else {}
        settings["ai_named_configs"] = named_configs
        settings["ai_profiles"] = profiles
        settings["ai"] = {
            "provider": provider,
            "apiKey": "" if provider == "ollama" else str(raw_ai.get("apiKey") or current["apiKey"] or settings.get("openai_api_key") or ""),
            "baseUrl": str((raw_ai.get("baseUrl") if legacy_provider == provider else "") or current["baseUrl"]),
            "model": str((raw_ai.get("model") if legacy_provider == provider else "") or current["model"]),
            "availableModels": current["models"],
            "targetLang": str(raw_ai.get("targetLang") or settings.get("ai_target_lang") or "简体中文"),
            "batchSize": _clamp_int(raw_ai.get("batchSize") or settings.get("ai_batch_size"), 20, 1, 200),
            "concurrency": _clamp_int(raw_ai.get("concurrency") or raw_ai.get("threads") or settings.get("ai_concurrency"), 1, 1, 8),
            "requestIntervalMs": _clamp_int(_first_present(raw_ai.get("requestIntervalMs"), raw_ai.get("rateLimitMs"), settings.get("ai_request_interval_ms")), 1200, 0, 60000),
            "rateLimitRetries": _clamp_int(_first_present(raw_ai.get("rateLimitRetries"), raw_ai.get("retry429"), settings.get("ai_rate_limit_retries")), 3, 0, 10),
            "requestTimeoutSec": _clamp_int(_first_present(raw_ai.get("requestTimeoutSec"), raw_ai.get("timeout"), settings.get("ai_request_timeout_sec")), 240, 30, 900),
        }
        return settings

    def settings_save(self, body: JsonDict) -> JsonDict:
        incoming = body.get("settings") if isinstance(body.get("settings"), dict) else body
        settings = self.workspace.load_settings()
        settings.update(incoming)
        ai = incoming.get("ai") if isinstance(incoming.get("ai"), dict) else None
        if ai is not None:
            provider = self._normalize_ai_provider(str(ai.get("provider") or "openai"))
            ai["provider"] = provider
            if provider == "ollama":
                ai["apiKey"] = ""
            settings["ai"] = ai
            keys = settings.get("ai_api_keys") if isinstance(settings.get("ai_api_keys"), dict) else {}
            urls = settings.get("ai_base_urls") if isinstance(settings.get("ai_base_urls"), dict) else {}
            models = settings.get("ai_models") if isinstance(settings.get("ai_models"), dict) else {}
            keys[provider] = str(ai.get("apiKey") or "")
            urls[provider] = str(ai.get("baseUrl") or "")
            models[provider] = str(ai.get("model") or "")
            ai["batchSize"] = _clamp_int(ai.get("batchSize"), 20, 1, 200)
            ai["concurrency"] = _clamp_int(ai.get("concurrency") or ai.get("threads"), 1, 1, 8)
            ai["requestIntervalMs"] = _clamp_int(_first_present(ai.get("requestIntervalMs"), ai.get("rateLimitMs")), 1200, 0, 60000)
            ai["rateLimitRetries"] = _clamp_int(_first_present(ai.get("rateLimitRetries"), ai.get("retry429")), 3, 0, 10)
            ai["requestTimeoutSec"] = _clamp_int(_first_present(ai.get("requestTimeoutSec"), ai.get("timeout")), 240, 30, 900)
            settings.update({
                "ai_provider": provider,
                "ai_api_keys": keys,
                "ai_base_urls": urls,
                "ai_models": models,
                "ai_model": models[provider],
                "ai_target_lang": str(ai.get("targetLang") or "简体中文"),
                "ai_batch_size": ai["batchSize"],
                "ai_concurrency": ai["concurrency"],
                "ai_request_interval_ms": ai["requestIntervalMs"],
                "ai_rate_limit_retries": ai["rateLimitRetries"],
                "ai_request_timeout_sec": ai["requestTimeoutSec"],
            })
        self.workspace.save_settings(settings)
        return {"ok": True, "settings": settings}

    def library_get(self) -> JsonDict:
        return {"ok": True, "entries": _plain(self.workspace.load_library())}

    def _project_display_name(self, project: ProjectInfo) -> str:
        launcher = project.launcher_path
        generic_names = {"game", "nw", "nwjs", "notification_helper"}
        for value in self._exe_metadata_names(launcher) if launcher else []:
            if value and value.strip().lower() not in generic_names:
                return value
        if launcher and launcher.stem.strip().lower() not in generic_names:
            return launcher.stem
        return project.root.name

    @staticmethod
    def _exe_metadata_names(path: Path | None) -> list[str]:
        if not path or not path.exists() or os.name != "nt":
            return []
        try:
            version = ctypes.windll.version
            size = version.GetFileVersionInfoSizeW(str(path), None)
            if not size:
                return []
            buffer = ctypes.create_string_buffer(size)
            if not version.GetFileVersionInfoW(str(path), 0, size, buffer):
                return []
            translate_ptr = ctypes.c_void_p()
            translate_len = ctypes.c_uint()
            if not version.VerQueryValueW(buffer, "\\VarFileInfo\\Translation", ctypes.byref(translate_ptr), ctypes.byref(translate_len)):
                return []
            if translate_len.value < 4:
                return []
            lang, codepage = ctypes.cast(translate_ptr, ctypes.POINTER(ctypes.c_ushort * 2)).contents
            names: list[str] = []
            for key in ("ProductName", "FileDescription", "OriginalFilename"):
                query = f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\{key}"
                value_ptr = ctypes.c_wchar_p()
                value_len = ctypes.c_uint()
                if version.VerQueryValueW(buffer, query, ctypes.byref(value_ptr), ctypes.byref(value_len)):
                    value = str(value_ptr.value or "").strip()
                    if value and value.lower().endswith(".exe"):
                        value = Path(value).stem
                    if value and value not in names:
                        names.append(value)
            return names
        except Exception:
            return []

    def _library_upsert_project(self, entries: list[LibraryEntry], project: ProjectInfo, now: str) -> tuple[bool, LibraryEntry]:
        launcher = str(project.launcher_path) if project.launcher_path else ""
        name = self._project_display_name(project)
        existing = next((entry for entry in entries if os.path.normcase(entry.path) == os.path.normcase(str(project.root))), None)
        if existing:
            existing.name = name
            existing.engine = project.engine
            existing.launcher_path = launcher
            existing.last_opened_at = now
            return False, existing
        entry = LibraryEntry(name=name, path=str(project.root), engine=project.engine, added_at=now, last_opened_at=now, launcher_path=launcher, note="", tags=[])
        entries.insert(0, entry)
        return True, entry

    def library_add(self, body: JsonDict) -> JsonDict:
        if self._active_game_path():
            raise ApiError("游戏运行中，不能添加或更换游戏。", 409)
        raw_path = str(body.get("path") or "").strip()
        if not raw_path:
            raise ApiError("缺少游戏路径。")
        project = detect_project(Path(raw_path).expanduser())
        entries = self.workspace.load_library()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._library_upsert_project(entries, project, now)
        self.workspace.save_library(entries)
        # Prepare the bundled bridge when the game enters the library so a later
        # launch does not depend on visiting a separate setup page first.
        try:
            if project.engine == "Ren'Py":
                RenPyService(project).install_live_translation_bridge(False)
            elif project.engine == "RPG Maker MV/MZ":
                RPGMakerService(project).install_runtime_bridge()
        except Exception:
            # Keep library import usable for non-standard or read-only projects.
            pass
        return {"ok": True, "entries": _plain(entries)}

    def library_add_folder(self, body: JsonDict) -> JsonDict:
        if self._active_game_path():
            raise ApiError("游戏运行中，不能添加或更换游戏。", 409)
        raw_path = str(body.get("path") or "").strip()
        if not raw_path:
            raise ApiError("缺少文件夹路径。")
        root = Path(raw_path).expanduser()
        if not root.is_dir():
            raise ApiError("请选择一个文件夹。")
        entries = self.workspace.load_library()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        projects, scanned = self._scan_importable_projects(root)
        added = 0
        updated = 0
        for project in projects.values():
            was_added, _entry = self._library_upsert_project(entries, project, now)
            if was_added:
                added += 1
            else:
                updated += 1
            try:
                if project.engine == "Ren'Py":
                    RenPyService(project).install_live_translation_bridge(False)
                elif project.engine == "RPG Maker MV/MZ":
                    RPGMakerService(project).install_runtime_bridge()
            except Exception:
                pass
        self.workspace.save_library(entries)
        return {"ok": True, "entries": _plain(entries), "added": added, "updated": updated, "found": len(projects), "scanned": scanned}

    def _scan_importable_projects(self, root: Path) -> tuple[dict[str, ProjectInfo], int]:
        projects: dict[str, ProjectInfo] = {}
        scanned = 0
        ignored_dirs = {
            ".git",
            ".svn",
            ".hg",
            ".rpgrtl_backup",
            ".rpgrtl_workspace",
            "__pycache__",
            "node_modules",
        }

        def remember(project: ProjectInfo) -> None:
            if project.engine not in {"RPG Maker MV/MZ", "Ren'Py"}:
                return
            if not project.launcher_path:
                return
            key = os.path.normcase(str(project.root.resolve()))
            existing = projects.get(key)
            if existing is None or (not existing.launcher_path and project.launcher_path):
                projects[key] = project

        for current, dirnames, filenames in os.walk(root):
            current_path = Path(current)
            dirnames[:] = [name for name in dirnames if name not in ignored_dirs]

            scanned += 1
            try:
                project = detect_project(current_path)
            except Exception:
                project = None
            if project:
                remember(project)
                dirnames[:] = []
                continue

            for filename in filenames:
                if not filename.lower().endswith(".exe"):
                    continue
                scanned += 1
                try:
                    project = detect_project(current_path / filename)
                except Exception:
                    continue
                remember(project)
                dirnames[:] = []
                break

        return projects, scanned

    def library_remove(self, body: JsonDict) -> JsonDict:
        raw_path = str(body.get("path") or "").strip()
        if not raw_path:
            raise ApiError("缺少游戏路径。")
        active = self._active_game_path()
        if active:
            raise ApiError("游戏运行中，不能移除或更换游戏。", 409)
        entries = [entry for entry in self.workspace.load_library() if entry.path != raw_path]
        self.workspace.save_library(entries)
        return {"ok": True, "entries": _plain(entries)}

    def library_launch(self, body: JsonDict) -> JsonDict:
        raw_path = str(body.get("path") or "").strip()
        if not raw_path:
            raise ApiError("缺少游戏路径。")
        active = self._active_game_path()
        if active:
            if active == raw_path:
                proc = self.game_processes[active]
                return {"ok": True, "pid": proc.pid, "alreadyRunning": True}
            raise ApiError("已有游戏正在运行，请先关闭游戏。", 409)
        entry = next((item for item in self.workspace.load_library() if item.path == raw_path), None)
        if entry is None:
            raise ApiError("游戏库中找不到该游戏。", 404)
        launcher = Path(entry.launcher_path) if entry.launcher_path else find_launcher(entry.path)
        if launcher is not None and not launcher.exists():
            launcher = find_launcher(entry.path, launcher.name)
        if launcher is None or not launcher.exists():
            raise ApiError(f"找不到游戏启动文件：{Path(entry.path)}", 404)
        proc = subprocess.Popen([str(launcher)], cwd=str(launcher.parent))
        self.processes.append(proc)
        self.game_processes[raw_path] = proc
        entries = self.workspace.load_library()
        for item in entries:
            if item.path == raw_path:
                item.last_opened_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        self.workspace.save_library(entries)
        return {"ok": True, "pid": proc.pid, "launcher": str(launcher)}

    def game_status(self) -> JsonDict:
        running: list[JsonDict] = []
        for path, proc in list(self.game_processes.items()):
            if proc.poll() is None:
                running.append({"path": path, "pid": proc.pid})
            else:
                self.game_processes.pop(path, None)
        return {"running": bool(running), "games": running, "activePath": running[0]["path"] if running else ""}

    def _active_game_path(self) -> str:
        self.game_status()
        return next(iter(self.game_processes), "")

    def load_project(self, body: JsonDict) -> JsonDict:
        raw_path = body.get("path")
        if not raw_path:
            raise ApiError("缺少 path。")
        active = self._active_game_path()
        requested = detect_project(Path(str(raw_path)).expanduser())
        if active and os.path.normcase(active) != os.path.normcase(str(requested.root)):
            raise ApiError("游戏运行中，不能切换到其他游戏。", 409)
        if self.project and self.project.root.resolve() != requested.root.resolve():
            self._stop_live_worker()
            if self.project.engine == "Ren'Py":
                RenPyService(self.project).stop_live_bridge_server()
            elif self.project.engine == "RPG Maker MV/MZ":
                RPGMakerService(self.project).stop_live_bridge_server()
        project = requested
        with self.lock:
            self.project = project
            self.translation_entries = []
            self.data_records = []
            self.save_payload = None
            self.save_path = None
        # Prepare the bundled runtime component as soon as a project is selected,
        # so users do not have to understand or repeat a manual installation step.
        try:
            if project.engine == "Ren'Py":
                RenPyService(project).install_live_translation_bridge(False)
            elif project.engine == "RPG Maker MV/MZ":
                RPGMakerService(project).install_runtime_bridge()
        except Exception:
            # Projects with a non-standard layout can still be opened for extraction.
            pass
        return self.project_summary(refresh=False)

    def project_summary(self, refresh: bool = False) -> JsonDict:
        project = self._project()
        summary: JsonDict = {
            "engine": project.engine,
            "root": str(project.root),
            "gameDir": str(project.game_dir),
            "launcherPath": str(project.launcher_path) if project.launcher_path else "",
            "dataDir": str(project.data_dir) if project.data_dir else "",
            "scriptsDir": str(project.scripts_dir) if project.scripts_dir else "",
            "supportsRpgMaker": project.engine.startswith("RPG Maker"),
            "supportsRenpy": project.engine == "Ren'Py",
            "supportsFullEditing": project.engine == "RPG Maker MV/MZ",
        }
        service = self._service()
        if not refresh:
            return summary
        try:
            entries = service.extract_translations()
            summary["translationCount"] = len(entries)
            if refresh:
                self.translation_entries = entries
        except Exception as exc:
            summary["translationError"] = str(exc)
        try:
            records = service.list_data_records()
            summary["dataRecordCount"] = len(records)
            if refresh:
                self.data_records = records
        except Exception as exc:
            summary["dataRecordError"] = str(exc)
        if project.engine == "RPG Maker MV/MZ":
            try:
                rpg = RPGMakerService(project)
                summary["mapCount"] = len(rpg.list_maps())
                summary["saveSlotCount"] = len(rpg.list_save_slots())
            except Exception as exc:
                summary["rpgMakerExtraError"] = str(exc)
        return summary

    def launch_project(self, body: JsonDict) -> JsonDict:
        project = self._project()
        raw_launcher = body.get("launcherPath") or project.launcher_path
        launcher: Path | None = Path(str(raw_launcher)) if raw_launcher else find_launcher(project.root)
        if launcher is not None and not launcher.exists():
            launcher = find_launcher(project.root, launcher.name if str(raw_launcher or "") else None)
        if launcher is None or not launcher.exists():
            raise ApiError("未找到游戏启动文件。")
        proc = subprocess.Popen([str(launcher)], cwd=str(launcher.parent))
        self.processes.append(proc)
        self.game_processes[str(project.root)] = proc
        return {"ok": True, "pid": proc.pid, "launcher": str(launcher)}

    def ai_models(self, body: JsonDict) -> JsonDict:
        provider = self._normalize_ai_provider(str(body.get("provider") or "openai"))
        api_key = str(body.get("apiKey") or "")
        base_url = str(body.get("baseUrl") or self._default_base_url(provider)).rstrip("/")
        if not base_url:
            raise ApiError("请先填写接口 URL。")
        headers: JsonDict = {"Accept": "application/json"}
        if provider == "ollama":
            native_base = base_url[:-3] if base_url.endswith("/v1") else base_url
            raw = self._http_get_json(native_base + "/api/tags", headers, timeout=10)
            values = raw.get("models") or []
            models = [str(item.get("name") or item.get("model") or "") for item in values if isinstance(item, dict)]
            return {"models": sorted({model for model in models if model}), "detected": True}
        if provider == "anthropic":
            headers.update({"x-api-key": api_key, "anthropic-version": "2023-06-01"})
        elif api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        url = base_url + "/models" if base_url.endswith("/v1") else base_url + "/v1/models"
        raw = self._http_get_json(url, headers, timeout=30)
        values = raw.get("data") or raw.get("models") or []
        models = []
        for item in values if isinstance(values, list) else []:
            model_id = item.get("id") if isinstance(item, dict) else item
            if model_id:
                models.append(str(model_id))
        return {"models": sorted(set(models))}

    @staticmethod
    def _normalize_ai_provider(provider: str) -> str:
        lowered = str(provider or "").strip().lower()
        if "ollama" in lowered or "本地模型" in lowered:
            return "ollama"
        if "anthropic" in lowered or "claude" in lowered:
            return "anthropic"
        return "openai"

    def translations(self, query: JsonDict) -> JsonDict:
        service = self._service()
        refresh = str(query.get("refresh", "0")).lower() in {"1", "true", "yes"}
        if refresh or not self.translation_entries:
            self.translation_entries = service.extract_translations()
            self._restore_translation_cache()
        safe_entries = self._filter_safe_translation_entries(self.translation_entries)
        entries = safe_entries
        text = str(query.get("q") or "").strip().lower()
        category = str(query.get("category") or "").strip()
        only_missing = str(query.get("missing", "0")).lower() in {"1", "true", "yes"}
        if text:
            entries = [e for e in entries if text in e.source.lower() or text in e.target.lower() or text in e.file.lower() or text in e.context.lower()]
        if category:
            entries = [e for e in entries if e.category == category or e.file == category]
        if only_missing:
            entries = [e for e in entries if not e.target]
        limit = max(1, min(int(query.get("limit") or 500), 5000))
        offset = max(0, int(query.get("offset") or 0))
        categories = sorted({e.category or e.file for e in safe_entries if e.category or e.file})
        return {"count": len(entries), "total": len(safe_entries), "categories": categories, "entries": _plain(entries[offset: offset + limit])}

    def translations_save_targets(self, body: JsonDict) -> JsonDict:
        updates = body.get("updates") or []
        if not isinstance(updates, list):
            raise ApiError("updates 必须是数组。")
        if not self.translation_entries:
            self.translation_entries = self._service().extract_translations()
        index = {e.entry_id: e for e in self._filter_safe_translation_entries(self.translation_entries)}
        changed = 0
        for raw in updates:
            if not isinstance(raw, dict):
                continue
            entry_id = str(raw.get("entry_id") or raw.get("id") or "")
            if entry_id in index:
                target = str(raw.get("target") or "")
                source = index[entry_id].source
                self._validate_translation_target(source, target)
                index[entry_id].target = target
                changed += 1
        self._persist_translation_cache()
        return {"ok": True, "changed": changed}

    def _translation_cache_path(self) -> Path:
        return self._project().root / ".rpgrtl_workspace" / "translation_entries.json"

    def _restore_translation_cache(self) -> None:
        path = self._translation_cache_path()
        if not path.exists():
            return
        try:
            payload = load_json(path)
            cached = payload.get("entries") if isinstance(payload, dict) else []
            by_id = {str(item.get("entry_id")): str(item.get("target") or "") for item in cached if isinstance(item, dict)}
            for entry in self.translation_entries:
                if entry.entry_id in by_id:
                    entry.target = by_id[entry.entry_id]
        except (OSError, ValueError, TypeError):
            return

    def _persist_translation_cache(self) -> None:
        path = self._translation_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = time.time()
        entries = _plain(self._filter_safe_translation_entries(self.translation_entries))
        save_json(path, {"version": 1, "updated_at": timestamp, "entries": entries})
        save_json(path.parent / "original_texts.json", {
            "version": 1,
            "updated_at": timestamp,
            "engine": self._project().engine,
            "entries": [{"entry_id": item.get("entry_id", ""), "source": item.get("source", ""), "file": item.get("file", ""), "context": item.get("context", ""), "category": item.get("category", "")} for item in entries],
        })
        save_json(path.parent / "translated_texts.json", {
            "version": 1,
            "updated_at": timestamp,
            "engine": self._project().engine,
            "entries": [{"entry_id": item.get("entry_id", ""), "source": item.get("source", ""), "target": item.get("target", ""), "file": item.get("file", ""), "category": item.get("category", "")} for item in entries if item.get("target", "")],
        })
    def _safe_translation_categories(self) -> set[str]:
        project = self._project()
        if project.engine == "RPG Maker MV/MZ":
            return {"database", "dialogue"}
        if project.engine == "Ren'Py":
            return {"dialogue", "choice"}
        return set()

    def _is_safe_translation_entry(self, entry: TranslationEntry) -> bool:
        categories = self._safe_translation_categories()
        return bool(entry.source and entry.category in categories)

    def _filter_safe_translation_entries(self, entries: list[TranslationEntry]) -> list[TranslationEntry]:
        return [entry for entry in entries if self._is_safe_translation_entry(entry)]

    def translations_apply(self, body: JsonDict) -> JsonDict:
        translations = self._merged_translation_map(body)
        changed = self._service().apply_translations(translations)
        self._persist_translation_cache()
        return {"ok": True, "changed": changed}

    def translations_export(self, body: JsonDict) -> JsonDict:
        raw = body.get("path")
        if not raw:
            raise ApiError("缺少导出路径。")
        path = Path(str(raw)).expanduser()
        if not self.translation_entries:
            self.translation_entries = self._service().extract_translations()
        translations = self._merged_translation_list(body)
        engine = self._project().engine
        export_translation_pack(path, engine, translations, translation_pack_signature(engine, translations))
        return {"ok": True, "path": str(path), "count": len(translations)}

    def translations_import(self, body: JsonDict) -> JsonDict:
        path = Path(str(body.get("path") or "")).expanduser()
        if not path.exists():
            raise ApiError("翻译包不存在。")
        imported = import_translation_pack(path)
        if not self.translation_entries:
            self.translation_entries = self._service().extract_translations()
        index = {e.entry_id: e for e in self._filter_safe_translation_entries(self.translation_entries)}
        matched = 0
        for entry_id, imported_entry in imported.items():
            if entry_id in index:
                self._validate_translation_target(index[entry_id].source, imported_entry.target)
                index[entry_id].target = imported_entry.target
                matched += 1
        self._persist_translation_cache()
        return {"ok": True, "matched": matched, "imported": len(imported)}

    def translations_runtime(self, body: JsonDict) -> JsonDict:
        project = self._project()
        translations = self._merged_translation_map(body)
        if str(body.get("mode") or "translated") == "original":
            original_map = {entry.target: entry.source for entry in translations.values() if entry.target.strip()}
            translations = {
                key: TranslationEntry(entry.entry_id, entry.source, entry.source, entry.file, entry.context, entry.category)
                for key, entry in translations.items()
            }
            translations.update({
                f"reverse:{key}": TranslationEntry(f"reverse:{key}", key, value, "", "", "")
                for key, value in original_map.items()
            })
        if project.engine == "RPG Maker MV/MZ":
            service = RPGMakerService(project)
            # The workbench replacement buttons must also work while the game
            # is already running, even when the user did not open Live first.
            # Starting without clear_events preserves the current queue and
            # lets the game's polling bridge connect on its next heartbeat.
            service.install_runtime_bridge()
            service.start_live_bridge_server(clear_events=False)
            if hasattr(service, "set_live_translations"):
                live_count = service.set_live_translations({entry.source: entry.target for entry in translations.values() if entry.source.strip() and entry.target.strip()})
            else:
                live_count = 0
            path, launcher, changed = service.build_runtime_copy(translations)
            return {"ok": True, "path": str(path), "launcher": str(launcher) if launcher else "", "changed": changed, "liveApplied": live_count}
        if project.engine == "Ren'Py":
            service = RenPyService(project)
            service.install_live_translation_bridge(False)
            for entry in translations.values():
                if entry.source.strip() and entry.target.strip():
                    service.merge_live_translations({entry.source: entry.target}, kind="mode_switch")
            path, changed = service.build_runtime_translation_patch(translations)
            return {"ok": True, "path": str(path), "changed": changed}
        raise ApiError("当前引擎不支持运行时翻译补丁。")

    def rpgmaker_install_bridge(self) -> JsonDict:
        project = self._project()
        if project.engine != "RPG Maker MV/MZ":
            raise ApiError("当前项目不是 RPG Maker MV/MZ。")
        path = RPGMakerService(project).install_runtime_bridge()
        return {"ok": True, "path": str(path)}

    def renpy_install_extractor(self, body: JsonDict) -> JsonDict:
        project = self._project()
        if project.engine != "Ren'Py":
            raise ApiError("当前项目不是 Ren'Py。")
        path = RenPyService(project).install_runtime_extractor(bool(body.get("clearCache", False)))
        return {"ok": True, "path": str(path)}

    def renpy_install_live_bridge(self, body: JsonDict) -> JsonDict:
        project = self._project()
        if project.engine != "Ren'Py":
            raise ApiError("当前项目不是 Ren'Py。")
        path = RenPyService(project).install_live_translation_bridge(bool(body.get("clearSeen", False)))
        return {"ok": True, "path": str(path)}

    def renpy_restore(self) -> JsonDict:
        project = self._project()
        if project.engine != "Ren'Py":
            raise ApiError("当前项目不是 Ren'Py。")
        count = RenPyService(project).restore_original_scripts()
        return {"ok": True, "restored": count}

    def data_records_get(self, query: JsonDict) -> JsonDict:
        service = self._service()
        refresh = str(query.get("refresh", "0")).lower() in {"1", "true", "yes"}
        if refresh or not self.data_records:
            self.data_records = service.list_data_records()
        records = self.data_records
        text = str(query.get("q") or "").strip().lower()
        category = str(query.get("category") or "").strip()
        if text:
            records = [r for r in records if text in r.label.lower() or text in r.value.lower() or text in r.object_label.lower() or text in r.file.lower()]
        if category:
            records = [r for r in records if r.category == category or r.file == category]
        limit = max(1, min(int(query.get("limit") or 500), 5000))
        offset = max(0, int(query.get("offset") or 0))
        categories = sorted({r.category or r.file for r in self.data_records if r.category or r.file})
        return {"count": len(records), "total": len(self.data_records), "categories": categories, "records": _plain(records[offset: offset + limit])}

    def data_update(self, body: JsonDict) -> JsonDict:
        record_id = str(body.get("record_id") or body.get("id") or "")
        new_value = str(body.get("value") if body.get("value") is not None else "")
        if not self.data_records:
            self.data_records = self._service().list_data_records()
        index = {r.record_id: r for r in self.data_records}
        record = index.get(record_id)
        if not record:
            raise ApiError("未找到数据记录。")
        self._service().update_record(record, new_value)
        record.value = new_value
        return {"ok": True, "record": _plain(record)}

    def save_slots(self) -> JsonDict:
        project = self._project()
        if project.engine != "RPG Maker MV/MZ":
            return {"count": 0, "slots": []}
        slots = RPGMakerService(project).list_save_slots()
        return {"count": len(slots), "slots": _plain(slots)}

    def save_load(self, body: JsonDict) -> JsonDict:
        project = self._project()
        if project.engine != "RPG Maker MV/MZ":
            raise ApiError("只有 RPG Maker MV/MZ 支持存档修改。")
        path = Path(str(body.get("path") or ""))
        if not path.exists():
            raise ApiError("存档文件不存在。")
        service = RPGMakerService(project)
        payload = service.load_save(path)
        self.save_payload = payload
        self.save_path = path
        return {"ok": True, "path": str(path), "summary": service.save_summary(payload), "payload": self._save_preview(payload)}

    def save_current(self) -> JsonDict:
        project = self._project()
        if project.engine != "RPG Maker MV/MZ" or self.save_payload is None:
            return {"loaded": False}
        return {"loaded": True, "path": str(self.save_path), "summary": RPGMakerService(project).save_summary(self.save_payload), "payload": self._save_preview(self.save_payload)}

    def save_mutate(self, body: JsonDict) -> JsonDict:
        project = self._project()
        if project.engine != "RPG Maker MV/MZ":
            raise ApiError("只有 RPG Maker MV/MZ 支持存档修改。")
        if self.save_payload is None:
            raise ApiError("尚未加载存档。")
        service = RPGMakerService(project)
        op = str(body.get("op") or "")
        if op == "gold":
            service.set_save_gold(self.save_payload, int(body.get("value") or 0))
        elif op == "item":
            service.set_save_item(self.save_payload, str(body.get("kind") or "items"), int(body.get("itemId") or 0), int(body.get("value") or 0))
        elif op == "actorLevel":
            service.set_save_actor_level(self.save_payload, int(body.get("actorId") or 0), int(body.get("value") or 1))
        elif op == "switch":
            service.set_save_switch(self.save_payload, int(body.get("switchId") or 0), bool(body.get("value")))
        elif op == "variable":
            service.set_save_variable(self.save_payload, int(body.get("variableId") or 0), body.get("value"))
        else:
            raise ApiError("未知存档修改操作。")
        return {"ok": True, "summary": service.save_summary(self.save_payload), "payload": self._save_preview(self.save_payload)}

    def save_write(self, body: JsonDict) -> JsonDict:
        project = self._project()
        if project.engine != "RPG Maker MV/MZ" or self.save_payload is None or self.save_path is None:
            raise ApiError("尚未加载存档。")
        path = Path(str(body.get("path") or self.save_path))
        RPGMakerService(project).save_save(path, self.save_payload)
        self.save_path = path
        return {"ok": True, "path": str(path)}
    def maps_get(self) -> JsonDict:
        project = self._project()
        if project.engine != "RPG Maker MV/MZ":
            return {"count": 0, "maps": []}
        maps = RPGMakerService(project).list_maps()
        return {"count": len(maps), "maps": _plain(maps)}

    def map_detail(self, query: JsonDict) -> JsonDict:
        project = self._project()
        if project.engine != "RPG Maker MV/MZ":
            raise ApiError("当前项目不支持地图。")
        map_id = int(query.get("id") or query.get("mapId") or 0)
        return _plain(RPGMakerService(project).map_detail(map_id))

    def runtime_state(self) -> JsonDict:
        try:
            self._require_rpgmaker_runtime()
            state = self._runtime_request("GET", "/state")
        except ApiError as exc:
            if exc.status == 503:
                return {"connected": False, "error": str(exc)}
            raise
        state["connected"] = True
        project = self._project()
        if project.data_dir:
            for kind, file_name in (("items", "Items.json"), ("weapons", "Weapons.json"), ("armors", "Armors.json")):
                counts = {int(item.get("id") or 0): int(item.get("count") or 0) for item in state.get(kind, []) if isinstance(item, dict)}
                path = project.data_dir / file_name
                catalog = load_json(path) if path.exists() else []
                state[kind] = [
                    {"id": int(item.get("id") or 0), "name": str(item.get("name") or ""), "count": counts.get(int(item.get("id") or 0), 0)}
                    for item in catalog if isinstance(item, dict) and item.get("id")
                ]
        return state

    def runtime_set(self, body: JsonDict) -> JsonDict:
        self._require_rpgmaker_runtime()
        return self._runtime_request("POST", "/set", body)

    def _require_rpgmaker_runtime(self) -> None:
        project = self._project()
        if project.engine != "RPG Maker MV/MZ":
            raise ApiError("只有 RPG Maker MV/MZ 支持实时修改。")
        ping = self._runtime_request("GET", "/ping")
        bridge_root = str(ping.get("root") or "")
        if not bridge_root:
            return
        try:
            resolved_bridge = Path(bridge_root).resolve()
            candidates = {project.root.resolve(), project.game_dir.resolve()}
            if project.data_dir:
                candidates.add(project.data_dir.resolve().parent)
            bridge_text = os.path.normcase(str(resolved_bridge))
            if any(
                bridge_text == os.path.normcase(str(candidate))
                or bridge_text.startswith(os.path.normcase(str(candidate)) + os.sep)
                for candidate in candidates
            ):
                return
        except OSError:
            return
        raise ApiError("实时端口正被其他游戏占用，请关闭旧游戏后重试。", 409)

    @staticmethod
    def _runtime_request(method: str, path: str, body: JsonDict | None = None) -> JsonDict:
        data = json.dumps(body or {}).encode("utf-8") if method == "POST" else None
        request = urllib.request.Request(
            f"http://127.0.0.1:32179{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=4.5) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise ApiError("无法连接游戏实时桥接，请启动游戏并进入地图；组件会在项目载入时自动准备。", 503) from exc
        if not isinstance(result, dict) or not result.get("ok", True):
            raise ApiError(str(result.get("error") if isinstance(result, dict) else "实时组件返回异常"), 502)
        return result

    def live_start(self, body: JsonDict) -> JsonDict:
        service = self._service()
        if not self.translation_entries:
            try:
                self.translation_entries = service.extract_translations()
                self._restore_translation_cache()
            except Exception:
                self.translation_entries = []
        if self.translation_entries and self.project:
            self._persist_translation_cache()
        if isinstance(service, RenPyService):
            service.install_live_translation_bridge(bool(body.get("clearEvents", False)))
            if self.translation_entries:
                translated = {entry.source: entry.target for entry in self.translation_entries if entry.source.strip() and entry.target.strip()}
                if translated:
                    service.merge_live_translations(translated, kind="loaded")
            if body.get("autoTranslate", True):
                self._start_live_worker(service)
        elif hasattr(service, "start_live_bridge_server"):
            RPGMakerService(service.project).install_runtime_bridge()
            # A new RPGMaker session must not inherit another game's capture queue.
            service.start_live_bridge_server(bool(body.get("clearEvents", True)))
            if self.translation_entries and hasattr(service, "set_live_translations"):
                service.set_live_translations({entry.source: entry.target for entry in self.translation_entries if entry.source.strip() and entry.target.strip()})
                service.seed_live_translation_queue(self.translation_entries)
            if body.get("autoTranslate", True):
                self._start_live_worker(service)
        return self.live_status()

    def live_stop(self) -> JsonDict:
        service = self._service()
        self._stop_live_worker()
        if hasattr(service, "stop_live_bridge_server"):
            service.stop_live_bridge_server()
        return self.live_status()

    def live_status(self) -> JsonDict:
        service = self._service()
        if hasattr(service, "live_bridge_status"):
            status = _plain(service.live_bridge_status())
            with self.lock:
                status["worker"] = dict(self.live_worker_stats)
            if hasattr(service, "read_live_debug_entries"):
                status["recentEvents"] = _plain(service.read_live_debug_entries(20))
            elif hasattr(service, "read_live_debug_events"):
                status["recentEvents"] = _plain(service.read_live_debug_events(20))
            return status
        return {"running": False}

    def live_debug(self, query: JsonDict) -> JsonDict:
        service = self._service()
        limit = _clamp_int(query.get("limit"), 160, 20, 500)
        autostart = str(query.get("autostart") or "").lower() in {"1", "true", "yes"}
        if str(query.get("clear") or "").lower() in {"1", "true", "yes"}:
            with self.lock:
                self.live_debug_events.clear()
            if hasattr(service, "append_live_debug_event"):
                service.append_live_debug_event("debug_clear", "Electron debug view cleared")
        status = self.live_status()
        worker_running = bool(status.get("worker", {}).get("running")) if isinstance(status.get("worker"), dict) else False
        if autostart and isinstance(service, RenPyService) and not worker_running and (status.get("connected") or int(status.get("queue_count") or 0) > 0):
            service.install_live_translation_bridge(False)
            self._start_live_worker(service)
            self._record_live_debug("worker", "autostart_live_worker", {"connected": bool(status.get("connected")), "queue_count": int(status.get("queue_count") or 0)})
            status = self.live_status()
        service_events = []
        if hasattr(service, "read_live_debug_entries"):
            service_events = _plain(service.read_live_debug_entries(min(limit, 120)))
        elif hasattr(service, "read_live_debug_events"):
            service_events = _plain(service.read_live_debug_events(min(limit, 120)))
        with self.lock:
            worker_events = list(self.live_debug_events)[-limit:]
            worker = dict(self.live_worker_stats)
        tree = [
            {
                "id": "bridge",
                "label": "Hook / Bridge",
                "children": [
                    {"id": "bridge-running", "label": f"Local server: {'running' if status.get('running') else 'stopped'}"},
                    {"id": "bridge-connected", "label": f"Game hook: {'connected' if status.get('connected') else 'waiting'}"},
                    {"id": "bridge-queue", "label": f"Queue: {status.get('queue_count', 0)}"},
                    {"id": "bridge-translations", "label": f"Injected cache: {status.get('translation_count', 0)}"},
                ],
            },
            {
                "id": "worker",
                "label": "AI Worker",
                "children": [
                    {"id": "worker-state", "label": f"State: {worker.get('state', 'unknown')}"},
                    {"id": "worker-translated", "label": f"Translated: {worker.get('translated', 0)}"},
                    {"id": "worker-failures", "label": f"Failures: {worker.get('failures', 0)}"},
                    {"id": "worker-last", "label": f"Last source: {str(worker.get('lastSource') or '')[:80]}"},
                ],
            },
        ]
        return {
            "ok": True,
            "status": status,
            "worker": worker,
            "tree": tree,
            "debugEvents": _plain(worker_events),
            "hookEvents": service_events,
        }

    def live_force_text(self, body: JsonDict) -> JsonDict:
        service = self._service()
        if not hasattr(service, "force_live_text"):
            raise ApiError("当前引擎不支持强制替换当前文本。")
        text = str(body.get("text") or "hello")
        try:
            seq = service.force_live_text(text)
        except RuntimeError as exc:
            raise ApiError(str(exc), 409) from exc
        self._record_live_debug("inject", "force_text", {"text": text, "notify_seq": seq})
        return {"ok": True, "seq": seq, "text": text}

    def live_merge(self, body: JsonDict) -> JsonDict:
        source = str(body.get("source") or "")
        target = str(body.get("target") or "")
        kind = str(body.get("kind") or "manual")
        if not source or not target:
            raise ApiError("source 和 target 不能为空。")
        self._service().merge_live_translation(source, target, kind)
        return {"ok": True}

    def live_refresh(self) -> JsonDict:
        count = self._service().notify_game_refresh()
        return {"ok": True, "count": count}

    def _record_live_debug(self, stage: str, title: str, payload: object = "") -> None:
        with self.lock:
            self.live_debug_seq += 1
            event = {
                "seq": self.live_debug_seq,
                "time": time.time(),
                "stage": str(stage or "debug"),
                "title": str(title or stage or "debug"),
                "payload": self._redact_debug_payload(payload),
            }
            self.live_debug_events.append(event)
            if len(self.live_debug_events) > 2000:
                del self.live_debug_events[: len(self.live_debug_events) - 2000]

    def _redact_debug_payload(self, value: object) -> object:
        if isinstance(value, dict):
            result: JsonDict = {}
            for key, item in value.items():
                name = str(key)
                if name.lower() in {"apikey", "api_key", "authorization", "x-api-key"}:
                    text = str(item or "")
                    result[name] = (text[:6] + "..." + text[-4:]) if len(text) > 12 else ("***" if text else "")
                else:
                    result[name] = self._redact_debug_payload(item)
            return result
        if isinstance(value, list):
            return [self._redact_debug_payload(item) for item in value[:200]]
        return value

    @staticmethod
    def _is_live_translation_source(text: str) -> bool:
        value = str(text or "").strip()
        if len(value) < 2 or len(value) > 2000:
            return False
        # Paths are often encountered while walking Ren'Py's AST (resource
        # directory, archive name, script origin). They contain letters but are
        # never player-facing dialogue and must not occupy an AI worker slot.
        if re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith(("/", "\\", "./", "../", "~/")):
            return False
        clean = re.sub(r"\{[^}]*\}", "", value).strip()
        if not clean or re.fullmatch(r"[\W_]+", clean):
            return False
        lowered = clean.lower()
        if re.fullmatch(r"https?://\S+|www\.\S+", lowered):
            return False
        if re.fullmatch(r"\S+\.(?:png|jpe?g|webp|ogg|wav|mp3|json|rpyc?|rpa|exe)", lowered):
            return False
        if re.search(r"[\\/]", clean) and re.fullmatch(r"[A-Za-z0-9._ ()\-\\/]+", clean):
            return False
        return any("a" <= char.lower() <= "z" or "\u3040" <= char <= "\u30ff" or "\u4e00" <= char <= "\u9fff" for char in clean)

    @staticmethod
    def _is_safe_rpgmaker_capture(event: str) -> bool:
        return str(event or "") in {
            "game_message_setText", "game_message_setChoice", "choice_drawItem",
            "cmd_401_dialogue", "cmd_102_choice", "cmd_405_scroll",
            "map_event_dialogue", "map_event_choice", "map_event_scroll",
            "common_event_dialogue", "showText", "scrollText", "dialogue_block",
        }

    def _live_ai_config(self) -> JsonDict:
        settings = self.settings_get()
        ai = settings.get("ai") if isinstance(settings.get("ai"), dict) else {}
        return {
            "provider": str(ai.get("provider") or "openai-compatible"),
            "apiKey": str(ai.get("apiKey") or ""),
            "baseUrl": str(ai.get("baseUrl") or ""),
            "model": str(ai.get("model") or ""),
            "targetLang": str(ai.get("targetLang") or "简体中文"),
            "batchSize": max(1, min(int(ai.get("batchSize") or 20), 200)),
            "concurrency": max(1, min(int(ai.get("concurrency") or ai.get("threads") or 1), 8)),
            "requestIntervalMs": max(0, min(int(ai.get("requestIntervalMs") or ai.get("rateLimitMs") or 1200), 60000)),
            "windowSize": 300,
        }

    def _start_live_worker(self, service: Any) -> None:
        project_root = str(service.project.root.resolve())
        if self.live_worker_thread and self.live_worker_thread.is_alive() and self.live_worker_project == project_root:
            return
        self._stop_live_worker()
        self.live_worker_stop = threading.Event()
        self.live_worker_project = project_root
        with self.lock:
            self.live_worker_stats = {"running": True, "state": "waiting", "translated": 0, "failures": 0, "lastError": "", "lastSource": "", "activeBatches": 0, "batchSize": 0, "concurrency": 1, "startedAt": time.time()}
        self.live_worker_thread = threading.Thread(target=self._live_worker_loop, args=(service, self.live_worker_stop, project_root), daemon=True, name="renpy-live-translator")
        self.live_worker_thread.start()

    def _stop_live_worker(self) -> None:
        self.live_worker_stop.set()
        thread = self.live_worker_thread
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        self.live_worker_thread = None
        self.live_worker_project = ""
        with self.lock:
            self.live_worker_stats["running"] = False
            self.live_worker_stats["state"] = "stopped"

    def _filter_live_translations(self, service: Any, sources: list[str], targets: list[str]) -> tuple[dict[str, str], list[str]]:
        translated: dict[str, str] = {}
        missing: list[str] = []
        for source, target in zip(sources, targets):
            value = str(target or "").strip()
            if not value or value == source:
                missing.append(source)
                continue
            if isinstance(service, RenPyService) and not RenPyService.control_tokens_preserved(source, value):
                missing.append(source)
                continue
            if isinstance(service, RPGMakerService) and not RPGMakerService.control_tokens_preserved(source, value):
                missing.append(source)
                continue
            translated[source] = value
        if len(targets) < len(sources):
            missing.extend(sources[len(targets):])
        return translated, missing

    def _translate_live_candidates_with_repair(self, service: Any, candidates: list[str], config: JsonDict) -> tuple[dict[str, str], list[str]]:
        try:
            targets = self._translate_openai_compatible(candidates, config)
        except ApiError as exc:
            # A timeout means the provider received a batch that is too expensive
            # for its current queue.  Split it immediately instead of making the
            # user wait for the whole batch to retry unchanged.
            if exc.status == 504 and len(candidates) > 1:
                midpoint = max(1, len(candidates) // 2)
                self._record_live_debug("api", "timeout_split_retry", {"count": len(candidates), "left": midpoint, "right": len(candidates) - midpoint, "reason": str(exc)})
                left_translated, left_missing = self._translate_live_candidates_with_repair(service, candidates[:midpoint], config)
                right_translated, right_missing = self._translate_live_candidates_with_repair(service, candidates[midpoint:], config)
                left_translated.update(right_translated)
                return left_translated, left_missing + right_missing
            raise
        self._record_live_debug("api", "parsed_translations", {"sources": candidates, "targets": targets})
        translated, missing = self._filter_live_translations(service, candidates, targets)
        return translated, missing

    def _live_worker_loop(self, service: Any, stop_event: threading.Event, project_root: str) -> None:
        failure_streak = 0
        source_attempts: dict[str, int] = {}
        retry_after: dict[str, float] = {}
        while not stop_event.is_set() and self.live_worker_project == project_root:
            config = self._live_ai_config()
            batch_size = int(config["batchSize"])
            concurrency = int(config["concurrency"])
            wave_size = min(int(config["windowSize"]), batch_size * concurrency)
            now = time.monotonic()
            # A visible line is the only latency-critical item.  Future lines
            # may use normal backoff after a malformed/partial AI response, but
            # never let that backoff prevent the player from receiving the line
            # currently on screen.
            try:
                current_source = str(service.live_bridge_status().get("current_source", "") or "").strip()
            except Exception:
                current_source = ""
            raw_candidates = service.take_live_translation_candidates(wave_size)
            deferred = [source for source in raw_candidates if self._is_live_translation_source(source) and source != current_source and retry_after.get(source, 0.0) > now]
            if deferred:
                service.requeue_live_translation_candidates(deferred)
            candidates = [source for source in raw_candidates if self._is_live_translation_source(source) and (source == current_source or retry_after.get(source, 0.0) <= now)]

            # The runtime AST often ends at a jump/menu after a few nodes. Once
            # the visible line gives us a reliable anchor, refill from the
            # extracted script order so a configured 50 x 4 worker can actually
            # receive up to 200 upcoming entries instead of only 6 or 7.
            seeded = 0
            if isinstance(service, RenPyService) and candidates and len(candidates) < wave_size and self.translation_entries:
                seeded = service.seed_live_translation_queue(self.translation_entries, candidates[0], config["windowSize"])
                if seeded:
                    extra_raw = service.take_live_translation_candidates(wave_size - len(candidates))
                    existing = set(candidates)
                    for source in extra_raw:
                        if not self._is_live_translation_source(source) or source in existing:
                            continue
                        if source != current_source and retry_after.get(source, 0.0) > now:
                            service.requeue_live_translation_candidates([source])
                            continue
                        candidates.append(source)
                        existing.add(source)
            if raw_candidates:
                self._record_live_debug("capture", "candidate_batch", {
                    "raw_count": len(raw_candidates),
                    "candidate_count": len(candidates),
                    "deferred_count": len(deferred),
                    "seeded_count": seeded,
                    "batch_size": batch_size,
                    "concurrency": concurrency,
                    "wave_size": wave_size,
                    "raw": raw_candidates,
                    "accepted": candidates,
                    "deferred": deferred,
                })
            if not candidates:
                with self.lock:
                    self.live_worker_stats["state"] = "waiting"
                stop_event.wait(0.25)
                continue
            if not config["baseUrl"] or not config["model"] or (config["provider"] != "ollama" and not config["apiKey"]):
                service.requeue_live_translation_candidates(candidates)
                with self.lock:
                    self.live_worker_stats.update({"state": "configuration_required", "lastError": "请先在 AI 设置中填写接口信息并选择模型。"})
                stop_event.wait(2.0)
                continue
            with self.lock:
                self.live_worker_stats.update({"state": "translating", "lastSource": candidates[0], "lastError": "", "activeBatches": min(concurrency, (len(candidates) + batch_size - 1) // batch_size), "batchSize": batch_size, "concurrency": concurrency})
            try:
                debug_config = dict(config)
                debug_config["_debugLive"] = True
                chunks = [candidates[index:index + batch_size] for index in range(0, len(candidates), batch_size)]
                translated: dict[str, str] = {}
                missing: list[str] = []
                request_lock = threading.Lock()
                next_request_at = [0.0]

                def translate_chunks_parallel(work_chunks: list[list[str]], phase: str) -> tuple[dict[str, str], list[str]]:
                    phase_translated: dict[str, str] = {}
                    phase_missing: list[str] = []
                    if not work_chunks:
                        return phase_translated, phase_missing

                    self._record_live_debug("api", "parallel_batch_wave", {
                        "candidate_count": sum(len(chunk) for chunk in work_chunks),
                        "batch_count": len(work_chunks),
                        "batch_size": max(len(chunk) for chunk in work_chunks),
                        "concurrency": concurrency,
                        "window_size": config["windowSize"],
                        "phase": phase,
                    })

                    def translate_chunk(chunk: list[str]) -> tuple[dict[str, str], list[str]]:
                        interval = float(config["requestIntervalMs"]) / 1000.0
                        with request_lock:
                            delay = max(0.0, next_request_at[0] - time.monotonic())
                            next_request_at[0] = max(next_request_at[0], time.monotonic()) + interval
                        if delay:
                            time.sleep(delay)
                        return self._translate_live_candidates_with_repair(service, chunk, debug_config)

                    with ThreadPoolExecutor(max_workers=min(concurrency, len(work_chunks)), thread_name_prefix="renpy-live-batch") as pool:
                        futures = {pool.submit(translate_chunk, chunk): chunk for chunk in work_chunks}
                        for future in as_completed(futures):
                            chunk = futures[future]
                            try:
                                chunk_translated, chunk_missing = future.result()
                                phase_translated.update(chunk_translated)
                                phase_missing.extend(chunk_missing)
                            except Exception as exc:
                                phase_missing.extend(chunk)
                                self._record_live_debug("error", "batch_request_failed", {"count": len(chunk), "sources": chunk, "error": str(exc), "phase": phase})
                    return phase_translated, phase_missing

                initial_translated, missing = translate_chunks_parallel(chunks, "primary")
                translated.update(initial_translated)

                # Some providers reject a large JSON batch but answer the same
                # entries correctly in a smaller request. Retry those entries in
                # compact batches while retaining the user's concurrency limit;
                # never degrade a failed 50-item batch into 50 serial calls.
                if missing and batch_size > 1:
                    repair_size = max(2, min(20, (batch_size + 2) // 3))
                    repair_chunks = [missing[index:index + repair_size] for index in range(0, len(missing), repair_size)]
                    self._record_live_debug("api", "parallel_repair_wave", {
                        "candidate_count": len(missing),
                        "batch_count": len(repair_chunks),
                        "batch_size": repair_size,
                        "concurrency": concurrency,
                    })
                    repaired, missing = translate_chunks_parallel(repair_chunks, "repair")
                    translated.update(repaired)

                # Futures finish in arbitrary order; restore the game-script
                # order before requeuing so current/upcoming dialogue keeps its
                # natural priority even after a parallel retry wave.
                missing = [source for source in candidates if source not in translated]

                # A partial batch response must not make the player wait for a
                # normal exponential retry.  Give the currently visible line
                # one focused request immediately; all look-ahead lines remain
                # on the configured parallel batch path.
                if current_source and current_source in missing:
                    self._record_live_debug("api", "urgent_current_retry", {"source": current_source})
                    try:
                        urgent_targets = self._translate_openai_compatible([current_source], debug_config)
                        urgent_translated, _ = self._filter_live_translations(service, [current_source], urgent_targets)
                        if urgent_translated:
                            translated.update(urgent_translated)
                            missing = [source for source in missing if source != current_source]
                    except Exception as exc:
                        self._record_live_debug("error", "urgent_current_retry_failed", {"source": current_source, "error": str(exc)})

                if translated:
                    service.merge_live_translations(translated, kind="automatic")
                    self._record_live_debug("inject", "merge_live_translations", {"count": len(translated), "translations": translated})
                    with self.lock:
                        for entry in self.translation_entries:
                            if entry.source in translated:
                                entry.target = translated[entry.source]
                        self.live_worker_stats["translated"] = int(self.live_worker_stats.get("translated", 0)) + len(translated)
                    if self.project:
                        self._persist_translation_cache()
                    for source in translated:
                        source_attempts.pop(source, None)
                        retry_after.pop(source, None)
                if missing:
                    service.requeue_live_translation_candidates(missing)
                    self._record_live_debug("filter", "translation_rejected", {"count": len(missing), "sources": missing})
                    for source in missing:
                        source_attempts[source] = source_attempts.get(source, 0) + 1
                        retry_delay = 0.5 if source == current_source else min(30.0, 2.0 ** min(source_attempts[source], 5))
                        retry_after[source] = time.monotonic() + retry_delay
                    with self.lock:
                        if any(source_attempts.get(source, 0) >= 3 for source in missing):
                            self.live_worker_stats["failures"] = int(self.live_worker_stats.get("failures", 0)) + len(missing)
                        self.live_worker_stats["lastError"] = f"{len(missing)} 条译文暂未可用，已自动拆小批并延迟重试。"
                failure_streak = 0
                with self.lock:
                    self.live_worker_stats["state"] = "waiting"
                    self.live_worker_stats["activeBatches"] = 0
                    if not missing:
                        self.live_worker_stats["lastError"] = ""
            except Exception as exc:
                service.requeue_live_translation_candidates(candidates)
                self._record_live_debug("error", "live_worker_exception", {"error": str(exc), "sources": candidates})
                failure_streak += 1
                with self.lock:
                    self.live_worker_stats["failures"] = int(self.live_worker_stats.get("failures", 0)) + 1
                    self.live_worker_stats.update({"state": "retrying", "activeBatches": 0, "lastError": str(exc)})
                stop_event.wait(min(30.0, 2.0 ** min(failure_streak, 5)))
        with self.lock:
            self.live_worker_stats["running"] = False
            self.live_worker_stats["state"] = "stopped"

    def ai_translate(self, body: JsonDict) -> JsonDict:
        entries = self._normalize_ai_entries(body.get("entries") or [])
        if entries:
            provider = str(body.get("provider") or "OpenAI")
            if provider == "\u767e\u5ea6\u7ffb\u8bd1":
                translations = self._translate_baidu([entry["source"] for entry in entries], body)
                return {"ok": True, "translations": [{"entry_id": entry["entry_id"], "target": translations[index] if index < len(translations) else ""} for index, entry in enumerate(entries)]}
            if provider in {"Google \u514d\u8d39", "MyMemory", "LibreTranslate"}:
                translations = self._translate_public_mt([entry["source"] for entry in entries], body)
                return {"ok": True, "translations": [{"entry_id": entry["entry_id"], "target": translations[index] if index < len(translations) else ""} for index, entry in enumerate(entries)]}
            return {"ok": True, "translations": self._translate_entries_openai_compatible(entries, body)}

        texts = body.get("texts") or []
        if isinstance(texts, str):
            texts = [texts]
        texts = [str(t) for t in texts if str(t).strip()]
        if not texts:
            return {"translations": []}
        provider = str(body.get("provider") or "OpenAI")
        if provider == "\u767e\u5ea6\u7ffb\u8bd1":
            translations = self._translate_baidu(texts, body)
        elif provider in {"Google \u514d\u8d39", "MyMemory", "LibreTranslate"}:
            translations = self._translate_public_mt(texts, body)
        else:
            translations = self._translate_openai_compatible(texts, body)
        return {"ok": True, "translations": translations}

    def _merged_translation_list(self, body: JsonDict) -> list[TranslationEntry]:
        if not self.translation_entries:
            self.translation_entries = self._service().extract_translations()
        index = {e.entry_id: TranslationEntry(e.entry_id, e.source, e.target, e.file, e.context, e.category) for e in self.translation_entries}
        for raw in body.get("entries") or body.get("updates") or []:
            if isinstance(raw, dict):
                entry_id = str(raw.get("entry_id") or raw.get("id") or "")
                if entry_id in index:
                    index[entry_id] = _entry_from_raw(raw, index[entry_id])
        entries = self._filter_safe_translation_entries(list(index.values()))
        for entry in entries:
            self._validate_translation_target(entry.source, entry.target)
        return entries

    def _validate_translation_target(self, source: str, target: str) -> None:
        if not target or not self.project:
            return
        if self.project.engine == "RPG Maker MV/MZ" and not RPGMakerService.control_tokens_preserved(source, target):
            raise ApiError(f"译文控制符不完整：{source[:80]}")
        if self.project.engine == "Ren'Py" and not RenPyService.control_tokens_preserved(source, target):
            raise ApiError(f"Ren'Py 控制符不完整：{source[:80]}")

    def _merged_translation_map(self, body: JsonDict) -> dict[str, TranslationEntry]:
        return {entry.entry_id: entry for entry in self._merged_translation_list(body)}

    def _project(self) -> ProjectInfo:
        if not self.project:
            raise ApiError("尚未载入项目。", 409)
        return self.project

    def _service(self) -> RPGMakerService | RenPyService:
        project = self._project()
        if project.engine == "RPG Maker MV/MZ":
            return RPGMakerService(project)
        if project.engine == "Ren'Py":
            return RenPyService(project)
        raise ApiError(f"暂不支持该引擎：{project.engine}")

    def _save_preview(self, payload: JsonDict) -> JsonDict:
        party = payload.get("party", {}) if isinstance(payload, dict) else {}
        actors = payload.get("actors", {}).get("_data", []) if isinstance(payload.get("actors"), dict) else []
        return {
            "party": {k: party.get(k) for k in ["_gold", "_steps"] if isinstance(party, dict)},
            "items": party.get("_items", {}) if isinstance(party, dict) else {},
            "weapons": party.get("_weapons", {}) if isinstance(party, dict) else {},
            "armors": party.get("_armors", {}) if isinstance(party, dict) else {},
            "actors": actors[:50] if isinstance(actors, list) else [],
        }

    @staticmethod
    def _normalize_ai_entries(raw_entries: Any) -> list[JsonDict]:
        if not isinstance(raw_entries, list):
            return []
        entries: list[JsonDict] = []
        for index, raw in enumerate(raw_entries):
            if not isinstance(raw, dict):
                continue
            source = str(raw.get("source") or "")
            if not source.strip():
                continue
            entry_id = str(raw.get("entry_id") or raw.get("id") or f"entry_{index}")
            entries.append({
                "entry_id": entry_id,
                "source": source,
                "file": str(raw.get("file") or ""),
                "context": str(raw.get("context") or ""),
                "category": str(raw.get("category") or ""),
            })
        return entries

    def _translate_entries_openai_compatible(self, entries: list[JsonDict], body: JsonDict) -> list[JsonDict]:
        provider = self._normalize_ai_provider(str(body.get("provider") or "openai"))
        api_key = str(body.get("apiKey") or "")
        model = str(body.get("model") or self._default_model(provider))
        base_url = str(body.get("baseUrl") or self._default_base_url(provider)).rstrip("/")
        if not base_url:
            raise ApiError("缺少 Base URL。")
        if not api_key and provider != "ollama":
            raise ApiError("缺少 API Key。")
        target_lang = str(body.get("targetLang") or "简体中文")
        source_lang = str(body.get("sourceLang") or "自动")
        compact_entries = [
            {
                "entry_id": entry["entry_id"],
                "source": entry["source"],
                "category": entry.get("category", ""),
                "file": entry.get("file", ""),
                "context": entry.get("context", ""),
            }
            for entry in entries
        ]
        prompt = (
            "你是专业游戏本地化译者。请把输入 JSON 中每个 source 从"
            f"{source_lang}翻译成{target_lang}，尤其必须输出简体中文译文。"
            "保持 RPG Maker/Ren'Py 控制符、变量、占位符、颜色/名称标签、转义符和换行不变。"
            "不要改 entry_id，不要合并或删除条目。除非 source 已经是目标语言、纯数字、纯符号或不可翻译控制符，否则不要原样照抄 source。"
            "只返回严格 JSON 对象，格式为 {\"translations\": {\"entry_id\": \"译文\"}}，不要 Markdown，不要解释。"
        )
        user_payload = json.dumps({"entries": compact_entries}, ensure_ascii=False)
        if provider == "anthropic":
            url = base_url + "/messages" if base_url.endswith("/v1") else base_url + "/v1/messages"
            payload = {
                "model": model,
                "max_tokens": int(body.get("maxTokens") or 4096),
                "temperature": float(body.get("temperature", 0.2)),
                "system": prompt,
                "messages": [{"role": "user", "content": user_payload}],
            }
            raw = self._http_json(url, payload, {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}, timeout=self._ai_timeout(body))
            blocks = raw.get("content") or []
            content = "".join(str(item.get("text") or "") for item in blocks if isinstance(item, dict))
        else:
            url = base_url
            if not url.endswith("/chat/completions"):
                url += "/chat/completions" if url.endswith("/v1") else "/v1/chat/completions"
            payload = {
                "model": model,
                "max_tokens": int(body.get("maxTokens") or 8192),
                "temperature": float(body.get("temperature", 0.2)),
                "stream": False,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_payload},
                ],
            }
            headers = {"Content-Type": "application/json"}
            if api_key and provider != "ollama":
                headers["Authorization"] = f"Bearer {api_key}"
            try:
                raw = self._http_json(url, payload, headers, timeout=self._ai_timeout(body))
            except ApiError as exc:
                # Some OpenAI-compatible gateways reject response_format or max_tokens.
                # Retry once with the portable request shape instead of losing a whole batch.
                if exc.status not in {400, 404, 422}:
                    raise
                payload.pop("response_format", None)
                payload.pop("max_tokens", None)
                raw = self._http_json(url, payload, headers, timeout=self._ai_timeout(body))
            content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
            if isinstance(content, list):
                content = "".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
        mapping = self._parse_translation_map(content, [entry["entry_id"] for entry in entries])
        return [{"entry_id": entry["entry_id"], "target": mapping.get(entry["entry_id"], "")} for entry in entries]

    def _translate_openai_compatible(self, texts: list[str], body: JsonDict) -> list[str]:
        provider = self._normalize_ai_provider(str(body.get("provider") or "openai"))
        api_key = str(body.get("apiKey") or "")
        model = str(body.get("model") or self._default_model(provider))
        base_url = str(body.get("baseUrl") or self._default_base_url(provider)).rstrip("/")
        if not base_url:
            raise ApiError("缺少 Base URL。")
        if not api_key and provider != "ollama":
            raise ApiError("缺少 API Key。")
        target_lang = str(body.get("targetLang") or "简体中文")
        source_lang = str(body.get("sourceLang") or "自动")
        prompt = (
            f"你是专业视觉小说本地化译者。把输入数组中的 {source_lang} 游戏文本逐条翻译为 {target_lang}。"
            "只翻译玩家可见的台词、旁白与选项；保留 Ren'Py/RPG Maker 控制符、变量、文本标签、换行、占位符和人名标记，例如 [mc]、{i}、{w}。"
            "译文要自然、符合角色语气；不要翻译路径、文件名或代码。"
            "输出必须且只能是一个 JSON 对象，格式严格为 {\"translations\":[\"译文1\",\"译文2\"]}。"
            "translations 数组长度必须等于输入长度，按原顺序对应；不要 Markdown、不要解释、不要把原文作为 JSON 的键。"
        )
        if provider == "anthropic":
            url = base_url + "/messages" if base_url.endswith("/v1") else base_url + "/v1/messages"
            payload = {
                "model": model,
                "max_tokens": int(body.get("maxTokens") or 4096),
                "temperature": float(body.get("temperature", 0.2)),
                "system": prompt,
                "messages": [{"role": "user", "content": json.dumps(texts, ensure_ascii=False)}],
            }
            if body.get("_debugLive"):
                self._record_live_debug("api", "submit_request", {"provider": provider, "url": url, "count": len(texts), "texts": texts, "payload": payload})
            raw = self._http_json(url, payload, {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}, timeout=self._ai_timeout(body))
            if body.get("_debugLive"):
                self._record_live_debug("api", "raw_response", {"provider": provider, "raw": raw})
            blocks = raw.get("content") or []
            content = "".join(str(item.get("text") or "") for item in blocks if isinstance(item, dict))
            result = self._parse_translation_array(content, len(texts))
            if body.get("_debugLive"):
                self._record_live_debug("api", "response_content", {"content": content, "translations": result})
            return result
        url = base_url
        if not url.endswith("/chat/completions"):
            url += "/chat/completions" if url.endswith("/v1") else "/v1/chat/completions"
        payload = {
            "model": model,
            "max_tokens": int(body.get("maxTokens") or 8192),
            "temperature": float(body.get("temperature", 0.2)),
            "stream": False,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(texts, ensure_ascii=False)},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if api_key and provider != "ollama":
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            if body.get("_debugLive"):
                self._record_live_debug("api", "submit_request", {"provider": provider, "url": url, "count": len(texts), "texts": texts, "payload": payload, "headers": headers})
            raw = self._http_json(url, payload, headers, timeout=self._ai_timeout(body))
        except ApiError as exc:
            if exc.status not in {400, 404, 422}:
                raise
            payload.pop("response_format", None)
            payload.pop("max_tokens", None)
            if body.get("_debugLive"):
                self._record_live_debug("api", "retry_request", {"provider": provider, "url": url, "reason": str(exc), "payload": payload, "headers": headers})
            raw = self._http_json(url, payload, headers, timeout=self._ai_timeout(body))
        if body.get("_debugLive"):
            self._record_live_debug("api", "raw_response", {"provider": provider, "raw": raw})
        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
        result = self._parse_translation_array(content, len(texts))
        if body.get("_debugLive"):
            self._record_live_debug("api", "response_content", {"content": content, "translations": result})
        return result

    def _translate_baidu(self, texts: list[str], body: JsonDict) -> list[str]:
        appid = str(body.get("appId") or body.get("apiKey") or "")
        secret = str(body.get("secret") or body.get("apiSecret") or "")
        if not appid or not secret:
            raise ApiError("百度翻译需要 appId/apiKey 和 secret。")
        q = "\n".join(texts)
        salt = str(int(time.time() * 1000))
        sign = hashlib.md5((appid + q + salt + secret).encode("utf-8")).hexdigest()
        params = urllib.parse.urlencode({"q": q, "from": body.get("from") or "auto", "to": body.get("to") or "zh", "appid": appid, "salt": salt, "sign": sign})
        req = urllib.request.Request("https://fanyi-api.baidu.com/api/trans/vip/translate", data=params.encode("utf-8"), headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        if "error_code" in raw:
            raise ApiError(f"百度翻译失败：{raw.get('error_msg') or raw.get('error_code')}")
        translated = "\n".join(item.get("dst", "") for item in raw.get("trans_result", []))
        parts = translated.split("\n")
        return (parts + [""] * len(texts))[: len(texts)]

    def _translate_public_mt(self, texts: list[str], body: JsonDict) -> list[str]:
        provider = str(body.get("provider") or "MyMemory")
        if provider == "LibreTranslate":
            base_url = str(body.get("baseUrl") or "https://libretranslate.com").rstrip("/")
            result = []
            for text in texts:
                payload = {"q": text, "source": body.get("from") or "auto", "target": body.get("to") or "zh", "format": "text"}
                if body.get("apiKey"):
                    payload["api_key"] = body.get("apiKey")
                raw = self._http_json(base_url + "/translate", payload, {"Content-Type": "application/json"}, timeout=60)
                result.append(str(raw.get("translatedText") or ""))
            return result
        result = []
        for text in texts:
            params = urllib.parse.urlencode({"q": text, "langpair": f"{body.get('from') or 'auto'}|{body.get('to') or 'zh-CN'}"})
            with urllib.request.urlopen("https://api.mymemory.translated.net/get?" + params, timeout=60) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            result.append(str(raw.get("responseData", {}).get("translatedText") or ""))
        return result
    @staticmethod
    def _ai_timeout(body: JsonDict) -> int:
        raw = _first_present(body.get("requestTimeoutSec"), body.get("timeout"), body.get("readTimeoutSec"))
        return _clamp_int(raw, 240, 30, 900)

    def _http_json(self, url: str, payload: JsonDict, headers: JsonDict, timeout: int = 120) -> JsonDict:
        req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise ApiError(f"HTTP {exc.code}: {detail}", exc.code)
        except (TimeoutError, socket.timeout) as exc:
            raise ApiError(f"AI 请求超时：{exc}。实时翻译会自动拆分队列后重试。", 504)
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in str(reason).lower():
                raise ApiError(f"AI 请求超时：{reason}。实时翻译会自动拆分队列后重试。", 504)
            raise

    @staticmethod
    def _http_get_json(url: str, headers: JsonDict, timeout: int = 30) -> JsonDict:
        req = urllib.request.Request(url, headers={str(key): str(value) for key, value in headers.items()}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise ApiError(f"获取模型失败：HTTP {exc.code}: {detail}", exc.code) from exc
        except Exception as exc:
            raise ApiError(f"获取模型失败：{exc}", 502) from exc

    @staticmethod
    def _json_from_model_content(content: str) -> Any:
        text = str(content or "").strip()
        fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        candidates = [text]
        for open_char, close_char in (("{", "}"), ("[", "]")):
            start = text.find(open_char)
            end = text.rfind(close_char)
            if 0 <= start < end:
                candidates.append(text[start:end + 1])
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise ValueError("empty content")

    def _parse_translation_map(self, content: str, entry_ids: list[str]) -> dict[str, str]:
        try:
            parsed = self._json_from_model_content(content)
        except Exception:
            return {}
        values: dict[str, str] = {}
        raw_translations = parsed.get("translations") if isinstance(parsed, dict) else parsed
        if isinstance(raw_translations, dict):
            for entry_id in entry_ids:
                if entry_id in raw_translations:
                    values[entry_id] = str(raw_translations.get(entry_id) or "")
        elif isinstance(raw_translations, list):
            expected = set(entry_ids)
            for index, item in enumerate(raw_translations[:len(entry_ids)]):
                entry_id = entry_ids[index]
                if isinstance(item, dict):
                    raw_id = str(item.get("entry_id") or item.get("id") or "")
                    if raw_id in expected:
                        entry_id = raw_id
                    values[entry_id] = str(item.get("target") or item.get("translation") or item.get("text") or "")
                else:
                    values[entry_id] = str(item or "")
        return values

    def _parse_translation_array(self, content: str, expected: int) -> list[str]:
        try:
            parsed = self._json_from_model_content(content)
            if isinstance(parsed, list):
                values = [str(v) for v in parsed]
                return (values + [""] * expected)[:expected]
            if isinstance(parsed, dict) and isinstance(parsed.get("translations"), list):
                values = [str(v) for v in parsed["translations"]]
                return (values + [""] * expected)[:expected]
            if isinstance(parsed, dict) and isinstance(parsed.get("translations"), dict):
                values = [str(value) for value in parsed["translations"].values()]
                return (values + [""] * expected)[:expected]
            if isinstance(parsed, dict):
                # Common small-model variants: {"text":"..."},
                # {"translation":"..."}, or a single {"source":"target"}
                # mapping.  Accept the value, never the whole JSON string.
                for key in ("text", "translation", "target", "result", "content"):
                    if key in parsed and isinstance(parsed[key], (str, int, float)):
                        return [str(parsed[key])] + [""] * (expected - 1)
                scalar_values = [str(value) for value in parsed.values() if isinstance(value, (str, int, float))]
                if scalar_values:
                    return (scalar_values + [""] * expected)[:expected]
        except Exception:
            pass
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        return (lines + [content.strip()] + [""] * expected)[:expected]

    def _default_model(self, provider: str) -> str:
        return {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-haiku-latest",
            "ollama": "",
            "OpenAI": "gpt-4o-mini",
            "DeepSeek": "deepseek-chat",
            "Doubao": "doubao-seed-2-0-mini",
            "GLM": "glm-4-flash",
            "NVIDIA": "meta/llama-3.1-70b-instruct",
            "Xiaomi Token Plan": "gpt-4o-mini",
            "Ollama 本地模型": "qwen2.5:7b",
        }.get(provider, "gpt-4o-mini")

    def _default_base_url(self, provider: str) -> str:
        return {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com",
            "ollama": "http://127.0.0.1:11434",
            "OpenAI": "https://api.openai.com/v1",
            "DeepSeek": "https://api.deepseek.com/v1",
            "Doubao": "https://ark.cn-beijing.volces.com/api/v3",
            "GLM": "https://open.bigmodel.cn/api/paas/v4",
            "NVIDIA": "https://integrate.api.nvidia.com/v1",
            "Xiaomi Token Plan": "https://api.chat.xiaomi.com/v1",
            "Ollama 本地模型": "http://127.0.0.1:11434/v1",
        }.get(provider, "")


class Handler(BaseHTTPRequestHandler):
    api: ToolkitApi

    def log_message(self, format: str, *args: Any) -> None:
        if os.environ.get("RPGRL_API_DEBUG"):
            super().log_message(format, *args)

    def do_OPTIONS(self) -> None:
        self._send(204, None)

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = dict(urllib.parse.parse_qsl(parsed.query))
        try:
            body = self._read_json() if method == "POST" else {}
            result = route(self.api, method, path, query, body)
            self._send(200, {"ok": True, "data": _plain(result)})
        except ApiError as exc:
            self._send(exc.status, {"ok": False, "error": str(exc)})
        except Exception as exc:
            traceback.print_exc()
            self._send(500, {"ok": False, "error": str(exc), "traceback": traceback.format_exc()})

    def _read_json(self) -> JsonDict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        if not raw:
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ApiError("请求体必须是 JSON 对象。")
        return data

    def _send(self, status: int, payload: Any) -> None:
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if payload is None:
            self.end_headers()
            return
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def route(api: ToolkitApi, method: str, path: str, query: JsonDict, body: JsonDict) -> Any:
    if method == "GET" and path == "/health": return api.health()
    if method == "GET" and path == "/settings": return api.settings_get()
    if method == "POST" and path == "/settings": return api.settings_save(body)
    if method == "GET" and path == "/library": return api.library_get()
    if method == "POST" and path == "/library/add": return api.library_add(body)
    if method == "POST" and path == "/library/add-folder": return api.library_add_folder(body)
    if method == "POST" and path == "/library/remove": return api.library_remove(body)
    if method == "POST" and path == "/library/launch": return api.library_launch(body)
    if method == "GET" and path == "/game/status": return api.game_status()
    if method == "POST" and path == "/project/load": return api.load_project(body)
    if method == "GET" and path == "/project/summary": return api.project_summary()
    if method == "POST" and path == "/project/launch": return api.launch_project(body)
    if method == "GET" and path == "/translations": return api.translations(query)
    if method == "POST" and path == "/translations/save-targets": return api.translations_save_targets(body)
    if method == "POST" and path == "/translations/apply": return api.translations_apply(body)
    if method == "POST" and path == "/translations/export": return api.translations_export(body)
    if method == "POST" and path == "/translations/import": return api.translations_import(body)
    if method == "POST" and path == "/translations/runtime": return api.translations_runtime(body)
    if method == "POST" and path == "/rpgmaker/install-bridge": return api.rpgmaker_install_bridge()
    if method == "POST" and path == "/renpy/install-extractor": return api.renpy_install_extractor(body)
    if method == "POST" and path == "/renpy/install-live-bridge": return api.renpy_install_live_bridge(body)
    if method == "POST" and path == "/renpy/restore": return api.renpy_restore()
    if method == "GET" and path == "/data": return api.data_records_get(query)
    if method == "POST" and path == "/data/update": return api.data_update(body)
    if method == "GET" and path == "/saves/slots": return api.save_slots()
    if method == "POST" and path == "/saves/load": return api.save_load(body)
    if method == "GET" and path == "/saves/current": return api.save_current()
    if method == "POST" and path == "/saves/mutate": return api.save_mutate(body)
    if method == "POST" and path == "/saves/write": return api.save_write(body)
    if method == "GET" and path == "/maps": return api.maps_get()
    if method == "GET" and path == "/maps/detail": return api.map_detail(query)
    if method == "GET" and path == "/runtime/state": return api.runtime_state()
    if method == "POST" and path == "/runtime/set": return api.runtime_set(body)
    if method == "POST" and path == "/live/start": return api.live_start(body)
    if method == "POST" and path == "/live/stop": return api.live_stop()
    if method == "GET" and path == "/live/status": return api.live_status()
    if method == "GET" and path == "/live/debug": return api.live_debug(query)
    if method == "POST" and path == "/live/merge": return api.live_merge(body)
    if method == "POST" and path == "/live/refresh": return api.live_refresh()
    if method == "POST" and path == "/live/force-text": return api.live_force_text(body)
    if method == "POST" and path == "/ai/translate": return api.ai_translate(body)
    if method == "POST" and path == "/ai/models": return api.ai_models(body)
    raise ApiError(f"未知接口：{method} {path}", 404)


def main() -> None:
    parser = argparse.ArgumentParser(description="RPGRenPyLocalizer local API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()
    port = args.port or _free_port()
    Handler.api = ToolkitApi(Path(args.project_root).resolve())
    server = ThreadingHTTPServer((args.host, port), Handler)
    print(json.dumps({"ready": True, "host": args.host, "port": port}, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
