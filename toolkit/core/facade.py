from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from ..detectors import detect_project
from ..models import ProjectInfo
from ..renpy import RenPyService
from ..rpgmaker import RPGMakerService


def _to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return _to_plain(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_to_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_plain(item) for key, item in value.items()}
    return value


class ToolkitCore:
    def __init__(self) -> None:
        self.project: ProjectInfo | None = None

    def load_project(self, path: str | Path) -> dict[str, Any]:
        self.project = detect_project(path)
        return self.project_summary()

    def project_summary(self) -> dict[str, Any]:
        project = self._require_project()
        summary = {
            "engine": project.engine,
            "root": str(project.root),
            "game_dir": str(project.game_dir),
            "launcher_path": str(project.launcher_path) if project.launcher_path else "",
            "data_dir": str(project.data_dir) if project.data_dir else "",
            "scripts_dir": str(project.scripts_dir) if project.scripts_dir else "",
            "supports_rpgmaker": project.engine.startswith("RPG Maker"),
            "supports_renpy": project.engine == "Ren'Py",
            "supports_webview": project.engine == "RPG Maker MV/MZ" and (project.game_dir / "index.html").exists(),
        }
        if project.engine == "RPG Maker MV/MZ" and project.data_dir:
            service = RPGMakerService(project)
            summary["translation_entries"] = len(service.extract_translations())
            summary["data_records"] = len(service.list_data_records())
            summary["maps"] = len(service.list_maps())
            summary["categories"] = _to_plain([
                {"id": "Actors.json", "label": "角色"},
                {"id": "Items.json", "label": "物品"},
                {"id": "MapInfos.json", "label": "地图"},
            ])
        elif project.engine == "Ren'Py" and project.scripts_dir:
            service = RenPyService(project)
            summary["translation_entries"] = len(service.extract_translations())
            summary["data_records"] = len(service.list_data_records())
            summary["categories"] = _to_plain([
                {"id": "scripts", "label": "脚本"},
                {"id": "archives", "label": "封包"},
            ])
        return summary

    def translation_entries(self, limit: int = 80) -> dict[str, Any]:
        service = self._service()
        entries = service.extract_translations()
        return {"count": len(entries), "entries": _to_plain(entries[: max(1, min(limit, 500))])}

    def data_records(self, category: str = "", limit: int = 120) -> dict[str, Any]:
        service = self._service()
        records = service.list_data_records()
        if category:
            records = [record for record in records if record.category == category or record.file == category]
        return {"count": len(records), "records": _to_plain(records[: max(1, min(limit, 500))])}

    def maps(self) -> dict[str, Any]:
        project = self._require_project()
        if project.engine != "RPG Maker MV/MZ":
            return {"count": 0, "maps": []}
        service = RPGMakerService(project)
        maps = service.list_maps()
        return {"count": len(maps), "maps": _to_plain(maps)}

    def map_detail(self, map_id: int) -> dict[str, Any]:
        project = self._require_project()
        if project.engine != "RPG Maker MV/MZ":
            raise ValueError("当前引擎不支持地图详情。")
        service = RPGMakerService(project)
        return _to_plain(service.map_detail(map_id))

    def _service(self) -> RPGMakerService | RenPyService:
        project = self._require_project()
        if project.engine == "RPG Maker MV/MZ":
            return RPGMakerService(project)
        if project.engine == "Ren'Py":
            return RenPyService(project)
        raise ValueError("当前引擎不支持该操作。")

    def _require_project(self) -> ProjectInfo:
        if not self.project:
            raise ValueError("尚未载入项目。")
        return self.project

