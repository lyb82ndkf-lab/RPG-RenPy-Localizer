from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from toolkit.detectors import detect_engine, detect_project
from toolkit.models import ProjectInfo, TranslationEntry
from toolkit.unknown_game import UnknownGameService


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
