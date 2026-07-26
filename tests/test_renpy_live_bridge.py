from __future__ import annotations

import json
import tempfile
import unittest
import urllib.request
from pathlib import Path

from toolkit.models import ProjectInfo, TranslationEntry
from toolkit.api.server import ToolkitApi
from toolkit.renpy import RENPY_LIVE_BRIDGE_SOURCE, RenPyService, _LIVE_SERVER_LOCK, _LIVE_SERVER_STATE


class RenPyLiveBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        game_dir = self.root / "game"
        game_dir.mkdir()
        self.service = RenPyService(
            ProjectInfo(engine="Ren'Py", root=self.root, game_dir=game_dir, scripts_dir=game_dir)
        )
        with _LIVE_SERVER_LOCK:
            _LIVE_SERVER_STATE.clear()
            _LIVE_SERVER_STATE.update(
                {"translations": {}, "events": [], "seen": {}, "notify_seq": 0, "force_text": "", "pre_translate_queue": []}
            )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_batch_merge_persists_and_notifies_once(self) -> None:
        seq = self.service.merge_live_translations(
            {"Hello": "你好", "Score [score]": "得分 [score]"}, kind="automatic"
        )

        payload = json.loads(self.service.live_translation_path().read_text(encoding="utf-8"))
        self.assertEqual(seq, 1)
        self.assertEqual(payload["translations"]["Hello"], "你好")
        self.assertEqual(payload["translations"]["Score [score]"], "得分 [score]")
        self.assertFalse(self.service.live_translation_path().with_suffix(".json.tmp").exists())

    def test_control_tokens_must_be_preserved_in_order(self) -> None:
        self.assertTrue(RenPyService.control_tokens_preserved("Hello [player] {b}world{/b}", "你好 [player] {b}世界{/b}"))
        self.assertFalse(RenPyService.control_tokens_preserved("Hello [player]", "你好"))
        self.assertFalse(RenPyService.control_tokens_preserved("{b}A{/b}", "{/b}甲{b}"))

    def test_runtime_extraction_excludes_system_strings(self) -> None:
        self.service.runtime_export_path().parent.mkdir(parents=True, exist_ok=True)
        self.service.runtime_export_path().write_text(
            json.dumps({"ok": True, "entries": [
                {"source": "A line", "category": "dialogue", "file": "script.rpy"},
                {"source": "A system label", "category": "system", "file": "gui.rpy"},
            ]}, ensure_ascii=False),
            encoding="utf-8",
        )
        entries = self.service.extract_translations()
        self.assertEqual([entry.source for entry in entries], ["A line"])

    def test_malformed_font_tags_are_removed_before_cache_write(self) -> None:
        target = "｛font = C:/Windows/Fonts/msyh.ttc｝行了行了 ……好吧。 {/font}"
        sanitized = RenPyService._sanitize_renpy_text("Yeah, yeah... Okay.", target)
        self.assertNotIn("font", sanitized.lower())
        self.assertNotIn("{/font}", sanitized)
        self.assertEqual(sanitized, "行了行了 ……好吧。")

    def test_http_hook_capture_translate_refresh_round_trip(self) -> None:
        def post(endpoint: str, payload: dict) -> dict:
            request = urllib.request.Request(
                "http://127.0.0.1:32180" + endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                return json.loads(response.read().decode("utf-8"))

        self.service.start_live_bridge_server(clear_events=True)
        try:
            captured = post("/pre_translate", {"texts": ["Hello [player]"]})
            self.assertEqual(captured["queued"], ["Hello [player]"])
            self.assertEqual(self.service.take_live_translation_candidates(), ["Hello [player]"])
            self.service.merge_live_translations({"Hello [player]": "你好 [player]"}, kind="automatic")
            replaced = post("/translation_batch", {"texts": ["Hello [player]"]})
            self.assertEqual(replaced["translations"]["Hello [player]"], "你好 [player]")
            missing = post("/translation_batch", {"texts": ["Later"]})
            self.assertEqual(missing["translations"], {})
            self.assertEqual(self.service.take_live_translation_candidates(), ["Later"])
            post("/notify", {"pid": 12345})
            self.assertTrue(self.service.live_bridge_status()["connected"])
        finally:
            self.service.stop_live_bridge_server()

    def test_activating_project_replaces_cross_project_state(self) -> None:
        self.service.live_translation_path().parent.mkdir(parents=True)
        self.service.live_translation_path().write_text(
            json.dumps({"version": 1, "translations": {"New": "新"}}, ensure_ascii=False),
            encoding="utf-8",
        )
        with _LIVE_SERVER_LOCK:
            _LIVE_SERVER_STATE["project_root"] = "C:/other-game"
            _LIVE_SERVER_STATE["translations"] = {"Old": "旧"}
            _LIVE_SERVER_STATE["events"] = [{"kind": "old"}]
            _LIVE_SERVER_STATE["pre_translate_queue"] = ["Old queue"]

        self.service._activate_live_project(clear_events=True)

        with _LIVE_SERVER_LOCK:
            self.assertEqual(_LIVE_SERVER_STATE["project_root"], str(self.root.resolve()))
            self.assertEqual(_LIVE_SERVER_STATE["translations"], {"New": "新"})
            self.assertEqual(_LIVE_SERVER_STATE["events"], [])
            self.assertEqual(_LIVE_SERVER_STATE["pre_translate_queue"], [])

    def test_api_worker_translates_and_merges_a_batch(self) -> None:
        stop_event = __import__("threading").Event()

        class FakeService:
            def __init__(self) -> None:
                self.returned = False
                self.merged = {}

            def take_live_translation_candidates(self, _limit: int) -> list[str]:
                if self.returned:
                    return []
                self.returned = True
                return ["Hello", "Start"]

            def requeue_live_translation_candidates(self, _values: list[str]) -> None:
                self.fail("unexpected requeue")

            def merge_live_translations(self, values: dict[str, str], kind: str) -> int:
                self.merged = {"values": values, "kind": kind}
                stop_event.set()
                return 1

        api = ToolkitApi(self.root, config_dir=self.root / "config")
        api.live_worker_project = "project"
        api.live_worker_stats.update({"running": True, "translated": 0, "failures": 0})
        api._live_ai_config = lambda: {"provider": "openai-compatible", "apiKey": "key", "baseUrl": "https://example.test/v1", "model": "model", "targetLang": "简体中文", "batchSize": 20, "concurrency": 1, "requestIntervalMs": 0, "windowSize": 300}
        api._translate_openai_compatible = lambda sources, _config: ["你好", "开始"]
        service = FakeService()

        api._live_worker_loop(service, stop_event, "project")

        self.assertEqual(service.merged["values"], {"Hello": "你好", "Start": "开始"})
        self.assertEqual(service.merged["kind"], "automatic")
        self.assertEqual(api.live_worker_stats["translated"], 2)

    def test_api_worker_repairs_missing_batch_in_parallel(self) -> None:
        stop_event = __import__("threading").Event()

        class FakeService:
            def __init__(self) -> None:
                self.returned = False
                self.requested_sizes = []

            def take_live_translation_candidates(self, _limit: int) -> list[str]:
                if self.returned:
                    return []
                self.returned = True
                return ["Line %d" % index for index in range(6)]

            def requeue_live_translation_candidates(self, values: list[str]) -> None:
                self.requeued = list(values)
                stop_event.set()

            def merge_live_translations(self, _values: dict[str, str], _kind: str) -> int:
                self.fail("an empty provider response must not merge translations")

        api = ToolkitApi(self.root, config_dir=self.root / "config")
        api.live_worker_project = "project"
        api.live_worker_stats.update({"running": True, "translated": 0, "failures": 0})
        api._live_ai_config = lambda: {"provider": "openai-compatible", "apiKey": "key", "baseUrl": "https://example.test/v1", "model": "model", "targetLang": "简体中文", "batchSize": 2, "concurrency": 3, "requestIntervalMs": 0, "windowSize": 300}

        def empty_response(sources: list[str], _config: dict) -> list[str]:
            service.requested_sizes.append(len(sources))
            return []

        api._translate_openai_compatible = empty_response
        service = FakeService()
        api._live_worker_loop(service, stop_event, "project")

        self.assertEqual(service.requested_sizes, [2, 2, 2, 2, 2, 2])
        self.assertEqual(service.requeued, ["Line %d" % index for index in range(6)])

    def test_live_bridge_does_not_mutate_menu_labels(self) -> None:
        bridge = RENPY_LIVE_BRIDGE_SOURCE
        menu_start = bridge.index("def _rpgrtl_hook_Menu_execute")
        menu_end = bridge.index("# Hook: renpy.display_menu", menu_start)
        menu_hook = bridge[menu_start:menu_end]
        self.assertNotIn("items[i] =", menu_hook)
        self.assertIn("_rpgrtl_pending_lookup.add(label.strip())", menu_hook)

    def test_seed_queue_fills_following_same_language_script_entries(self) -> None:
        entries = [
            TranslationEntry("%d" % index, "Line %d" % index, file="script.rpy", category="dialogue")
            for index in range(340)
        ]
        entries.insert(30, TranslationEntry("jp", "日本語", file="script.rpy", category="dialogue"))
        self.service._activate_live_project(clear_events=True)

        added = self.service.seed_live_translation_queue(entries, "Line 10", 300)

        self.assertEqual(added, 300)
        with _LIVE_SERVER_LOCK:
            queued = list(_LIVE_SERVER_STATE["pre_translate_queue"])
        self.assertEqual(queued[0], "Line 11")
        self.assertEqual(len(queued), 300)
        self.assertNotIn("日本語", queued)

    def test_seed_queue_matches_visible_text_after_renpy_tags_are_removed(self) -> None:
        entries = [
            TranslationEntry("a", "{i}Current line{/i}", file="script.rpy", category="dialogue"),
            TranslationEntry("b", "Following line", file="script.rpy", category="dialogue"),
        ]
        self.service._activate_live_project(clear_events=True)

        added = self.service.seed_live_translation_queue(entries, "Current line", 10)

        self.assertEqual(added, 1)
        with _LIVE_SERVER_LOCK:
            queued = list(_LIVE_SERVER_STATE["pre_translate_queue"])
        self.assertEqual(queued, ["Following line"])


if __name__ == "__main__":
    unittest.main()
