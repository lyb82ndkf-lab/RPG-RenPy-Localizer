from __future__ import annotations

import argparse
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

from toolkit.detectors import detect_project
from toolkit.models import DataRecord, ProjectInfo, TranslationEntry
from toolkit.renpy import RenPyService
from toolkit.rpgmaker import RPGMakerService, load_json
from toolkit.storage import export_translation_pack, import_translation_pack, translation_pack_signature
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
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.workspace = Workspace(project_root)
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
        settings["ai_profiles"] = profiles
        settings["ai"] = {
            "provider": provider,
            "apiKey": "" if provider == "ollama" else str(raw_ai.get("apiKey") or current["apiKey"] or settings.get("openai_api_key") or ""),
            "baseUrl": str((raw_ai.get("baseUrl") if legacy_provider == provider else "") or current["baseUrl"]),
            "model": str((raw_ai.get("model") if legacy_provider == provider else "") or current["model"]),
            "availableModels": current["models"],
            "targetLang": str(raw_ai.get("targetLang") or settings.get("ai_target_lang") or "简体中文"),
            "batchSize": int(raw_ai.get("batchSize") or settings.get("ai_batch_size") or 20),
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
            settings.update({
                "ai_provider": provider,
                "ai_api_keys": keys,
                "ai_base_urls": urls,
                "ai_models": models,
                "ai_model": models[provider],
                "ai_target_lang": str(ai.get("targetLang") or "简体中文"),
                "ai_batch_size": int(ai.get("batchSize") or 20),
            })
        self.workspace.save_settings(settings)
        return {"ok": True, "settings": settings}

    def library_get(self) -> JsonDict:
        return {"ok": True, "entries": _plain(self.workspace.load_library())}

    def library_add(self, body: JsonDict) -> JsonDict:
        if self._active_game_path():
            raise ApiError("游戏运行中，不能添加或更换游戏。", 409)
        raw_path = str(body.get("path") or "").strip()
        if not raw_path:
            raise ApiError("缺少游戏路径。")
        project = detect_project(Path(raw_path).expanduser())
        entries = self.workspace.load_library()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        launcher = str(project.launcher_path) if project.launcher_path else ""
        existing = next((entry for entry in entries if entry.path == str(project.root)), None)
        if existing:
            existing.name = project.root.name
            existing.engine = project.engine
            existing.launcher_path = launcher
            existing.last_opened_at = now
        else:
            entries.insert(0, LibraryEntry(name=project.root.name, path=str(project.root), engine=project.engine, added_at=now, last_opened_at=now, launcher_path=launcher, note="", tags=[]))
        self.workspace.save_library(entries)
        return {"ok": True, "entries": _plain(entries)}

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
        launcher = Path(entry.launcher_path) if entry.launcher_path else Path(entry.path) / "Game.exe"
        if not launcher.exists():
            raise ApiError(f"找不到游戏启动文件：{launcher}", 404)
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
        project = requested
        with self.lock:
            self.project = project
            self.translation_entries = []
            self.data_records = []
            self.save_payload = None
            self.save_path = None
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
        launcher = Path(str(body.get("launcherPath") or project.launcher_path or ""))
        if not launcher.exists():
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
        entries = self.translation_entries
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
        categories = sorted({e.category or e.file for e in self.translation_entries if e.category or e.file})
        return {"count": len(entries), "total": len(self.translation_entries), "categories": categories, "entries": _plain(entries[offset: offset + limit])}

    def translations_save_targets(self, body: JsonDict) -> JsonDict:
        updates = body.get("updates") or []
        if not isinstance(updates, list):
            raise ApiError("updates 必须是数组。")
        if not self.translation_entries:
            self.translation_entries = self._service().extract_translations()
        index = {e.entry_id: e for e in self.translation_entries}
        changed = 0
        for raw in updates:
            if not isinstance(raw, dict):
                continue
            entry_id = str(raw.get("entry_id") or raw.get("id") or "")
            if entry_id in index:
                index[entry_id].target = str(raw.get("target") or "")
                changed += 1
        return {"ok": True, "changed": changed}
    def translations_apply(self, body: JsonDict) -> JsonDict:
        translations = self._merged_translation_map(body)
        changed = self._service().apply_translations(translations)
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
        index = {e.entry_id: e for e in self.translation_entries}
        matched = 0
        for entry_id, imported_entry in imported.items():
            if entry_id in index:
                index[entry_id].target = imported_entry.target
                matched += 1
        return {"ok": True, "matched": matched, "imported": len(imported)}

    def translations_runtime(self, body: JsonDict) -> JsonDict:
        project = self._project()
        translations = self._merged_translation_map(body)
        if project.engine == "RPG Maker MV/MZ":
            path, launcher, changed = RPGMakerService(project).build_runtime_copy(translations)
            return {"ok": True, "path": str(path), "launcher": str(launcher) if launcher else "", "changed": changed}
        if project.engine == "Ren'Py":
            path, changed = RenPyService(project).build_runtime_translation_patch(translations)
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
            raise ApiError("无法连接游戏实时组件，请先安装组件、重启游戏并进入地图。", 503) from exc
        if not isinstance(result, dict) or not result.get("ok", True):
            raise ApiError(str(result.get("error") if isinstance(result, dict) else "实时组件返回异常"), 502)
        return result

    def live_start(self, body: JsonDict) -> JsonDict:
        service = self._service()
        if isinstance(service, RenPyService):
            service.install_live_translation_bridge(bool(body.get("clearEvents", False)))
            if self.translation_entries:
                translated = {entry.source: entry.target for entry in self.translation_entries if entry.source.strip() and entry.target.strip()}
                if translated:
                    service.merge_live_translations(translated, kind="loaded")
            if body.get("autoTranslate", True):
                self._start_live_worker(service)
        elif hasattr(service, "start_live_bridge_server"):
            service.start_live_bridge_server(bool(body.get("clearEvents", False)))
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
            return status
        return {"running": False}

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

    @staticmethod
    def _is_live_translation_source(text: str) -> bool:
        value = str(text or "").strip()
        if len(value) < 2 or len(value) > 2000:
            return False
        clean = re.sub(r"\{[^}]*\}", "", value).strip()
        if not clean or re.fullmatch(r"[\W_]+", clean):
            return False
        lowered = clean.lower()
        if re.fullmatch(r"https?://\S+|www\.\S+", lowered):
            return False
        if re.fullmatch(r"\S+\.(?:png|jpe?g|webp|ogg|wav|mp3|json|rpyc?|rpa|exe)", lowered):
            return False
        return any("a" <= char.lower() <= "z" or "\u3040" <= char <= "\u30ff" or "\u4e00" <= char <= "\u9fff" for char in clean)

    def _live_ai_config(self) -> JsonDict:
        settings = self.settings_get()
        ai = settings.get("ai") if isinstance(settings.get("ai"), dict) else {}
        return {
            "provider": str(ai.get("provider") or "openai-compatible"),
            "apiKey": str(ai.get("apiKey") or ""),
            "baseUrl": str(ai.get("baseUrl") or ""),
            "model": str(ai.get("model") or ""),
            "targetLang": str(ai.get("targetLang") or "简体中文"),
            "batchSize": max(1, min(int(ai.get("batchSize") or 20), 50)),
        }

    def _start_live_worker(self, service: RenPyService) -> None:
        project_root = str(service.project.root.resolve())
        if self.live_worker_thread and self.live_worker_thread.is_alive() and self.live_worker_project == project_root:
            return
        self._stop_live_worker()
        self.live_worker_stop = threading.Event()
        self.live_worker_project = project_root
        with self.lock:
            self.live_worker_stats = {"running": True, "state": "waiting", "translated": 0, "failures": 0, "lastError": "", "lastSource": "", "startedAt": time.time()}
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

    def _live_worker_loop(self, service: RenPyService, stop_event: threading.Event, project_root: str) -> None:
        failure_streak = 0
        source_attempts: dict[str, int] = {}
        retry_after: dict[str, float] = {}
        while not stop_event.is_set() and self.live_worker_project == project_root:
            config = self._live_ai_config()
            batch_size = int(config["batchSize"])
            now = time.monotonic()
            raw_candidates = service.take_live_translation_candidates(batch_size)
            deferred = [source for source in raw_candidates if self._is_live_translation_source(source) and retry_after.get(source, 0.0) > now]
            if deferred:
                service.requeue_live_translation_candidates(deferred)
            candidates = [source for source in raw_candidates if self._is_live_translation_source(source) and retry_after.get(source, 0.0) <= now]
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
                self.live_worker_stats.update({"state": "translating", "lastSource": candidates[0], "lastError": ""})
            try:
                targets = self._translate_openai_compatible(candidates, config)
                translated = {
                    source: str(target or "").strip()
                    for source, target in zip(candidates, targets)
                    if str(target or "").strip() and str(target or "").strip() != source and RenPyService.control_tokens_preserved(source, str(target or "").strip())
                }
                missing = [source for source in candidates if source not in translated]
                if translated:
                    service.merge_live_translations(translated, kind="automatic")
                    with self.lock:
                        for entry in self.translation_entries:
                            if entry.source in translated:
                                entry.target = translated[entry.source]
                        self.live_worker_stats["translated"] = int(self.live_worker_stats.get("translated", 0)) + len(translated)
                    for source in translated:
                        source_attempts.pop(source, None)
                        retry_after.pop(source, None)
                if missing:
                    service.requeue_live_translation_candidates(missing)
                    for source in missing:
                        source_attempts[source] = source_attempts.get(source, 0) + 1
                        retry_after[source] = time.monotonic() + min(30.0, 2.0 ** min(source_attempts[source], 5))
                    with self.lock:
                        self.live_worker_stats["failures"] = int(self.live_worker_stats.get("failures", 0)) + len(missing)
                        self.live_worker_stats["lastError"] = f"{len(missing)} 条译文为空、与原文相同或丢失控制符，已延迟重试。"
                failure_streak = 0
                with self.lock:
                    self.live_worker_stats["state"] = "waiting"
                    if not missing:
                        self.live_worker_stats["lastError"] = ""
            except Exception as exc:
                service.requeue_live_translation_candidates(candidates)
                failure_streak += 1
                with self.lock:
                    self.live_worker_stats["failures"] = int(self.live_worker_stats.get("failures", 0)) + 1
                    self.live_worker_stats.update({"state": "retrying", "lastError": str(exc)})
                stop_event.wait(min(30.0, 2.0 ** min(failure_streak, 5)))
        with self.lock:
            self.live_worker_stats["running"] = False
            self.live_worker_stats["state"] = "stopped"

    def ai_translate(self, body: JsonDict) -> JsonDict:
        texts = body.get("texts") or []
        if isinstance(texts, str):
            texts = [texts]
        texts = [str(t) for t in texts if str(t).strip()]
        if not texts:
            return {"translations": []}
        provider = str(body.get("provider") or "OpenAI")
        if provider == "百度翻译":
            translations = self._translate_baidu(texts, body)
        elif provider in {"Google 免费", "MyMemory", "LibreTranslate"}:
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
        return list(index.values())

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
        switches = payload.get("switches", {}).get("_data", []) if isinstance(payload.get("switches"), dict) else []
        variables = payload.get("variables", {}).get("_data", []) if isinstance(payload.get("variables"), dict) else []
        return {
            "party": {k: party.get(k) for k in ["_gold", "_steps"] if isinstance(party, dict)},
            "items": party.get("_items", {}) if isinstance(party, dict) else {},
            "weapons": party.get("_weapons", {}) if isinstance(party, dict) else {},
            "armors": party.get("_armors", {}) if isinstance(party, dict) else {},
            "actors": actors[:50] if isinstance(actors, list) else [],
            "switches": switches[:200] if isinstance(switches, list) else [],
            "variables": variables[:200] if isinstance(variables, list) else [],
        }

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
        prompt = f"你是专业游戏本地化译者。请把以下 {source_lang} 游戏文本翻译成 {target_lang}。保持 RPG Maker/Ren'Py 控制符、变量、换行和占位符不变。只返回 JSON 数组，顺序与输入一致，不要解释。"
        if provider == "anthropic":
            url = base_url + "/messages" if base_url.endswith("/v1") else base_url + "/v1/messages"
            payload = {
                "model": model,
                "max_tokens": int(body.get("maxTokens") or 4096),
                "temperature": float(body.get("temperature", 0.2)),
                "system": prompt,
                "messages": [{"role": "user", "content": json.dumps(texts, ensure_ascii=False)}],
            }
            raw = self._http_json(url, payload, {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}, timeout=int(body.get("timeout") or 120))
            blocks = raw.get("content") or []
            content = "".join(str(item.get("text") or "") for item in blocks if isinstance(item, dict))
            return self._parse_translation_array(content, len(texts))
        url = base_url
        if not url.endswith("/chat/completions"):
            url += "/chat/completions" if url.endswith("/v1") else "/v1/chat/completions"
        payload = {
            "model": model,
            "temperature": float(body.get("temperature", 0.2)),
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(texts, ensure_ascii=False)},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if api_key and provider != "ollama":
            headers["Authorization"] = f"Bearer {api_key}"
        raw = self._http_json(url, payload, headers, timeout=int(body.get("timeout") or 120))
        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
        return self._parse_translation_array(content, len(texts))

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
    def _http_json(self, url: str, payload: JsonDict, headers: JsonDict, timeout: int = 120) -> JsonDict:
        req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise ApiError(f"HTTP {exc.code}: {detail}", exc.code)

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

    def _parse_translation_array(self, content: str, expected: int) -> list[str]:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                values = [str(v) for v in parsed]
                return (values + [""] * expected)[:expected]
            if isinstance(parsed, dict) and isinstance(parsed.get("translations"), list):
                values = [str(v) for v in parsed["translations"]]
                return (values + [""] * expected)[:expected]
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
    if method == "POST" and path == "/live/merge": return api.live_merge(body)
    if method == "POST" and path == "/live/refresh": return api.live_refresh()
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
