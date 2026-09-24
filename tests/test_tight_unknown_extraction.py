from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from toolkit.api.server import ToolkitApi
from toolkit.detectors import detect_project
from toolkit.unknown_game import UnknownGameService, _looks_like_player_text


class TightExtractionTests(unittest.TestCase):
    def test_unity_ignores_root_txt_but_keeps_content_dialogue_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "UnityPlayer.dll").write_bytes(b"unity")
            (root / "Demo.exe").write_bytes(b"MZ")
            (root / "notes.txt").write_text(
                "Hello from a random notes file.\nAnother line that looks like dialogue.\nTODO\n",
                encoding="utf-8",
            )
            (root / "Demo_Data" / "Managed").mkdir(parents=True)
            (root / "Demo_Data" / "Managed" / "UnityEngine.CoreModule.dll").write_bytes(b"x")
            (root / "Demo_Data" / "dialogue.json").write_text(
                '{"line":"Hello from the game."}\n',
                encoding="utf-8",
            )
            service = UnknownGameService(detect_project(root))
            self.assertEqual(service.project.engine, "Unity")
            entries = service.extract_translations()
            sources = [item.source for item in entries]
            self.assertIn("Hello from the game.", sources)
            self.assertFalse(any("random notes file" in source for source in sources))
            self.assertFalse(any("Another line that looks" in source for source in sources))

            api = ToolkitApi(root, config_dir=root / ".cfg")
            api.load_project({"path": str(root)})
            exposed = api.translations({"refresh": "1"})["entries"]
            exposed_sources = [item["source"] for item in exposed]
            self.assertIn("Hello from the game.", exposed_sources)
            self.assertFalse(any("random notes file" in source for source in exposed_sources))

    def test_demo_data_dialogue_txt_still_extracted_for_generic_game(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Demo_Data").mkdir()
            (root / "Demo_Data" / "dialogue.txt").write_text("Hello from the game.\n", encoding="utf-8")
            (root / "Demo.exe").write_bytes(b"MZ")
            (root / "scratch.txt").write_text("Ignore this root scratch file entirely.\n", encoding="utf-8")
            service = UnknownGameService(detect_project(root))
            entries = service.extract_translations()
            sources = [item.source for item in entries]
            self.assertIn("Hello from the game.", sources)
            self.assertFalse(any("root scratch" in source for source in sources))

    def test_player_text_filter_rejects_bare_identifiers(self) -> None:
        self.assertTrue(_looks_like_player_text("Hello from the game."))
        self.assertTrue(_looks_like_player_text("こんにちは、旅の人。"))
        self.assertFalse(_looks_like_player_text("TODO"))
        self.assertFalse(_looks_like_player_text("version"))

    def test_unreal_archive_only_path_not_polluted_by_root_txt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "UE4Game.exe").write_bytes(b"MZ")
            (root / "scratch.txt").write_text("Welcome to my scratch notes about the game.\n", encoding="utf-8")
            content = root / "Content" / "Localization" / "Game" / "en" / "Game.archive"
            content.parent.mkdir(parents=True)
            content.write_text(
                json.dumps({
                    "Subnamespaces": [{
                        "Children": [{
                            "Namespace": "NS",
                            "Key": "K",
                            "Source": {"Text": "Start a new game."},
                            "Translation": {"Text": ""},
                        }],
                    }],
                }),
                encoding="utf-8",
            )
            service = UnknownGameService(detect_project(root))
            self.assertEqual(service.project.engine, "Unreal Engine 4/5")
            entries = service.extract_translations()
            sources = [item.source for item in entries]
            self.assertIn("Start a new game.", sources)
            self.assertFalse(any("scratch notes" in source for source in sources))


if __name__ == "__main__":
    unittest.main()
