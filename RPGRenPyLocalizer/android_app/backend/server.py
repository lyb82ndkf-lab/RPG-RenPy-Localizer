from __future__ import annotations

import json
import mimetypes
import sys
import traceback
from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from toolkit.detectors import detect_project  # noqa: E402
from toolkit.models import ProjectInfo  # noqa: E402
from toolkit.renpy import RenPyService  # noqa: E402
from toolkit.rpgmaker import RPGMakerService  # noqa: E402
from toolkit.storage import load_json  # noqa: E402


MOBILE_UI_DIR = ROOT / "android_app" / "mobile_ui"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 38765


class PrototypeState:
    def __init__(self) -> None:
        self.project: ProjectInfo | None = None
        self.last_error = ""


STATE = PrototypeState()


def dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        payload = asdict(value)
        return dataclass_to_dict(payload)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, tuple):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {str(key): dataclass_to_dict(item) for key, item in value.items()}
    return value


def project_to_dict(project: ProjectInfo) -> dict[str, Any]:
    payload = dataclass_to_dict(project)
    payload["supports_webview"] = bool(
        project.engine == "RPG Maker MV/MZ" and (project.game_dir / "index.html").exists()
    )
    payload["web_entry"] = str(project.game_dir / "index.html") if payload["supports_webview"] else ""
    payload["android_runtime_note"] = android_runtime_note(project)
    return payload


def android_runtime_note(project: ProjectInfo) -> str:
    if project.engine == "RPG Maker MV/MZ":
        web_ready = project.game_dir.joinpath("index.html").exists()
        if web_ready:
            return "RPG Maker MV/MZ 可优先用 Android WebView 直接加载 www/index.html。"
        return "RPG Maker MV/MZ 目录存在，但未找到 index.html，先检查游戏资源结构。"
    if project.engine == "Ren'Py":
        return "Ren'Py Windows exe 不能原生在 Android 运行，建议先做翻译补丁或导出 Ren'Py Android 包。"
    if project.launcher_path and project.launcher_path.suffix.lower() == ".exe":
        return "Android 不能原生运行 Windows exe，需要 Winlator/Wine 这类兼容层。"
    return "当前引擎在 Android 上需要进一步适配运行层。"


def current_service() -> RPGMakerService | RenPyService | None:
    project = STATE.project
    if not project:
        return None
    if project.engine == "RPG Maker MV/MZ":
        return RPGMakerService(project)
    if project.engine == "Ren'Py":
        return RenPyService(project)
    return None


def summarize_project(project: ProjectInfo) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "engine": project.engine,
        "root": str(project.root),
        "game_dir": str(project.game_dir),
        "launcher": str(project.launcher_path) if project.launcher_path else "",
        "translation_entries": 0,
        "data_records": 0,
        "maps": 0,
        "items": 0,
        "actors": 0,
        "scripts": 0,
        "archives": 0,
        "webview_ready": False,
    }
    if project.engine == "RPG Maker MV/MZ" and project.data_dir:
        service = RPGMakerService(project)
        maps = service.list_maps()
        summary["maps"] = len(maps)
        summary["data_records"] = len(service.list_data_records())
        summary["translation_entries"] = len(service.extract_translations())
        summary["webview_ready"] = (project.game_dir / "index.html").exists()
        summary["items"] = count_rpg_database(project.data_dir / "Items.json")
        summary["actors"] = count_rpg_database(project.data_dir / "Actors.json")
        summary["categories"] = summarize_rpg_categories(project.data_dir)
        return summary
    if project.engine == "Ren'Py" and project.scripts_dir:
        service = RenPyService(project)
        summary["translation_entries"] = len(service.extract_translations())
        summary["data_records"] = len(service.list_data_records())
        summary["scripts"] = len(list(project.scripts_dir.rglob("*.rpy"))) + len(list(project.scripts_dir.rglob("*.rpyc")))
        summary["archives"] = len(list(project.scripts_dir.rglob("*.rpa")))
        summary["categories"] = summarize_renpy_categories(project.scripts_dir)
        return summary
    return summary


def summarize_rpg_categories(data_dir: Path) -> list[dict[str, Any]]:
    categories = [
        ("Actors.json", "角色"),
        ("Classes.json", "职业"),
        ("Items.json", "物品"),
        ("Weapons.json", "武器"),
        ("Armors.json", "防具"),
        ("Skills.json", "技能"),
        ("States.json", "状态"),
        ("Enemies.json", "敌人"),
        ("System.json", "系统"),
        ("MapInfos.json", "地图"),
        ("CommonEvents.json", "公共事件"),
    ]
    result: list[dict[str, Any]] = []
    for file_name, label in categories:
        path = data_dir / file_name
        count = count_rpg_database(path)
        result.append(
            {
                "id": file_name,
                "label": label,
                "count": count,
                "exists": path.exists(),
                "highlight": count > 0,
            }
        )
    return result


def summarize_renpy_categories(scripts_dir: Path) -> list[dict[str, Any]]:
    total_rpy = len(list(scripts_dir.rglob("*.rpy")))
    total_rpyc = len(list(scripts_dir.rglob("*.rpyc")))
    total_rpa = len(list(scripts_dir.rglob("*.rpa")))
    return [
        {"id": "scripts", "label": "脚本", "count": total_rpy + total_rpyc, "exists": total_rpy + total_rpyc > 0, "highlight": total_rpy + total_rpyc > 0},
        {"id": "archives", "label": "封包", "count": total_rpa, "exists": total_rpa > 0, "highlight": total_rpa > 0},
        {"id": "translations", "label": "翻译文件", "count": len(list(scripts_dir.rglob("tl"))), "exists": True, "highlight": True},
    ]


def count_rpg_database(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        payload = load_json(path)
    except Exception:
        return 0
    if isinstance(payload, list):
        return sum(1 for item in payload if item)
    if isinstance(payload, dict):
        return len(payload)
    return 0


class MobilePrototypeHandler(BaseHTTPRequestHandler):
    server_version = "RPGRenPyLocalizerAndroidPrototype/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        print("[android-prototype]", format % args)

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self.send_json({"ok": True, "name": "RPGRenPyLocalizer Android Prototype"})
                return
            if parsed.path == "/api/project/current":
                self.require_project(lambda project: self.send_json({"ok": True, "project": project_to_dict(project)}))
                return
            if parsed.path == "/api/project/summary":
                self.require_project(lambda project: self.send_json({"ok": True, "summary": summarize_project(project)}))
                return
            if parsed.path == "/api/maps":
                self.handle_maps()
                return
            if parsed.path.startswith("/api/maps/"):
                self.handle_map_detail(parsed.path.rsplit("/", 1)[-1])
                return
            if parsed.path == "/api/translate/entries":
                self.handle_translation_entries(parsed.query)
                return
            if parsed.path == "/api/records":
                self.handle_records(parsed.query)
                return
            self.serve_static(parsed.path)
        except Exception as exc:
            self.send_error_json(str(exc), traceback.format_exc())

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/api/project/load":
                self.handle_load_project()
                return
            self.send_json({"ok": False, "error": "unknown endpoint"}, status=404)
        except Exception as exc:
            self.send_error_json(str(exc), traceback.format_exc())

    def handle_load_project(self) -> None:
        payload = self.read_json()
        raw_path = str(payload.get("path") or "").strip().strip('"')
        if not raw_path:
            self.send_json({"ok": False, "error": "请输入游戏目录或 exe 路径。"}, status=400)
            return
        project = detect_project(raw_path)
        STATE.project = project
        STATE.last_error = ""
        self.send_json(
            {
                "ok": True,
                "project": project_to_dict(project),
                "summary": summarize_project(project),
            }
        )

    def handle_maps(self) -> None:
        project = STATE.project
        if not project:
            self.send_json({"ok": False, "error": "请先加载游戏。"}, status=400)
            return
        if project.engine != "RPG Maker MV/MZ":
            self.send_json({"ok": True, "maps": [], "note": "当前引擎暂不支持地图列表。"})
            return
        maps = RPGMakerService(project).list_maps()
        self.send_json({"ok": True, "maps": dataclass_to_dict(maps)})

    def handle_map_detail(self, raw_map_id: str) -> None:
        project = STATE.project
        if not project:
            self.send_json({"ok": False, "error": "请先加载游戏。"}, status=400)
            return
        if project.engine != "RPG Maker MV/MZ":
            self.send_json({"ok": False, "error": "当前引擎暂不支持地图详情。"}, status=400)
            return
        detail = RPGMakerService(project).map_detail(int(raw_map_id))
        self.send_json({"ok": True, "detail": dataclass_to_dict(detail)})

    def handle_translation_entries(self, query: str) -> None:
        service = current_service()
        if not service:
            self.send_json({"ok": False, "error": "请先加载 RPG Maker MV/MZ 或 Ren'Py 游戏。"}, status=400)
            return
        params = parse_qs(query)
        limit = int((params.get("limit") or ["80"])[0])
        entries = service.extract_translations()
        self.send_json(
            {
                "ok": True,
                "count": len(entries),
                "entries": dataclass_to_dict(entries[: max(1, min(limit, 500))]),
            }
        )

    def handle_records(self, query: str) -> None:
        service = current_service()
        if not service:
            self.send_json({"ok": False, "error": "请先加载 RPG Maker MV/MZ 或 Ren'Py 游戏。"}, status=400)
            return
        params = parse_qs(query)
        category = (params.get("category") or [""])[0]
        limit = int((params.get("limit") or ["120"])[0])
        records = service.list_data_records()
        if category:
            records = [record for record in records if record.category == category or record.file == category]
        self.send_json({"ok": True, "count": len(records), "records": dataclass_to_dict(records[: max(1, min(limit, 500))])})

    def require_project(self, callback: Any) -> None:
        if not STATE.project:
            self.send_json({"ok": False, "error": "请先加载游戏。"}, status=400)
            return
        callback(STATE.project)

    def serve_static(self, raw_path: str) -> None:
        relative = unquote(raw_path).lstrip("/") or "index.html"
        if relative == "mobile":
            relative = "index.html"
        target = (MOBILE_UI_DIR / relative).resolve()
        if not str(target).startswith(str(MOBILE_UI_DIR.resolve())) or not target.exists() or target.is_dir():
            self.send_json({"ok": False, "error": "not found"}, status=404)
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        payload = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw.strip() else {}

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, detail: str = "") -> None:
        STATE.last_error = message
        self.send_json({"ok": False, "error": message, "detail": detail}, status=500)

    def do_OPTIONS(self) -> None:
        self.send_json({"ok": True})


def run(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    server = ThreadingHTTPServer((host, port), MobilePrototypeHandler)
    print(f"RPGRenPyLocalizer Android prototype: http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    run()
