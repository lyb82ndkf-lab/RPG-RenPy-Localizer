from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from toolkit.api.server import ToolkitApi
from toolkit.models import TranslationEntry
from toolkit import unity_xua


class UnityLiveStartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.root = root
        (root / "UnityPlayer.dll").write_bytes(b"unity")
        (root / "Demo.exe").write_bytes(b"MZ")
        (root / "Demo_Data").mkdir()
        (root / "Demo_Data" / "dialogue.json").write_text(
            '{"line":"Hello from the game."}',
            encoding="utf-8",
        )
        self.api = ToolkitApi(root, config_dir=root / ".cfg")
        self.api.load_project({"path": str(root)})

    def tearDown(self) -> None:
        unity_xua.stop_live_bridge_server()
        self.temp_dir.cleanup()

    def test_live_start_boots_xua_server_and_seeds_targets(self) -> None:
        self.api.translation_entries = [
            TranslationEntry("e1", "Hello from the game.", "你好，游戏。", "Demo_Data/dialogue.json", category="dialogue"),
        ]
        status = self.api.live_start({"autoTranslate": True})
        self.assertTrue(status.get("ok"))
        self.assertTrue(status.get("running"))
        self.assertEqual(status.get("seeding"), 1)
        self.assertTrue((self.root / "AutoTranslator" / "Config" / "Config.ini").is_file())
        self.assertEqual(unity_xua.live_status()["translated"], 1)
        # Must not raise the RPG Maker restriction for Unity.
        self.assertNotIn("RPG Maker", str(status.get("hint") or ""))

    def test_live_status_reports_recent_events_helper(self) -> None:
        self.api.translation_entries = []
        self.api.live_start({})
        self.assertTrue(self.api.live_status().get("running"))
        self.assertIsInstance(unity_xua.read_live_events(5), list)


class UnrealLivePreheatTests(unittest.TestCase):
    def test_unreal_live_start_preheats_archive_queue_without_claiming_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "UE5Game.exe").write_bytes(b"MZ")
            archive = root / "Content" / "Localization" / "Game" / "en" / "Game.archive"
            archive.parent.mkdir(parents=True)
            archive.write_text('{"Children":[{"Source":{"Text":"First line."}},{"Source":{"Text":"Second line."}}]}', encoding="utf-8")
            api = ToolkitApi(root, config_dir=root / ".cfg")
            api.load_project({"path": str(root)})
            status = api.live_start({"autoTranslate": False, "clearEvents": True})
            self.assertTrue(status.get("running"))
            self.assertEqual(status.get("mode"), "archive-preheat")
            self.assertGreaterEqual(status.get("queue_count", 0), 2)
            self.assertIn("UnrealPak", status.get("hint", ""))
            api.live_stop()


if __name__ == "__main__":
    unittest.main()
