from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from toolkit.live_prefetch import nearby_translation_sources
from toolkit.models import TranslationEntry
from toolkit.unknown_game import UnknownGameService
from toolkit.detectors import detect_project
from toolkit import unity_xua


class LivePrefetchTests(unittest.TestCase):
    def tearDown(self) -> None:
        unity_xua.stop_live_bridge_server()

    def test_nearby_sources_stay_in_anchor_file_and_safe_categories(self) -> None:
        entries = [
            TranslationEntry("a", "Current   line", file="table.csv", category="unity_localization"),
            TranslationEntry("b", "Next line", file="table.csv", category="dialogue"),
            TranslationEntry("c", "Unsafe", file="table.csv", category="unknown"),
            TranslationEntry("d", "Already translated", target="done", file="table.csv", category="dialogue"),
            TranslationEntry("e", "Other file", file="other.csv", category="dialogue"),
        ]
        self.assertEqual(
            nearby_translation_sources(entries, "Current line", {}, 10, {"dialogue", "unity_localization"}),
            ["Next line"],
        )

    def test_unknown_game_unity_queue_prioritizes_urgent_capture_then_lookahead(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "UnityPlayer.dll").write_bytes(b"unity")
            service = UnknownGameService(detect_project(root))
            entries = [
                TranslationEntry("a", "Current line", file="table.csv", category="unity_localization"),
                TranslationEntry("b", "Next line", file="table.csv", category="unity_localization"),
            ]
            service.start_live_bridge_server(clear_events=True)
            service.requeue_live_translation_candidates(["Current line"])
            self.assertEqual(service.seed_live_translation_queue(entries, "Current line", 10), 1)
            self.assertEqual(service.take_live_translation_candidates(10), ["Current line", "Next line"])


if __name__ == "__main__":
    unittest.main()
