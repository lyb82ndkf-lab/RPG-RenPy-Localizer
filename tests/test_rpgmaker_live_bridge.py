from __future__ import annotations

import json
import subprocess
import textwrap
import time
import urllib.request
from pathlib import Path

from toolkit.models import ProjectInfo
from toolkit.models import TranslationEntry
from toolkit.api.server import ApiError, ToolkitApi
from toolkit.workspace import LibraryEntry
from toolkit.rpgmaker import (
    RUNTIME_BRIDGE_NAME,
    RPGMakerService,
    _RPGRM_LIVE_SERVER_STATE,
)


def make_project(tmp_path: Path) -> ProjectInfo:
    root = tmp_path / "game"
    data = root / "data"
    (root / "js" / "plugins").mkdir(parents=True)
    data.mkdir(parents=True)
    (root / "js" / "plugins.js").write_text("var $plugins = [];", encoding="utf-8")
    return ProjectInfo("RPG Maker MV/MZ", root, root, data_dir=data)


def test_extracts_database_and_dialogue_only(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    data = project.data_dir
    assert data is not None
    (data / "System.json").write_text(json.dumps({"gameTitle": "SYSTEM_TEXT"}), encoding="utf-8")
    (data / "Items.json").write_text(json.dumps([None, {"name": "Potion", "description": "Heals"}]), encoding="utf-8")
    (data / "Map001.json").write_text(
        json.dumps(
            {
                "width": 1,
                "height": 1,
                "events": [None, {"id": 1, "pages": [{"list": [
                    {"code": 401, "parameters": ["Hello"]},
                    {"code": 355, "parameters": ["SCRIPT_TEXT"]},
                ]}]}],
            }
        ),
        encoding="utf-8",
    )

    sources = {entry.source for entry in RPGMakerService(project).extract_translations()}

    assert {"Potion", "Heals", "Hello"}.issubset(sources)
    assert "SYSTEM_TEXT" not in sources
    assert "SCRIPT_TEXT" not in sources


def test_rpgmaker_plugin_command_internals_are_not_translated(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    data = project.data_dir
    assert data is not None
    map_path = data / "Map001.json"
    map_payload = {
        "width": 1,
        "height": 1,
        "events": [
            None,
            {
                "id": 1,
                "name": "Event name is editor-only here",
                "pages": [
                    {
                        "list": [
                            {"code": 101, "parameters": ["", 0, 0, 2, "Narrator"]},
                            {"code": 401, "parameters": ["Hello"]},
                            {"code": 102, "parameters": [["Yes", "No"], 0, 0, 2, 0]},
                            {
                                "code": 357,
                                "parameters": [
                                    "TRP_ParticleMZ",
                                    "set",
                                    "set/表示",
                                    {
                                        "id": "Actor2TP4",
                                        "target": "enemy:1",
                                        "name": "def",
                                        "z": "screen",
                                        "tag": "",
                                        "edit": "false",
                                        "delay": "0",
                                    },
                                ],
                            },
                            {"code": 657, "parameters": ["データ名 = def"]},
                        ]
                    }
                ],
            },
        ],
    }
    map_path.write_text(json.dumps(map_payload), encoding="utf-8")
    service = RPGMakerService(project)

    entries = service.extract_translations()
    sources = {entry.source for entry in entries}
    ids = {entry.entry_id for entry in entries}

    assert {"Narrator", "Hello", "Yes", "No"}.issubset(sources)
    assert "def" not in sources
    assert "Actor2TP4" not in sources
    assert all("parameters/3" not in entry_id for entry_id in ids)
    assert all("parameters/0" not in entry_id for entry_id in ids if "list/4" in entry_id)

    translations = {
        entry.entry_id: TranslationEntry(
            entry.entry_id,
            entry.source,
            f"CN:{entry.source}",
            entry.file,
            entry.context,
            entry.category,
        )
        for entry in entries
    }
    service.apply_translations(translations)
    updated = json.loads(map_path.read_text(encoding="utf-8"))
    commands = updated["events"][1]["pages"][0]["list"]

    assert commands[0]["parameters"][4] == "CN:Narrator"
    assert commands[1]["parameters"][0] == "CN:Hello"
    assert commands[2]["parameters"][0] == ["CN:Yes", "CN:No"]
    assert commands[3]["parameters"][3]["id"] == "Actor2TP4"
    assert commands[3]["parameters"][3]["name"] == "def"
    assert commands[4]["parameters"][0] == "データ名 = def"


def test_rpgmaker_only_translates_documented_database_slots_and_event_lists(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    data = project.data_dir
    assert data is not None
    map_path = data / "Map001.json"
    map_path.write_text(json.dumps({
        "displayName": "Town",
        "meta": {"name": "PluginInternalName", "description": "Plugin configuration"},
        "events": [None, {
            "name": "EditorOnlyEventName",
            "pages": [{"list": [
                {"code": 401, "parameters": ["Visible dialogue"]},
                {"code": 102, "parameters": [["Yes", "No"], 0, 0, 2, 0]},
            ]}],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    (data / "Items.json").write_text(json.dumps([
        None,
        {"name": "Potion", "description": "Visible item", "meta": {"name": "DoNotTranslate"}},
    ], ensure_ascii=False), encoding="utf-8")

    service = RPGMakerService(project)
    entries = service.extract_translations()
    sources = {entry.source for entry in entries}
    assert {"Town", "Potion", "Visible item", "Visible dialogue", "Yes", "No"}.issubset(sources)
    assert not {"PluginInternalName", "Plugin configuration", "EditorOnlyEventName", "DoNotTranslate"} & sources

    translations = {
        entry.entry_id: TranslationEntry(entry.entry_id, entry.source, f"CN:{entry.source}", entry.file, entry.context, entry.category)
        for entry in entries
    }
    service.apply_translations(translations)
    updated_map = json.loads(map_path.read_text(encoding="utf-8"))
    updated_item = json.loads((data / "Items.json").read_text(encoding="utf-8"))
    assert updated_map["displayName"] == "CN:Town"
    assert updated_map["meta"] == {"name": "PluginInternalName", "description": "Plugin configuration"}
    assert updated_map["events"][1]["name"] == "EditorOnlyEventName"
    assert updated_map["events"][1]["pages"][0]["list"][0]["parameters"][0] == "CN:Visible dialogue"
    assert updated_map["events"][1]["pages"][0]["list"][1]["parameters"][0] == ["CN:Yes", "CN:No"]
    assert updated_item[1]["name"] == "CN:Potion"
    assert updated_item[1]["meta"]["name"] == "DoNotTranslate"


def test_rpgmaker_source_fallback_never_crosses_database_dialogue_boundary(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    data = project.data_dir
    assert data is not None
    (data / "Items.json").write_text(json.dumps([None, {"name": "Yes", "description": "Item"}]), encoding="utf-8")
    (data / "Map001.json").write_text(json.dumps({"events": [None, {"pages": [{"list": [
        {"code": 102, "parameters": [["Yes"], 0, 0, 2, 0]},
    ]}]}]}), encoding="utf-8")
    service = RPGMakerService(project)
    entries = service.extract_translations()
    choice = next(entry for entry in entries if entry.category == "dialogue" and entry.source == "Yes")
    service.apply_translations({choice.entry_id: TranslationEntry(
        choice.entry_id, "Yes", "是", choice.file, choice.context, choice.category,
    )})
    items = json.loads((data / "Items.json").read_text(encoding="utf-8"))
    game_map = json.loads((data / "Map001.json").read_text(encoding="utf-8"))
    assert items[1]["name"] == "Yes"
    assert game_map["events"][1]["pages"][0]["list"][0]["parameters"][0] == ["是"]


def test_rpgmaker_control_tokens_must_be_preserved(tmp_path: Path) -> None:
    service = RPGMakerService(make_project(tmp_path))
    slash = chr(92)
    source = "Hello " + slash + "N[1] " + slash + "C[2]" + slash + "I[3]"
    target = "浣犲ソ " + slash + "N[1] " + slash + "C[2]" + slash + "I[3]"
    assert service.control_tokens_preserved(source, target)
    assert not service.control_tokens_preserved(source, "浣犲ソ")
    assert not service.control_tokens_preserved(source, "浣犲ソ " + slash + "N[2] " + slash + "C[2]" + slash + "I[3]")


def test_manual_target_save_rejects_broken_control_tokens(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.project = project
    api.translation_entries = [TranslationEntry("1", r"Hello \N[1]", "", "Map001.json", category="dialogue")]
    try:
        api.translations_save_targets({"updates": [{"entry_id": "1", "target": "浣犲ソ"}]})
    except ApiError:
        pass
    else:
        raise AssertionError("broken RPG Maker control tokens were accepted")


def test_partial_target_save_keeps_valid_entries_when_one_control_token_is_missing(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.project = project
    api.translation_entries = [
        TranslationEntry("1", r"\C[27]Hello", "", "Map001.json", category="dialogue"),
        TranslationEntry("2", "Goodbye", "", "Map001.json", category="dialogue"),
    ]
    result = api.translations_save_targets({"allowPartial": True, "updates": [
        {"entry_id": "1", "target": "你好"},
        {"entry_id": "2", "target": "再见"},
    ]})
    assert result["changed"] == 1
    assert result["rejected"] and result["rejected"][0]["entry_id"] == "1"
    assert api.translation_entries[0].target == ""
    assert api.translation_entries[1].target == "再见"


def test_runtime_patch_rejects_broken_control_tokens(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.project = project
    api.translation_entries = [TranslationEntry("1", r"Hello \N[1]", "", "Map001.json", category="dialogue")]
    try:
        api.translations_runtime({"entries": [{"entry_id": "1", "source": r"Hello \N[1]", "target": "浣犲ソ"}]})
    except ApiError:
        pass
    else:
        raise AssertionError("runtime patch accepted broken RPG Maker control tokens")


def test_bridge_install_and_live_queue_priority(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    service = RPGMakerService(project)
    bridge_path = service.install_runtime_bridge()
    plugins_text = (project.root / "js" / "plugins.js").read_text(encoding="utf-8")

    assert bridge_path.exists()
    assert RUNTIME_BRIDGE_NAME in plugins_text
    assert '"status": true' in plugins_text

    _RPGRM_LIVE_SERVER_STATE["translations"] = {}
    _RPGRM_LIVE_SERVER_STATE["pre_translate_queue"] = [
        {"text": "low", "priority": "low"},
        {"text": "high", "priority": "high"},
        {"text": "urgent", "priority": "urgent"},
    ]
    service.set_live_translations({"Hello": "浣犲ソ"})
    seeded = service.seed_live_translation_queue([
        TranslationEntry("1", "Hello", "浣犲ソ", category="dialogue"),
        TranslationEntry("2", "Future dialogue", category="dialogue"),
        TranslationEntry("3", "Item name", category="database"),
        TranslationEntry("4", "Unsafe event", category="event"),
    ])

    assert service.take_live_translation_candidates(1) == ["urgent"]
    assert seeded == 2
    assert "Future dialogue" in str(_RPGRM_LIVE_SERVER_STATE["pre_translate_queue"])
    assert _RPGRM_LIVE_SERVER_STATE["translations"]["Hello"] == "浣犲ソ"
    status = service.live_bridge_status()
    assert "running" in status and "connected" in status

    _RPGRM_LIVE_SERVER_STATE["translations"] = {}
    _RPGRM_LIVE_SERVER_STATE["pre_translate_queue"] = []


def test_bridge_install_uses_www_runtime_root_for_deployed_projects(tmp_path: Path) -> None:
    root = tmp_path / "deployed"
    game_dir = root / "www"
    data = game_dir / "data"
    (game_dir / "js" / "plugins").mkdir(parents=True)
    data.mkdir(parents=True)
    (game_dir / "js" / "plugins.js").write_text("var $plugins = [];", encoding="utf-8")
    project = ProjectInfo("RPG Maker MV/MZ", root, game_dir, data_dir=data)

    bridge_path = RPGMakerService(project).install_runtime_bridge()

    assert bridge_path == game_dir / "js" / "plugins" / f"{RUNTIME_BRIDGE_NAME}.js"
    plugins_text = (game_dir / "js" / "plugins.js").read_text(encoding="utf-8")
    assert RUNTIME_BRIDGE_NAME in plugins_text
    assert not (root / "js" / "plugins").exists()


def test_uninstall_bridge_restores_original_game_and_removes_tool_font(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    service = RPGMakerService(project)
    bridge_path = service.install_runtime_bridge()
    fonts = project.root / "fonts"
    fonts.mkdir()
    generated_font = fonts / "RPGRenPyLocalizerCJK.ttf"
    generated_font.write_bytes(b"tool-font")

    removed = service.uninstall_runtime_bridge()

    assert removed >= 3
    assert not bridge_path.exists()
    assert not generated_font.exists()
    assert RUNTIME_BRIDGE_NAME not in (project.root / "js" / "plugins.js").read_text(encoding="utf-8")


def test_runtime_translation_uses_in_place_bridge_without_copying_game_files(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    data = project.data_dir
    assert data is not None
    (data / "Map001.json").write_text(json.dumps({"events": [None, {"pages": [{"list": [{"code": 401, "parameters": ["Hello"]}]}]}]}), encoding="utf-8")
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.project = project
    api.translation_entries = RPGMakerService(project).extract_translations()
    hello = next(entry for entry in api.translation_entries if entry.source == "Hello")
    hello.target = "你好"

    result = api.translations_runtime({"versionId": "current"})

    assert result["mode"] == "in-place"
    assert Path(result["path"]) == project.root
    assert (project.root / "js" / "plugins" / f"{RUNTIME_BRIDGE_NAME}.js").exists()
    assert RUNTIME_BRIDGE_NAME in (project.root / "js" / "plugins.js").read_text(encoding="utf-8")
    assert not (project.root / ".rpgrtl_workspace" / "runtime_game").exists()
    assert json.loads((project.root / "data" / "Map001.json").read_text(encoding="utf-8"))["events"][1]["pages"][0]["list"][0]["parameters"][0] == "Hello"
    live_table = json.loads(Path(result["translationTable"]).read_text(encoding="utf-8"))
    assert live_table["translations"]["Hello"] == "你好"


def test_live_capture_queue_only_accepts_safe_dialogue_events(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    service = RPGMakerService(project)
    service.start_live_bridge_server(clear_events=True)
    try:
        body = json.dumps({"items": [
            {"text": "System popup", "event": "bitmap_drawText"},
            {"text": "A line of dialogue", "event": "game_message_setText"},
        ]}).encode("utf-8")
        request = urllib.request.Request(
            "http://127.0.0.1:32181/seen_batch",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            assert json.loads(response.read().decode("utf-8"))["ok"] is True
        queued = [item["text"] for item in _RPGRM_LIVE_SERVER_STATE["pre_translate_queue"]]
        assert queued == ["A line of dialogue"]
        assert _RPGRM_LIVE_SERVER_STATE["pre_translate_queue"][0]["priority"] == "urgent"
    finally:
        service.stop_live_bridge_server()
        _RPGRM_LIVE_SERVER_STATE["translations"] = {}
        _RPGRM_LIVE_SERVER_STATE["pre_translate_queue"] = []


def test_runtime_bridge_replaces_message_but_keeps_generic_bitmap_text(tmp_path: Path) -> None:
    from toolkit.rpgmaker import RUNTIME_BRIDGE_SOURCE

    source_path = tmp_path / "bridge.js"
    harness_path = tmp_path / "harness.js"
    source_path.write_text(RUNTIME_BRIDGE_SOURCE, encoding="utf-8")
    harness_path.write_text(
        textwrap.dedent(
            f"""
            const fs = require('fs');
            global.window = global;
            global.Input = {{ isPressed: () => false }};
            global.Graphics = {{}};
            global.SceneManager = {{ _scene: null }};
            global.TouchInput = {{ isTriggered: () => false, x: 0, y: 0 }};
            global.DataManager = {{ saveGame: () => {{}} }};
            global.$dataSystem = {{ switches: [], variables: [] }};
            global.$dataMap = {{ events: [] }};
            global.$dataCommonEvents = [];
            global.$dataMapInfos = [];
            global.$gameActors = {{ _data: [] }};
            global.$gameSwitches = {{ value: () => false, setValue: () => {{}} }};
            global.$gameVariables = {{ value: () => 0, setValue: () => {{}} }};
            global.$gameParty = {{ _items: {{}}, _weapons: {{}}, _armors: {{}}, gold: () => 0, steps: () => 0, members: () => [] }};
            global.$gameMap = {{ mapId: () => 1, requestRefresh: () => {{}}, canvasToMapX: x => x, canvasToMapY: y => y }};
            global.$gamePlayer = {{ x: 0, y: 0, isThrough: () => false, setThrough: () => {{}}, setPosition: () => {{}}, center: () => {{}} }};
            global.BattleManager = {{ update: () => {{}}, processVictory: () => {{}}, processDefeat: () => {{}}, processEscape: () => {{}}, inputting: () => false }};

            function Game_BattlerBase() {{}};
            Game_BattlerBase.prototype.refresh = function() {{}};
            global.Game_BattlerBase = Game_BattlerBase;
            function Game_Player() {{}};
            Game_Player.prototype.realMoveSpeed = function() {{ return 4; }};
            Game_Player.prototype.setThrough = function() {{}};
            global.Game_Player = Game_Player;
            function Game_Message() {{ this._texts = []; this._choices = []; }};
            Game_Message.prototype.setText = function(text) {{ this._texts = [text]; }};
            Game_Message.prototype.setChoices = function(choices) {{ this._choices = choices; }};
            global.Game_Message = Game_Message;
            function Game_Interpreter() {{ this._params = []; }};
            Game_Interpreter.prototype.command401 = function() {{ return true; }};
            Game_Interpreter.prototype.command102 = function() {{ return true; }};
            Game_Interpreter.prototype.command405 = function() {{ return true; }};
            global.Game_Interpreter = Game_Interpreter;
            function Game_Map() {{}};
            Game_Map.prototype.setup = function() {{}};
            global.Game_Map = Game_Map;
            function Bitmap() {{}};
            Bitmap.prototype.initialize = function() {{}};
            Bitmap.prototype.drawText = function(text) {{ global.drawnText = text; }};
            global.Bitmap = Bitmap;
            function Window_Base() {{}};
            Window_Base.prototype.convertEscapeCharacters = function(text) {{ return text; }};
            global.Window_Base = Window_Base;
            function Window_Message() {{}};
            Window_Message.prototype = Object.create(Window_Base.prototype);
            Window_Message.prototype.startMessage = function() {{ this._textState = {{ active: true }}; this.startedText = $gameMessage._texts.join('|'); }};
            global.Window_Message = Window_Message;
            function Window_ChoiceList() {{}};
            Window_ChoiceList.prototype = Object.create(Window_Base.prototype);
            Window_ChoiceList.prototype.commandName = function(index) {{ return $gameMessage._choices[index]; }};
            Window_ChoiceList.prototype.drawItem = function() {{}};
            global.Window_ChoiceList = Window_ChoiceList;
            function Scene_Map() {{}};
            Scene_Map.prototype.update = function() {{}};
            global.Scene_Map = Scene_Map;
            function Scene_Battle() {{}};
            Scene_Battle.prototype.update = function() {{}};
            global.Scene_Battle = Scene_Battle;

            eval(fs.readFileSync({json.dumps(str(source_path))}, 'utf8'));
            const http = require('http');
            setTimeout(() => {{
              global.$gameMessage = new Game_Message();
              $gameMessage.setText('Hello');
              const message = new Window_Message();
              message.startMessage();
              SceneManager._scene = {{ _messageWindow: message, _choiceListWindow: null, _scrollTextWindow: null, refresh: () => {{}} }};
              const payload = JSON.stringify({{dict: {{Hello: '浣犲ソ'}}, enabled: true}});
              const req = http.request({{hostname: '127.0.0.1', port: 32179, path: '/translation', method: 'POST', headers: {{'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload)}}}}, res => {{
                res.on('data', () => {{}});
                res.on('end', () => {{
                  new Bitmap().drawText('Hello', 0, 0, 100, 20, 'left');
                  if (message.startedText !== '浣犲ソ' || global.drawnText !== 'Hello') process.exit(2);
                  window.RPGRenPyBridge.server.close();
                  clearInterval(window.RPGRenPyBridge._pollTimer);
                  process.stdout.write('runtime bridge replacement ok\\n');
                }});
              }});
              req.on('error', err => {{ console.error(err); process.exit(3); }});
              req.end(payload);
            }}, 80);
            """
        ),
        encoding="utf-8",
    )
    result = subprocess.run(["node", str(harness_path)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "runtime bridge replacement ok" in result.stdout


def test_seen_batch_translation_refreshes_active_message_queue(tmp_path: Path) -> None:
    from toolkit.rpgmaker import RUNTIME_BRIDGE_SOURCE

    project = make_project(tmp_path)
    service = RPGMakerService(project)
    service.start_live_bridge_server(clear_events=True)
    service.set_live_translations({"Hello": "浣犲ソ"})
    source_path = tmp_path / "bridge.js"
    harness_path = tmp_path / "harness.js"
    source_path.write_text(RUNTIME_BRIDGE_SOURCE, encoding="utf-8")
    harness = r"""
      const fs = require('fs'); global.window = global;
      global.Input = { isPressed: () => false }; global.Graphics = {};
      global.SceneManager = { _scene: null }; global.TouchInput = { isTriggered: () => false, x: 0, y: 0 };
      global.DataManager = { saveGame: () => {} }; global.$dataActors = []; global.$dataArmors = [];
      global.$dataClasses = []; global.$dataEnemies = []; global.$dataItems = []; global.$dataMap = { events: [] };
      global.$dataCommonEvents = []; global.$dataMapInfos = []; global.$dataSkills = []; global.$dataStates = []; global.$dataWeapons = [];
      global.$gameActors = { _data: [] }; global.$gameSwitches = { value: () => false, setValue: () => {} };
      global.$gameVariables = { value: () => 0, setValue: () => {} }; global.$gameParty = { _items: {}, _weapons: {}, _armors: {}, gold: () => 0, steps: () => 0, members: () => [] };
      global.$gameMap = { mapId: () => 1, requestRefresh: () => {}, canvasToMapX: x => x, canvasToMapY: y => y };
      global.$gamePlayer = { x: 0, y: 0, isThrough: () => false, setThrough: () => {}, setPosition: () => {}, center: () => {} };
      global.BattleManager = { update: () => {}, processVictory: () => {}, processDefeat: () => {}, processEscape: () => {}, inputting: () => false };
      function Game_BattlerBase() {} Game_BattlerBase.prototype.refresh = function() {}; global.Game_BattlerBase = Game_BattlerBase;
      function Game_Player() {} Game_Player.prototype.realMoveSpeed = function() { return 4; }; global.Game_Player = Game_Player;
      function Game_Message() { this._texts = []; this._choices = []; } Game_Message.prototype.add = function(text) { this._texts.push(text); }; global.Game_Message = Game_Message;
      function Game_Interpreter() {} Game_Interpreter.prototype.command401 = function() {}; Game_Interpreter.prototype.command102 = function() {}; Game_Interpreter.prototype.command405 = function() {}; global.Game_Interpreter = Game_Interpreter;
      function Game_Map() {} Game_Map.prototype.setup = function() {}; global.Game_Map = Game_Map;
      function Bitmap() {} Bitmap.prototype.initialize = function() {}; Bitmap.prototype.drawText = function() {}; global.Bitmap = Bitmap;
      function Window_Base() {} Window_Base.prototype.convertEscapeCharacters = function(text) { return text; }; global.Window_Base = Window_Base;
      function Window_Message() {} Window_Message.prototype = Object.create(Window_Base.prototype); Window_Message.prototype.startMessage = function() { this._textState = { active: true }; this.startedText = $gameMessage._texts.join('|'); }; global.Window_Message = Window_Message;
      function Window_ChoiceList() {} Window_ChoiceList.prototype = Object.create(Window_Base.prototype); Window_ChoiceList.prototype.drawItem = function() {}; global.Window_ChoiceList = Window_ChoiceList;
      function Scene_Map() {} Scene_Map.prototype.update = function() {}; global.Scene_Map = Scene_Map; function Scene_Battle() {} Scene_Battle.prototype.update = function() {}; global.Scene_Battle = Scene_Battle;
      eval(fs.readFileSync(__SOURCE__, 'utf8'));
      // Make the bridge dictionary empty after startup; /seen_batch must supply the known target.
      bridge = window.RPGRenPyBridge; bridge.translations = {}; bridge.translationEnabled = true;
      global.$gameMessage = new Game_Message(); $gameMessage.add('Hello');
      const message = new Window_Message(); message.startMessage(); SceneManager._scene = { _messageWindow: message, _choiceListWindow: null, _scrollTextWindow: null, refresh: () => {} };
      setTimeout(() => { if (message.startedText !== '浣犲ソ' || $gameMessage._texts[0] !== '浣犲ソ') process.exit(2); process.stdout.write('seen batch refresh ok\n'); bridge.server.close(); clearInterval(bridge._pollTimer); }, 1200);
    """.replace("__SOURCE__", json.dumps(str(source_path)))
    harness_path.write_text(textwrap.dedent(harness), encoding="utf-8")
    result = subprocess.run(["node", str(harness_path)], capture_output=True, text=True, timeout=8)
    try:
        assert result.returncode == 0, result.stderr or result.stdout
        assert "seen batch refresh ok" in result.stdout
    finally:
        service.stop_live_bridge_server()
        _RPGRM_LIVE_SERVER_STATE["translations"] = {}
        _RPGRM_LIVE_SERVER_STATE["events"] = []


def test_runtime_bridge_full_capture_to_late_refresh_flow(tmp_path: Path) -> None:
    from toolkit.rpgmaker import RUNTIME_BRIDGE_SOURCE

    project = make_project(tmp_path)
    service = RPGMakerService(project)
    source_path = tmp_path / "bridge.js"
    harness_path = tmp_path / "harness.js"
    source_path.write_text(RUNTIME_BRIDGE_SOURCE, encoding="utf-8")
    harness = r"""
      const fs = require('fs');
      global.window = global;
      global.Input = { isPressed: () => false };
      global.Graphics = {};
      global.SceneManager = { _scene: null };
      global.TouchInput = { isTriggered: () => false, x: 0, y: 0 };
      global.DataManager = { saveGame: () => {} };
      global.$dataActors = []; global.$dataArmors = []; global.$dataClasses = [];
      global.$dataEnemies = []; global.$dataItems = [];
      global.$dataMap = { events: [null, { pages: [{ list: [
        { code: 355, parameters: ['Hello'] },
        { code: 401, parameters: ['Hello'] }
      ] }] }] };
      global.$dataCommonEvents = []; global.$dataMapInfos = []; global.$dataSkills = [];
      global.$dataStates = []; global.$dataWeapons = [];
      global.$gameActors = { _data: [] };
      global.$gameSwitches = { value: () => false, setValue: () => {} };
      global.$gameVariables = { value: () => 0, setValue: () => {} };
      global.$gameParty = { _items: {}, _weapons: {}, _armors: {}, gold: () => 0, steps: () => 0, members: () => [] };
      global.$gameMap = { mapId: () => 1, requestRefresh: () => {}, canvasToMapX: x => x, canvasToMapY: y => y };
      global.$gamePlayer = { x: 0, y: 0, isThrough: () => false, setThrough: () => {}, setPosition: () => {}, center: () => {} };
      global.BattleManager = { update: () => {}, processVictory: () => {}, processDefeat: () => {}, processEscape: () => {}, inputting: () => false };
      function Game_BattlerBase() {}
      Game_BattlerBase.prototype.refresh = function() {};
      global.Game_BattlerBase = Game_BattlerBase;
      function Game_Player() {}
      Game_Player.prototype.realMoveSpeed = function() { return 4; };
      global.Game_Player = Game_Player;
      function Game_Message() { this._texts = []; this._choices = []; }
      Game_Message.prototype.setText = function(text) { this._texts = [text]; };
      Game_Message.prototype.add = function(text) { this._texts.push(text); };
      Game_Message.prototype.setChoices = function(choices) { this._choices = choices; };
      global.Game_Message = Game_Message;
      function Game_Interpreter() { this._params = []; }
      Game_Interpreter.prototype.command401 = function() { return true; };
      Game_Interpreter.prototype.command102 = function() { return true; };
      Game_Interpreter.prototype.command405 = function() { return true; };
      global.Game_Interpreter = Game_Interpreter;
      function Game_Map() {}
      Game_Map.prototype.setup = function() {};
      global.Game_Map = Game_Map;
      function Bitmap() {}
      Bitmap.prototype.initialize = function() {};
      Bitmap.prototype.drawText = function(text) { global.drawnText = text; };
      global.Bitmap = Bitmap;
      function Window_Base() {}
      Window_Base.prototype.convertEscapeCharacters = function(text) { return text; };
      global.Window_Base = Window_Base;
      function Window_Message() {}
      Window_Message.prototype = Object.create(Window_Base.prototype);
      Window_Message.prototype.startMessage = function() { this._textState = { active: true }; this.startedText = $gameMessage._texts.join('|'); };
      global.Window_Message = Window_Message;
      function Window_ChoiceList() {}
      Window_ChoiceList.prototype = Object.create(Window_Base.prototype);
      Window_ChoiceList.prototype.commandName = function(index) { return $gameMessage._choices[index]; };
      Window_ChoiceList.prototype.drawItem = function() {};
      global.Window_ChoiceList = Window_ChoiceList;
      function Scene_Map() {}
      Scene_Map.prototype.update = function() {};
      global.Scene_Map = Scene_Map;
      function Scene_Battle() {}
      Scene_Battle.prototype.update = function() {};
      global.Scene_Battle = Scene_Battle;
      eval(fs.readFileSync(__SOURCE__, 'utf8'));
      global.$gameMessage = new Game_Message();
      $gameMessage.add('Hello');
      const message = new Window_Message();
      message.startMessage();
      SceneManager._scene = { _messageWindow: message, _choiceListWindow: null, _scrollTextWindow: null, refresh: () => {} };
      setTimeout(() => {
        if (message.startedText !== '浣犲ソ' || $dataMap.events[1].pages[0].list[0].parameters[0] !== 'Hello' || $dataMap.events[1].pages[0].list[1].parameters[0] !== '浣犲ソ') process.exit(2);
        process.stdout.write('capture refresh ok\n');
        window.RPGRenPyBridge.server.close();
        clearInterval(window.RPGRenPyBridge._pollTimer);
      }, 2200);
    """.replace("__SOURCE__", json.dumps(str(source_path)))
    harness_path.write_text(textwrap.dedent(harness), encoding="utf-8")
    process = subprocess.Popen(["node", str(harness_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    merged = False
    try:
        # Model the real startup order: the game/plugin may start before the
        # user opens Live. Captured text must survive failed tool requests.
        time.sleep(1.0)
        service.start_live_bridge_server(clear_events=True)
        deadline = time.monotonic() + 8
        while process.poll() is None and time.monotonic() < deadline:
            if "Hello" in _RPGRM_LIVE_SERVER_STATE["seen"] and not merged:
                service.merge_live_translation("Hello", "浣犲ソ", kind="integration")
                merged = True
            time.sleep(0.05)
        stdout, stderr = process.communicate(timeout=3)
        assert merged, "RPGMaker bridge never reported captured dialogue"
        assert process.returncode == 0, stderr or stdout
        assert "capture refresh ok" in stdout
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        service.stop_live_bridge_server()
        _RPGRM_LIVE_SERVER_STATE["translations"] = {}
        _RPGRM_LIVE_SERVER_STATE["pre_translate_queue"] = []


def test_translation_cache_writes_original_and_translated_files(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.project = project
    api.translation_entries = [
        TranslationEntry("1", "Hello", "浣犲ソ", "Map001.json", category="dialogue"),
        TranslationEntry("2", "Potion", "", "Items.json", category="database"),
    ]

    api._persist_translation_cache()
    cache = project.root / ".rpgrtl_workspace"
    original = json.loads((cache / "original_texts.json").read_text(encoding="utf-8"))
    translated = json.loads((cache / "translated_texts.json").read_text(encoding="utf-8"))

    assert [item["source"] for item in original["entries"]] == ["Hello", "Potion"]
    assert [(item["source"], item["target"]) for item in translated["entries"]] == [("Hello", "浣犲ソ")]


def test_translation_versions_keep_full_project_and_support_live_switch(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.project = project
    api.translation_entries = [
        TranslationEntry(str(index), f"Line {index}", f"译文 {index}", "Map001.json", category="dialogue")
        for index in range(5001)
    ]

    # `all=1` is deliberately not constrained by the legacy 5000 row cap.
    assert len(api.translations({"all": "1"})["entries"]) == 5001
    api._persist_translation_cache()
    version = api._create_translation_snapshot("测试版本", force=True)
    assert version is not None
    assert api.translations_versions()["versions"][1]["id"] == version["id"]

    result = api.translations_runtime({"versionId": version["id"], "hotSwitch": True})
    try:
        assert result["hotSwitched"] is True
        assert _RPGRM_LIVE_SERVER_STATE["translations"]["Line 5000"] == "译文 5000"
        original = api.translations_runtime({"versionId": "original", "hotSwitch": True})
        assert original["liveApplied"] == 0
    finally:
        RPGMakerService(project).stop_live_bridge_server()
        _RPGRM_LIVE_SERVER_STATE["translations"] = {}
        _RPGRM_LIVE_SERVER_STATE["events"] = []


def test_runtime_patch_starts_rpgmaker_server_for_live_replacement(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.project = project
    api.translation_entries = [TranslationEntry("1", "Hello", "浣犲ソ", "Map001.json", category="dialogue")]

    result = api.translations_runtime({"entries": [{"entry_id": "1", "source": "Hello", "target": "浣犲ソ"}]})
    try:
        assert result["liveApplied"] >= 1
        assert RPGMakerService(project).live_bridge_status()["running"] is True
        assert _RPGRM_LIVE_SERVER_STATE["translations"]["Hello"] == "浣犲ソ"
    finally:
        RPGMakerService(project).stop_live_bridge_server()
        _RPGRM_LIVE_SERVER_STATE["translations"] = {}
        _RPGRM_LIVE_SERVER_STATE["events"] = []


def test_translation_runtime_keeps_selected_version_in_lightweight_live_table(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    launcher = project.root / "Project1.exe"
    launcher.write_bytes(b"fake exe")
    project.launcher_path = launcher
    data = project.data_dir
    assert data is not None
    (data / "Map001.json").write_text(json.dumps({"events": [None, {"pages": [{"list": [{"code": 401, "parameters": ["Hello"]}]}]}]}), encoding="utf-8")
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.project = project
    api.translation_entries = [TranslationEntry("1", "Hello", "你好", "Map001.json", category="dialogue")]

    result = api.translations_runtime({"entries": [{"entry_id": "1", "source": "Hello", "target": "你好", "file": "Map001.json", "category": "dialogue"}]})
    try:
        original_map = project.root / "data" / "Map001.json"
        original = json.loads(original_map.read_text(encoding="utf-8"))
        live_table = json.loads(Path(result["translationTable"]).read_text(encoding="utf-8"))

        assert result["changed"] == 0
        assert original["events"][1]["pages"][0]["list"][0]["parameters"][0] == "Hello"
        assert live_table["translations"]["Hello"] == "你好"
    finally:
        RPGMakerService(project).stop_live_bridge_server()
        _RPGRM_LIVE_SERVER_STATE["translations"] = {}
        _RPGRM_LIVE_SERVER_STATE["events"] = []


def test_in_place_runtime_returns_original_launcher_without_copying_it(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    launcher = project.root / "Project1.exe"
    launcher.write_bytes(b"fake exe")
    project.launcher_path = launcher
    data = project.data_dir
    assert data is not None
    (data / "Map001.json").write_text(json.dumps({"events": [None, {"pages": [{"list": [{"code": 401, "parameters": ["Hello"]}]}]}]}), encoding="utf-8")

    bridge, table, launcher, count = RPGMakerService(project).install_in_place_runtime({"1": TranslationEntry("1", "Hello", "浣犲ソ", "Map001.json", category="dialogue")})

    assert bridge.exists()
    assert table == project.root / ".rpgrtl_workspace" / "live_translation.json"
    assert launcher == project.root / "Project1.exe"
    assert count == 1
    assert not (project.root / ".rpgrtl_workspace" / "runtime_game").exists()
    assert json.loads((project.root / "data" / "Map001.json").read_text(encoding="utf-8"))["events"][1]["pages"][0]["list"][0]["parameters"][0] == "Hello"


def test_in_place_runtime_does_not_copy_cjk_font_or_game_assets(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    fake_font = tmp_path / "fake-cjk.ttf"
    fake_font.write_bytes(b"fake font")
    service = RPGMakerService(project)
    service._find_system_cjk_font = lambda: fake_font  # type: ignore[method-assign]

    service.install_in_place_runtime({})

    assert not (project.root / "fonts" / "RPGRenPyLocalizerCJK.ttf").exists()
    assert not (project.root / ".rpgrtl_workspace" / "runtime_game").exists()


def test_live_translation_table_is_loaded_directly_by_runtime_bridge(tmp_path: Path) -> None:
    service = RPGMakerService(make_project(tmp_path))
    path, count = service.write_live_translation_table({"Hello": "你好"})

    bridge = service.install_runtime_bridge()
    source = bridge.read_text(encoding="utf-8")

    assert path.name == "live_translation.json"
    assert count == 1
    assert "loadLocalTranslationTable" in source
    assert "live_translation.json" in source
    assert 'Graphics.loadFont(RPGRenPyCjkFontFamily' not in source


def test_library_launch_finds_non_game_exe_for_old_entries(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    launcher = project.root / "Project1.exe"
    launcher.write_bytes(b"fake exe")
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    api.workspace.save_library([LibraryEntry(
        name="Project1",
        path=str(project.root),
        engine="RPG Maker MV/MZ",
        added_at="2026-07-22 00:00:00",
        launcher_path="",
    )])

    called = {}
    original_popen = subprocess.Popen

    class FakeProc:
        pid = 123

        def poll(self):
            return None

    def fake_popen(args, cwd=None):
        called["args"] = args
        called["cwd"] = cwd
        return FakeProc()

    subprocess.Popen = fake_popen
    try:
        result = api.library_launch({"path": str(project.root)})
    finally:
        subprocess.Popen = original_popen

    assert result["launcher"] == str(launcher)
    assert called["args"] == [str(launcher)]
    assert called["cwd"] == str(project.root)


def test_save_preview_hides_switches_and_variables(tmp_path: Path) -> None:
    api = ToolkitApi(tmp_path / "workspace", config_dir=tmp_path / "config")
    preview = api._save_preview({
        "party": {"_gold": 10, "_steps": 2, "_items": {"1": 3}},
        "actors": {"_data": [None, {"_level": 2}]},
        "switches": {"_data": [None, True]},
        "variables": {"_data": [None, 99]},
    })
    assert "switches" not in preview
    assert "variables" not in preview
    assert preview["party"]["_gold"] == 10
