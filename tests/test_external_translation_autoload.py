from __future__ import annotations

import json
from pathlib import Path

from toolkit.api.server import ToolkitApi
from toolkit.models import ProjectInfo, TranslationEntry
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
                "width": 1,
                "height": 1,
                "events": [
                    None,
                    {
                        "id": 1,
                        "pages": [
                            {
                                "list": [
                                    {"code": 401, "parameters": ["Hello"]},
                                    {"code": 401, "parameters": ["AlreadyDone"]},
                                ]
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return ProjectInfo("RPG Maker MV/MZ", root, root, data_dir=data)


def test_external_dict_fills_empty_targets(tmp_path: Path) -> None:
    game = tmp_path / "game"
    make_rpgmaker_game(game)
    (game / "翻译文件.json").write_text(
        json.dumps({"Hello": "你好", "AlreadyDone": "外部旧译"}, ensure_ascii=False),
        encoding="utf-8",
    )

    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.load_project({"path": str(game)})
    api.translation_entries = RPGMakerService(api._project()).extract_translations()
    api._restore_translation_cache()

    by_source = {entry.source: entry.target for entry in api.translation_entries}
    assert by_source["Hello"] == "你好"
    assert by_source["AlreadyDone"] == "外部旧译"


def test_workspace_cache_wins_over_external_dict(tmp_path: Path) -> None:
    game = tmp_path / "game"
    project = make_rpgmaker_game(game)
    (game / "翻译文件.json").write_text(
        json.dumps({"Hello": "外部译文"}, ensure_ascii=False),
        encoding="utf-8",
    )

    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.load_project({"path": str(game)})
    api.translation_entries = [
        TranslationEntry("map-1", "Hello", "", "Map001.json", "cmd=401", "dialogue"),
        TranslationEntry("map-2", "AlreadyDone", "", "Map001.json", "cmd=401", "dialogue"),
    ]
    api.translation_entries[0].target = "工作台译文"
    api._persist_translation_cache()

    # Fresh load: extract-like empty entries, then restore from workspace + external.
    api.translation_entries = [
        TranslationEntry("map-1", "Hello", "", "Map001.json", "cmd=401", "dialogue"),
        TranslationEntry("map-2", "AlreadyDone", "", "Map001.json", "cmd=401", "dialogue"),
    ]
    api._restore_translation_cache()

    by_id = {entry.entry_id: entry.target for entry in api.translation_entries}
    assert by_id["map-1"] == "工作台译文"
    # Not present in workspace cache or external dict — stays empty.
    assert by_id["map-2"] == ""


def test_workspace_empty_target_can_be_refilled_only_when_absent_key(tmp_path: Path) -> None:
    game = tmp_path / "game"
    make_rpgmaker_game(game)
    (game / "translation.json").write_text(
        json.dumps({"translations": {"Hello": "你好"}}),
        encoding="utf-8",
    )

    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.load_project({"path": str(game)})
    api.translation_entries = [TranslationEntry("e1", "Hello", "", "Map001.json", category="dialogue")]
    filled = api._merge_external_translation_dicts()
    assert filled == 1
    assert api.translation_entries[0].target == "你好"


def test_manual_transfile_and_stripped_source(tmp_path: Path) -> None:
    game = tmp_path / "game"
    make_rpgmaker_game(game)
    (game / "ManualTransFile.json").write_text(
        json.dumps({"  Potion  ": " 药水 "}, ensure_ascii=False),
        encoding="utf-8",
    )

    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.load_project({"path": str(game)})
    api.translation_entries = [TranslationEntry("e1", "Potion", "", "Items.json", category="database")]
    api._restore_translation_cache()
    assert api.translation_entries[0].target == " 药水 "


def test_preflight_counts_external_merged_targets(tmp_path: Path) -> None:
    game = tmp_path / "game"
    make_rpgmaker_game(game)
    (game / "翻译文件.json").write_text(
        json.dumps({"Hello": "你好", "AlreadyDone": "已完成"}, ensure_ascii=False),
        encoding="utf-8",
    )

    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.load_project({"path": str(game)})
    # Leave translation_entries empty so preflight extracts + restores + merges.
    report = api.translations_preflight({})
    summary = report["summary"]
    assert summary["total"] >= 2
    assert summary["translated"] >= 2
    assert summary["missing"] == summary["total"] - summary["translated"]


def test_translations_import_mtool_flat_with_bom(tmp_path: Path) -> None:
    game = tmp_path / "game"
    make_rpgmaker_game(game)
    mtool_pack = tmp_path / "mtool_export.json"
    # Write UTF-8 with BOM
    content = "\ufeff" + json.dumps({"Hello": "你好", "AlreadyDone": "已完成"}, ensure_ascii=False)
    mtool_pack.write_text(content, encoding="utf-8")

    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.load_project({"path": str(game)})
    res = api.translations_import({"path": str(mtool_pack)})
    assert res["ok"] is True
    assert res["matched"] >= 2
    by_src = {e.source: e.target for e in api.translation_entries}
    assert by_src["Hello"] == "你好"
    assert by_src["AlreadyDone"] == "已完成"


def test_translations_import_mtool_nested_translations(tmp_path: Path) -> None:
    game = tmp_path / "game"
    make_rpgmaker_game(game)
    mtool_pack = tmp_path / "mtool_nested.json"
    payload = {
        "version": 1,
        "engine": "RPGMaker",
        "translations": {
            "Hello": "你好（嵌套）",
            "AlreadyDone": "完成（嵌套）"
        }
    }
    mtool_pack.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.load_project({"path": str(game)})
    res = api.translations_import({"path": str(mtool_pack)})
    assert res["ok"] is True
    assert res["matched"] >= 2
    by_src = {e.source: e.target for e in api.translation_entries}
    assert by_src["Hello"] == "你好（嵌套）"


def test_translations_import_mtool_array_format(tmp_path: Path) -> None:
    game = tmp_path / "game"
    make_rpgmaker_game(game)
    mtool_pack = tmp_path / "mtool_array.json"
    payload = [
        {"src": "Hello", "dst": "你好（数组）"},
        {"src": "AlreadyDone", "dst": "完成（数组）"}
    ]
    mtool_pack.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.load_project({"path": str(game)})
    res = api.translations_import({"file_path": str(mtool_pack)})
    assert res["ok"] is True
    assert res["matched"] >= 2
    by_src = {e.source: e.target for e in api.translation_entries}
    assert by_src["Hello"] == "你好（数组）"


def test_translations_import_whitespace_tolerance(tmp_path: Path) -> None:
    game = tmp_path / "game"
    make_rpgmaker_game(game)
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.load_project({"path": str(game)})
    # Simulate an entry that has trailing newline or whitespace
    api.translation_entries = [
        TranslationEntry("e1", "Hello \n", "", "Map001.json", category="dialogue")
    ]
    mtool_pack = tmp_path / "mtool_trimmed.json"
    mtool_pack.write_text(json.dumps({"Hello": "你好（去空格）"}, ensure_ascii=False), encoding="utf-8")

    res = api.translations_import({"path": str(mtool_pack)})
    assert res["ok"] is True
    assert res["matched"] == 1
    assert api.translation_entries[0].target == "你好（去空格）"


def test_live_import_mtool_payload(tmp_path: Path) -> None:
    game = tmp_path / "game"
    make_rpgmaker_game(game)
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.load_project({"path": str(game)})
    api.translation_entries = [
        TranslationEntry("e1", "Hello", "", "Map001.json", category="dialogue")
    ]
    # Test live_import with "pairs" parameter as sent by App.vue
    res = api.live_import({"pairs": [{"src": "Hello", "dst": "你好（实时）"}]})
    assert res["ok"] is True
    assert res["count"] >= 1
    assert api.translation_entries[0].target == "你好（实时）"

