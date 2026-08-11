from __future__ import annotations

import tempfile
import csv
import unittest
import struct
import json
from pathlib import Path

from toolkit.detectors import detect_engine, detect_project
from toolkit.api.server import ToolkitApi
from toolkit.models import ProjectInfo, TranslationEntry
from toolkit.unknown_game import UnknownGameService


def _wolf_string(value: str, encoding: str = "cp932") -> bytes:
    payload = value.encode(encoding)
    return struct.pack("<I", len(payload) + 1) + payload + b"\x00"


def _wolf_mps_with_message(message: str) -> bytes:
    """Build the smallest valid unencrypted MPS fixture with one message."""
    header = bytes((
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x57, 0x4F, 0x4C, 0x46, 0x4D, 0,
        0, 0, 0, 0, 0x64, 0, 0, 0, 0x65, 0x03, 0, 0, 0, 0x4E, 0x6F, 0,
    ))
    command = (
        b"\x01" + struct.pack("<I", 101) + b"\x00\x01" + _wolf_string(message)
        + b"\x00"
    )
    page = (
        b"y" + struct.pack("<I", 0) + _wolf_string("") + b"\x00" * (4 + 37 + 4 + 2)
        + struct.pack("<I", 0) + struct.pack("<I", 1) + command
        + b"\x03\x00\x00\x00" + b"\x00\x00\x00z" + b"p"
    )
    event = (
        b"o\x39\x30\x00\x00" + struct.pack("<I", 1) + _wolf_string("Event")
        + struct.pack("<III", 0, 0, 1) + b"\x00\x00\x00\x00" + page
    )
    return header + struct.pack("<IIII", 0, 0, 0, 1) + event + b"f"


class UnknownGameServiceTests(unittest.TestCase):
    def test_detect_unity_and_extract_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "UnityPlayer.dll").write_bytes(b"unity")
            (root / "Demo_Data" / "Managed").mkdir(parents=True)
            (root / "Demo_Data" / "Managed" / "UnityEngine.CoreModule.dll").write_bytes(b"x")
            (root / "Demo_Data" / "dialogue.json").write_text('{"line":"Hello from the game."}\n', encoding="utf-8")
            (root / "Demo.exe").write_bytes(b"MZ")
            self.assertEqual(detect_engine(root), "Unity")
            project = detect_project(root)
            self.assertEqual(project.engine, "Unity")
            entries = UnknownGameService(project).extract_translations()
            self.assertTrue(any(item.source == "Hello from the game." for item in entries))

    def test_galgame_galtransl_json_and_kirikiri_scenario_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "krkr.exe").write_bytes(b"MZ")
            script = root / "data" / "scenario" / "opening.ks"
            script.parent.mkdir(parents=True)
            script.write_text('Alice?Hello, welcome to our school.?\n', encoding="utf-8")
            dialog = root / "script_jp" / "chapter1.json"
            dialog.parent.mkdir(parents=True)
            dialog.write_text(json.dumps([
                {"name": "Alice", "message": "Hello, welcome to our school."},
                {"name": "Bob", "message": "I will see you tomorrow."},
            ]), encoding="utf-8")
            project = detect_project(root)
            self.assertEqual(project.engine, "Visual Novel / Galgame")
            service = UnknownGameService(project)
            entries = service.extract_translations()
            json_entry = next(item for item in entries if item.source == "Hello, welcome to our school.")
            self.assertTrue(json_entry.entry_id.startswith("galtransl::"))
            self.assertEqual(json_entry.category, "galgame_dialogue")
            self.assertIn("speaker=Alice", json_entry.context)
            scenario_entry = next(item for item in entries if "Alice" in item.source and "school" in item.source)
            self.assertEqual(scenario_entry.category, "galgame_dialogue")
            json_entry.target = "\u4f60\u597d\uff0c\u6b22\u8fce\u6765\u5230\u5b66\u6821\u3002"
            runtime, _launcher, changed = service.build_runtime_copy({json_entry.entry_id: json_entry})
            self.assertEqual(changed, 1)
            payload = json.loads((runtime / "script_jp" / "chapter1.json").read_text(encoding="utf-8"))
            self.assertEqual(payload[0]["pre_zh"], json_entry.target)
            self.assertEqual(payload[0]["message"], json_entry.source)

    def test_unreal_ue4_ue5_archive_extracts_and_writes_translation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "UE5Game.exe").write_bytes(b"MZ")
            archive = root / "Content" / "Localization" / "Game" / "zh-Hans" / "Game.archive"
            archive.parent.mkdir(parents=True)
            archive.write_text(json.dumps({
                "FormatVersion": 1,
                "Namespace": "Game",
                "Subnamespaces": [{
                    "Namespace": "Menu",
                    "Children": [{
                        "Source": {"Text": "Would you like to start a new game?"},
                        "Translation": {"Text": ""},
                        "Key": "MENU_START",
                    }],
                }],
            }), encoding="utf-8")
            project = detect_project(root)
            self.assertEqual(project.engine, "Unreal Engine 4/5")
            service = UnknownGameService(project)
            entries = service.extract_translations()
            self.assertEqual([item.source for item in entries], ["Would you like to start a new game?"])
            entry = entries[0]
            self.assertEqual(entry.category, "unreal_localization")
            self.assertTrue(entry.context.startswith("unreal-archive;"))
            api = ToolkitApi(root, config_dir=root / ".test-config")
            api.load_project({"path": str(root)})
            exposed = api.translations({"refresh": "1"})["entries"]
            self.assertEqual([item["entry_id"] for item in exposed], [entry.entry_id])
            entry.target = "\u8981\u5f00\u59cb\u65b0\u6e38\u620f\u5417\uff1f"
            runtime, _launcher, changed = service.build_runtime_copy({entry.entry_id: entry})
            self.assertEqual(changed, 1)
            payload = json.loads((runtime / "Content" / "Localization" / "Game" / "zh-Hans" / "Game.archive").read_text(encoding="utf-8"))
            self.assertEqual(payload["Subnamespaces"][0]["Children"][0]["Translation"]["Text"], entry.target)
            self.assertEqual(payload["Subnamespaces"][0]["Children"][0]["Source"]["Text"], entry.source)

    def test_unity_polyglot_table_uses_simplified_chinese_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "UnityPlayer.dll").write_bytes(b"unity")
            (root / "Demo.exe").write_bytes(b"MZ")
            table = root / "Demo_Data" / "StreamingAssets" / "Polyglot.csv"
            table.parent.mkdir(parents=True)
            table.write_text('BEGIN,Description\nUI_WELCOME,Welcome label,"Welcome, traveler."\nEND\n', encoding="utf-8")
            service = UnknownGameService(detect_project(root))
            self.assertEqual(service.project.engine, "Unity")
            entries = service.extract_translations()
            self.assertEqual([item.source for item in entries], ["Welcome, traveler."])
            entry = entries[0]
            self.assertEqual(entry.category, "unity_localization")
            self.assertIn("kind=polyglot", entry.context)
            entry.target = "\u6b22\u8fce\uff0c\u65c5\u884c\u8005\u3002"
            runtime, _launcher, changed = service.build_runtime_copy({entry.entry_id: entry})
            self.assertEqual(changed, 1)
            with (runtime / "Demo_Data" / "StreamingAssets" / "Polyglot.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[1][19], entry.target)
            self.assertEqual(rows[1][2], "Welcome, traveler.")

    def test_unity_header_and_json_locale_tables_patch_target_cells(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "UnityPlayer.dll").write_bytes(b"unity")
            (root / "Demo.exe").write_bytes(b"MZ")
            folder = root / "Demo_Data" / "StreamingAssets" / "Localization"
            folder.mkdir(parents=True)
            csv_table = folder / "StringTable.csv"
            csv_table.write_text('Key,English,zh-Hans\nPLAY,"Start a new game.",\n', encoding="utf-8")
            json_table = folder / "LocaleTable.json"
            json_table.write_text(json.dumps({"en": {"QUIT": "Leave the game now?"}, "zh-Hans": {"QUIT": ""}}), encoding="utf-8")
            service = UnknownGameService(detect_project(root))
            entries = service.extract_translations()
            self.assertEqual({item.source for item in entries}, {"Start a new game.", "Leave the game now?"})
            for entry in entries:
                entry.target = "\u7ffb\u8bd1: " + entry.source
            runtime, _launcher, changed = service.build_runtime_copy({entry.entry_id: entry for entry in entries})
            self.assertEqual(changed, 2)
            with (runtime / "Demo_Data" / "StreamingAssets" / "Localization" / "StringTable.csv").open(encoding="utf-8", newline="") as handle:
                csv_rows = list(csv.reader(handle))
            self.assertEqual(csv_rows[1][2], "\u7ffb\u8bd1: Start a new game.")
            payload = json.loads((runtime / "Demo_Data" / "StreamingAssets" / "Localization" / "LocaleTable.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["zh-Hans"]["QUIT"], "\u7ffb\u8bd1: Leave the game now?")

    def test_runtime_copy_is_reversible(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Demo_Data").mkdir()
            source_file = root / "Demo_Data" / "dialogue.txt"
            source_file.write_text("Hello from the game.\n", encoding="utf-8")
            launcher = root / "Demo.exe"
            launcher.write_bytes(b"MZ")
            project = detect_project(root)
            entries = UnknownGameService(project).extract_translations()
            entry = next(item for item in entries if item.source == "Hello from the game.")
            entry.target = "你好，游戏。"
            runtime, runtime_launcher, changed = UnknownGameService(project).build_runtime_copy({entry.entry_id: entry})
            self.assertEqual(changed, 1)
            self.assertEqual(source_file.read_text(encoding="utf-8"), "Hello from the game.\n")
            self.assertEqual((runtime / "Demo_Data" / "dialogue.txt").read_text(encoding="utf-8"), "你好，游戏。\n")
            self.assertTrue(runtime_launcher and runtime_launcher.exists())

    def test_wolf_generic_fallback_ignores_dump_and_root_txt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "wolfDataLock.json").write_text("{}", encoding="utf-8")
            (root / "Game.exe").write_bytes(b"MZ")
            (root / "Game.ini").write_text("Start=0", encoding="utf-8")
            (root / "LICENSE_OFL.txt").write_text("font license", encoding="utf-8")
            (root / "dump").mkdir()
            (root / "dump" / "candidate.txt").write_text("This is not game dialogue.", encoding="utf-8")
            (root / "Data" / "MapData").mkdir(parents=True)
            # The fixture need only carry the Wolf map signature and an ASCII
            # message; the service must still select the binary resource path.
            (root / "Data" / "MapData" / "demo.mps").write_bytes(
                b"\x00" * 10 + b"WOLFM\x00" + b"\x00" * 64 + b"Hello from the map."
            )
            project = ProjectInfo(engine="Generic Windows Game", root=root, game_dir=root)
            service = UnknownGameService(project)
            self.assertEqual(service.project.engine, "Wolf RPG Editor")
            paths = list(service._iter_files())
            self.assertTrue(any(path.suffix.lower() == ".mps" for path in paths))
            self.assertFalse(any("dump" in path.parts for path in paths))
            entries = service.extract_translations()
            self.assertFalse(any(item.file.lower().endswith(".txt") for item in entries))
            self.assertFalse(any(item.file.lower() == "game.ini" for item in entries))

    def test_wolf_mps_messages_are_patchable_in_isolated_runtime_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Game.exe").write_bytes(b"MZ")
            source_path = root / "Data" / "MapData" / "Map001.mps"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(_wolf_mps_with_message("Welcome to the village."))
            service = UnknownGameService(detect_project(root))
            self.assertEqual(service.project.engine, "Wolf RPG Editor")
            entries = service.extract_translations()
            entry = next(item for item in entries if item.source == "Welcome to the village.")
            self.assertTrue(entry.entry_id.startswith("wolf::"))
            self.assertEqual(entry.category, "wolf_dialogue")
            self.assertIn("wolf-field;offset=", entry.context)
            api = ToolkitApi(root, config_dir=root / ".test-config")
            api.load_project({"path": str(root)})
            exposed = api.translations({"refresh": "1"})["entries"]
            self.assertEqual([item["entry_id"] for item in exposed], [entry.entry_id])
            entry.target = "\u6b22\u8fce\u6765\u5230\u6751\u5e84\u3002"
            runtime, _launcher, changed = service.build_runtime_copy({entry.entry_id: entry})
            self.assertEqual(changed, 1)
            self.assertEqual(source_path.read_bytes(), _wolf_mps_with_message("Welcome to the village."))
            copied = runtime / "Data" / "MapData" / "Map001.mps"
            copied_entries = UnknownGameService(ProjectInfo("Wolf RPG Editor", runtime, runtime)).extract_translations()
            self.assertIn(entry.target, [item.source for item in copied_entries])
            self.assertNotEqual(copied.read_bytes(), source_path.read_bytes())

    def test_mtool_dump_extracts_messages_and_writes_runtime_translation_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Game.exe").write_bytes(b"MZ")
            (root / "wolfDataLock.json").write_text("{}", encoding="utf-8")
            dump = root / "dump" / "mps"
            dump.mkdir(parents=True)
            (dump / "Map001.json").write_text(json.dumps({
                "events": [{"id": 3, "pages": [{"id": 1, "list": [
                    {"code": 101, "index": 5, "stringArgs": ["A message from MTool."]},
                    {"code": 102, "index": 6, "stringArgs": ["Yes", "No"]},
                ]}]}],
            }, ensure_ascii=False), encoding="utf-8")
            (root / "翻译文件.json").write_text('{"existing": "保留"}', encoding="utf-8")
            service = UnknownGameService(detect_project(root))
            entries = service.extract_translations()
            self.assertEqual(len(entries), 3)
            message = next(item for item in entries if item.source == "A message from MTool.")
            self.assertTrue(message.entry_id.startswith("mtool::"))
            self.assertEqual(message.category, "wolf_dialogue")
            message.target = "来自 MTool 的消息。"
            runtime, _launcher, changed = service.build_runtime_copy({message.entry_id: message})
            self.assertEqual(changed, 1)
            mapping = json.loads((runtime / "翻译文件.json").read_text(encoding="utf-8"))
            self.assertEqual(mapping["existing"], "保留")
            self.assertEqual(mapping[message.source], message.target)

    def test_legacy_rpgmaker_2000_is_detected_without_txt_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "RPG_RT.exe").write_bytes(b"MZ")
            (root / "RPG_RT.ini").write_text("GameTitle=fixture", encoding="utf-8")
            (root / "Map001.lmu").write_bytes(b"\x00\x00Japanese message\x00")
            (root / "README.txt").write_text("documentation", encoding="utf-8")
            project = detect_project(root)
            self.assertEqual(project.engine, "RPG Maker 2000/2003")
            service = UnknownGameService(project)
            plan = service.plan()
            self.assertEqual(plan["engine"], "RPG Maker 2000/2003")
            self.assertIn(".lmu", " ".join(plan["extraction_plan"]))
            entries = service.extract_translations()
            self.assertFalse(any(item.file.lower().endswith(".txt") for item in entries))


if __name__ == "__main__":
    unittest.main()
