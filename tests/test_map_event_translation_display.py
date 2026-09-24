from __future__ import annotations

import json
from pathlib import Path

from toolkit.api.server import ToolkitApi
from toolkit.models import ProjectInfo
from toolkit.rpgmaker import RPGMakerService


def make_rpgmaker_game(root: Path) -> ProjectInfo:
    data = root / "data"
    (root / "js" / "plugins").mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    (root / "js" / "plugins.js").write_text("var $plugins = [];", encoding="utf-8")
    (data / "System.json").write_text(json.dumps({"gameTitle": "TestGame", "terms": {}}), encoding="utf-8")
    (data / "Map001.json").write_text(
        json.dumps(
            {
                "width": 4,
                "height": 4,
                "displayName": "村の入口",
                "events": [
                    None,
                    {
                        "id": 1,
                        "name": "EV001",
                        "x": 1,
                        "y": 1,
                        "pages": [
                            {
                                "list": [
                                    {"code": 101, "parameters": ["Actor1", 0, 0, 0, "村长"]},
                                    {"code": 401, "parameters": ["こんにちは、旅の人。"]},
                                    {"code": 102, "parameters": [["はい", "いいえ"], 1]},
                                    {"code": 402, "parameters": [0, "はい"]},
                                ]
                            }
                        ],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return ProjectInfo("RPG Maker MV/MZ", root, root, data_dir=data)


def test_map_detail_uses_workspace_targets(tmp_path: Path) -> None:
    game = tmp_path / "game"
    make_rpgmaker_game(game)
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.load_project({"path": str(game)})
    api.translation_entries = RPGMakerService(api._project()).extract_translations()
    by_source = {entry.source: entry for entry in api.translation_entries}
    by_source["こんにちは、旅の人。"].target = "你好，旅行者。"
    by_source["村の入口"].target = "村庄入口"
    by_source["はい"].target = "好的"
    api._persist_translation_cache()

    # Fresh load path used by the maps view.
    api.translation_entries = RPGMakerService(api._project()).extract_translations()
    report = api.map_detail({"id": 1})

    record = report["record"]
    assert record["display_name"] == "村庄入口"
    commands = report["events"][0]["commands"]
    assert any("对话：你好，旅行者。" in item for item in commands)
    assert any("选项：好的 / いいえ" in item for item in commands)
    assert any("选项分支：好的" in item for item in commands)


def test_map_detail_fills_from_external_dict(tmp_path: Path) -> None:
    game = tmp_path / "game"
    make_rpgmaker_game(game)
    (game / "翻译文件.json").write_text(
        json.dumps({"こんにちは、旅的人。": "你好", "こんにちは、旅の人。": "你好，旅行者。"}, ensure_ascii=False),
        encoding="utf-8",
    )

    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.load_project({"path": str(game)})
    report = api.map_detail({"id": 1})
    commands = report["events"][0]["commands"]
    assert any("对话：你好，旅行者。" in item for item in commands)


def test_map_detail_without_translations_keeps_source(tmp_path: Path) -> None:
    game = tmp_path / "game"
    make_rpgmaker_game(game)
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.load_project({"path": str(game)})
    report = api.map_detail({"id": 1})
    commands = report["events"][0]["commands"]
    assert any("对话：こんにちは、旅の人。" in item for item in commands)


def test_mtool_overlay_formats_translated_event_commands() -> None:
    overlay = Path("android_app/shell/app/src/main/assets/mtool/mtool_overlay.js").read_text(encoding="utf-8")
    assert "function translateLine" in overlay
    assert 'getTranslationMap' in overlay
    assert "cmd.code===401||cmd.code===405" in overlay
    assert "transCache=null" in overlay
